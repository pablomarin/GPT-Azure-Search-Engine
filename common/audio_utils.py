# audio_utils.py

import os
import logging
import requests
from io import BytesIO

# LangChain Imports needed
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import azure.cognitiveservices.speech as speechsdk
from openai import AzureOpenAI
try:
    from .prompts import SUMMARIZER_TEXT
except Exception as e:
    from prompts import SUMMARIZER_TEXT


###############################################################################
# Environment & Client Setup
###############################################################################

def get_env_var(var_name, default_value=None, required=True):
    """
    Retrieves an environment variable, optionally providing a default value.
    Raises an error if `required` is True and variable is not found.
    """
    value = os.getenv(var_name, default_value)
    if required and value is None:
        raise EnvironmentError(f"Environment variable '{var_name}' is not set.")
    return value


os.environ["OPENAI_API_VERSION"] = get_env_var("AZURE_OPENAI_API_VERSION")

# For demonstration, pick which engine you want to use
SPEECH_ENGINE = get_env_var("SPEECH_ENGINE", default_value="openai", required=False).lower()
assert SPEECH_ENGINE in ["azure", "openai"], (
    "SPEECH_ENGINE must be one of: azure, openai"
)

# Setup for OpenAI or Azure keys
openai_client = AzureOpenAI()

if SPEECH_ENGINE == "azure":
    azure_speech_key = get_env_var("AZURE_SPEECH_KEY", required=True)
    azure_speech_region = get_env_var("AZURE_SPEECH_REGION", required=True)
    azure_speech_voice_name = get_env_var("AZURE_SPEECH_VOICE_NAME", default_value="en-US-AriaNeural", required=False)
    # not used for azure mode:
    whisper_model_name = None
    tts_model_name = None
    tts_voice_name = None

elif SPEECH_ENGINE == "openai":
    whisper_model_name = get_env_var("AZURE_OPENAI_WHISPER_MODEL_NAME", default_value="whisper", required=True)
    tts_model_name = get_env_var("AZURE_OPENAI_TTS_MODEL_NAME", default_value="tts-hd", required=True)
    tts_voice_name = get_env_var("AZURE_OPENAI_TTS_VOICE_NAME", default_value="nova", required=False)
    # not used for openai mode:
    azure_speech_key = None
    azure_speech_region = None
    azure_speech_voice_name = None


###############################################################################
# Speech-to-Text Functions
###############################################################################

def recognize_whisper_api(audio_file, whisper_model: str):
    """
    Call AzureOpenAI Whisper model to transcribe the audio.
    """
    return openai_client.audio.transcriptions.create(
        model=whisper_model,
        response_format="text",
        file=audio_file
    )

def recognize_whisper_api_from_file(file_name: str, whisper_model: str):
    with open(file_name, "rb") as audio_file:
        transcript = recognize_whisper_api(audio_file, whisper_model)
    return transcript

def recognize_azure_speech_to_text_from_file(file_path: str, key: str, region: str):
    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    audio_config = speechsdk.AudioConfig(filename=file_path)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result = speech_recognizer.recognize_once_async().get()
    return result.text

def speech_to_text_from_file(file_path: str):
    """
    High-level function to transcribe audio from file, removing the file afterwards.
    """
    try:
        if SPEECH_ENGINE == "openai":
            # Uses AzureOpenAI Whisper
            result = recognize_whisper_api_from_file(file_path, whisper_model_name)
        elif SPEECH_ENGINE == "azure":
            # Uses Azure speech
            result = recognize_azure_speech_to_text_from_file(file_path, azure_speech_key, azure_speech_region)
        else:
            result = None
    except Exception as e:
        print(f"Error in STT: {e}")
        result = None
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        return result

def speech_to_text_from_bytes(audio_bytes: BytesIO, temp_filename: str = "temp_audio_listen.wav"):
    """
    Write a BytesIO object to disk, then call `speech_to_text_from_file`.
    """
    with open(temp_filename, "wb") as audio_file:
        audio_file.write(audio_bytes.getbuffer())

    return speech_to_text_from_file(temp_filename)



###############################################################################
# Text-to-Speech (TTS) Functions
###############################################################################

import traceback

def summarize_text(input_text: str) -> str:
    """
    Summarize the text using the Azure GPT-4o mini model if it exceeds 500 characters.
    Otherwise, return the text as-is.

    This uses LangChain's AzureChatOpenAI with your custom summarization instructions.
    """
    # If text is short, no need to summarize
    if len(input_text) <= 500:
        return input_text

    # For example, define how many tokens we allow for the completion
    COMPLETION_TOKENS = 1000

    # Build the prompt template for LangChain
    output_parser = StrOutputParser()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SUMMARIZER_TEXT),
        ("user", "{input}")
    ])
    
    try:
        # Create the LLM with AzureChatOpenAI using your deployment name
        llm = AzureChatOpenAI(
            deployment_name=os.environ["GPT4oMINI_DEPLOYMENT_NAME"],
            temperature=0.5,
            max_tokens=COMPLETION_TOKENS 
        )

        # Build the chain
        chain = prompt | llm | output_parser

        # Run the chain with your input text
        summary = chain.invoke({"input": input_text})

        # Return the summarized content
        return summary.strip()

    except Exception as e:
        logging.error("Error summarizing text with GPT-4o mini via LangChain: %s", str(e))
        traceback.print_exc()
        # If summarization fails, just return the original text
        return input_text

def text_to_speech_azure(input_text: str, output_filename="temp_audio_play.wav"):
    """
    Use Azure TTS to synthesize speech from text, saving to `output_filename`.
    """
    speech_config = speechsdk.SpeechConfig(
        subscription=azure_speech_key,
        region=azure_speech_region
    )
    speech_config.speech_synthesis_voice_name = azure_speech_voice_name
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
    try:
        summarized_text = summarize_text(input_text)
        result = speech_synthesizer.speak_text_async(summarized_text).get()
        audio_stream = speechsdk.AudioDataStream(result)
        audio_stream.save_to_wav_file(output_filename)
        return output_filename
    except Exception as e:
        print("Azure TTS error:", e)
        traceback.print_exc()
        return None

def text_to_speech_openai(input_text: str, output_filename="temp_audio_play.wav"):
    """
    Use AzureOpenAI TTS. Adjust to reference openai_client usage for TTS if available.
    """
    try:
        summarized_text = summarize_text(input_text)
        with openai_client.audio.speech.with_streaming_response.create(
            model=tts_model_name,
            voice=tts_voice_name,
            input=summarized_text
        ) as response:
            response.stream_to_file(output_filename)
        return output_filename
    except Exception as e:
        print("OpenAI TTS error:", e)
        traceback.print_exc()
        return None

def text_to_speech(input_text: str, engine=SPEECH_ENGINE, output_filename="temp_audio_play.wav"):
    """
    High-level function to pick the correct TTS engine based on environment or parameter.
    """
    if engine == "azure":
        return text_to_speech_azure(input_text, output_filename=output_filename)
    elif engine == "openai":
        return text_to_speech_openai(input_text, output_filename=output_filename)
    else:
        print("No valid speech engine specified.")
        return None
    

