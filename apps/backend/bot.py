# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import re
from langchain.chat_models import AzureChatOpenAI
from langchain.utilities import BingSearchAPIWrapper
from langchain.memory import ConversationBufferWindowMemory
from langchain.agents import ConversationalChatAgent, AgentExecutor, Tool

#custom libraries that we will use later in the app
from utils import DocSearchWrapper, CSVTabularWrapper, SQLDbWrapper, ChatGPTWrapper
from prompts import CUSTOM_CHATBOT_PREFIX, CUSTOM_CHATBOT_SUFFIX

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount


os.environ["OPENAI_API_BASE"] = os.environ.get("AZURE_OPENAI_ENDPOINT")
os.environ["OPENAI_API_KEY"] = os.environ.get("AZURE_OPENAI_API_KEY")
os.environ["OPENAI_API_VERSION"] = os.environ.get("AZURE_OPENAI_API_VERSION")
os.environ["OPENAI_API_TYPE"] = "azure"


class MyBot(ActivityHandler):
    # See https://aka.ms/about-bot-activity-message to learn more about the message and other activity types.
    
    # Set a Deployment model name
    MODEL = os.environ.get("AZURE_OPENAI_MODEL_NAME")
    
    # Initialize our Tools/Experts
    doc_search = DocSearchWrapper(indexes=["cogsrch-index-files", "cogsrch-index-csv"],k=5, deployment_name=MODEL, chunks_limit=100, similarity_k=5)
    www_search = BingSearchAPIWrapper(k=3)
    sql_search = SQLDbWrapper(deployment_name=MODEL)
    
    tools = [
        Tool(
            name = "Current events, facts, and news",
            func=www_search.run,
            description='useful to get current events information like weather, news, sports results, restaurants, current movies.\n'
        ),
        Tool(
            name = "Covid statistics",
            func=sql_search.run,
            description='useful  when you need to answer questions about number of cases, deaths, hospitalizations, tests, people in ICU, people in Ventilator, in the United States related to Covid.\n',
            return_direct=True
        ),
        Tool(
            name = "Search",
            func=doc_search.run,
            description='useful ONLY when you need to answer questions about Covid or about Computer Science, nothing else.\n',
            return_direct=True
        ),
    ]
    
    # Set main Agent
    llm = AzureChatOpenAI(deployment_name=MODEL, temperature=0.5, max_tokens=500)
    agent = ConversationalChatAgent.from_llm_and_tools(llm=llm, tools=tools, system_message=CUSTOM_CHATBOT_PREFIX, human_message=CUSTOM_CHATBOT_SUFFIX)
    memory = ConversationBufferWindowMemory(memory_key="chat_history", return_messages=True, k=10)
    agent_chain = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True, memory=memory)

    async def on_message_activity(self, turn_context: TurnContext):
        answer = self.agent_chain.run(input=turn_context.activity.text) 
        await turn_context.send_activity(answer)

    async def on_members_added_activity(
        self,
        members_added: ChannelAccount,
        turn_context: TurnContext
    ):
        for member_added in members_added:
            if member_added.id != turn_context.activity.recipient.id:
                await turn_context.send_activity("Hello and welcome!")
