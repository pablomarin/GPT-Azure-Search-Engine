import streamlit as st
import os


def sidebar():
    with st.sidebar:
        st.image("https://fossbytes.com/wp-content/uploads/2019/07/open-AI-microsoft.jpg")
        st.markdown(
            "## How to use\n"
            "1. Upload a pdf, docx, or txt file📄\n"
            "2. Ask a question about the document💬\n"
        )

        st.markdown("---")
        st.markdown("# About")
        st.markdown(
            "GPT Smart Search allows you to ask questions about your "
            "documents and get accurate answers with instant citations. "
        )
        st.markdown("---")
