import re
import os
import json
from io import BytesIO
from typing import Any, Dict, List, Optional, Awaitable, Callable, Tuple, Type, Union
import requests
import asyncio

from collections import OrderedDict
import base64
from bs4 import BeautifulSoup
import docx2txt
import tiktoken
import html
import time
from time import sleep
from typing import List, Tuple
from pypdf import PdfReader, PdfWriter
from dataclasses import dataclass
from sqlalchemy.engine.url import URL
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain.pydantic_v1 import BaseModel, Field, Extra
from langchain.tools import BaseTool, StructuredTool, tool
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import BaseOutputParser, OutputParserException
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_experimental.agents.agent_toolkits import create_csv_agent
from langchain.tools import BaseTool, StructuredTool, tool
from langchain.prompts import PromptTemplate
from langchain.sql_database import SQLDatabase
from langchain.agents import AgentExecutor, initialize_agent, AgentType, Tool
from langchain_community.utilities import BingSearchAPIWrapper
from langchain.agents import create_sql_agent, create_openai_tools_agent
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities.sql_database import SQLDatabase
from langchain.callbacks.base import BaseCallbackManager
from langchain.requests import RequestsWrapper
from langchain.chains import APIChain
from langchain.agents.agent_toolkits.openapi.spec import reduce_openapi_spec
from langchain.utils.json_schema import dereference_refs
from langchain_openai import AzureChatOpenAI
from langchain_openai import AzureOpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from operator import itemgetter
from typing import List



try:
    from .prompts import (AGENT_DOCSEARCH_PROMPT, CSV_PROMPT_PREFIX, MSSQL_AGENT_PREFIX,
                          CHATGPT_PROMPT, BINGSEARCH_PROMPT, APISEARCH_PROMPT)
except Exception as e:
    print(e)
    from prompts import (AGENT_DOCSEARCH_PROMPT, CSV_PROMPT_PREFIX, MSSQL_AGENT_PREFIX,
                         CHATGPT_PROMPT, BINGSEARCH_PROMPT, APISEARCH_PROMPT)


def text_to_base64(text):
    # Convert text to bytes using UTF-8 encoding
    bytes_data = text.encode('utf-8')

    # Perform Base64 encoding
    base64_encoded = base64.b64encode(bytes_data)

    # Convert the result back to a UTF-8 string representation
    base64_text = base64_encoded.decode('utf-8')

    return base64_text

def table_to_html(table):
    table_html = "<table>"
    rows = [sorted([cell for cell in table.cells if cell.row_index == i], key=lambda cell: cell.column_index) for i in range(table.row_count)]
    for row_cells in rows:
        table_html += "<tr>"
        for cell in row_cells:
            tag = "th" if (cell.kind == "columnHeader" or cell.kind == "rowHeader") else "td"
            cell_spans = ""
            if cell.column_span > 1: cell_spans += f" colSpan={cell.column_span}"
            if cell.row_span > 1: cell_spans += f" rowSpan={cell.row_span}"
            table_html += f"<{tag}{cell_spans}>{html.escape(cell.content)}</{tag}>"
        table_html +="</tr>"
    table_html += "</table>"
    return table_html


def parse_pdf(file, form_recognizer=False, formrecognizer_endpoint=None, formrecognizerkey=None, model="prebuilt-document", from_url=False, verbose=False):
    """Parses PDFs using PyPDF or Azure Document Intelligence SDK (former Azure Form Recognizer)"""
    offset = 0
    page_map = []
    if not form_recognizer:
        if verbose: print(f"Extracting text using PyPDF")
        reader = PdfReader(file)
        pages = reader.pages
        for page_num, p in enumerate(pages):
            page_text = p.extract_text()
            page_map.append((page_num, offset, page_text))
            offset += len(page_text)
    else:
        if verbose: print(f"Extracting text using Azure Document Intelligence")
        credential = AzureKeyCredential(os.environ["FORM_RECOGNIZER_KEY"])
        form_recognizer_client = DocumentAnalysisClient(endpoint=os.environ["FORM_RECOGNIZER_ENDPOINT"], credential=credential)
        
        if not from_url:
            with open(file, "rb") as filename:
                poller = form_recognizer_client.begin_analyze_document(model, document = filename)
        else:
            poller = form_recognizer_client.begin_analyze_document_from_url(model, document_url = file)
            
        form_recognizer_results = poller.result()

        for page_num, page in enumerate(form_recognizer_results.pages):
            tables_on_page = [table for table in form_recognizer_results.tables if table.bounding_regions[0].page_number == page_num + 1]

            # mark all positions of the table spans in the page
            page_offset = page.spans[0].offset
            page_length = page.spans[0].length
            table_chars = [-1]*page_length
            for table_id, table in enumerate(tables_on_page):
                for span in table.spans:
                    # replace all table spans with "table_id" in table_chars array
                    for i in range(span.length):
                        idx = span.offset - page_offset + i
                        if idx >=0 and idx < page_length:
                            table_chars[idx] = table_id

            # build page text by replacing charcters in table spans with table html
            page_text = ""
            added_tables = set()
            for idx, table_id in enumerate(table_chars):
                if table_id == -1:
                    page_text += form_recognizer_results.content[page_offset + idx]
                elif not table_id in added_tables:
                    page_text += table_to_html(tables_on_page[table_id])
                    added_tables.add(table_id)

            page_text += " "
            page_map.append((page_num, offset, page_text))
            offset += len(page_text)

    return page_map    


def read_pdf_files(files, form_recognizer=False, verbose=False, formrecognizer_endpoint=None, formrecognizerkey=None):
    """This function will go through pdf and extract and return list of page texts (chunks)."""
    text_list = []
    sources_list = []
    for file in files:
        page_map = parse_pdf(file, form_recognizer=form_recognizer, verbose=verbose, formrecognizer_endpoint=formrecognizer_endpoint, formrecognizerkey=formrecognizerkey)
        for page in enumerate(page_map):
            text_list.append(page[1][2])
            sources_list.append(file.name + "_page_"+str(page[1][0]+1))
    return [text_list,sources_list]
    
    

# Returns the num of tokens used on a string
def num_tokens_from_string(string: str) -> int:
    encoding_name ='cl100k_base'
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

# Returns num of toknes used on a list of Documents objects
def num_tokens_from_docs(docs: List[Document]) -> int:
    num_tokens = 0
    for i in range(len(docs)):
        num_tokens += num_tokens_from_string(docs[i].page_content)
    return num_tokens


@dataclass(frozen=True)
class ReducedOpenAPISpec:
    """A reduced OpenAPI spec.

    This is a quick and dirty representation for OpenAPI specs.

    Attributes:
        servers: The servers in the spec.
        description: The description of the spec.
        endpoints: The endpoints in the spec.
    """

    servers: List[dict]
    description: str
    endpoints: List[Tuple[str, str, dict]]


def reduce_openapi_spec(spec: dict, dereference: bool = True) -> ReducedOpenAPISpec:
    """Simplify/distill/minify a spec somehow.

    I want a smaller target for retrieval and (more importantly)
    I want smaller results from retrieval.
    I was hoping https://openapi.tools/ would have some useful bits
    to this end, but doesn't seem so.
    """
    # 1. Consider only get, post, patch, put, delete endpoints.
    endpoints = [
        (f"{operation_name.upper()} {route}", docs.get("description"), docs)
        for route, operation in spec["paths"].items()
        for operation_name, docs in operation.items()
        if operation_name in ["get", "post", "patch", "put", "delete"]
    ]

    # 2. Replace any refs so that complete docs are retrieved.
    # Note: probably want to do this post-retrieval, it blows up the size of the spec.
    if dereference:
        endpoints = [
            (name, description, dereference_refs(docs, full_schema=spec))
            for name, description, docs in endpoints
        ]

    # 3. Strip docs down to required request args + happy path response.
    def reduce_endpoint_docs(docs: dict) -> dict:
        out = {}
        if docs.get("description"):
            out["description"] = docs.get("description")
        if docs.get("parameters"):
            out["parameters"] = [
                parameter
                for parameter in docs.get("parameters", [])
                if parameter.get("required")
            ]
        if "200" in docs["responses"]:
            out["responses"] = docs["responses"]["200"]
        if docs.get("requestBody"):
            out["requestBody"] = docs.get("requestBody")
        return out

    endpoints = [
        (name, description, reduce_endpoint_docs(docs))
        for name, description, docs in endpoints
    ]
    return ReducedOpenAPISpec(
        servers=spec["servers"] if "servers" in spec.keys() else [{"url": "https://" + spec["host"]}],
        description=spec["info"].get("description", ""),
        endpoints=endpoints,
    )


def get_search_results(query: str, indexes: list, 
                       k: int = 5,
                       reranker_threshold: int = 1,
                       sas_token: str = "") -> List[dict]:
    """Performs multi-index hybrid search and returns ordered dictionary with the combined results"""
    
    headers = {'Content-Type': 'application/json','api-key': os.environ["AZURE_SEARCH_KEY"]}
    params = {'api-version': os.environ['AZURE_SEARCH_API_VERSION']}

    agg_search_results = dict()
    
    for index in indexes:
        search_payload = {
            "search": query,
            "select": "id, title, chunk, name, location",
            "queryType": "semantic",
            "vectorQueries": [{"text": query, "fields": "chunkVector", "kind": "text", "k": k}],
            "semanticConfiguration": "my-semantic-config",
            "captions": "extractive",
            "answers": "extractive",
            "count":"true",
            "top": k    
        }

        resp = requests.post(os.environ['AZURE_SEARCH_ENDPOINT'] + "/indexes/" + index + "/docs/search",
                         data=json.dumps(search_payload), headers=headers, params=params)

        search_results = resp.json()
        agg_search_results[index] = search_results
    
    content = dict()
    ordered_content = OrderedDict()
    
    for index,search_results in agg_search_results.items():
        for result in search_results['value']:
            if result['@search.rerankerScore'] > reranker_threshold: # Show results that are at least N% of the max possible score=4
                content[result['id']]={
                                        "title": result['title'], 
                                        "name": result['name'], 
                                        "chunk": result['chunk'],
                                        "location": result['location'] + sas_token if result['location'] else "",
                                        "caption": result['@search.captions'][0]['text'],
                                        "score": result['@search.rerankerScore'],
                                        "index": index
                                    }
                

    topk = k
        
    count = 0  # To keep track of the number of results added
    for id in sorted(content, key=lambda x: content[x]["score"], reverse=True):
        ordered_content[id] = content[id]
        count += 1
        if count >= topk:  # Stop after adding topK results
            break

    return ordered_content



class CustomAzureSearchRetriever(BaseRetriever):
    
    indexes: List
    topK : int
    reranker_threshold : int
    sas_token : str = ""
    
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        
        ordered_results = get_search_results(query, self.indexes, k=self.topK, reranker_threshold=self.reranker_threshold, sas_token=self.sas_token)
        
        top_docs = []
        for key,value in ordered_results.items():
            location = value["location"] if value["location"] is not None else ""
            top_docs.append(Document(page_content=value["chunk"], metadata={"source": location, "score":value["score"]}))

        return top_docs

    
def get_answer(llm: AzureChatOpenAI,
               retriever: CustomAzureSearchRetriever, 
               query: str,
               memory: ConversationBufferMemory = None
              ) -> Dict[str, Any]:
    
    """Gets an answer to a question from a list of Documents."""

    # Get the answer
        
    chain = (
        {
            "context": itemgetter("question") | retriever, # Passes the question to the retriever and the results are assign to context
            "question": itemgetter("question")
        }
        | DOCSEARCH_PROMPT  # Passes the 4 variables above to the prompt template
        | llm   # Passes the finished prompt to the LLM
        | StrOutputParser()  # converts the output (Runnable object) to the desired output (string)
    )
    
    answer = chain.invoke({"question": query})

    return answer

    

#####################################################################################################
############################### AGENTS AND TOOL CLASSES #############################################
#####################################################################################################
    
class SearchInput(BaseModel):
    query: str = Field(description="should be a search query")

class GetDocSearchResults_Tool(BaseTool):
    name = "docsearch"
    description = "useful when the questions includes the term: docsearch"
    args_schema: Type[BaseModel] = SearchInput
    
    indexes: List[str] = []
    k: int = 10
    reranker_th: int = 1
    sas_token: str = "" 

    def _run(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:

        retriever = CustomAzureSearchRetriever(indexes=self.indexes, topK=self.k, reranker_threshold=self.reranker_th, 
                                               sas_token=self.sas_token, callback_manager=self.callbacks)
        results = retriever.get_relevant_documents(query=query)
        
        return results

    async def _arun(
        self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool asynchronously."""
        
        retriever = CustomAzureSearchRetriever(indexes=self.indexes, topK=self.k, reranker_threshold=self.reranker_th, 
                                               sas_token=self.sas_token, callback_manager=self.callbacks)
        # Please note below that running a non-async function like run_agent in a separate thread won't make it truly asynchronous. 
        # It allows the function to be called without blocking the event loop, but it may still have synchronous behavior internally.
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(ThreadPoolExecutor(), retriever.get_relevant_documents, query)
        
        return results


class DocSearchAgent(BaseTool):
    """Agent to interact with for Azure AI Search """
    
    name = "docsearch"
    description = "useful when the questions includes the term: docsearch.\n"
    args_schema: Type[BaseModel] = SearchInput

    llm: AzureChatOpenAI
    indexes: List[str] = []
    k: int = 10
    reranker_th: int = 1
    sas_token: str = ""   
    
    class Config:
        extra = Extra.allow  # Allows setting attributes not declared in the model
    
    def __init__(self, **data):
        super().__init__(**data)
        tools = [GetDocSearchResults_Tool(indexes=self.indexes, k=self.k, reranker_th=self.reranker_th, sas_token=self.sas_token)]

        agent = create_openai_tools_agent(self.llm, tools, AGENT_DOCSEARCH_PROMPT)

        self.agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=self.verbose, callback_manager=self.callbacks, handle_parsing_errors=True)
        
    
    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        try:
            result = self.agent_executor.invoke({"question": query})
            return result['output']
        except Exception as e:
            print(e)
            return str(e)  # Return an empty string or some error indicator

    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        try:
            result = await self.agent_executor.ainvoke({"question": query})
            return result['output']
        except Exception as e:
            print(e)
            return str(e)  # Return an empty string or some error indicator
    


class CSVTabularAgent(BaseTool):
    """Agent to interact with CSV files"""
    
    name = "csvfile"
    description = "useful when the questions includes the term: csvfile.\n"
    args_schema: Type[BaseModel] = SearchInput

    path: str
    llm: AzureChatOpenAI

    class Config:
        extra = Extra.allow  # Allows setting attributes not declared in the model

    def __init__(self, **data):
        super().__init__(**data)
        # Create the agent_executor within the __init__ method as requested
        self.agent_executor = create_csv_agent(self.llm, self.path, 
                                               agent_type="openai-tools",
                                               prefix=CSV_PROMPT_PREFIX,
                                               verbose=self.verbose, 
                                               callback_manager=self.callbacks,
                                               )

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        try:
            # Use the initialized agent_executor to invoke the query
            result = self.agent_executor.invoke(query)
            return result['output']
        except Exception as e:
            print(e)
            return str(e)  # Return an error indicator

    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        # Note: Implementation assumes the agent_executor and its methods support async operations
        try:
            # Use the initialized agent_executor to asynchronously invoke the query
            result = await self.agent_executor.ainvoke(query)
            return result['output']
        except Exception as e:
            print(e)
            return str(e)  # Return an error indicator



class SQLSearchAgent(BaseTool):
    """Agent to interact with SQL databases"""
    
    name = "sqlsearch"
    description = "useful when the questions includes the term: sqlsearch.\n"
    args_schema: Type[BaseModel] = SearchInput

    llm: AzureChatOpenAI
    k: int = 30

    class Config:
        extra = Extra.allow  # Allows setting attributes not declared in the model

    def __init__(self, **data):
        super().__init__(**data)
        db_config = self.get_db_config()
        db_url = URL.create(**db_config)
        db = SQLDatabase.from_uri(db_url)
        toolkit = SQLDatabaseToolkit(db=db, llm=self.llm)

        self.agent_executor = create_sql_agent(
            prefix=MSSQL_AGENT_PREFIX,
            llm=self.llm,
            toolkit=toolkit,
            top_k=self.k,
            agent_type="openai-tools",
            callback_manager=self.callbacks,
            verbose=self.verbose,
        )

    def get_db_config(self):
        """Returns the database configuration."""
        return {
            'drivername': 'mssql+pyodbc',
            'username': os.environ["SQL_SERVER_USERNAME"] + '@' + os.environ["SQL_SERVER_NAME"],
            'password': os.environ["SQL_SERVER_PASSWORD"],
            'host': os.environ["SQL_SERVER_NAME"],
            'port': 1433,
            'database': os.environ["SQL_SERVER_DATABASE"],
            'query': {'driver': 'ODBC Driver 17 for SQL Server'}
        }

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        try:
            # Use the initialized agent_executor to invoke the query
            result = self.agent_executor.invoke(query)
            return result['output']
        except Exception as e:
            print(e)
            return str(e)  # Return an error indicator

    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        # Note: Implementation assumes the agent_executor and its methods support async operations
        try:
            # Use the initialized agent_executor to asynchronously invoke the query
            result = await self.agent_executor.ainvoke(query)
            return result['output']
        except Exception as e:
            print(e)
            return str(e)  # Return an error indicator

        

class ChatGPTTool(BaseTool):
    """Tool for a ChatGPT clone"""
    
    name = "chatgpt"
    description = "default tool for general questions, profile or greeting like questions.\n"
    args_schema: Type[BaseModel] = SearchInput

    llm: AzureChatOpenAI

    class Config:
        extra = Extra.allow  # Allows setting attributes not declared in the model

    def __init__(self, **data):
        super().__init__(**data)

        output_parser = StrOutputParser()
        self.chatgpt_chain = CHATGPT_PROMPT | self.llm | output_parser

    def _run(self, query: str) -> str:
        try:
            response = self.chatgpt_chain.invoke({"question": query})
            return response
        except Exception as e:
            print(e)
            return str(e)  # Return an error indicator

    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        """Implement the tool to be used asynchronously."""
        try:
            response = await self.chatgpt_chain.ainvoke({"question": query})
            return response
        except Exception as e:
            print(e)
            return str(e)  # Return an error indicator
               
    
    
class GetBingSearchResults_Tool(BaseTool):
    """Tool for a Bing Search Wrapper"""

    name = "Searcher"
    description = "useful to search the internet.\n"
    args_schema: Type[BaseModel] = SearchInput

    k: int = 5
    
    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        bing = BingSearchAPIWrapper(k=self.k)
        try:
            return bing.results(query,num_results=self.k)
        except:
            return "No Results Found"
    
    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        bing = BingSearchAPIWrapper(k=self.k)
        loop = asyncio.get_event_loop()
        try:
            results = await loop.run_in_executor(ThreadPoolExecutor(), bing.results, query, self.k)
            return results
        except:
            return "No Results Found"
            


class BingSearchAgent(BaseTool):
    """Agent to interact with Bing"""
    
    name = "bing"
    description = "useful when the questions includes the term: bing.\n"
    args_schema: Type[BaseModel] = SearchInput

    llm: AzureChatOpenAI
    k: int = 5
    
    class Config:
        extra = Extra.allow  # Allows setting attributes not declared in the model

    def __init__(self, **data):
        super().__init__(**data)
        
        web_fetch_tool = Tool.from_function(
            func=self.fetch_web_page,
            name="WebFetcher",
            description="useful to fetch the content of a url"
        )

        tools = [GetBingSearchResults_Tool(k=self.k), web_fetch_tool]
        agent = create_openai_tools_agent(self.llm, tools, BINGSEARCH_PROMPT)

        self.agent_executor = AgentExecutor(agent=agent, tools=tools,
                                            return_intermediate_steps=True,
                                            callback_manager=self.callbacks,
                                            verbose=self.verbose,
                                            handle_parsing_errors=True)

    def parse_html(self, content) -> str:
        """Parses HTML content to text."""
        soup = BeautifulSoup(content, 'html.parser')
        text_content_with_links = soup.get_text()
        return text_content_with_links

    def fetch_web_page(self, url: str) -> str:
        """Fetches a webpage and returns its text content."""
        HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0'}
        response = requests.get(url, headers=HEADERS)
        return self.parse_html(response.content)

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        try:
            response = self.agent_executor.invoke({"question": query})
            return response['output']
        except Exception as e:
            print(e)
            return str(e)  # Return an error indicator

    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        """Implements the tool to be used asynchronously."""
        try:
            response = await self.agent_executor.ainvoke({"question": query})
            return response['output']
        except Exception as e:
            print(e)
            return str(e)  # Return an error indicator

        

class GetAPISearchResults_Tool(BaseTool):
    """APIChain as a tool"""
    
    name = "apisearch"
    description = "useful when the questions includes the term: apisearch.\n"
    args_schema: Type[BaseModel] = SearchInput

    llm: AzureChatOpenAI
    api_spec: str
    headers: dict = {}
    limit_to_domains: list = None
    verbose: bool = False
    
    class Config:
        extra = Extra.allow  # Allows setting attributes not declared in the model

    def __init__(self, **data):
        super().__init__(**data)
        self.chain = APIChain.from_llm_and_api_docs(
            llm=self.llm,
            api_docs=self.api_spec,
            headers=self.headers,
            verbose=self.verbose,
            limit_to_domains=self.limit_to_domains
        )

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        try:
            # Optionally sleep to avoid possible TPM rate limits
            sleep(2)
            response = self.chain.invoke(query)
        except Exception as e:
            response = str(e)  # Ensure the response is always a string

        return response

    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        """Use the tool asynchronously."""
        loop = asyncio.get_event_loop()
        try:
            # Optionally sleep to avoid possible TPM rate limits, handled differently in async context
            await asyncio.sleep(2)
            # Execute the synchronous function in a separate thread
            response = await loop.run_in_executor(ThreadPoolExecutor(), self.chain.invoke, query)
        except Exception as e:
            response = str(e)  # Ensure the response is always a string

        return response

        
        
class APISearchAgent(BaseTool):
    """Agent to interact with any API given a OpenAPI 3.0 spec"""
    
    name = "apisearch"
    description = "useful when the questions includes the term: apisearch.\n"
    args_schema: Type[BaseModel] = SearchInput

    llm: AzureChatOpenAI
    llm_search: AzureChatOpenAI
    api_spec: str
    headers: dict = {}
    limit_to_domains: list = None
    
    class Config:
        extra = Extra.allow  # Allows setting attributes not declared in the model

    def __init__(self, **data):
        super().__init__(**data)
        tools = [GetAPISearchResults_Tool(llm=self.llm,
                                          llm_search=self.llm_search,
                                          api_spec=str(self.api_spec),
                                          headers=self.headers,
                                          verbose=self.verbose,
                                          limit_to_domains=self.limit_to_domains)]
        
        agent = create_openai_tools_agent(llm=self.llm, tools=tools, prompt=APISEARCH_PROMPT)
        self.agent_executor = AgentExecutor(agent=agent, tools=tools, 
                                            verbose=self.verbose, 
                                            return_intermediate_steps=True,
                                            callback_manager=self.callbacks)

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        try:
            # Use the initialized agent_executor to invoke the query
            response = self.agent_executor.invoke({"question":query})
            return response['output']
        except Exception as e:
            print(e)
            return str(e)  # Return an error indicator

    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        # Note: Implementation assumes the agent_executor and its methods support async operations
        try:
            # Use the initialized agent_executor to asynchronously invoke the query
            response = await self.agent_executor.ainvoke({"question":query})
            return response['output']
        except Exception as e:
            print(e)
            return str(e)  # Return an error indicator



