import re
import os
import json
import requests
import asyncio
import base64
import shutil
import zipfile
import time
import tiktoken

from time import sleep
from io import BytesIO
from typing import Any, Dict, List, Optional, Awaitable, Callable, Tuple, Type, Union
from operator import itemgetter
from typing import List
from pydantic import BaseModel, Field, Extra
from pypdf import PdfReader, PdfWriter
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from tqdm import tqdm
from bs4 import BeautifulSoup

from sqlalchemy.engine.url import URL
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient


from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun,CallbackManagerForToolRun
from langchain_core.utils.json_schema import dereference_refs
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun, Callbacks
from langchain_experimental.tools import PythonAstREPLTool


from langchain_community.utilities import BingSearchAPIWrapper
from langchain_community.tools.bing_search import BingSearchResults
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.utilities.requests import RequestsWrapper, TextRequestsWrapper
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit


from langchain_openai import AzureChatOpenAI
from langchain_openai import AzureOpenAIEmbeddings

from langgraph.prebuilt import create_react_agent


import logging
logger = logging.getLogger(__name__)


try:
    from .prompts import (DOCSEARCH_PROMPT_TEXT, CSV_AGENT_PROMPT_TEXT, MSSQL_AGENT_PROMPT_TEXT,
                           BING_PROMPT_TEXT, APISEARCH_PROMPT_TEXT)
except Exception as e:
    print(e)
    from prompts import (DOCSEARCH_PROMPT_TEXT, CSV_AGENT_PROMPT_TEXT, MSSQL_AGENT_PROMPT_TEXT,
                         BING_PROMPT_TEXT, APISEARCH_PROMPT_TEXT)

    
# Function to upload a single file
def upload_file_to_blob(file_path, blob_name, container_name):
    blob_service_client = BlobServiceClient.from_connection_string(os.environ['BLOB_CONNECTION_STRING'])
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_name)
    with open(file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

# Unzip the file to a temporary directory
def extract_zip_file(zip_path, extract_to):
    print(f"Extracting {zip_path} ... ")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"Extracted {zip_path} to {extract_to}")

# Recursive function to upload all files in a directory with overall progress bar
def upload_directory_to_blob(local_directory, container_name, container_folder=""):
    total_files = sum([len(files) for _, _, files in os.walk(local_directory)])  # Get total number of files
    with tqdm(total=total_files, desc="Uploading Files", ncols=100) as overall_progress:
        for root, dirs, files in os.walk(local_directory):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, local_directory)
                blob_name = os.path.join(container_folder, relative_path).replace("\\", "/")  # Adjust path for Azure
                upload_file_to_blob(file_path, blob_name, container_name)
                overall_progress.update(1)  # Update progress after each file is uploaded


# Function that uses PyPDF of Azure Form Recognizer to parse PDFs
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
            # If file is a string (file path), open it normally; if it's BytesIO, pass it directly
            if isinstance(file, str):
                with open(file, "rb") as filename:
                    poller = form_recognizer_client.begin_analyze_document(model, document=filename)
            elif isinstance(file, BytesIO):
                poller = form_recognizer_client.begin_analyze_document(model, document=file)
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
                       search_filter: str = "",
                       k: int = 5,
                       reranker_threshold: float = 1,
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
        
        if search_filter:
            search_payload["filter"] = search_filter

        resp = requests.post(os.environ['AZURE_SEARCH_ENDPOINT'] + "/indexes/" + index + "/docs/search",
                         data=json.dumps(search_payload), headers=headers, params=params)

        search_results = resp.json()
        agg_search_results[index] = search_results
        
        
    if not any("value" in results for results in agg_search_results.values()):
        logger.warning("Empty Search Response")
        return {}
    
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
    reranker_threshold : float
    sas_token : str = ""
    search_filter : str = ""
    
    
    def _get_relevant_documents(
        self, input: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[dict]:
        
        ordered_results = get_search_results(input, self.indexes, k=self.topK, reranker_threshold=self.reranker_threshold, sas_token=self.sas_token, search_filter=self.search_filter)
        
        top_docs = []
        for key,value in ordered_results.items():
            location = value["location"] if value["location"] is not None else ""
            document = {"source": location,
                        "score": value["score"],
                        "page_content": value["chunk"]}
            top_docs.append(document)

        return top_docs

    
def get_answer(llm: AzureChatOpenAI,
               retriever: CustomAzureSearchRetriever, 
               query: str,
               ) -> Dict[str, Any]:
    
    """Gets an answer to a question from a list of Documents."""

    # Get the answer
    
    # Define prompt template
    DOCSEARCH_PROMPT = ChatPromptTemplate.from_messages(
            [
                ("system", DOCSEARCH_PROMPT_TEXT + "\n\nCONTEXT:\n{context}\n\n"),
                ("human", "{question}"),
            ]
        )
        
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
    return_direct: bool = Field(
        description="Whether or the result of this should be returned directly to the user without you seeing what it is",
        default=False,
    )



class GetDocSearchResults_Tool(BaseTool):
    name: str = "documents_retrieval"
    description: str = "Retrieves documents from knowledge base"
    args_schema: Type[BaseModel] = SearchInput
    
    indexes: List[str] = []
    k: int = 10
    reranker_th: float = 1
    sas_token: str = "" 

    def _run(self, query: str,  return_direct = False,  run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:

        retriever = CustomAzureSearchRetriever(indexes=self.indexes, topK=self.k, reranker_threshold=self.reranker_th, 
                                               sas_token=self.sas_token, callback_manager=self.callbacks)
        results = retriever.invoke(input=query)
        
        return results

    async def _arun(self, query: str, return_direct = False, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        """Use the tool asynchronously."""
        
        retriever = CustomAzureSearchRetriever(indexes=self.indexes, topK=self.k, reranker_threshold=self.reranker_th, 
                                               sas_token=self.sas_token, callback_manager=self.callbacks)
        # Please note below that running a non-async function like run_agent in a separate thread won't make it truly asynchronous. 
        # It allows the function to be called without blocking the event loop, but it may still have synchronous behavior internally.
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(ThreadPoolExecutor(), retriever.invoke, query)
        
        return results


def create_docsearch_agent(
        llm:AzureChatOpenAI,
        indexes: List, k:int, reranker_th:float,
        prompt:str,
        sas_token:str=""
    ):


    docsearch_tool = GetDocSearchResults_Tool(indexes=indexes,
                                              k=k,
                                              reranker_th=reranker_th, 
                                              sas_token=sas_token)

    docsearch_agent = create_react_agent(llm, tools=[docsearch_tool], state_modifier=prompt)
    
    return docsearch_agent
    

def create_csvsearch_agent(
        llm:AzureChatOpenAI,
        prompt:str,
    ):
    csvsearch_agent = create_react_agent(llm,tools=[PythonAstREPLTool()], state_modifier=prompt)
    
    return csvsearch_agent  
 

def create_sqlsearch_agent(
        llm:AzureChatOpenAI,
        prompt:str,
    ):
    
    # Configuration for the database connection
    db_config = {
        'drivername': 'mssql+pyodbc',
        'username': os.environ["SQL_SERVER_USERNAME"] + '@' + os.environ["SQL_SERVER_NAME"],
        'password': os.environ["SQL_SERVER_PASSWORD"],
        'host': os.environ["SQL_SERVER_NAME"],
        'port': 1433,
        'database': os.environ["SQL_SERVER_DATABASE"],
        'query': {'driver': 'ODBC Driver 17 for SQL Server'},
    }

    # Create a URL object for connecting to the database
    db_url = URL.create(**db_config)
    
    toolkit = SQLDatabaseToolkit(db=SQLDatabase.from_uri(db_url), llm=llm)
    
    sqlsearch_agent = create_react_agent(llm, 
                                     tools=toolkit.get_tools(), 
                                     state_modifier=prompt)
    
    return sqlsearch_agent  


def create_websearch_agent(
        llm:AzureChatOpenAI,
        prompt:str,
        k:int=10
    ):
    
    bing_tool = BingSearchResults(api_wrapper=BingSearchAPIWrapper(), 
                              num_results=k,
                              name="Searcher",
                              description="useful to search the internet")

    def parse_html(content) -> str:
        soup = BeautifulSoup(content, 'html.parser')
        text_content_with_links = soup.get_text()
        # Split the text into words and limit to the first 10,000
        limited_text_content = ' '.join(text_content_with_links.split()[:10000])
        return limited_text_content

    def fetch_web_page(url: str) -> str:
        HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0'}
        response = requests.get(url, headers=HEADERS)
        return parse_html(response.content)

    web_fetch_tool = StructuredTool.from_function(
        func=fetch_web_page,
        name="WebFetcher",
        description="useful to fetch the content of a url"
    )
    
    websearch_agent = create_react_agent(llm, 
                                     tools=[bing_tool, web_fetch_tool], 
                                     state_modifier=prompt)
    
    return websearch_agent


def create_apisearch_agent(
        llm:AzureChatOpenAI,
        prompt:str,
    ):
    
    toolkit = RequestsToolkit(requests_wrapper=RequestsWrapper(),allow_dangerous_requests=True)

    
    apisearch_agent = create_react_agent(llm, 
                                     tools=toolkit.get_tools(), 
                                     state_modifier=prompt)
    
    return apisearch_agent 