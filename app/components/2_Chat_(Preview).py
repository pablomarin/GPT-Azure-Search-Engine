import streamlit as st
import time
import numpy as np

from components.sidebar import sidebar

st.set_page_config(page_title="GPT Smart Chat (Preview)", page_icon="📖", layout="wide")
st.header("GPT Smart Chat (Preview)")

with st.sidebar:
    st.markdown("""# Instructions""")
    st.markdown("""
Ask a question that you think can be answered with the information in about 10k Arxiv Computer Science publications from 2020-2021 or in 52k Medical Covid-19 Publications from 2020.

For example:
- What are markov chains?
- List the authors that talk about Gradient Boosting Machines
- How does random forest work?
- What kind of problems can I solve with reinforcement learning? Give me some real life examples
- What kind of problems Turing Machines solve?
- What are the main risk factors for Covid-19?
- What medicine reduces inflamation in the lungs?
- Why Covid doesn't affect kids that much compared to adults?
    
    \nYou will notice that the answers to these questions are diferent from the open ChatGPT, since these papers are the only possible context. This search engine does not look at the open internet to answer these questions. If the context doesn't contain information, the engine will respond: I don't know.
    """)
    st.markdown("""
                - ***Quick Answer***: GPT model only uses, as context, the captions of the results coming from Azure Search
                - ***Best Answer***: GPT model uses, as context. all of the content of the documents coming from Azure Search
                """)



# Streamlit widgets automatically run the script from top to bottom. Since
# this button is not connected to any other logic, it just causes a plain
# rerun.
newChatButton = st.button("New Chat")

if newChatButton:
    st.success("Thanks for you interest in this feature. It is still in development. Please check back later.")