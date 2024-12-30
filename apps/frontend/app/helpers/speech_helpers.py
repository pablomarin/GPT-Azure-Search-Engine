import base64
import os
from io import BytesIO

import azure.cognitiveservices.speech as speechsdk
import streamlit as st
from openai import AzureOpenAI
from streamlit.logger import get_logger
from langchain import hub
from app import (
    azure_speech_key,
    azure_speech_region,
    azure_speech_voice_name,
    speech_engine,
    tts_model_name,
    tts_voice_name,
    whisper_model_name,
)

def get_logger(name):
    from streamlit.logger import get_logger
    return get_logger(name)

logger = get_logger(__name__)

tts_temp_filename = "temp_audio_play.wav"
stt_temp_filename = "temp_audio_listen.wav"
openai_client = AzureOpenAI()

def recognize_whisper_api(audio_file):
    return openai_client.audio.transcriptions.create(
        model=whisper_model_name, response_format="text", file=audio_file
    )

def recognize_whisper_api_from_file(file_name: str):
    with open(file_name, "rb") as audio_file:
        transcript = recognize_whisper_api(audio_file)
    return transcript

def recognize_azure_speech_to_text_from_file(file_path: str):
    speech_config = speechsdk.SpeechConfig(
        subscription=azure_speech_key, region=azure_speech_region
    )
    audio_config = speechsdk.AudioConfig(filename=file_path)
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config
    )

    logger.debug(f"Recognizing from file at {file_path}")
    result = speech_recognizer.recognize_once_async().get()
    logger.debug("Recognition complete")
    return result.text

def speech_to_text_from_file(file_path: str):
    try:
        if speech_engine == "openai" or speech_engine == "elevenlabs":
            result = recognize_whisper_api_from_file(file_path)
        elif speech_engine == "azure":
            result = recognize_azure_speech_to_text_from_file(file_path)
        else:
            result = None

    except Exception as e:
        logger.error(f"Error: {e}")
        result = None

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        return result

def speech_to_text_from_bytes(audio_bytes: BytesIO):
    file_path = stt_temp_filename
    logger.debug(f"File path: {file_path}")

    with open(file_path, "wb") as audio_file:
        logger.debug(f"Writing file {file_path}")
        audio_file.write(audio_bytes)

    return speech_to_text_from_file(file_path)


def summarize_text(input_text: str):
    try:
        # Check if the input text is more than 500 characters
        if len(input_text) > 600 or "http" in input_text or "Searching Tool" in input_text:
            # Summarize the text to around 450 characters
            logger.info(f"Summarizing response since it has {len(input_text)} characters")
            prompt = hub.pull(f"{os.environ['SUMMARIZER_PROMPT_NAME']}")
            prompt_text = prompt.get_prompts()[0].messages[0].prompt.template
            response = openai_client.chat.completions.create(
                model=os.environ.get("AZURE_OPENAI_MODEL_NAME"),  # Replace with your deployment ID
                messages=[
                    {"role": "system", "content": prompt_text },
                    {"role": "user", "content": f"Text:\n{input_text}"}
                ]
            )
            summarized_text = response.choices[0].message.content.strip()
        else:
            summarized_text = input_text
            
        return summarized_text
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

def text_to_speech_azure(input_text: str):
    speech_config = speechsdk.SpeechConfig(
        subscription=azure_speech_key, region=azure_speech_region
    )
    speech_config.speech_synthesis_voice_name = azure_speech_voice_name
    audio_config = None
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config,audio_config=audio_config)

    try:
        summarized_text = summarize_text(input_text)
        result = speech_synthesizer.speak_text_async(summarized_text).get()
        audio_stream = speechsdk.AudioDataStream(result)
        audio_stream.save_to_wav_file(tts_temp_filename)
    except Exception as e:
        logger.error(f"Error: {e}")
    return tts_temp_filename 
    
def text_to_speech_tts(input_text: str):
    try:
        summarized_text = summarize_text(input_text)
        with openai_client.audio.speech.with_streaming_response.create(
                model=tts_model_name, voice=tts_voice_name, input=summarized_text
            ) as response:
                response.stream_to_file(tts_temp_filename)
        
        return tts_temp_filename
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

def text_to_speech(input_text: str):
    logger.debug(f"Text-to-speech using speech engine: {speech_engine}")

    if speech_engine == "openai":
        return text_to_speech_tts(input_text)
    elif speech_engine == "azure":
        return text_to_speech_azure(input_text)
    return None