import re
from io import BytesIO
from typing import Any, Dict, List

import docx2txt
import streamlit as st
from embeddings import OpenAIEmbeddings
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.chains.question_answering import load_qa_chain
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.docstore.document import Document
from langchain.llms import AzureOpenAI
from langchain.chat_models import AzureChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import VectorStore
from langchain.vectorstores.faiss import FAISS
from openai.error import AuthenticationError
from prompts import STUFF_PROMPT, REFINE_PROMPT, REFINE_QUESTION_PROMPT
from pypdf import PdfReader
import tiktoken


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
def embed_docs(docs: List[Document], language: str) -> VectorStore:
    """Embeds a list of Documents and returns a FAISS index"""
 
    # Select the Embedder model
    if len(docs) < 50:
        # OpenAI models are accurate but slower
        embedder = OpenAIEmbeddings(document_model_name="text-embedding-ada-002", query_model_name="text-embedding-ada-002") 
    else:
        # Bert based models are faster (3x-10x) but not as accurate
        # For Multiple language support we need to use a multilingual model. But if English only is the requirement, use "multi-qa-MiniLM-L6-cos-v1" for a good trade-off between quality and speed
        # The fastest english model though is "all-MiniLM-L12-v2"
        if language == "en":
            embedder = HuggingFaceEmbeddings(model_name = 'all-MiniLM-L12-v2')
        else:
            embedder = HuggingFaceEmbeddings(model_name = 'distiluse-base-multilingual-cased-v2')

    index = FAISS.from_documents(docs, embedder)

    return index


# @st.cache_data
def search_docs(index: VectorStore, query: str) -> List[Document]:
    """Searches a FAISS index for similar chunks to the query
    and returns a list of Documents."""

    # Search for similar chunks
    docs = index.similarity_search(query, k=4)
    return docs


# @st.cache_data
def get_answer(docs: List[Document], 
               query: str, 
               deployment: str, 
               chain_type: str, 
               temperature: float, 
               max_tokens: int
              ) -> Dict[str, Any]:
    
    """Gets an answer to a question from a list of Documents."""

    # Get the answer
    
    if (deployment in ["gpt-35-turbo", "gpt-4", "gpt-4-32k"]) :
        llm = AzureChatOpenAI(deployment_name=deployment, temperature=temperature, max_tokens=max_tokens)
    else:
        llm = AzureOpenAI(deployment_name=deployment, temperature=temperature, max_tokens=max_tokens)
    
    chain = load_qa_with_sources_chain(llm, chain_type=chain_type)
    
    answer = chain( {"input_documents": docs, "question": query}, return_only_outputs=True)
    #answer = chain( {"input_documents": docs, "question": query, "language": language}, return_only_outputs=True)

    return answer



# @st.cache_data
def get_sources(answer: Dict[str, Any], docs: List[Document]) -> List[Document]:
    """Gets the source documents for an answer."""

    # Get sources for the answer
    source_keys = [s for s in answer["output_text"].split("SOURCES: ")[-1].split(", ")]

    source_docs = []
    for doc in docs:
        if doc.metadata["source"] in source_keys:
            source_docs.append(doc)

    return source_docs


def wrap_text_in_html(text: str | List[str]) -> str:
    """Wraps each text block separated by newlines in <p> tags"""
    if isinstance(text, list):
        # Add horizontal rules between pages
        text = "\n<hr/>\n".join(text)
    return "".join([f"<p>{line}</p>" for line in text.split("\n")])

# defining the token count function
def num_tokens_from_string(string: str, encoding_name: str) -> int:
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
