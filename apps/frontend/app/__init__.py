# app/__init__.py

import os

def get_env_var(var_name, default_value=None, required=True):
    """
    Retrieve an environment variable, optionally providing a default value.

    :param var_name: The name of the environment variable
    :param default_value: The fallback value if var_name is not found
    :param required: Whether to raise an error if the variable is missing
    :return: The value of the environment variable or default_value
    :raises EnvironmentError: If required=True and the variable is not set
    """
    value = os.getenv(var_name, default_value)
    if required and value is None:
        raise EnvironmentError(f"Environment variable '{var_name}' is not set.")
    return value

# -----------------------------------------------------------------------------
# 1) Endpoint & Model Config
# -----------------------------------------------------------------------------
# The backend SSE endpoint, e.g. "http://localhost:8000" or your deployed URL.
# We'll append "/stream" for SSE.
api_url = get_env_var("FAST_API_SERVER", required=True).rstrip("/") + "/stream"

# The primary model name or deployment name for OpenAI / Azure OpenAI
model_name = get_env_var("GPT4o_DEPLOYMENT_NAME", required=True)

# -----------------------------------------------------------------------------
# 2) OpenAI API Config
# -----------------------------------------------------------------------------
openai_api_version = get_env_var("AZURE_OPENAI_API_VERSION", required=True)
os.environ["OPENAI_API_VERSION"] = openai_api_version

openai_endpoint = get_env_var("AZURE_OPENAI_ENDPOINT", required=True)
openai_api_key = get_env_var("AZURE_OPENAI_API_KEY", required=True)

# -----------------------------------------------------------------------------
# 3) Speech Engine Config
# -----------------------------------------------------------------------------
speech_engine = get_env_var("SPEECH_ENGINE", required=True).lower()
if speech_engine not in ["azure", "openai"]:
    raise EnvironmentError("Environment variable 'SPEECH_ENGINE' must be either 'azure' or 'openai'.")

# For Azure-based TTS or STT
if speech_engine == "azure":
    azure_speech_key = get_env_var("AZURE_SPEECH_KEY", required=True)
    azure_speech_region = get_env_var("AZURE_SPEECH_REGION", required=True)
    azure_speech_voice_name = get_env_var("AZURE_SPEECH_VOICE_NAME", default_value="en-US-AndrewMultilingualNeural", required=False)
    whisper_model_name = None
    tts_voice_name = None
    tts_model_name = None

# For OpenAI-based Whisper + TTS
elif speech_engine == "openai":
    azure_speech_key = None
    azure_speech_region = None
    azure_speech_voice_name = None
    whisper_model_name = get_env_var("AZURE_OPENAI_WHISPER_MODEL_NAME", default_value="whisper", required=True)
    tts_voice_name = get_env_var("AZURE_OPENAI_TTS_VOICE_NAME", default_value="nova", required=False)
    tts_model_name = get_env_var("AZURE_OPENAI_TTS_MODEL_NAME", default_value="tts", required=True)
