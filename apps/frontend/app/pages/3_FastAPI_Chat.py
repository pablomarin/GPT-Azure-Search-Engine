# app/pages/Chat.py

import os
import sys

# Import STT and TTS functions from audio_utils.py
try:
    from audio_utils import (
        speech_to_text_from_bytes as speech_to_text,
        text_to_speech,
    )
except Exception as e:
    # Add the path four levels up
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))
    from common.audio_utils import (
        speech_to_text_from_bytes as speech_to_text,
        text_to_speech,
    )

    
import streamlit as st

from app import model_name, api_url, get_env_var
from langchain_core.messages import AIMessage, HumanMessage
from helpers.streamlit_helpers import (
    configure_page,
    get_or_create_ids,
    consume_api,
    initialize_chat_history,
    display_chat_history,
    autoplay_audio,
    get_logger,
)

from audio_recorder_streamlit import audio_recorder

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
page_title = get_env_var("AGENT_PAGE_TITLE", default_value="AI Agent", required=True)
configure_page(page_title, "💬")
logger = get_logger(__name__)
logger.info(f"Page configured with title: {page_title}")

# -----------------------------------------------------------------------------
# Session IDs and Chat History
# -----------------------------------------------------------------------------
session_id, user_id = get_or_create_ids()
initialize_chat_history(model_name)

# -----------------------------------------------------------------------------
# Sidebar with optional voice input
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Voice Input")
    voice_enabled = st.checkbox("Enable Voice Capabilities")

    audio_bytes = None
    if voice_enabled:
        audio_bytes = audio_recorder(
            text="Click to Talk",
            recording_color="red",
            neutral_color="#6aa36f",
            icon_size="2x",
            sample_rate=16000
        )
        if audio_bytes:
            logger.info("Audio recorded from user microphone.")

# -----------------------------------------------------------------------------
# Display existing chat messages
# -----------------------------------------------------------------------------
display_chat_history()
logger.debug("Displayed existing chat history.")


# -----------------------------------------------------------------------------
# Handle User Input (Text & Audio)
# -----------------------------------------------------------------------------
user_query = st.chat_input("Type your message here...")

# Track whether a new user message was added
new_user_message = False

# Handle audio input
if audio_bytes:
    transcript = speech_to_text(audio_bytes)
    logger.debug(f"Transcript from STT: {transcript}")
    if transcript:
        st.session_state.chat_history.append(HumanMessage(content=transcript))
        with st.chat_message("Human"):
            st.write(transcript)
        logger.info("Transcript added to chat history.")
        new_user_message = True

# Handle text input (st.chat_input)
if user_query is not None and user_query.strip() and not new_user_message:
    st.session_state.chat_history.append(HumanMessage(content=user_query))
    with st.chat_message("Human"):
        st.markdown(user_query)
    logger.info("User query added to chat history: %s", user_query)
    new_user_message = True

# -----------------------------------------------------------------------------
# Generate AI response if the last message is from a Human
# -----------------------------------------------------------------------------
if new_user_message and not isinstance(st.session_state.chat_history[-1], AIMessage):
    with st.chat_message("AI"):
        try:
            logger.info("Sending request to SSE /stream endpoint with user query.")
            user_text = st.session_state.chat_history[-1].content

            ai_response = st.write_stream(
                consume_api(api_url, user_text, session_id, user_id)
            )
            logger.info("AI streaming complete. Final text aggregated.")
        except Exception as e:
            logger.error(f"Error during SSE consumption: {e}", exc_info=True)
            st.error("Failed to get a response from the AI.")
            ai_response = None

        # Append AI response to chat history
        if ai_response:
            st.session_state.chat_history.append(AIMessage(content=ai_response))

            # Voice Output (if enabled)
            if voice_enabled:
                try:
                    audio_file_path = text_to_speech(ai_response)
                    if audio_file_path:
                        autoplay_audio(audio_file_path)
                        logger.info("Audio response generated and played.")
                        os.remove(audio_file_path)
                        logger.info("Temporary audio file removed.")
                except Exception as ex:
                    logger.error(f"Error generating or playing audio: {ex}", exc_info=True)


