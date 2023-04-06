import streamlit as st
import os


def sidebar():
    with st.sidebar:
        st.image("https://fossbytes.com/wp-content/uploads/2019/07/open-AI-microsoft.jpg")

        st.markdown("---")
        st.markdown("# About")
        st.markdown("""
            GPT Smart Search allows you to ask questions about your
            documents and get accurate answers with instant citations.
            
            This engine finds information from the following:
            - ~10k [Computer Science Publications in Arxiv from 2020-2022](https://www.kaggle.com/datasets/1b6883fb66c5e7f67c697c2547022cc04c9ee98c3742f9a4d6c671b4f4eda591)
            - ~52k [COVID-19 literature in LitCovid from 2020-2023](https://www.ncbi.nlm.nih.gov/research/coronavirus/)
            
            [Github Repo](https://github.com/pablomarin/GPT-Azure-Search-Engine/)
        """
        )
        st.markdown("---")
