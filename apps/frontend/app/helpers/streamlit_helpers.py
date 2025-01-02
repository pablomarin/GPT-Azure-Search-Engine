# app/helpers/streamlit_helpers.py

import json
import uuid
import os

import requests
import streamlit as st
from sseclient import SSEClient  # Import SSEClient from sseclient-py
from langchain_core.messages import AIMessage, HumanMessage
from langchain import hub

try:
    from common.prompts import WELCOME_MESSAGE
except Exception as e:
    from ..common.prompts import WELCOME_MESSAGE
    

def get_logger(name):
    """
    Retrieve a Streamlit logger instance.

    :param name: The name for the logger
    :return: Logger instance
    """
    from streamlit.logger import get_logger
    return get_logger(name)

logger = get_logger(__name__)

def configure_page(title, icon):
    """
    Configure the Streamlit page settings: page title, icon, and layout.
    Also applies minimal styling for spacing.

    :param title: The title of the page
    :param icon: The favicon/icon for the page
    """
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 2rem;
                padding-bottom: 0rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

def get_or_create_ids():
    """
    Generate or retrieve session and user IDs from Streamlit's session_state.

    :return: (session_id, user_id)
    """
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
        logger.info("Created new session_id: %s", st.session_state["session_id"])
    else:
        logger.info("Found existing session_id: %s", st.session_state["session_id"])

    if "user_id" not in st.session_state:
        st.session_state["user_id"] = str(uuid.uuid4())
        logger.info("Created new user_id: %s", st.session_state["user_id"])
    else:
        logger.info("Found existing user_id: %s", st.session_state["user_id"])

    return st.session_state["session_id"], st.session_state["user_id"]

def consume_api(url, user_query, session_id, user_id):
    """
    Send a POST request to the FastAPI backend at `url` (the SSE /stream endpoint),
    and consume the SSE stream using sseclient-py.

    The server is expected to return events like:
        {"event": "partial", "data": "..."}
        {"event": "end", "data": "..."}
        {"event": "tool_start", "data": "..."}
        {"event": "tool_end", "data": "..."}
        {"event": "error", "data": "some error text"}

    This function yields text chunks (e.g., partial content) as they arrive.

    :param url: SSE /stream endpoint
    :param user_query: The user query text to send
    :param session_id: A unique ID representing the conversation
    :param user_id: The user ID (not strictly used in this minimal example)
    :yield: Text chunks that Streamlit can display incrementally
    """
    headers = {"Content-Type": "application/json"}
    payload = {
        "user_input": user_query,
        "thread_id": session_id  # Typically reusing session_id as conversation ID
    }

    logger.info(
        "Sending SSE request to %s with session_id=%s, user_id=%s",
        url, session_id, user_id
    )
    logger.debug("Payload: %s", payload)

    try:
        with requests.post(url, json=payload, headers=headers, stream=True) as resp:
            resp.raise_for_status()
            logger.info("SSE stream opened successfully with status code %d.", resp.status_code)

            # Use SSEClient to parse the stream
            client = SSEClient(resp)
            for event in client.events():
                if not event.data.strip():
                    # Skip keep-alive messages or empty lines
                    continue

                evt_type = event.event
                evt_data = event.data
                logger.debug("Received SSE event: %s, data: %s", evt_type, evt_data)

                # Switch on event type from the server
                if evt_type == "partial":
                    # Yield partial text; can be streamed in real-time
                    yield evt_data
                
                elif evt_type == "tool_start":
                    # Display tool start
                    # e.g. [Tool Start] Starting documents_retrieval
                    # yield f"\n[Tool Start] {evt_data}\n"
                    pass

                elif evt_type == "tool_end":
                    # Display tool end
                    # e.g. [Tool End] Done documents_retrieval
                    # yield f"\n[Tool End] {evt_data}\n"
                    pass
                    
                elif evt_type == "end":
                    # Yield final accumulated text without leading newline
                    yield evt_data
                elif evt_type == "error":
                    yield f"[SSE Error] {evt_data}"
                else:
                    # Unrecognized event
                    yield f"[Unrecognized event: {evt_type}] {evt_data}"

    except requests.exceptions.HTTPError as err:
        logger.error("HTTP Error: %s", err)
        yield f"[HTTP Error] {err}"
    except Exception as e:
        logger.error("An error occurred during SSE consumption: %s", e)
        yield f"[Error] {e}"

def initialize_chat_history(model):
    """
    Initialize the chat history with a welcome message from the AI model.
    By default, attempts to pull a prompt from the prompts library if WELCOME_PROMPT_NAME is set,
    otherwise uses a fallback string.

    :param model: The name of the model (for logging or referencing)
    """
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [AIMessage(content=WELCOME_MESSAGE)]
        logger.info("Chat history initialized for model: %s", model)
    else:
        logger.info("Chat history already exists for model: %s", model)

def display_chat_history():
    """
    Render the existing chat history in Streamlit:
    - AI messages labeled "AI"
    - Human messages labeled "Human"
    """
    for message in st.session_state.chat_history:
        if isinstance(message, AIMessage):
            with st.chat_message("AI"):
                st.write(message.content)
            logger.info("Displayed AI message: %s", message.content)
        elif isinstance(message, HumanMessage):
            with st.chat_message("Human"):
                st.write(message.content)
            logger.info("Displayed Human message: %s", message.content)

def autoplay_audio(file_path):
    """
    Play an audio file in the user's browser automatically using an <audio> tag.

    :param file_path: The path to the WAV file to play
    """
    import base64
    if not os.path.exists(file_path):
        logger.error("Audio file does not exist: %s", file_path)
        return

    with open(file_path, "rb") as audio_file:
        audio_data = audio_file.read()

    audio_base64 = base64.b64encode(audio_data).decode("utf-8")
    audio_html = f"""
    <audio autoplay>
        <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)
    logger.info("Autoplayed audio: %s", file_path)
