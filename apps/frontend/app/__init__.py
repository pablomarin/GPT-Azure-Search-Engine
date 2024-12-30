import os

# Helper function to get environment variables with validation
def get_env_var(var_name, default_value=None, required=True):
    value = os.getenv(var_name, default_value)
    if required and value is None:
        raise EnvironmentError(f"Environment variable '{var_name}' is not set.")
    return value

# Set environment variables for LangChain
api_url = get_env_var("FAST_API_SERVER",required=True) + "/stream"
model_name = get_env_var("AZURE_OPENAI_MODEL_NAME", required=True)

# Set environment variables for OpenAI
openai_api_version = get_env_var("AZURE_OPENAI_API_VERSION", required=False)
os.environ["OPENAI_API_VERSION"] = openai_api_version
openai_endpoint = get_env_var("AZURE_OPENAI_ENDPOINT", required=True)
openai_api_key = get_env_var("AZURE_OPENAI_API_KEY", required=True)

# Validate and set the speech engine related variables
speech_engine = get_env_var("SPEECH_ENGINE", required=True).lower()

if speech_engine not in ["azure", "openai"]:
    raise EnvironmentError("Environment variable 'SPEECH_ENGINE' must be either 'azure' or 'openai'.")

if speech_engine == "azure":
    azure_speech_key = get_env_var("AZURE_SPEECH_KEY", required=True)
    azure_speech_region = get_env_var("AZURE_SPEECH_REGION", required=True)
    azure_speech_voice_name = get_env_var("AZURE_SPEECH_VOICE_NAME", default_value="en-US-AriaNeural", required=False)
    whisper_model_name = None
    tts_voice_name = None
    tts_model_name = None
elif speech_engine == "openai":
    azure_speech_key = None
    azure_speech_region = None
    azure_speech_voice_name = None
    whisper_model_name = get_env_var("AZURE_OPENAI_WHISPER_MODEL_NAME", required=True)
    tts_voice_name = get_env_var("AZURE_OPENAI_TTS_VOICE_NAME",default_value="nova", required=False)
    tts_model_name = get_env_var("AZURE_OPENAI_TTS_MODEL_NAME", required=True)