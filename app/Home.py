import streamlit as st

st.set_page_config(page_title="GPT Smart Search", page_icon="📖", layout="wide")

st.image("https://user-images.githubusercontent.com/113465005/226238596-cc76039e-67c2-46b6-b0bb-35d037ae66e1.png")

st.header("GPT Smart Search Engine")


st.markdown("---")
st.markdown("""
    GPT Smart Search allows you to ask questions about your
    documents and get accurate answers with instant citations.
    
    This engine finds information from the following:
    - ~10k [Computer Science Publications in Arxiv from 2020-2021](https://www.kaggle.com/datasets/1b6883fb66c5e7f67c697c2547022cc04c9ee98c3742f9a4d6c671b4f4eda591)
    - ~52k [COVID-19 literature in LitCovid from 2020-2021](https://www.ncbi.nlm.nih.gov/research/coronavirus/)
    - [Covid Tracking Project Dataset](https://covidtracking.com/). A CSV with tabular information of Covid cases and hospitalizations in the US from 2020-2021.
    
    **👈 Select a demo from the sidebar** to see some examples
    of what Azure Cognitive Search and Azure OpenAI Service can do!
    ### Want to learn more?
    - Check out [Github Repo](https://github.com/pablomarin/GPT-Azure-Search-Engine/)
    - Jump into [Azure OpenAI documentation](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/)
    - Ask a question or submit a [GitHub Issue!](https://github.com/pablomarin/GPT-Azure-Search-Engine/issues/new)


    
"""
)
st.markdown("---")


st.sidebar.success("Select a demo above.")
