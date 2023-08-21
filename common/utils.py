import re
import os
import json
from io import BytesIO
from typing import Any, Dict, List, Optional, Awaitable, Callable, Tuple, Type, Union
import requests

from collections import OrderedDict
import base64

import docx2txt
import tiktoken
import html
import time
from pypdf import PdfReader, PdfWriter
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

from langchain.embeddings import OpenAIEmbeddings
from langchain.docstore.document import Document
from langchain.llms import AzureOpenAI
from langchain.chat_models import AzureChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import BaseOutputParser, OutputParserException
from langchain.vectorstores import VectorStore
from langchain.vectorstores.faiss import FAISS
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.agents import create_csv_agent
from langchain.chains.question_answering import load_qa_chain
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.chains import ConversationalRetrievalChain
from langchain.chains.conversational_retrieval.prompts import CONDENSE_QUESTION_PROMPT
from langchain.tools import BaseTool
from langchain.prompts import PromptTemplate
from openai.error import AuthenticationError
from langchain.docstore.document import Document
from pypdf import PdfReader
from sqlalchemy.engine.url import URL
from langchain.sql_database import SQLDatabase
from langchain.agents import AgentExecutor, initialize_agent, AgentType
from langchain.tools import BaseTool
from langchain.utilities import BingSearchAPIWrapper
from langchain.agents import create_sql_agent
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.callbacks.base import BaseCallbackManager

try:
    from .prompts import (COMBINE_QUESTION_PROMPT, COMBINE_PROMPT, COMBINE_CHAT_PROMPT,
                          CSV_PROMPT_PREFIX, CSV_PROMPT_SUFFIX, MSSQL_PROMPT, MSSQL_AGENT_PREFIX, 
                          MSSQL_AGENT_FORMAT_INSTRUCTIONS, CHATGPT_PROMPT, BING_PROMPT_PREFIX, DOCSEARCH_PROMPT_PREFIX)
except Exception as e:
    print(e)
    from prompts import (COMBINE_QUESTION_PROMPT, COMBINE_PROMPT, COMBINE_CHAT_PROMPT,
                          CSV_PROMPT_PREFIX, CSV_PROMPT_SUFFIX, MSSQL_PROMPT, MSSQL_AGENT_PREFIX, 
                          MSSQL_AGENT_FORMAT_INSTRUCTIONS, CHATGPT_PROMPT, BING_PROMPT_PREFIX, DOCSEARCH_PROMPT_PREFIX)


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
    
    
def parse_docx(file: BytesIO) -> str:
    text = docx2txt.process(file)
    # Remove multiple newlines
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text


def parse_txt(file: BytesIO) -> str:
    text = file.read().decode("utf-8")
    # Remove multiple newlines
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text


def text_to_docs(text: List[str]) -> List[Document]:
    """Converts a string or list of strings to a list of Documents
    with metadata."""
    if isinstance(text, str):
        # Take a single string as one page
        text = [text]
    page_docs = [Document(page_content=page) for page in text]

    # Add page numbers as metadata
    for i, doc in enumerate(page_docs):
        doc.metadata["page"] = i + 1

    # Split pages into chunks
    doc_chunks = []

    for doc in page_docs:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            chunk_overlap=0,
        )
        chunks = text_splitter.split_text(doc.page_content)
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk, metadata={"page": doc.metadata["page"], "chunk": i}
            )
            # Add sources a metadata
            doc.metadata["source"] = f"{doc.metadata['page']}-{doc.metadata['chunk']}"
            doc_chunks.append(doc)
    return doc_chunks


def embed_docs_faiss(docs: List[Document], chunks_limit: int=100, verbose: bool = False) -> VectorStore:
    """Embeds a list of Documents and returns a FAISS index"""
 
    # Select the Embedder model'
    if verbose: print("Number of chunks:",len(docs))
    embedder = OpenAIEmbeddings(deployment="text-embedding-ada-002", chunk_size=1) 
    
    if len(docs) > chunks_limit:
        docs = docs[:chunks_limit]
        if verbose: print("Truncated Number of chunks:",len(docs))

    index = FAISS.from_documents(docs, embedder)

    return index


def search_docs_faiss(index: VectorStore, query: str, k: int=2) -> List[Document]:
    """Searches a FAISS index for similar chunks to the query
    and returns a list of Documents."""

    # Search for similar chunks
    docs = index.similarity_search(query, k)
    return docs



def wrap_text_in_html(text: List[str]) -> str:
    """Wraps each text block separated by newlines in <p> tags"""
    if isinstance(text, list):
        # Add horizontal rules between pages
        text = "\n<hr/>\n".join(text)
    return "".join([f"<p>{line}</p>" for line in text.split("\n")])


# Returns the num of tokens used on a string
def num_tokens_from_string(string: str) -> int:
    encoding_name ='cl100k_base'
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

# Returning the toekn limit based on model selection
def model_tokens_limit(model: str) -> int:
    """Returns the number of tokens limits in a text model."""
    if model == "gpt-35-turbo":
        token_limit = 4096
    elif model == "gpt-4":
        token_limit = 8192
    elif model == "gpt-35-turbo-16k":
        token_limit = 16384
    elif model == "gpt-4-32k":
        token_limit = 32768
    else:
        token_limit = 4096
    return token_limit

# Returns num of toknes used on a list of Documents objects
def num_tokens_from_docs(docs: List[Document]) -> int:
    num_tokens = 0
    for i in range(len(docs)):
        num_tokens += num_tokens_from_string(docs[i].page_content)
    return num_tokens


def get_search_results(query: str, indexes: list, 
                       k: int = 5,
                       reranker_threshold: int = 1,
                       sas_token: str = "",
                       vector_search: bool = False,
                       similarity_k: int = 3, 
                       query_vector: list = []) -> List[dict]:
    
    headers = {'Content-Type': 'application/json','api-key': os.environ["AZURE_SEARCH_KEY"]}
    params = {'api-version': os.environ['AZURE_SEARCH_API_VERSION']}

    agg_search_results = dict()
    
    for index in indexes:
        search_payload = {
            "search": query,
            "queryType": "semantic",
            "semanticConfiguration": "my-semantic-config",
            "count": "true",
            "speller": "lexicon",
            "queryLanguage": "en-us",
            "captions": "extractive",
            "answers": "extractive",
            "top": k
        }
        if vector_search:
            search_payload["vectors"]= [{"value": query_vector, "fields": "chunkVector","k": k}]
            search_payload["select"]= "id, title, chunk, name, location"
        else:
            search_payload["select"]= "id, title, chunks, language, name, location, vectorized"
        

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
                                        "location": result['location'] + sas_token if result['location'] else "",
                                        "caption": result['@search.captions'][0]['text'],
                                        "index": index
                                    }
                if vector_search:
                    content[result['id']]["chunk"]= result['chunk']
                    content[result['id']]["score"]= result['@search.score'] # Uses the Hybrid RRF score
              
                else:
                    content[result['id']]["chunks"]= result['chunks']
                    content[result['id']]["language"]= result['language']
                    content[result['id']]["score"]= result['@search.rerankerScore'] # Uses the reranker score
                    content[result['id']]["vectorized"]= result['vectorized']
                
    # After results have been filtered, sort and add the top k to the ordered_content
    if vector_search:
        topk = similarity_k
    else:
        topk = k*len(indexes)
        
    count = 0  # To keep track of the number of results added
    for id in sorted(content, key=lambda x: content[x]["score"], reverse=True):
        ordered_content[id] = content[id]
        count += 1
        if count >= topk:  # Stop after adding 5 results
            break

    return ordered_content


def update_vector_indexes(ordered_search_results: dict, embedder: OpenAIEmbeddings):
    
    """Get as input the results of a text-based multi-index search, vectorize the documents chunks that has not been done before and updates the vector-based indexes"""
    
    headers = {'Content-Type': 'application/json','api-key': os.environ["AZURE_SEARCH_KEY"]}
    params = {'api-version': os.environ['AZURE_SEARCH_API_VERSION']}
    
    for key,value in ordered_search_results.items():
        if value["vectorized"] != True: # If the document has not been vectorized yet
            i = 0
            for chunk in value["chunks"]: # Iterate over the text chunks
                try:
                    upload_payload = {  # Insert the chunk and its vector/embedding in the vector-based index
                        "value": [
                            {
                                "id": key + "_" + str(i),
                                "title": f"{value['title']}_chunk_{str(i)}",
                                "chunk": chunk,
                                "chunkVector": embedder.embed_query(chunk if chunk!="" else "-------"),
                                "name": value["name"],
                                "location": value["location"],
                                "@search.action": "upload"
                            },
                        ]
                    }

                    r = requests.post(os.environ['AZURE_SEARCH_ENDPOINT'] + "/indexes/" + value["index"]+"-vector" + "/docs/index",
                                         data=json.dumps(upload_payload), headers=headers, params=params)
                    if r.status_code != 200:
                        print(r.status_code)
                        print(r.text)
                    else:
                        i = i + 1 #increment chunk number

                        # Update document in text-based index and mark it as "vectorized"
                        upload_payload = {
                            "value": [
                                {
                                    "id": key,
                                    "vectorized": True,
                                    "@search.action": "merge"
                                },
                            ]
                        }

                        r = requests.post(os.environ['AZURE_SEARCH_ENDPOINT'] + "/indexes/" + value["index"]+ "/docs/index",
                                         data=json.dumps(upload_payload), headers=headers, params=params)


                except Exception as e:
                    print("Exception:",e)
                    print(content)
                    continue


def get_answer(llm: AzureChatOpenAI,
               docs: List[Document], 
               query: str, 
               language: str, 
               chain_type: str,
               memory: ConversationBufferMemory = None,
               callback_manager: BaseCallbackManager = None
              ) -> Dict[str, Any]:
    
    """Gets an answer to a question from a list of Documents."""

    # Get the answer
        
    if chain_type == "stuff":
        if memory == None:
            chain = load_qa_with_sources_chain(llm, chain_type=chain_type,
                                               prompt=COMBINE_PROMPT,
                                               callback_manager=callback_manager)
        else:
            chain = load_qa_with_sources_chain(llm, chain_type=chain_type, 
                                               prompt=COMBINE_CHAT_PROMPT,
                                               memory=memory,
                                               callback_manager=callback_manager)

    elif chain_type == "map_reduce":
        if memory == None:
            chain = load_qa_with_sources_chain(llm, chain_type=chain_type, 
                                               question_prompt=COMBINE_QUESTION_PROMPT,
                                               combine_prompt=COMBINE_PROMPT,
                                               callback_manager=callback_manager)
        else:
            chain = load_qa_with_sources_chain(llm, chain_type=chain_type, 
                                               question_prompt=COMBINE_QUESTION_PROMPT,
                                               combine_prompt=COMBINE_CHAT_PROMPT,
                                               memory=memory,
                                               callback_manager=callback_manager)
    else:
        print("Error: chain_type", chain_type, "not supported")
    
    answer = chain( {"input_documents": docs, "question": query, "language": language}, return_only_outputs=True)

    return answer


def run_agent(question:str, agent_chain: AgentExecutor) -> str:
    """Function to run the brain agent and deal with potential parsing errors"""
    
    try:
        return agent_chain.run(input=question)
    
    except OutputParserException as e:
        # If the agent has a parsing error, we use OpenAI model again to reformat the error and give a good answer
        chatgpt_chain = LLMChain(
                llm=agent_chain.agent.llm_chain.llm, 
                    prompt=PromptTemplate(input_variables=["error"],template='Remove any json formating from the below text, also remove any portion that says someting similar this "Could not parse LLM output: ". Reformat your response in beautiful Markdown. Just give me the reformated text, nothing else.\n Text: {error}'), 
                verbose=False
            )

        response = chatgpt_chain.run(str(e))
        return response
    

######## TOOL CLASSES #####################################
###########################################################
    
class DocSearchResults(BaseTool):
    """Tool for Azure Search results"""
    
    name = "search knowledge base"
    description = "search documents in search engine"
    
    indexes: List[str] = []
    vector_only_indexes: List[str] = []
    k: int = 10
    reranker_th: int = 1
    similarity_k: int = 3
    sas_token: str = "" 
    embedding_model: str = "text-embedding-ada-002"
    
    def _run(self, query: str) -> str:
        
        embedder = OpenAIEmbeddings(deployment=self.embedding_model, chunk_size=1)
    
        if self.indexes:
            # Search in text-based indexes first and update corresponding vector indexes
            ordered_results = get_search_results(query, indexes=self.indexes, k=self.k, 
                                                    reranker_threshold=self.reranker_th,
                                                    vector_search=False)
            
            update_vector_indexes(ordered_search_results=ordered_results, embedder=embedder)
            
            vector_indexes = [index+"-vector" for index in self.indexes]
            if self.vector_only_indexes:
                vector_indexes = vector_indexes + self.vector_only_indexes
                    
        if self.vector_only_indexes and not self.indexes:
            vector_indexes = self.vector_only_indexes

        if self.verbose:
            print("Vector Indexes:",vector_indexes)

        # Search in all vector-based indexes available
        ordered_results = get_search_results(query, indexes=vector_indexes, k=self.k,
                                             reranker_threshold=self.reranker_th,
                                             vector_search=True,
                                             similarity_k=self.similarity_k,
                                             query_vector = embedder.embed_query(query),
                                             sas_token=self.sas_token,
                                            )
        
        return ordered_results

    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("DocSearchResults does not support async")
  

class DocSearchTool(BaseTool):
    """Tool for Azure GPT Smart Search Engine"""
    
    name = "@docsearch"
    description = "useful when the questions includes the term: @docsearch.\n"

    llm: AzureChatOpenAI
    indexes: List[str] = []
    vector_only_indexes: List[str] = []
    k: int = 10
    reranker_th: int = 1
    similarity_k: int = 3
    sas_token: str = ""   
    embedding_model: str = "text-embedding-ada-002"
    
    def _run(self, tool_input: Union[str, Dict],) -> str:
        try:
            tools = [DocSearchResults(indexes=self.indexes,vector_only_indexes=self.vector_only_indexes,
                                      k=self.k, reranker_th=self.reranker_th, similarity_k=self.similarity_k,
                                      sas_token=self.sas_token, embedding_model=self.embedding_model)]
            
            parsed_input = self._parse_input(tool_input)
            
            agent_executor = initialize_agent(tools=tools, 
                                              llm=self.llm, 
                                              agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, 
                                              agent_kwargs={'prefix':DOCSEARCH_PROMPT_PREFIX},
                                              callback_manager=self.callbacks,
                                              verbose=self.verbose)
            
            for i in range(2):
                try:
                    response = run_agent(parsed_input, agent_executor)
                    break
                except Exception as e:
                    response = str(e)
                    continue

            return response
        
        except Exception as e:
            print(e)
    
    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("DocSearchTool does not support async")
    
    

class CSVTabularTool(BaseTool):
    """Tool CSV agent"""
    
    name = "@csvfile"
    description = "useful when the questions includes the term: @csvfile.\n"

    path: str
    llm: AzureChatOpenAI
    
    def _run(self, query: str) -> str:
        
        try:
            agent = create_csv_agent(self.llm, self.path, verbose=self.verbose, callback_manager=self.callbacks)
            for i in range(5):
                try:
                    response = agent.run(CSV_PROMPT_PREFIX + query + CSV_PROMPT_SUFFIX) 
                    break
                except:
                    response = "Error too many failed retries"
                    continue

            return response
        except Exception as e:
            print(e)
            response = e
            return response
    
    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("CSVTabularTool does not support async")
        
        
class SQLDbTool(BaseTool):
    """Tool SQLDB Agent"""
    
    name = "@sqlsearch"
    description = "useful when the questions includes the term: @sqlsearch.\n"

    llm: AzureChatOpenAI
    k: int = 30
    
    def _run(self, query: str) -> str:
        db_config = {
            'drivername': 'mssql+pyodbc',
            'username': os.environ["SQL_SERVER_USERNAME"] +'@'+ os.environ["SQL_SERVER_NAME"],
            'password': os.environ["SQL_SERVER_PASSWORD"],
            'host': os.environ["SQL_SERVER_NAME"],
            'port': 1433,
            'database': os.environ["SQL_SERVER_DATABASE"],
            'query': {'driver': 'ODBC Driver 17 for SQL Server'}
        }

        db_url = URL.create(**db_config)
        db = SQLDatabase.from_uri(db_url)
        toolkit = SQLDatabaseToolkit(db=db, llm=self.llm)
        agent_executor = create_sql_agent(
            prefix=MSSQL_AGENT_PREFIX,
            format_instructions = MSSQL_AGENT_FORMAT_INSTRUCTIONS,
            llm=self.llm,
            toolkit=toolkit,
            callback_manager=self.callbacks,
            top_k=self.k,
            verbose=self.verbose
        )

        for i in range(2):
            try:
                response = agent_executor.run(query) 
                break
            except Exception as e:
                response = str(e)
                continue

        return response
        
    
    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("SQLDbTool does not support async")
        
        
        
class ChatGPTTool(BaseTool):
    """Tool for a ChatGPT clone"""
    
    name = "@chatgpt"
    description = "useful when the questions includes the term: @chatgpt.\n"

    llm: AzureChatOpenAI
    
    def _run(self, query: str) -> str:
        try:
            chatgpt_chain = LLMChain(
                llm=self.llm, 
                prompt=CHATGPT_PROMPT,
                callback_manager=self.callbacks,
                verbose=self.verbose
            )

            response = chatgpt_chain.run(query)

            return response
        except Exception as e:
            print(e)
            
    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("ChatGPTTool does not support async")
        
    
    
class BingSearchResults(BaseTool):
    """Tool for a Bing Search Wrapper"""

    name = "@bing"
    description = "useful when the questions includes the term: @bing.\n"

    k: int = 5

    def _run(self, query: str) -> str:
        bing = BingSearchAPIWrapper(k=self.k)
        try:
            return bing.results(query,num_results=self.k)
        except:
            return "No Results Found"
    
    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("BingSearchResults does not support async")
            

class BingSearchTool(BaseTool):
    """Tool for a Bing Search Wrapper"""
    
    name = "@bing"
    description = "useful when the questions includes the term: @bing.\n"
    
    llm: AzureChatOpenAI
    k: int = 5
    
    def _run(self, tool_input: Union[str, Dict],) -> str:
        try:
            tools = [BingSearchResults(k=self.k)]
            parsed_input = self._parse_input(tool_input)

            agent_executor = initialize_agent(tools=tools, 
                                              llm=self.llm, 
                                              agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, 
                                              agent_kwargs={'prefix':BING_PROMPT_PREFIX},
                                              callback_manager=self.callbacks,
                                              verbose=self.verbose)
            
            for i in range(2):
                try:
                    response = run_agent(parsed_input, agent_executor)
                    break
                except Exception as e:
                    response = str(e)
                    continue

            return response
        
        except Exception as e:
            print(e)
    
    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("BingSearchTool does not support async")