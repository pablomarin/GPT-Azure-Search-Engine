import os
import random
from collections import OrderedDict
import streamlit as st
from streamlit_chat import message
from langchain.chains import ConversationChain
from langchain.chains.conversation.memory import ConversationEntityMemory
from langchain.chains.conversation.prompt import ENTITY_MEMORY_CONVERSATION_TEMPLATE
from langchain.chat_models import AzureChatOpenAI



# From here down is all the StreamLit UI.
st.set_page_config(page_title="LangChain Demo", page_icon=":robot:", layout='wide')

AZURE_OPENAI_API_VERSION = "2023-03-15-preview"

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
        save = []
        for i in range(len(st.session_state['generated'])-1, -1, -1):
            save.append("User:" + st.session_state["past"][i])
            save.append("Bot:" + st.session_state["generated"][i])        
        st.session_state["stored_session"].append(save)
        st.session_state["generated"] = []
        st.session_state["past"] = []
        st.session_state["input"] = ""
        st.session_state["entity_memory"].entity_store.clear()
        st.session_state["entity_memory"].buffer.clear()

    # Set up sidebar with various options
    with st.sidebar:
        MODEL = st.selectbox(label='Model', options=['gpt-35-turbo','gpt-4'])
        K = st.number_input(' (#)Summary of prompts to consider', min_value=3, max_value=1000)


    # Create an OpenAI instance
    llm = AzureChatOpenAI(deployment_name=MODEL, temperature=0.5)


    # Create a ConversationEntityMemory object if not already created
    if "entity_memory" not in st.session_state:
            st.session_state["entity_memory"] = ConversationEntityMemory(llm=llm, k=K )

    # Create the ConversationChain object with the specified configuration
    chain = ConversationChain(
            llm=llm, 
            prompt=ENTITY_MEMORY_CONVERSATION_TEMPLATE,
            memory=st.session_state["entity_memory"]
        )  



    # Add a button to start a new chat
    st.sidebar.button("New Chat", on_click = new_chat, type='primary')


    def get_text():
        input_text = st.text_input("You: ", key="input")
        return input_text


    query = get_text()

    if query:
                  
        output = chain.predict(input=query)

        st.session_state["past"].append(query)
        st.session_state["generated"].append(output) 


        if st.session_state["generated"]:

            for i in range(len(st.session_state["generated"]) - 1, -1, -1):
                message(st.session_state["generated"][i], key=str(i))
                message(st.session_state["past"][i], is_user=True, key=str(i) + "_user")

        
        


