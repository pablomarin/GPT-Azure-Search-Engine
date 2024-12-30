import os
import streamlit as st
from app import model_name, api_url, get_env_var
from langchain_core.messages import AIMessage, HumanMessage
from helpers.streamlit_helpers import (
    configure_page,
    get_or_create_ids,
    consume_api,
    initialize_chat_history,
    display_chat_history,
    get_logger,
)
from audio_recorder_streamlit import audio_recorder
from helpers.speech_helpers import (
    autoplay_audio,
    speech_to_text_from_bytes as speech_to_text,
    text_to_speech,
)

# Configure the Streamlit page
page_title = get_env_var("AGENT_PAGE_TITLE", default_value="AI Agent", required=True)
configure_page(page_title, "💬")
logger = get_logger(__name__)
logger.info(f"Page configured with title {page_title}")

# Initialize session and user IDs
session_id, user_id = get_or_create_ids()

# Initialize chat history
initialize_chat_history(model_name)

# Create sidebar for the microphone input
with st.sidebar:
    st.header("Voice Input")
    voice_enabled = st.checkbox("Enable Voice Capabilities")

    audio_bytes = None
    if voice_enabled:
        audio_bytes = audio_recorder(text="Click to Talk",
                                     recording_color="red",
                                     neutral_color="#6aa36f",
                                     icon_size="2x",
                                     sample_rate=16000)
        if audio_bytes:
            logger.info("Audio recorded.")

# Display chat history
display_chat_history()
logger.debug("Chat history displayed.")

# User input for chat at the bottom of the main content
user_query = st.chat_input("Type your message here...")

# Handle audio input and transcription
if audio_bytes:
    transcript = speech_to_text(audio_bytes)
    logger.debug(f"Transcript: {transcript}")
    if transcript:
        st.session_state.chat_history.append(HumanMessage(content=transcript))
        with st.chat_message("Human"):
            st.write(transcript)
        logger.info("Transcript added to chat history.")

# Handle text input
if user_query is not None and user_query != "":
    logger.debug(f"User query received: {user_query}")
    st.session_state.chat_history.append(HumanMessage(content=user_query))
    with st.chat_message("Human"):
        st.markdown(user_query)
        logger.info("User query added to chat history and displayed.")

# Generate and display AI response if the last message is not from the AI
if not isinstance(st.session_state.chat_history[-1], AIMessage):
    with st.chat_message("AI"):
        try:
            ai_response = st.write_stream(
                consume_api(api_url, st.session_state.chat_history[-1].content, session_id, user_id)
            )
            logger.info("AI response received and written to stream.")
        except Exception as e:
            print(e)
            logger.error(f"Error consuming API: {e}")
            st.error("Failed to get a response from the AI.")
            ai_response = None

        if ai_response:
            st.session_state.chat_history.append(AIMessage(content=ai_response))
            if voice_enabled:
                try:
                    audio_file_path = text_to_speech(ai_response)
                    autoplay_audio(audio_file_path)
                    logger.info("Audio response generated and played.")
                except Exception as e:
                    logger.error(f"Error generating or playing audio response: {e}")
                finally:
                    if os.path.exists(audio_file_path):
                        os.remove(audio_file_path)
                        logger.info("Temporary audio file removed.")
