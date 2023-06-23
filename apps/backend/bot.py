# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from langchain.chat_models import AzureChatOpenAI
from langchain.utilities import BingSearchAPIWrapper
from langchain.memory import ConversationBufferWindowMemory
from langchain.agents import ConversationalChatAgent, AgentExecutor, Tool

#custom libraries that we will use later in the app
from utils import DocSearchTool, CSVTabularTool, SQLDbTool, ChatGPTTool, BingSearchTool, run_agent
from callbacks import MyCustomHandler
from prompts import CUSTOM_CHATBOT_PREFIX, CUSTOM_CHATBOT_SUFFIX 

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount, Activity, ActivityTypes


os.environ["OPENAI_API_BASE"] = os.environ.get("AZURE_OPENAI_ENDPOINT")
os.environ["OPENAI_API_KEY"] = os.environ.get("AZURE_OPENAI_API_KEY")
os.environ["OPENAI_API_VERSION"] = os.environ.get("AZURE_OPENAI_API_VERSION")
os.environ["OPENAI_API_TYPE"] = "azure"


class MyBot(ActivityHandler):
    # See https://aka.ms/about-bot-activity-message to learn more about the message and other activity types.
    
    # Set a Deployment model name
    MODEL_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_MODEL_NAME")
    
    llm = AzureChatOpenAI(deployment_name=MODEL_DEPLOYMENT_NAME, temperature=0.5, max_tokens=500)
    
    # Initialize our Tools/Experts
    indexes = ["cogsrch-index-files", "cogsrch-index-csv"]
    doc_search = DocSearchTool(llm=llm, indexes=indexes, k=10, chunks_limit=100, similarity_k=5)
    www_search = BingSearchTool(llm=llm, k=5)
    sql_search = SQLDbTool(llm=llm)
    chatgpt_search = ChatGPTTool(llm=llm)
    
    tools = [
        Tool(
            name = "@bing",
            func=www_search.run,
            description='useful when the questions includes the term: @bing.\n',
            return_direct=True
            ),
        Tool(
            name = "@covidstats",
            func=sql_search.run,
            description='useful when the questions includes the term: @covidstats.\n',
            return_direct=True
        ),
        Tool(
            name = "@docsearch",
            func=doc_search.run,
            description='useful when the questions includes the term: @docsearch.\n',
            return_direct=True
        ),
        Tool(
            name = "@chatgpt",
            func=chatgpt_search.run,
            description='useful when the questions includes the term: @chatgpt.\n',
            return_direct=True
        ),
    ]
    
    # Set main Agent
    llm_a = AzureChatOpenAI(deployment_name=MODEL_DEPLOYMENT_NAME, temperature=0.5, max_tokens=500)
    agent = ConversationalChatAgent.from_llm_and_tools(llm=llm_a, tools=tools, system_message=CUSTOM_CHATBOT_PREFIX, human_message=CUSTOM_CHATBOT_SUFFIX)
    memory = ConversationBufferWindowMemory(memory_key="chat_history", return_messages=True, k=10)
    agent_chain = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, memory=memory)
    
    
    async def on_message_activity(self, turn_context: TurnContext):
        typing_activity = Activity(type=ActivityTypes.typing)
        await turn_context.send_activity(typing_activity)

        # Please note below that running a non-async function like run_agent in a separate thread won't make it truly asynchronous. It allows the function to be called without blocking the event loop, but it may still have synchronous behavior internally.
        
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(ThreadPoolExecutor(), run_agent, turn_context.activity.text, self.agent_chain)

        await turn_context.send_activity(answer)


    async def on_members_added_activity(self, members_added: ChannelAccount, turn_context: TurnContext):
        for member_added in members_added:
            if member_added.id != turn_context.activity.recipient.id:
                await turn_context.send_activity("Hello and welcome!")
