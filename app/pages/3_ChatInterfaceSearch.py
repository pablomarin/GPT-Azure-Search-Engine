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
st.set_page_config(page_title="LangChain Demo", page_icon=":robot:", layout='wide')

AZURE_OPENAI_API_VERSION = "2023-03-15-preview"
# setting encoding for GPT3.5 / GPT4 models
encoding_name ='cl100k_base'
CHAT_HISTORY = []

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
    if "input" not in st.session_state:
        st.session_state["input"] = ""
    if "stored_session" not in st.session_state:
        st.session_state["stored_session"] = []


    # Define function to start a new chat
    def new_chat():
        """
        Clears session state and starts a new chat.
        """        
        st.session_state["generated"] = []
        st.session_state["past"] = []
        st.session_state["input"] = ""
        # st.session_state.entity_memory.entity_store.clear()
        # st.session_state.entity_memory.buffer.clear()
        CHAT_HISTORY = []

    # Set up sidebar with various options
    with st.sidebar:
        MODEL = st.selectbox(label='Model', options=['gpt-35-turbo','gpt-4'])
        K = st.number_input(' (#)Summary of prompts to consider',min_value=3,max_value=1000)


    # Create an OpenAI instance
    llm = AzureChatOpenAI(deployment_name=MODEL, temperature=0)


    # Create a ConversationEntityMemory object if not already created
    if 'entity_memory' not in st.session_state:
            #st.session_state.entity_memory = ConversationEntityMemory(llm=llm, k=K )
            st.session_state.entity_memory = ConversationBufferMemory()

    # Create the ConversationChain object with the specified configuration
    # chain = ConversationChain(
    #         llm=llm, 
    #         prompt=ENTITY_MEMORY_CONVERSATION_TEMPLATE,
    #         memory=st.session_state.entity_memory
    #     )  



    # Add a button to start a new chat
    st.sidebar.button("New Chat", on_click = new_chat, type='primary')


    def get_text():
        input_text = st.text_input("You: ", key="input")
        return input_text


    query = get_text()

    if query:
        
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

        #After results have been filtered we will Sort and add them as an Ordered list
        for id in sorted(content, key= lambda x: content[x]["score"], reverse=True):
            file_content[id] = content[id]
        
        
        if "file_content" in locals():
            try:
                docs = []
                for key,value in file_content.items():
                    docs.append(Document(page_content=value['caption'], metadata={"source": value["location"]}))
                    add_text = "Searching... ⏳"

                if "add_text" in locals():
                    with st.spinner(add_text):
                        if(len(docs)>0):                          
                            language = random.choice(list(file_content.items()))[1]["language"]
                            index = embed_docs(docs, language)
                            answer = get_answer_with_memory(query, index, CHAT_HISTORY, deployment="gpt-35-turbo", chain_type = "stuff", temperature=0.5, max_tokens=500)

                        else:
                            answer = "No results found"
                else:
                    answer = "No results found"
                    
               
                #output = chain.predict(input=user_input)

                st.session_state.past.append(query)
                st.session_state.generated.append(answer) 
                

                if st.session_state["generated"]:
                    print(st.session_state.generated)

                    for i in range(len(st.session_state["generated"]) - 1, -1, -1):
                        message(st.session_state["generated"][i], key=str(i))
                        message(st.session_state["past"][i], is_user=True, key=str(i) + "_user")
                        
                    for i in range(len(st.session_state['generated'])-1, -1, -1):
                        CHAT_HISTORY.append("Human:" + st.session_state["past"][i])
                        CHAT_HISTORY.append("AI:" + st.session_state["generated"][i])

            except OpenAIError as e:
                    st.error(e)
        
        


