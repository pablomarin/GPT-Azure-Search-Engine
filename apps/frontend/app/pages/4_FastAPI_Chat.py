import os
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import AzureChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langserve import RemoteRunnable
import uuid
import requests
import json
import sys
import time
import random

# Env variables needed by langchain
os.environ["OPENAI_API_VERSION"] = os.environ.get("AZURE_OPENAI_API_VERSION")

# app config
st.set_page_config(page_title="FastAPI Backend Bot", page_icon="🤖", layout="wide")

with st.sidebar:
    st.markdown("""# Instructions""")
    st.markdown("""

This Chatbot is hosted in an independent Backend Azure Web App and was created using the Bot Framework SDK.
The Bot Interface is just a window to a Bot Service app hosted in Azure.

It has access to the following tools/pluggins:

- Bing Search (***use @bing in your question***)
- ChatGPT for common knowledge (***use @chatgpt in your question***)
- Azure SQL for covid statistics data (***use @sqlsearch in your question***)
- Azure Search for documents knowledge - Arxiv papers and Covid Articles (***use @docsearch in your question***)
- Azure Search for books knowledge - 5 PDF books (***use @booksearch in your question***)
- API Search for real-time covid statistics for US States, Countries and Continents (***use @apisearch in your question***)

Note: If you don't use any of the tool names beginning with @, the bot will try to use it's own knowledge or tool available to answer the question.

Example questions:

- Hello, my name is Bob, what's yours?
- bing, What's the main economic news of today?
- chatgpt, How do I cook a chocolate cake?
- booksearch, what normally rich dad do that is different from poor dad?
- docsearch, Why Covid doesn't affect kids that much compared to adults?
- sqlsearch, How many people where hospitalized in Arkansas in June 2020?
- docsearch, List the authors that talk about Boosting Algorithms
- bing, what movies are showing tonight in Seattle?
- Please tell me a joke
    """)

st.markdown("""
        <style>
               .block-container {
                    padding-top: 2rem;
                    padding-bottom: 0rem;
                }
        </style>
        """, unsafe_allow_html=True)


# ENTER HERE YOUR LANGSERVE FASTAPI ENDPOINT
# for example: "https://webapp-backend-botid-zf4fwhz3gdn64-staging.azurewebsites.net"

url = "https://<name-of-backend-app-service>-staging.azurewebsites.net" + "/agent/stream_events"

def get_or_create_ids():
    """Generate or retrieve session and user IDs."""
    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = str(uuid.uuid4())
    if 'user_id' not in st.session_state:
        st.session_state['user_id'] = str(uuid.uuid4())
    return st.session_state['session_id'], st.session_state['user_id']

    
def consume_api(url, user_query, session_id, user_id):
    """Uses requests POST to talk to the FastAPI backend, supports streaming."""
    headers = {'Content-Type': 'application/json'}
    config = {"configurable": {"session_id": session_id, "user_id": user_id}}
    payload = {'input': {"question": user_query}, 'config': config}
    
    with requests.post(url, json=payload, headers=headers, stream=True) as response:
        try:
            response.raise_for_status()  # Raises an HTTPError if the response is not 200.
            for line in response.iter_lines():
                if line:  # Check if the line is not empty.
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        # Extract JSON data following 'data: '.
                        json_data = decoded_line[len('data: '):]
                        try:
                            data = json.loads(json_data)
                            if "event" in data:
                                kind = data["event"]
                                if kind == "on_chat_model_stream":
                                    content = data["data"]["chunk"]["content"]
                                    if content:  # Ensure content is not None or empty.
                                        yield content  # Two newlines for a paragraph break in Markdown.
                                elif kind == "on_tool_start":
                                        tool_inputs = data['data'].get('input')
                                        if isinstance(tool_inputs, dict):
                                            # Joining the dictionary into a string format key: 'value'
                                            inputs_str = ", ".join(f"'{v}'" for k, v in tool_inputs.items())
                                        else:
                                            # Fallback if it's not a dictionary or in an unexpected format
                                            inputs_str = str(tool_inputs)
                                        yield f"Searching Tool: {data['name']} with input: {inputs_str} ⏳\n\n"
                                elif kind == "on_tool_end":
                                        yield "Search completed.\n\n"
                            elif "content" in data:
                                # If there is immediate content to print, with added Markdown for line breaks.
                                yield f"{data['content']}\n\n"
                            elif "steps" in data:
                                yield f"{data['steps']}\n\n"
                            elif "output" in data:
                                yield f"{data['output']}\n\n"
                        except json.JSONDecodeError as e:
                            yield f"JSON decoding error: {e}\n\n"
                    elif decoded_line.startswith('event: '):
                        pass
                    elif ": ping" in decoded_line:
                        pass
                    else:
                        yield f"{decoded_line}\n\n"  # Adding line breaks for plain text lines.
        except requests.exceptions.HTTPError as err:
            yield f"HTTP Error: {err}\n\n"
        except Exception as e:
            yield f"An error occurred: {e}\n\n"


# session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [AIMessage(content="Hello, I am a GPT-4o bot hosted in Azure using FastAPI Streaming. How can I help you?")]

    
# conversation
for message in st.session_state.chat_history:
    if isinstance(message, AIMessage):
        with st.chat_message("AI"):
            st.write(message.content)
    elif isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.write(message.content)

# user input

session_id, user_id = get_or_create_ids()

user_query = st.chat_input("Type your message here...")

if user_query is not None and user_query != "":
    st.session_state.chat_history.append(HumanMessage(content=user_query))

    with st.chat_message("Human"):
        st.markdown(user_query)

    with st.chat_message("AI"):
        with st.spinner(text=""):
            response = st.write_stream(consume_api(url, user_query, session_id, user_id))

    st.session_state.chat_history.append(AIMessage(content=response))