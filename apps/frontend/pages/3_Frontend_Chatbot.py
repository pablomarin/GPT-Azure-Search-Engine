import os
import re
import streamlit as st
from streamlit_chat import message
import langchain
from langchain.chat_models import AzureChatOpenAI
from langchain.utilities import BingSearchAPIWrapper
from langchain.memory import ConversationBufferWindowMemory
from langchain.agents import ConversationalChatAgent, AgentExecutor, Tool
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.manager import CallbackManager
import sys
from callbacks import StdOutCallbackHandler
from utils import DocSearchWrapper, DocSearchTool, CSVTabularWrapper, SQLDbWrapper, ChatGPTWrapper, run_agent
from prompts import CUSTOM_CHATBOT_PREFIX, CUSTOM_CHATBOT_SUFFIX


# From here down is all the StreamLit UI.
st.set_page_config(page_title="GPT Smart Search", page_icon="📖", layout="wide")
# Add custom CSS styles to adjust padding
st.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                }
        </style>
        """, unsafe_allow_html=True)

st.header("GPT Smart Search Engine - Frontend Chatbot")


with st.sidebar:
    st.markdown("""# Instructions""")
    st.markdown("""

This Chatbot is running in the frontend application. It has access to the following tools/pluggins:

- Bing Search (***use @bing in your question***)
- ChatGPT for common knowledge (***use @chatgpt in your question***)
- Azure SQL for covid statistics data (***use @covidstats in your question***)
- Azure Search for documents knowledge - Arxiv papers and Covid Articles (***use @docsearch in your question***)
- Azure Search for books knowledge - 5 PDF books (***use @booksearch in your question***)

Note: If you don't use any of the tool names beginning with @, the bot will try to use it's own knowledge or tool available to answer the question.

Example questions:

- Hello, my name is Bob, what's yours?
- @bing, What's the main economic news of today?
- @chatgpt, How do I cook a chocolate cake?
- @booksearch, what normally rich dad do that is different from poor dad?
- @docsearch, What medicine reduces inflammation in the lungs?
- @docsearch, Why Covid doesn't affect kids that much compared to adults?
- What are markov chains?
- @covidstats, How many people where hospitalized in Arkansas in June 2020?
- @docsearch, List the authors that talk about Boosting Algorithms
- @booksearch, Tell me a summary of the book Boundaries
- @chatgpt, how do I fix this error: aiohttp.web_exceptions.HTTPNotFound: Not Found
- @bing, what movies are showing tonight in Seattle?
- @docsearch, What are the main risk factors for Covid-19?
- Please tell me a joke
    """)

if (not os.environ.get("AZURE_SEARCH_ENDPOINT")) or (os.environ.get("AZURE_SEARCH_ENDPOINT") == ""):
    st.error("Please set your AZURE_SEARCH_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_SEARCH_KEY")) or (os.environ.get("AZURE_SEARCH_KEY") == ""):
    st.error("Please set your AZURE_SEARCH_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_OPENAI_ENDPOINT")) or (os.environ.get("AZURE_OPENAI_ENDPOINT") == ""):
    st.error("Please set your AZURE_OPENAI_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_OPENAI_API_KEY")) or (os.environ.get("AZURE_OPENAI_API_KEY") == ""):
    st.error("Please set your AZURE_OPENAI_API_KEY on your Web App Settings")
elif (not os.environ.get("BLOB_SAS_TOKEN")) or (os.environ.get("BLOB_SAS_TOKEN") == ""):
    st.error("Please set your BLOB_SAS_TOKEN on your Web App Settings")
else: 

    # Don't mess with this unless you really know what you are doing
    AZURE_SEARCH_API_VERSION = '2021-04-30-Preview'
    AZURE_OPENAI_API_VERSION = "2023-03-15-preview"
    BING_SEARCH_URL = "https://api.bing.microsoft.com/v7.0/search"

    os.environ["OPENAI_API_BASE"] = os.environ.get("AZURE_OPENAI_ENDPOINT")
    os.environ["OPENAI_API_KEY"] = os.environ.get("AZURE_OPENAI_API_KEY")
    os.environ["OPENAI_API_VERSION"] = os.environ["AZURE_OPENAI_API_VERSION"] = AZURE_OPENAI_API_VERSION
    os.environ["OPENAI_API_TYPE"] = "azure"
    os.environ["BING_SEARCH_URL"] =  BING_SEARCH_URL

    DATASOURCE_SAS_TOKEN = os.environ['BLOB_SAS_TOKEN']

    index1_name = "cogsrch-index-files"
    index2_name = "cogsrch-index-csv"
    text_indexes = [index1_name, index2_name]
    vector_indexes = [index+"-vector" for index in text_indexes]
    # Initialize session states
    if "generated" not in st.session_state:
        st.session_state["generated"] = []
    if "past" not in st.session_state:
        st.session_state["past"] = []
    if "docs" not in st.session_state:
        st.session_state["docs"] = []
    if "input" not in st.session_state:
        st.session_state["input"] = ""
    if "memory" not in st.session_state:
        st.session_state["memory"] = ConversationBufferWindowMemory(memory_key="chat_history", return_messages=True, k=10)

    # Define function to start a new chat
    def new_chat():
        """
        Clears session state and starts a new chat.
        """        
        st.session_state["generated"] = []
        st.session_state["past"] = []
        st.session_state["docs"] = []
        st.session_state["input"] = ""
        st.session_state["memory"] = ConversationBufferWindowMemory(memory_key="chat_history", return_messages=True, k=10)

    MODEL = os.environ.get("AZURE_OPENAI_MODEL_NAME")


    cb_handler = StdOutCallbackHandler()
    cb_manager = CallbackManager(handlers=[cb_handler])

    # Initialize our Tools/Experts
    www_search = BingSearchAPIWrapper(k=5)
    sql_search = SQLDbWrapper(k=30,deployment_name=MODEL)
  
    llm = AzureChatOpenAI(deployment_name=MODEL, temperature=0.5, max_tokens=500)
    doc_search = DocSearchTool(
        llm=llm,
        indexes=text_indexes,
        k=10, similarity_k=4, reranker_th=0,
        sas_token=DATASOURCE_SAS_TOKEN,
        callback_manager=cb_manager, 
        return_direct=True)

    tools = [doc_search, www_search, sql_search]
    
    # Set main Agent
    llm_a = AzureChatOpenAI(deployment_name=MODEL, temperature=0.5, max_tokens=500)
    agent = ConversationalChatAgent.from_llm_and_tools(llm=llm_a, tools=tools, 
        system_message=CUSTOM_CHATBOT_PREFIX, human_message=CUSTOM_CHATBOT_SUFFIX)
    agent_chain = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools,memory=st.session_state["memory"])


    col1, col2 = st.columns([6,1])
    with col1:
        query = st.text_input("Talk with your enterprise data lake", key="input", label_visibility="collapsed")
    with col2:
        st.button("New Topic", on_click = new_chat, type='primary')

    if query:
        with st.spinner("Thinking ... ⏳"):
            for i in range(3):
                try:
                    query = query 
                    answer = run_agent(query, agent_chain)
                    break
                except Exception as e:
                    answer = "Error too many failed retries: "+str(e)
                    continue


        # Append question and answer to memory
        st.session_state["past"].append(query)
        st.session_state["generated"].append(answer)


        for i in range(len(st.session_state["generated"]) - 1, -1, -1):
            message(st.session_state["generated"][i], key=str(i))
            message(st.session_state["past"][i], is_user=True, key=str(i) + "_user", 
                    avatar_style="lorelei-neutral", seed="Harley")

