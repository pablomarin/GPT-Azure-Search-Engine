#!/usr/bin/env python
import os
import sys
from operator import itemgetter
from datetime import datetime
from typing import Any, Dict, TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from langserve import add_routes
from langchain_openai import AzureChatOpenAI
from langchain.pydantic_v1 import BaseModel
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnableMap, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import ConfigurableField, ConfigurableFieldSpec
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.utilities import BingSearchAPIWrapper
from langchain_community.chat_message_histories import CosmosDBChatMessageHistory
from langchain.agents import AgentExecutor, Tool, create_openai_tools_agent


### uncomment this section to run server in local host #########

# from pathlib import Path
# from dotenv import load_dotenv
# # Calculate the path three directories above the current script
# library_path = Path(__file__).resolve().parents[4]
# sys.path.append(str(library_path))
# load_dotenv(str(library_path) + "/credentials.env")
# os.environ["AZURE_OPENAI_MODEL_NAME"] = os.environ["GPT4_DEPLOYMENT_NAME"]

###################################

from common.utils import (
    DocSearchAgent, 
    CSVTabularAgent, 
    SQLSearchAgent, 
    ChatGPTTool, 
    BingSearchAgent
)
from common.prompts import CUSTOM_CHATBOT_PROMPT, WELCOME_MESSAGE

# Env variable needed by langchain

os.environ["OPENAI_API_VERSION"] = os.environ["AZURE_OPENAI_API_VERSION"]

# Declaration of the App
app = FastAPI(
    title="LangChain Server",
    version="1.0",
    description="A simple api server using Langchain's Runnable interfaces",
)


# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Default route -> leads to the OpenAPI Swagger definition
@app.get("/")
async def redirect_root_to_docs():
    return RedirectResponse("/docs")


###################### Simple route/chain -> just the llms
add_routes(
    app,
    AzureChatOpenAI(deployment_name=os.environ.get("AZURE_OPENAI_MODEL_NAME") , 
                      temperature=0.5, 
                      max_tokens=500),
    path="/chatgpt",
)

###################### More complex chain/route with a prompt and custom input and output

prompt = ChatPromptTemplate.from_messages(
    [("human", "make a joke about `{topic}` in {language}")]
)

model = AzureChatOpenAI(deployment_name=os.environ.get("AZURE_OPENAI_MODEL_NAME"), temperature=0.9, max_tokens=500)

output_parser = StrOutputParser()

# Chain definition
chain = prompt | model | output_parser

# Define a wrapper chain that responds with extra content
answer_chain  = RunnablePassthrough.assign(output=chain) | {
    "content": lambda x: x["output"],
    "info": lambda x: {"timestamp": datetime.now()},
}

# Define the pydantic input and output schema
class InputJoke(TypedDict):
    topic: str
    language: str

class OutputJoke(TypedDict):
    content: chain.output_schema
    info: Dict[str, Any]
    
# Define the endpoint for this chain
add_routes(
    app,
    answer_chain.with_types(input_type=InputJoke, output_type=OutputJoke),
    path="/joke",
)


###################### Now a complex agent

# History function
def get_session_history(session_id: str, user_id: str) -> CosmosDBChatMessageHistory:
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


# Set LLM
llm = AzureChatOpenAI(deployment_name=os.environ.get("AZURE_OPENAI_MODEL_NAME"), temperature=0, max_tokens=1500, streaming=True)

# Initialize our Tools/Experts
doc_indexes = ["srch-index-files", "srch-index-csv"]

doc_search = DocSearchAgent(llm=llm, indexes=doc_indexes,
                   k=6, reranker_th=1,
                   sas_token=os.environ['BLOB_SAS_TOKEN'],
                   name="docsearch",
                   description="useful when the questions includes the term: docsearch",
                   verbose=False)

book_indexes = ["srch-index-books"]

book_search = DocSearchAgent(llm=llm, indexes=book_indexes,
                   k=6, reranker_th=1,
                   sas_token=os.environ['BLOB_SAS_TOKEN'],
                   name="booksearch",
                   description="useful when the questions includes the term: booksearch",
                   verbose=False)


www_search = BingSearchAgent(llm=llm, k=10,
                             name="bing",
                             description="useful when the questions includes the term: bing",
                             verbose=False)

sql_search = SQLSearchAgent(llm=llm, k=30,
                    name="sqlsearch",
                    description="useful when the questions includes the term: sqlsearch",
                    verbose=False)

chatgpt_search = ChatGPTTool(llm=llm,
                     name="chatgpt",
                    description="useful when the questions includes the term: chatgpt",
                    verbose=False)

tools = [doc_search, book_search, www_search, sql_search, chatgpt_search]

# Create the brain Agent

agent = create_openai_tools_agent(llm, tools, CUSTOM_CHATBOT_PROMPT)
agent_executor = AgentExecutor(agent=agent, tools=tools)
brain_agent_executor = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
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

# Create Input and Output Schemas

class Input(TypedDict):
    question: str

class Output(BaseModel):
    output: Any

# Add API route

add_routes(
    app,
    brain_agent_executor.with_types(input_type=Input, output_type=Output),
    path="/agent",
)



###################### Run the server

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)