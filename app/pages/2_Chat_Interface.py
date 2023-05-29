import os
import re
import streamlit as st
from streamlit_chat import message
from langchain.chat_models import AzureChatOpenAI
from langchain.utilities import BingSearchAPIWrapper
from langchain.memory import ConversationBufferWindowMemory
from langchain.agents import ConversationalChatAgent, AgentExecutor, Tool

#custom libraries that we will use later in the app
from utils import DocSearchWrapper, CSVTabularWrapper, SQLDbWrapper, ChatGPTWrapper
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

st.header("GPT Smart Search Engine - Chatbot")


with st.sidebar:
    st.markdown("""# Instructions""")
    st.markdown("""

This Chatbot has access tothe following tools/pluggins:
- Bing Search for Current Events
- ChatGPT for common knowledge
- Azure SQL for covid statistics data
- Azure Search for corporate knowledge (Arxiv papers and Covid Articles)

Example questions:
- Hello, my name is Bob, what's yours?
- What's the main economic news of today?
- How do I cook a chocolate cake?
- What medicine reduces inflammation in the lungs?
- Why Covid doesn't affect kids that much compared to adults?
- What are markov chains?
- How many people where hospitalized in Arkansas in June 2020?
- List the authors that talk about Boosting Algorithms
- How does random forest work?
- What kind of problems can I solve with reinforcement learning? Give me some real life examples
- What kind of problems Turing Machines solve?
- What are the main risk factors for Covid-19?
    
    """)


if (not os.environ.get("AZURE_SEARCH_ENDPOINT")) or (os.environ.get("AZURE_SEARCH_ENDPOINT") == ""):
    st.error("Please set your AZURE_SEARCH_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_SEARCH_KEY")) or (os.environ.get("AZURE_SEARCH_KEY") == ""):
    st.error("Please set your AZURE_SEARCH_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_OPENAI_ENDPOINT")) or (os.environ.get("AZURE_OPENAI_ENDPOINT") == ""):
    st.error("Please set your AZURE_OPENAI_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_OPENAI_API_KEY")) or (os.environ.get("AZURE_OPENAI_API_KEY") == ""):
    st.error("Please set your AZURE_OPENAI_API_KEY on your Web App Settings")
elif (not os.environ.get("BING_SUBSCRIPTION_KEY")) or (os.environ.get("BING_SUBSCRIPTION_KEY") == ""):
    st.error("Please set your BING_SUBSCRIPTION_KEY on your Web App Settings")
elif (not os.environ.get("DATASOURCE_SAS_TOKEN")) or (os.environ.get("DATASOURCE_SAS_TOKEN") == ""):
    st.error("Please set your DATASOURCE_SAS_TOKEN on your Web App Settings")
elif (not os.environ.get("SQL_SERVER_ENDPOINT")) or (os.environ.get("SQL_SERVER_ENDPOINT") == ""):
    st.error("Please set your SQL_SERVER_ENDPOINT on your Web App Settings")
elif (not os.environ.get("SQL_SERVER_DATABASE")) or (os.environ.get("SQL_SERVER_DATABASE") == ""):
    st.error("Please set your SQL_SERVER_DATABASE on your Web App Settings")
elif (not os.environ.get("SQL_SERVER_USERNAME")) or (os.environ.get("SQL_SERVER_USERNAME") == ""):
    st.error("Please set your SQL_SERVER_USERNAME on your Web App Settings")
elif (not os.environ.get("SQL_SERVER_PASSWORD")) or (os.environ.get("SQL_SERVER_PASSWORD") == ""):
    st.error("Please set your SQL_SERVER_PASSWORD on your Web App Settings")
    

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


    # Select a Deployment model name
    MODEL_DEPLOYMENT_NAME = "gpt-35-turbo"
    
    # Initialize our Tools/Experts
    doc_search = DocSearchWrapper(indexes=["cogsrch-index-files", "cogsrch-index-csv"],k=5, deployment_name=MODEL_DEPLOYMENT_NAME)
    www_search = BingSearchAPIWrapper(k=5)
    sql_search = SQLDbWrapper(k=30,deployment_name=MODEL_DEPLOYMENT_NAME)
    
    tools = [
        Tool(
            name = "Current events and news",
            func=www_search.run,
            description='useful to get current events information like weather, news, sports results, current movies.\n'
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
            description='useful only when you need to answer questions about Covid-19 or about Computer Science.\n',
            return_direct=True
        ),
    ]

    # Set main Agent
    llm = AzureChatOpenAI(deployment_name=MODEL_DEPLOYMENT_NAME, temperature=0.5, max_tokens=500)
    agent = ConversationalChatAgent.from_llm_and_tools(llm=llm, tools=tools, system_message=CUSTOM_CHATBOT_PREFIX, human_message=CUSTOM_CHATBOT_SUFFIX)
    agent_chain = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True, memory=st.session_state["memory"])
    

    col1, col2 = st.columns([6,1])
    with col1:
        query = st.text_input("Talk with your enterprise data lake", key="input", label_visibility="collapsed")
    with col2:
        st.button("New Topic", on_click = new_chat, type='primary')
    
    if query:
        with st.spinner("Thinking ... ⏳"):
            for i in range(3):
                try:
                    answer = agent_chain.run(input=query) 
                    break
                except:
                    answer = "Error too many failed retries"
                    continue
            

        # Append question and answer to memory
        st.session_state["past"].append(query)
        st.session_state["generated"].append(answer)

        
        for i in range(len(st.session_state["generated"]) - 1, -1, -1):
            message(st.session_state["generated"][i], key=str(i))
            message(st.session_state["past"][i], is_user=True, key=str(i) + "_user", 
                    avatar_style="lorelei-neutral", seed="Harley")




        


