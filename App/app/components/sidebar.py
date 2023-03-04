import streamlit as st
import os


def set_openai_api_key():
    os.environ["AZURE_OPENAI_API_KEY"] = st.session_state["AZURE_OPENAI_API_KEY"] = "48e3114b81d1430eb1f3df7fb783f176"
    os.environ["AZURE_OPENAI_ENDPOINT"] = st.session_state["AZURE_OPENAI_ENDPOINT "] = "https://pablo.openai.azure.com/"


def sidebar():
    with st.sidebar:
        st.markdown(
            "## How to use\n"
            "1. Upload a pdf, docx, or txt file📄\n"
            "2. Ask a question about the document💬\n"
        )
        
        set_openai_api_key()

        st.markdown("---")
        st.markdown("# About")
        st.markdown(
            "GPT Smart Search allows you to ask questions about your "
            "documents and get accurate answers with instant citations. "
        )
        st.markdown("---")
