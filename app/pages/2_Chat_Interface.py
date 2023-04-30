import os
import random
from collections import OrderedDict
import streamlit as st
from streamlit_chat import message
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.chains.conversation.prompt import ENTITY_MEMORY_CONVERSATION_TEMPLATE
from langchain.chat_models import AzureChatOpenAI
from openai.error import OpenAIError
from langchain.docstore.document import Document
from prompts import CSV_PROMPT_PREFIX, CSV_PROMPT_SUFFIX


from utils import (
    get_search_results,
    order_search_results,
    model_tokens_limit,
    num_tokens_from_docs,
    embed_docs,
    search_docs,
    get_answer,
)

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


AZURE_OPENAI_API_VERSION = "2023-03-15-preview"
# setting encoding for GPT3.5 / GPT4 models
MODEL = "gpt-35-turbo"
tokens_limit = model_tokens_limit(MODEL)

with st.sidebar:
    st.markdown("""# Instructions""")
    st.markdown("""
You can select if you want to talk to your documents only or to ChatGPT. 
***The memory is shared between both usage modes.***

Example questions:
- What are markov chains?
- List the authors that talk about Boosting Algorithms
- How does random forest work?
- What kind of problems can I solve with reinforcement learning? Give me some real life examples
- What kind of problems Turing Machines solve?
- What are the main risk factors for Covid-19?
- What medicine reduces inflammation in the lungs?
- Why Covid doesn't affect kids that much compared to adults?
    
    """)


if (not os.environ.get("AZURE_SEARCH_ENDPOINT")) or (os.environ.get("AZURE_SEARCH_ENDPOINT") == ""):
    st.error("Please set your AZURE_SEARCH_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_SEARCH_KEY")) or (os.environ.get("AZURE_SEARCH_KEY") == ""):
    st.error("Please set your AZURE_SEARCH_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_OPENAI_ENDPOINT")) or (os.environ.get("AZURE_OPENAI_ENDPOINT") == ""):
    st.error("Please set your AZURE_OPENAI_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_OPENAI_API_KEY")) or (os.environ.get("AZURE_OPENAI_API_KEY") == ""):
    st.error("Please set your AZURE_OPENAI_API_KEY on your Web App Settings")

else: 
    os.environ["OPENAI_API_BASE"] = os.environ.get("AZURE_OPENAI_ENDPOINT")
    os.environ["OPENAI_API_KEY"] = os.environ.get("AZURE_OPENAI_API_KEY")
    os.environ["OPENAI_API_VERSION"] = os.environ["AZURE_OPENAI_API_VERSION"] = AZURE_OPENAI_API_VERSION
    os.environ["OPENAI_API_TYPE"] = "azure"


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
        st.session_state["memory"] = ConversationBufferMemory(memory_key="chat_history",input_key="question")

    # Define function to start a new chat
    def new_chat():
        """
        Clears session state and starts a new chat.
        """        
        st.session_state["generated"] = []
        st.session_state["past"] = []
        st.session_state["docs"] = []
        st.session_state["input"] = ""
        st.session_state["memory"] = ConversationBufferMemory(memory_key="chat_history",input_key="question")


    # Create an OpenAI instance
    llm = AzureChatOpenAI(deployment_name=MODEL, temperature=0)
    
    
    coli1, coli2, coli3 = st.columns([3,1,1])
    with coli1:
        mode = st.radio("Usage Mode",('Corporate Documents Knowledge', 'ChatGPT Knowledge'))
    with coli2:
        language= st.selectbox('Chat language',('English', 'Spanish', 'French', 'German', 'Portuguese', 'Italian'), index=0)
    with coli3:
        K = st.number_input('Memory size (msgs)',min_value=5,max_value=1000)
        

    col1, col2 = st.columns([6,1])
    with col1:
        query = st.text_input("Talk with your enterprise data lake", key="input", label_visibility="collapsed")
    with col2:
        st.button("New Topic", on_click = new_chat, type='primary')
    
    if query:
        open_chain = ConversationChain(llm=llm)
    
        if mode == 'ChatGPT Knowledge':
            answer = open_chain.run(query)
        else:
            try:
                index1_name = "cogsrch-index-files"
                index2_name = "cogsrch-index-csv"
                indexes = [index1_name, index2_name]
                
                agg_search_results = get_search_results(query, indexes)
                ordered_results = order_search_results(agg_search_results, reranker_threshold=1)
                
            except:
                st.markdown("Not data returned from Azure Search, check connection..")
                st.stop()

            try:
                
                if len(st.session_state["docs"]) == 0 :
                    with st.spinner("Searching in corporate documents... ⏳"):
                        for key,value in ordered_results.items():
                            for page in value["chunks"]:
                                    st.session_state["docs"].append(Document(page_content=page, metadata={"source": value["name"]}))
                        num_tokens = num_tokens_from_docs(st.session_state["docs"])

                        if num_tokens > tokens_limit:
                            index = embed_docs(st.session_state["docs"])
                            top_docs = search_docs(index,query)
                            num_tokens = num_tokens_from_docs(top_docs)
                            chain_type = "map_reduce" if num_tokens > tokens_limit else "stuff"
                        else:
                            top_docs = st.session_state["docs"]
                            chain_type = "stuff"

                        answer = get_answer(top_docs, query, language=language, deployment=MODEL, chain_type = chain_type, memory=st.session_state["memory"])["output_text"]

                elif len(st.session_state["docs"]) > 0:
                    num_tokens = num_tokens_from_docs(st.session_state["docs"])
                    if num_tokens > tokens_limit:
                        index = embed_docs(st.session_state["docs"])
                        top_docs = search_docs(index,query)
                        num_tokens = num_tokens_from_docs(top_docs)
                        chain_type = "map_reduce" if num_tokens > tokens_limit else "stuff"
                    else:
                        top_docs = st.session_state["docs"]
                        chain_type = "stuff"

                    answer = get_answer(top_docs, query, language=language, deployment=MODEL, chain_type = chain_type, memory=st.session_state["memory"])["output_text"]
                else:
                    answer = "Results Not Found"

            
            except OpenAIError as e:
                    st.error(e)


        # Append question and answer to memory
        st.session_state["past"].append(query)
        try:
            st.session_state["generated"].append(answer.split("SOURCES:")[0])
        except:
            st.session_state["generated"].append(answer.split("Sources:")[0])

        
        for i in range(len(st.session_state["generated"]) - 1, -1, -1):
            message(st.session_state["generated"][i], key=str(i))
            message(st.session_state["past"][i], is_user=True, key=str(i) + "_user", 
                    avatar_style="lorelei-neutral", seed="Harley")




        


