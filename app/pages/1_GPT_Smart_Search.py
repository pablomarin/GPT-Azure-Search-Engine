import streamlit as st
import urllib
import os
import re
import time
import random
from collections import OrderedDict
from openai.error import OpenAIError
from langchain.docstore.document import Document

from utils import (
    get_search_results,
    order_search_results,
    model_tokens_limit,
    num_tokens_from_docs,
    embed_docs,
    search_docs,
    get_answer,
)
st.set_page_config(page_title="OXXO GPT Smart Search", page_icon="📖", layout="wide")
# Add custom CSS styles to adjust padding
st.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                }
        </style>
        """, unsafe_allow_html=True)

st.header("OXXO GPT Smart Search Engine")

AZURE_OPENAI_API_VERSION = "2023-03-15-preview"

# setting encoding for GPT3.5 / GPT4 models
MODEL = "gpt-35-turbo"

def clear_submit():
    st.session_state["submit"] = False


with st.sidebar:
    st.markdown("""# Instrucciones""")
    st.markdown("""
Puedes hacer preguntas de incidentes y obtener algunas respuestas genrales de cauda raíz 

Por :
- que es goldengate?
- otros detalles de causa raíz 

    
    \n Las respeustas solo son una muestra de algunos docuemtos Oxxo. el sisitema no responde información que no tiene como ccontexto. y no está conectado a internet.
    """)

coli1, coli2= st.columns([3,1])
with coli1:
    query = st.text_input("Ask a question to your enterprise data lake", value= "que es goldengate?", on_change=clear_submit)
with coli2:
    language= st.selectbox('Answer language',('English', 'Spanish', 'French', 'German', 'Portuguese', 'Italian'), index=0)

# options = ['English', 'Spanish', 'Portuguese', 'French', 'Russian']
# selected_language = st.selectbox('Answer Language:', options, index=0)

button = st.button('Search')



if (not os.environ.get("AZURE_SEARCH_ENDPOINT")) or (os.environ.get("AZURE_SEARCH_ENDPOINT") == ""):
    st.error("Please set your AZURE_SEARCH_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_SEARCH_KEY")) or (os.environ.get("AZURE_SEARCH_KEY") == ""):
    st.error("Please set your AZURE_SEARCH_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_OPENAI_ENDPOINT")) or (os.environ.get("AZURE_OPENAI_ENDPOINT") == ""):
    st.error("Please set your AZURE_OPENAI_ENDPOINT on your Web App Settings")
elif (not os.environ.get("AZURE_OPENAI_API_KEY")) or (os.environ.get("AZURE_OPENAI_API_KEY") == ""):
    st.error("Please set your AZURE_OPENAI_API_KEY on your Web App Settings")
elif (not os.environ.get("DATASOURCE_SAS_TOKEN")) or (os.environ.get("DATASOURCE_SAS_TOKEN") == ""):
    st.error("Please set your DATASOURCE_SAS_TOKEN on your Web App Settings")

else: 
    os.environ["OPENAI_API_BASE"] = os.environ.get("AZURE_OPENAI_ENDPOINT")
    os.environ["OPENAI_API_KEY"] = os.environ.get("AZURE_OPENAI_API_KEY")
    os.environ["OPENAI_API_VERSION"] = os.environ["AZURE_OPENAI_API_VERSION"] = AZURE_OPENAI_API_VERSION
    os.environ["OPENAI_API_TYPE"] = "azure"


    if button or st.session_state.get("submit"):
        if not query:
            st.error("Please enter a question!")
        else:
            # Azure Search

            try:
                index1_name = "cogsrch-index-files"
                index2_name = "cogsrch-index-csv"
                indexes = [index1_name, index2_name]
                
                agg_search_results = get_search_results(query, indexes)
                ordered_results = order_search_results(agg_search_results, reranker_threshold=1)


                st.session_state["submit"] = True
                # Output Columns
                placeholder = st.empty()

            except Exception as e:
                st.markdown("Not data returned from Azure Search, check connection..")
                st.markdown(e)
            
            if "ordered_results" in locals():
                try:
                    docs = []
                    for key,value in ordered_results.items():
                        for page in value["chunks"]:
                            docs.append(Document(page_content=page, metadata={"source": value["location"]}))
                            add_text = "Buscando Información de la fuente... ⏳"

                    if "add_text" in locals():
                        with st.spinner(add_text):
                            if(len(docs)>0):
                                
                                tokens_limit = model_tokens_limit(MODEL)
                                num_tokens = num_tokens_from_docs(docs)
                                
                                if num_tokens > tokens_limit:
                                    index = embed_docs(docs)
                                    top_docs = search_docs(index,query)
                                    num_tokens = num_tokens_from_docs(top_docs)
                                    chain_type = "map_reduce" if num_tokens > tokens_limit else "stuff"
                                else:
                                    top_docs = docs
                                    chain_type = "stuff"
                                
                                answer = get_answer(top_docs, query, language=language, deployment=MODEL, chain_type = chain_type)
                            else:
                                answer = {"output_text":"No results found" }
                    else:
                        answer = {"output_text":"No results found" }


                    with placeholder.container():

                        st.markdown("#### Answer")
                        split_word = "Source"
                        split_regex = re.compile(f"{split_word}s:?\\W*", re.IGNORECASE)
                        answer_text = split_regex.split(answer["output_text"])[0]
                        st.markdown(answer_text)
                        try:
                            sources_list = split_regex.split(answer["output_text"])[1].replace(" ","").split(",")
                            #sources_list = answer["output_text"].split("SOURCES:")[1].replace(" ","").split(",")
                            sources_markdown = "Sources: "
                            for index, value in enumerate(sources_list):
                                sources_markdown += "[[" + str(index+1) + "]](" + value + os.environ.get("DATASOURCE_SAS_TOKEN") + ")"
                            st.markdown(sources_markdown)
                        except Exception as e:
                            st.markdown("Sources: N/A")
                            
                        st.markdown("---")
                        st.markdown("#### Search Results")

                        if(len(docs)>0):
                            for key, value in ordered_results.items():
                                url = value['location'] + os.environ.get("DATASOURCE_SAS_TOKEN")
                                title = str(value['title']) if (value['title']) else value['name']
                                score = str(round(value['score']*100/4,2))
                                st.markdown("[" + title +  "](" + url + ")" + "  (Score: " + score + "%)")
                                st.markdown(value["caption"])
                                st.markdown("---")

                except OpenAIError as e:
                    st.error(e)
