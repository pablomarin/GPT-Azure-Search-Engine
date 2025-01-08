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
    """
    Recognize speech from an audio file with automatic language detection 
    across the top 6 spoken languages globally.
    
    Args:
        file_path (str): Path to the audio file.
        key (str): Azure Speech Service subscription key.
        region (str): Azure service region.

    Returns:
        string: Transcribed text.
    
    Raises:
        RuntimeError: If an error occurs during speech recognition.
    """
    try:
        # Create a speech configuration with your subscription key and region
        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        
        # Create an audio configuration pointing to the audio file
        audio_config = speechsdk.AudioConfig(filename=file_path)
        
        # Top 4 most spoken languages (ISO language codes)
        # SDK only supports 4 languages as options
        languages = ["en-US", "zh-CN", "hi-IN", "es-ES"]
        
        # Configure auto language detection with the specified languages
        auto_detect_source_language_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=languages)
        
        # Create a speech recognizer with the auto language detection configuration
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
            auto_detect_source_language_config=auto_detect_source_language_config
        )
        
        # Perform speech recognition
        result = speech_recognizer.recognize_once_async().get()
        
        # Check the result
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            # Retrieve the detected language
            detected_language = result.properties.get(
                speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult,
                "Unknown"
            )
            logging.debug("Detected Language %s", detected_language, exc_info=True)
            return result.text
        
        elif result.reason == speechsdk.ResultReason.NoMatch:
            raise RuntimeError("No speech could be recognized from the audio.")
        
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speechsdk.CancellationDetails(result)
            raise RuntimeError(f"Speech Recognition canceled: {cancellation_details.reason}. "
                               f"Error details: {cancellation_details.error_details}")
        
        else:
            raise RuntimeError("Unknown error occurred during speech recognition.")
    
    except Exception as e:
        raise RuntimeError(f"An error occurred during speech recognition: {e}")


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
        audio_file.write(audio_bytes)

    return speech_to_text_from_file(temp_filename)


###############################################################################
# Text-to-Speech (TTS) Functions
###############################################################################

import traceback

def summarize_text(input_text: str) -> str:
    """
    Converts the input text to a voice-ready short answer.

    This uses LangChain's AzureChatOpenAI with your custom summarization instructions.
    """

    # For example, define how many tokens we allow for the completion
    COMPLETION_TOKENS = 1000

    # Build the prompt template for LangChain
    output_parser = StrOutputParser()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SUMMARIZER_TEXT),
        ("human", "Input Text: \n{input}")
    ])
    
    try:
        # Create the LLM with AzureChatOpenAI using your deployment name
        llm = AzureChatOpenAI(
            deployment_name=os.environ["GPT4o_DEPLOYMENT_NAME"],
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
        logging.error("Error summarizing text with GPT-4o via LangChain: %s", str(e), exc_info=True)
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
        
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            if result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                logging.error(f"Speech synthesis canceled: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    logging.error(f"Error details: {cancellation_details.error_details}")
            raise Exception(f"Speech synthesis failed with reason: {result.reason}")
        
        audio_stream = speechsdk.AudioDataStream(result)
        audio_stream.save_to_wav_file(output_filename)
        return output_filename
    except Exception as e:
        logging.error("Azure TTS error: %s", e, exc_info=True)
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
        logging.error("OpenAI TTS error: %s", e, exc_info=True)
        return None


def text_to_speech(input_text: str, engine=SPEECH_ENGINE, output_filename="temp_audio_play.wav"):
    """
    High-level function to pick the correct TTS engine based on environment or parameter.

    :param input_text: Text to synthesize into speech
    :param engine: Which speech engine to use ("azure" or "openai")
    :param output_filename: Filename to save the synthesized speech
    :return: Path to the audio file or None if failed
    """
    if engine == "azure":
        return text_to_speech_azure(input_text, output_filename=output_filename)
    elif engine == "openai":
        return text_to_speech_openai(input_text, output_filename=output_filename)
    else:
        logging.error("No valid speech engine specified.")
        return None
    

