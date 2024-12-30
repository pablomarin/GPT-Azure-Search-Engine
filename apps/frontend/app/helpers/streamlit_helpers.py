import json
import uuid
import os

import requests
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from langchain import hub


def get_logger(name):
    from streamlit.logger import get_logger

    return get_logger(name)


logger = get_logger(__name__)


def configure_page(title, icon):
    """Configure the Streamlit page settings."""
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
    """Generate or retrieve session and user IDs."""
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
    """Send a POST request to the FastAPI backend and handle streaming responses."""
    headers = {"Content-Type": "application/json"}
    config = {"configurable": {"session_id": session_id, "user_id": user_id}}
    payload = {"input": {"question": user_query},"config": config}
    
    logger.info(
        "Sending API request to %s with session_id: %s and user_id: %s",
        url,
        session_id,
        user_id,
    )
    logger.debug("Payload: %s", payload)

    with requests.post(url, json=payload, headers=headers, stream=True) as response:
        try:
            response.raise_for_status()  # Raises an HTTPError if the response is not 200.
            logger.info("Received streaming response from API.")
            for line in response.iter_lines():
                if line:  # Check if the line is not empty.
                    decoded_line = line.decode("utf-8")
                    logger.debug("Received line: %s", decoded_line)
                    if decoded_line.startswith("data: "):
                        # Extract JSON data following 'data: '.
                        json_data = decoded_line[len("data: ") :]
                        try:
                            data = json.loads(json_data)
                            if "event" in data:
                                event_type = data["event"]
                                logger.debug("Event type: %s", event_type)
                                if event_type == "on_chat_model_stream":
                                    content = data["data"]["chunk"]["content"]
                                    if content:  # Ensure content is not None or empty.
                                        yield content  # Yield content with paragraph breaks.
                                elif event_type == "on_tool_start":
                                    tool_inputs = data["data"].get("input")
                                    if isinstance(tool_inputs, dict):
                                        # Join the dictionary into a string format key: 'value'
                                        inputs_str = ", ".join(
                                            f"'{v}'" for k, v in tool_inputs.items()
                                        )
                                    else:
                                        # Fallback if it's not a dictionary or in an unexpected format
                                        inputs_str = str(tool_inputs)
                                    #yield f"Searching Tool: {data['name']} with input: {inputs_str} ⏳\n\n"
                                    pass
                                elif event_type == "on_tool_end":
                                    pass
                            elif "content" in data:
                                # Yield immediate content with added Markdown for line breaks.
                                yield f"{data['content']}\n\n"
                            elif "steps" in data:
                                yield f"{data['steps']}\n\n"
                            elif "output" in data:
                                yield f"{data['output']}\n\n"
                        except json.JSONDecodeError as e:
                            logger.error("JSON decoding error: %s", e)
                            yield f"JSON decoding error: {e}\n\n"
                    # Decoding if using invoke endpoint
                    elif decoded_line.startswith("{\"output\":"):
                        json_data = json.loads(decoded_line)
                        yield f"{json_data['output']['output']}\n\n"
                    elif decoded_line.startswith("event: "):
                        pass
                    elif ": ping" in decoded_line:
                        pass
                    else:
                        yield f"{decoded_line}\n\n"  # Adding line breaks for plain text lines.
        except requests.exceptions.HTTPError as err:
            logger.error("HTTP Error: %s", err)
            yield f"HTTP Error: {err}\n\n"
        except Exception as e:
            logger.error("An error occurred: %s", e)
            yield f"An error occurred: {e}\n\n"


def initialize_chat_history(model):
    """Initialize the chat history with a welcome message from the AI model."""
    if "chat_history" not in st.session_state:
        try:
            prompt = hub.pull(f"{os.environ['WELCOME_PROMPT_NAME']}")
            prompt_text = prompt.get_prompts()[0].messages[0].prompt.template
        except Exception as e:
            print(e)
            prompt_text = "Welcome, how can I help you today?"
            logger.info("LangSmith hub prompt failed, setting default")
            
        st.session_state.chat_history = [AIMessage(content=prompt_text)]
        logger.info("Chat history initialized with model: %s", model)
    else:
        logger.info("Found existing chat history with model: %s", model)


def display_chat_history():
    """Display the chat history in Streamlit."""
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
    with open(file_path, "rb") as audio_file:
        audio_data = audio_file.read()

    audio_base64 = base64.b64encode(audio_data).decode("utf-8")
    audio_html = f"""
    <audio autoplay>
        <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)