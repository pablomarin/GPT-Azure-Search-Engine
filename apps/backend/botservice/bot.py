# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import re
import asyncio
import random
import requests
import json
import logging
import functools
import operator
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union, Annotated, Sequence, Literal
from typing_extensions import TypedDict

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from langgraph.graph import END, StateGraph, START
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


from common.utils import (
    create_docsearch_agent,
    create_csvsearch_agent,
    create_sqlsearch_agent,
    create_websearch_agent,
    create_apisearch_agent,
    reduce_openapi_spec
)
from common.cosmosdb_checkpointer import CosmosDBSaver, AsyncCosmosDBSaver

from common.prompts import (
    WELCOME_MESSAGE,
    CUSTOM_CHATBOT_PREFIX,
    DOCSEARCH_PROMPT_TEXT,
    CSV_AGENT_PROMPT_TEXT,
    MSSQL_AGENT_PROMPT_TEXT,
    BING_PROMPT_TEXT,
    APISEARCH_PROMPT_TEXT,
)


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

        # Set LLM 
        llm = AzureChatOpenAI(deployment_name=self.model_name, temperature=0, 
                              max_tokens=1500, streaming=True)

        # Initialize our Tools/Experts
        doc_indexes = ["srch-index-files", "srch-index-csv", "srch-index-books"]
        docsearch_agent = create_docsearch_agent(llm,indexes,k=20,reranker_th=1.5,
                                         prompt=CUSTOM_CHATBOT_PREFIX + DOCSEARCH_PROMPT_TEXT,
                                         sas_token=os.environ['BLOB_SAS_TOKEN']
                                        )
        
        sqlsearch_agent = create_sqlsearch_agent(llm, 
                                     prompt=CUSTOM_CHATBOT_PREFIX + MSSQL_AGENT_PROMPT_TEXT)
        
        websearch_agent = create_websearch_agent(llm, 
                                     prompt=CUSTOM_CHATBOT_PREFIX+BING_PROMPT_TEXT)
        
        api_file_path = "./openapi_kraken.json"
        with open(api_file_path, 'r') as file:
            spec = json.load(file)

        reduced_api_spec = reduce_openapi_spec(spec)

        apisearch_agent = create_apisearch_agent(llm, 
                            prompt=CUSTOM_CHATBOT_PREFIX + APISEARCH_PROMPT_TEXT.format(api_spec=reduced_api_spec))
        

        await turn_context.send_activity(Activity(type=ActivityTypes.typing))
        
        answer = brain_agent_executor.invoke({"question": input_text}, config=config)["output"]
        
        await turn_context.send_activity(answer)



