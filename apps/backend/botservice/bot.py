# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import re
import asyncio
import random
import requests
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union

from langchain_openai import AzureChatOpenAI
from langchain_community.utilities import BingSearchAPIWrapper
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.runnables import ConfigurableField, ConfigurableFieldSpec
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory, CosmosDBChatMessageHistory
from langchain.agents import ConversationalChatAgent, AgentExecutor, Tool
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.manager import CallbackManager
from langchain.schema import AgentAction, AgentFinish, LLMResult
from langchain_core.runnables.history import RunnableWithMessageHistory

#custom libraries that we will use later in the app
from common.utils import (
    DocSearchAgent, 
    CSVTabularAgent, 
    SQLSearchAgent, 
    ChatGPTTool, 
    BingSearchAgent
)
from common.prompts import CUSTOM_CHATBOT_PROMPT, WELCOME_MESSAGE

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount, Activity, ActivityTypes

# Env variables needed by langchain
os.environ["OPENAI_API_VERSION"] = os.environ.get("AZURE_OPENAI_API_VERSION")


# Callback hanlder used for the bot service to inform the client of the thought process before the final response
class BotServiceCallbackHandler(BaseCallbackHandler):
    """Callback handler to use in Bot Builder Application"""
    
    def __init__(self, turn_context: TurnContext) -> None:
        self.tc = turn_context

    async def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> Any:
        await self.tc.send_activity(f"LLM Error: {error}\n")

    async def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> Any:
        await self.tc.send_activity(f"Tool: {serialized['name']}")

    async def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
        await self.tc.send_activity(f"\u2611{action.log} ...")
        await self.tc.send_activity(Activity(type=ActivityTypes.typing))

            
# Bot Class
class MyBot(ActivityHandler):
    
    def __init__(self):
        self.model_name = os.environ.get("AZURE_OPENAI_MODEL_NAME") 
        
    def get_session_history(self, session_id: str, user_id: str) -> CosmosDBChatMessageHistory:
        cosmos = CosmosDBChatMessageHistory(
            cosmos_endpoint=os.environ['AZURE_COSMOSDB_ENDPOINT'],
            cosmos_database=os.environ['AZURE_COSMOSDB_NAME'],
            cosmos_container=os.environ['AZURE_COSMOSDB_CONTAINER_NAME'],
            connection_string=os.environ['AZURE_COMOSDB_CONNECTION_STRING'],
            session_id=session_id,
            user_id=user_id
            )

        # prepare the cosmosdb instance
        cosmos.prepare_cosmos()
        return cosmos
    
    # Function to show welcome message to new users
    async def on_members_added_activity(self, members_added: ChannelAccount, turn_context: TurnContext):
        for member_added in members_added:
            if member_added.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(WELCOME_MESSAGE)
    
    
    # See https://aka.ms/about-bot-activity-message to learn more about the message and other activity types.
    async def on_message_activity(self, turn_context: TurnContext):
             
        # Extract info from TurnContext - You can change this to whatever , this is just one option 
        session_id = turn_context.activity.conversation.id
        user_id = turn_context.activity.from_property.id + "-" + turn_context.activity.channel_id
        
        input_text_metadata = dict()
        
        # Check if local_timestamp exists and is not None before formatting it
        input_text_metadata["local_timestamp"] = turn_context.activity.local_timestamp.strftime("%I:%M:%S %p, %A, %B %d of %Y") if turn_context.activity.local_timestamp else "Not Available"
    
        # Check if local_timezone exists and is not None before assigning it
        input_text_metadata["local_timezone"] = turn_context.activity.local_timezone if turn_context.activity.local_timezone else "Not Available"
    
        # Check if locale exists and is not None before assigning it
        input_text_metadata["locale"] = turn_context.activity.locale if turn_context.activity.locale else "Not Available"

        # Setting the query to send to OpenAI
        input_text = turn_context.activity.text + "\n\n metadata:\n" + str(input_text_metadata)    
            
        # Set Callback Handler
        cb_handler = BotServiceCallbackHandler(turn_context)
        cb_manager = CallbackManager(handlers=[cb_handler])

        # Set LLM 
        llm = AzureChatOpenAI(deployment_name=self.model_name, temperature=0, 
                              max_tokens=1500, callback_manager=cb_manager, streaming=True)

        # Initialize our Tools/Experts
        doc_indexes = ["srch-index-files", "srch-index-csv"]
        
        doc_search = DocSearchAgent(llm=llm, indexes=doc_indexes,
                           k=6, reranker_th=1,
                           sas_token=os.environ['BLOB_SAS_TOKEN'],
                           name="docsearch",
                           description="useful when the questions includes the term: docsearch",
                           callback_manager=cb_manager, verbose=False)
        
        book_indexes = ["srch-index-books"]
        
        book_search = DocSearchAgent(llm=llm, indexes=book_indexes,
                           k=6, reranker_th=1,
                           sas_token=os.environ['BLOB_SAS_TOKEN'],
                           name="booksearch",
                           description="useful when the questions includes the term: booksearch",
                           callback_manager=cb_manager, verbose=False)
        
        www_search = BingSearchAgent(llm=llm, k=10, callback_manager=cb_manager,
                                    name="bing",
                                    description="useful when the questions includes the term: bing")
        
        sql_search = SQLSearchAgent(llm=llm, k=30, callback_manager=cb_manager,
                            name="sqlsearch",
                            description="useful when the questions includes the term: sqlsearch",
                            verbose=False)
        
        chatgpt_search = ChatGPTTool(llm=llm, callback_manager=cb_manager,
                             name="chatgpt",
                            description="useful when the questions includes the term: chatgpt",
                            verbose=False)
        
        tools = [doc_search, book_search, www_search, sql_search, chatgpt_search]
        
        agent = create_openai_tools_agent(llm, tools, CUSTOM_CHATBOT_PROMPT)
        agent_executor = AgentExecutor(agent=agent, tools=tools)
        brain_agent_executor = RunnableWithMessageHistory(
            agent_executor,
            self.get_session_history,
            input_messages_key="question",
            history_messages_key="history",
            history_factory_config=[
                ConfigurableFieldSpec(
                    id="user_id",
                    annotation=str,
                    name="User ID",
                    description="Unique identifier for the user.",
                    default="",
                    is_shared=True,
                ),
                ConfigurableFieldSpec(
                    id="session_id",
                    annotation=str,
                    name="Session ID",
                    description="Unique identifier for the conversation.",
                    default="",
                    is_shared=True,
                ),
            ],
        )
        
        config={"configurable": {"session_id": session_id, "user_id": user_id}}

        await turn_context.send_activity(Activity(type=ActivityTypes.typing))
        
        answer = brain_agent_executor.invoke({"question": input_text}, config=config)["output"]
        
        await turn_context.send_activity(answer)



