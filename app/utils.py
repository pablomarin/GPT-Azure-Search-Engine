import re
from io import BytesIO
from typing import Any, Dict, List
import requests
import os
from collections import OrderedDict

import docx2txt
import streamlit as st
from langchain.embeddings import OpenAIEmbeddings
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.docstore.document import Document
from langchain.llms import AzureOpenAI
from langchain.chat_models import AzureChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
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
from openai.error import AuthenticationError
from langchain.docstore.document import Document
from pypdf import PdfReader
from sqlalchemy.engine.url import URL
from langchain.sql_database import SQLDatabase
from langchain import SQLDatabaseChain
from langchain.agents import AgentExecutor
from langchain.agents import create_sql_agent
from langchain.agents.agent_toolkits import SQLDatabaseToolkit

import tiktoken

try:
    from .prompts import (COMBINE_QUESTION_PROMPT, COMBINE_PROMPT, COMBINE_CHAT_PROMPT,
                          CSV_PROMPT_PREFIX, CSV_PROMPT_SUFFIX, MSSQL_PROMPT, MSSQL_AGENT_PREFIX, 
                          MSSQL_AGENT_FORMAT_INSTRUCTIONS, CHATGPT_PROMPT)
except Exception as e:
    print(e)
    from prompts import (COMBINE_QUESTION_PROMPT, COMBINE_PROMPT, COMBINE_CHAT_PROMPT,
                          CSV_PROMPT_PREFIX, CSV_PROMPT_SUFFIX, MSSQL_PROMPT, MSSQL_AGENT_PREFIX, 
                          MSSQL_AGENT_FORMAT_INSTRUCTIONS, CHATGPT_PROMPT)



# @st.cache_data
def parse_docx(file: BytesIO) -> str:
    text = docx2txt.process(file)
    # Remove multiple newlines
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text


# @st.cache_data
def parse_pdf(file: BytesIO) -> List[str]:
    pdf = PdfReader(file)
    output = []
    for page in pdf.pages:
        text = page.extract_text()
        # Merge hyphenated words
        text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
        # Fix newlines in the middle of sentences
        text = re.sub(r"(?<!\n\s)\n(?!\s\n)", " ", text.strip())
        # Remove multiple newlines
        text = re.sub(r"\n\s*\n", "\n\n", text)

        output.append(text)

    return output


# @st.cache_data
def parse_txt(file: BytesIO) -> str:
    text = file.read().decode("utf-8")
    # Remove multiple newlines
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text


# @st.cache_data
def text_to_docs(text: str | List[str]) -> List[Document]:
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


# @st.cache_data(show_spinner=False)
def embed_docs(docs: List[Document]) -> VectorStore:
    """Embeds a list of Documents and returns a FAISS index"""
 
    # Select the Embedder model'
    print("Number of chunks:",len(docs))
    if len(docs) < 50:
        # OpenAI models are accurate but slower
        embedder = OpenAIEmbeddings(deployment="text-embedding-ada-002", chunk_size=1) 
    else:
        # Bert based models are faster (3x-10x) but not as accurate
        # For Multiple language support we need to use a multilingual model. But if English only is the requirement, use "multi-qa-MiniLM-L6-cos-v1" for a good trade-off between quality and speed
        # The fastest english model though is "all-MiniLM-L12-v2"
        embedder = HuggingFaceEmbeddings(model_name = 'distiluse-base-multilingual-cased-v2')


    index = FAISS.from_documents(docs, embedder)

    return index


def search_docs(index: VectorStore, query: str) -> List[Document]:
    """Searches a FAISS index for similar chunks to the query
    and returns a list of Documents."""

    # Search for similar chunks
    docs = index.similarity_search(query, k=4)
    return docs


def get_sources(answer: Dict[str, Any], docs: List[Document]) -> List[Document]:
    """Gets the source documents for an answer."""

    # Get sources for the answer
    source_keys = [s for s in answer["output_text"].split("SOURCES: ")[-1].split(", ")]

    source_docs = []
    for doc in docs:
        if doc.metadata["source"] in source_keys:
            source_docs.append(doc)

    return source_docs



def get_answer(docs: List[Document], 
               query: str, 
               language: str,
               deployment: str, 
               chain_type: str,
               memory: ConversationBufferMemory = None,
               temperature: float = 0.5, 
               max_tokens: int = 500
              ) -> Dict[str, Any]:
    
    """Gets an answer to a question from a list of Documents."""

    # Get the answer
    
    if (deployment in ["gpt-35-turbo", "gpt-4", "gpt-4-32k"]) :
        llm = AzureChatOpenAI(deployment_name=deployment, temperature=temperature, max_tokens=max_tokens)
    else:
        llm = AzureOpenAI(deployment_name=deployment, temperature=temperature, max_tokens=max_tokens)
    
    if chain_type == "stuff":
        if memory == None:
            chain = load_qa_with_sources_chain(llm, chain_type=chain_type,
                                               prompt=COMBINE_PROMPT)
        else:
            chain = load_qa_with_sources_chain(llm, chain_type=chain_type, 
                                               prompt=COMBINE_CHAT_PROMPT,
                                               memory=memory)

    elif chain_type == "map_reduce":
        if memory == None:
            chain = load_qa_with_sources_chain(llm, chain_type=chain_type, 
                                               question_prompt=COMBINE_QUESTION_PROMPT,
                                               combine_prompt=COMBINE_PROMPT)
        else:
            chain = load_qa_with_sources_chain(llm, chain_type=chain_type, 
                                               question_prompt=COMBINE_QUESTION_PROMPT,
                                               combine_prompt=COMBINE_CHAT_PROMPT,
                                               memory=memory)
    else:
        print("Error: chain_type", chain_type, "not supported")
    
    answer = chain( {"input_documents": docs, "question": query, "language": language}, return_only_outputs=True)

    return answer



def wrap_text_in_html(text: str | List[str]) -> str:
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
        token_limit = 3000
    elif model == "gpt-4":
        token_limit = 7000
    elif model == "gpt-4-32k":
        token_limit = 31000
    else:
        token_limit = 3000
    return token_limit

# Returns num of toknes used on a list of Documents objects
def num_tokens_from_docs(docs: List[Document]) -> int:
    num_tokens = 0
    for i in range(len(docs)):
        num_tokens += num_tokens_from_string(docs[i].page_content)
    return num_tokens


def get_search_results(query: str, indexes: list, k: int = 5) -> List[dict]:
    
    AZURE_SEARCH_API_VERSION = '2021-04-30-Preview'
    headers = {'Content-Type': 'application/json','api-key': os.environ["AZURE_SEARCH_KEY"]}

    agg_search_results = []
    
    for index in indexes:
        url = os.environ["AZURE_SEARCH_ENDPOINT"] + '/indexes/'+ index + '/docs'
        url += '?api-version={}'.format(AZURE_SEARCH_API_VERSION)
        url += '&search={}'.format(query)
        url += '&select=*'
        url += '&$top={}'.format(k)  # You can change this to anything you need/want
        url += '&queryLanguage=en-us'
        url += '&queryType=semantic'
        url += '&semanticConfiguration=my-semantic-config'
        url += '&$count=true'
        url += '&speller=lexicon'
        url += '&answers=extractive|count-3'
        url += '&captions=extractive|highlight-false'

        resp = requests.get(url, headers=headers)

        search_results = resp.json()
        agg_search_results.append(search_results)

    return agg_search_results
    

def order_search_results( agg_search_results: List[dict], reranker_threshold: int) -> OrderedDict:
    
    """Orders based on score the results from get_search_results function"""
    
    content = dict()
    ordered_content = OrderedDict()
    
    for search_results in agg_search_results:
        for result in search_results['value']:
            if result['@search.rerankerScore'] > reranker_threshold: # Show results that are at least 25% of the max possible score=4
                content[result['id']]={
                                        "title": result['title'],
                                        "chunks": result['pages'],
                                        "language": result['language'],
                                        "caption": result['@search.captions'][0]['text'],
                                        "score": result['@search.rerankerScore'],
                                        "name": result['metadata_storage_name'],
                                        "location": result['metadata_storage_path']                  
                                    }
    #After results have been filtered we will Sort and add them as an Ordered list
    for id in sorted(content, key= lambda x: content[x]["score"], reverse=True):
        ordered_content[id] = content[id]

    return ordered_content


class DocSearchWrapper(BaseTool):
    """Wrapper for Azure GPT Smart Search Engine"""
    
    name = "Doc Search"
    description = 'useful for when you need to answer questions that **DO NOT** begin with "Hey Bing" or "Hey ChatGPT".\n'

    indexes: List[str]
    k: int = 10
    deployment_name: str = "gpt-35-turbo"
    response_language: str = "English"
    reranker_th: int = 1
    max_tokens: int = 500
    temperature: float = 0.5
    
    def _run(self, query: str) -> str:

        try:
            agg_search_results = get_search_results(query, self.indexes, self.k)
            ordered_results = order_search_results(agg_search_results, reranker_threshold=self.reranker_th)
            docs = []
            for key,value in ordered_results.items():
                for page in value["chunks"]:
                    docs.append(Document(page_content=page, metadata={"source": value["location"]}))

            # Calculate number of tokens of our docs
            tokens_limit = model_tokens_limit(self.deployment_name)

            if(len(docs)>0):
                num_tokens = num_tokens_from_docs(docs)
                print("Custom token limit for", self.deployment_name, ":", tokens_limit)
                print("Combined docs tokens count:",num_tokens)

            else:
                return "No Results Found in my knowledge base"

            if num_tokens > tokens_limit:
                index = embed_docs(docs)
                top_docs = search_docs(index, query)

                # Now we need to recalculate the tokens count of the top results from similarity vector search
                # in order to select the chain type: stuff or map_reduce

                num_tokens = num_tokens_from_docs(top_docs)   
                print("Token count after similarity search:", num_tokens)
                chain_type = "map_reduce" if num_tokens > tokens_limit else "stuff"

            else:
                # if total tokens is less than our limit, we don't need to vectorize and do similarity search
                top_docs = docs
                chain_type = "stuff"

            print("Chain Type selected:", chain_type)

            response = get_answer(docs=top_docs, query=query, language=self.response_language, 
                                  deployment=self.deployment_name, chain_type=chain_type,
                                  temperature=self.temperature, max_tokens=self.max_tokens)

            return response['output_text']
        
        except Exception as e:
            print(e)
    
    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("SmartSearchWrapper does not support async")
    

class CSVTabularWrapper(BaseTool):
    """Wrapper CSV agent"""
    
    name = "CSV Search"
    description = 'useful for when you need to answer questions about number of cases, deaths, hospitalizations, tests, people in ICU, people in Ventilator, in the United States related to Covid-19.\n'

    path: str
    deployment_name: str = "gpt-4"
    max_tokens: int = 500
    temperature: float = 0
    
    def _run(self, query: str) -> str:
        
        try:
            llm = AzureChatOpenAI(deployment_name=self.deployment_name, temperature=self.temperature, max_tokens=self.max_tokens)
            agent = create_csv_agent(llm, self.path, verbose=True)
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
        raise NotImplementedError("CSVTabularWrapper does not support async")
        
        
class SQLDbWrapper(BaseTool):
    """Wrapper SQLDB Agent"""
    
    name = "SQL Search"
    description = 'useful for when you need to answer questions about number of cases, deaths, hospitalizations, tests, people in ICU, people in Ventilator, in the United States related to Covid-19.\n'

    k:str = 5
    deployment_name: str = "gpt-35-turbo"
    max_tokens: int = 500
    temperature: float = 0
    
    def _run(self, query: str) -> str:
        try:
            db_config = {
                'drivername': 'mssql+pyodbc',
                'username': os.environ["SQL_SERVER_USERNAME"] +'@'+ os.environ["SQL_SERVER_ENDPOINT"],
                'password': os.environ["SQL_SERVER_PASSWORD"],
                'host': os.environ["SQL_SERVER_ENDPOINT"],
                'port': 1433,
                'database': os.environ["SQL_SERVER_DATABASE"],
                'query': {'driver': 'ODBC Driver 17 for SQL Server'}
            }

            db_url = URL.create(**db_config)
            db = SQLDatabase.from_uri(db_url)
            llm = AzureChatOpenAI(deployment_name=self.deployment_name, temperature=self.temperature, max_tokens=self.max_tokens)
            toolkit = SQLDatabaseToolkit(db=db, llm=llm)
            agent_executor = create_sql_agent(
                prefix=MSSQL_AGENT_PREFIX,
                format_instructions = MSSQL_AGENT_FORMAT_INSTRUCTIONS,
                llm=llm,
                toolkit=toolkit,
                verbose=True
            )
            
            for i in range(5):
                try:
                    response = agent_executor.run(query) 
                    break
                except:
                    response = "Error too many failed retries"
                    continue
        
            return response
        
        except Exception as e:
            response = e
            print(e)
            return response
    
    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("SQLDbWrapper does not support async")
        
        
class ChatGPTWrapper(BaseTool):
    """Wrapper for a ChatGPT clone"""
    
    name = "ChatGPT Search"
    description = 'useful **ONLY** when you need to answer questions that begin with "Hey ChatGPT".\n'

    deployment_name: str = "gpt-35-turbo"
    max_tokens: int = 500
    temperature: float = 0.5
    
    def _run(self, query: str) -> str:
        try:
            llm = AzureChatOpenAI(deployment_name=self.deployment_name, temperature=self.temperature, max_tokens=self.max_tokens)
            chatgpt_chain = LLMChain(
                llm=llm, 
                prompt=CHATGPT_PROMPT, 
                verbose=False
            )

            response = chatgpt_chain.run(query)

            return response
        except Exception as e:
            print(e)
            
    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("ChatGPTWrapper does not support async")