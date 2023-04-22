import os
import random
from collections import OrderedDict
import streamlit as st
from streamlit_chat import message
from langchain.chains import ConversationChain
from langchain.chains.conversation.memory import ConversationEntityMemory
from langchain.memory import ConversationBufferMemory
from langchain.chains.conversation.prompt import ENTITY_MEMORY_CONVERSATION_TEMPLATE
from langchain.chat_models import AzureChatOpenAI
from openai.error import OpenAIError
from langchain.docstore.document import Document

from utils import (
    get_search_results,
    embed_docs,
    get_answer_with_memory,
    get_sources,
    search_docs,
    num_tokens_from_string,
    model_tokens_limit
)

# From here down is all the StreamLit UI.
st.set_page_config(page_title="GPT Smart Search", page_icon="📖", layout="wide")
st.header("GPT Smart Search Engine - Chat Bot Style")

AZURE_OPENAI_API_VERSION = "2023-03-15-preview"
# setting encoding for GPT3.5 / GPT4 models
encoding_name ='cl100k_base'

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


    # Initialize session states
    if "generated" not in st.session_state:
        st.session_state["generated"] = []
    if "past" not in st.session_state:
        st.session_state["past"] = []
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "docs" not in st.session_state:
        st.session_state["docs"] = []
    if "input" not in st.session_state:
        st.session_state["input"] = ""
    if "memory" not in st.session_state:
        st.session_state["memory"] = ConversationBufferMemory()

    # Define function to start a new chat
    def new_chat():
        """
        Clears session state and starts a new chat.
        """        
        st.session_state["generated"] = []
        st.session_state["past"] = []
        st.session_state["chat_history"] = []
        st.session_state["input"] = ""
        st.session_state["memory"] = ConversationBufferMemory()

    # Set up sidebar with various options
    with st.sidebar:
        MODEL = st.selectbox(label='Model', options=['gpt-35-turbo','gpt-4'])
        K = st.number_input(' No. Messages to remember',min_value=3,max_value=1000)
        mode = st.radio("Usage Mode",('Corporate Documents Knowledge', 'ChatGPT Knowledge'))
            


    # Create an OpenAI instance
    llm = AzureChatOpenAI(deployment_name=MODEL, temperature=0)

    # Add a button to start a new chat
    st.sidebar.button("New Chat", on_click = new_chat, type='primary')

    query = st.text_input("You: ", key="input")
    
    if query:
        question_assesser = ConversationChain(llm=llm)
        open_chain = ConversationChain(llm=llm, memory=st.session_state["memory"])
        is_question = question_assesser.predict(input='If the prhase "' + query + '" is a considered grammatically a Question,  then respond only with the word:"yes", if not respond only with the word: "No". No more words in your response.')
        
        print("is_question", is_question)
    
        if ("No" in is_question ) or (mode == 'ChatGPT Knowledge'):
            answer = open_chain.run(query)
            answer = open_chain.run(query)

        else:

            index1_name = "cogsrch-index-files"
            index2_name = "cogsrch-index-csv"
            indexes = [index1_name, index2_name]

            agg_search_results = get_search_results(query, indexes)

            file_content = OrderedDict()
            content = dict()

            try:
                for search_results in agg_search_results:
                    for result in search_results['value']:
                        if result['@search.rerankerScore'] > 1: # Show results that are at least 25% of the max possible score=4
                            content[result['id']]={
                                                    "title": result['title'],
                                                    "chunks": result['pages'],
                                                    "language": result['language'],
                                                    "caption": result['@search.captions'][0]['text'],
                                                    "score": result['@search.rerankerScore'],
                                                    "location": result['metadata_storage_path']                  
                                                }
            except:
                st.markdown("Not data returned from Azure Search, check connection..")
                st.stop()

            #After results have been filtered we will Sort and add them as an Ordered list
            for id in sorted(content, key= lambda x: content[x]["score"], reverse=True):
                file_content[id] = content[id]


            try:
                with st.spinner("Searching in corporate documents... ⏳"):
                    if len(file_content) > 0:
                        for key,value in file_content.items():
                            # st.session_state["docs"].append(Document(page_content=value['chunks'], metadata={"source": value["location"]}))
                            for page in value["chunks"]:
                                    st.session_state["docs"].append(Document(page_content=page, metadata={"source": value["location"]}))

                        language = random.choice(list(file_content.items()))[1]["language"]
                        index = embed_docs(st.session_state["docs"], language)
                        answer = get_answer_with_memory(query, index, 
                                                        st.session_state["chat_history"], 
                                                        deployment="gpt-35-turbo", 
                                                        chain_type = "stuff", 
                                                        temperature=0.5, 
                                                        max_tokens=500)

                    elif len(st.session_state["docs"]) > 0:
                        index = embed_docs(st.session_state["docs"], "en")
                        answer = get_answer_with_memory(query, index, 
                                                        st.session_state["chat_history"], 
                                                        deployment="gpt-35-turbo", 
                                                        chain_type = "stuff", 
                                                        temperature=0.5, 
                                                        max_tokens=500)
                    else:
                        answer = "Results Not Found"

            
            except OpenAIError as e:
                    st.error(e)

        st.session_state["past"].append(query)
        st.session_state["generated"].append(answer) 
        st.session_state["memory"].chat_memory.add_user_message(query)
        st.session_state["memory"].chat_memory.add_ai_message(answer)

        
        for i in range(len(st.session_state["generated"]) - 1, -1, -1):
            message(st.session_state["generated"][i], key=str(i))
            message(st.session_state["past"][i], is_user=True, key=str(i) + "_user", 
                    avatar_style="lorelei-neutral", seed="Harley")

        for i in range(len(st.session_state['generated'])-1, -1, -1):
            st.session_state["chat_history"].append(("Human:" + st.session_state["past"][i],"AI:" + st.session_state["generated"][i]))



        


