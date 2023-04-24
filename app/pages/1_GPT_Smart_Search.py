import streamlit as st
import urllib
import os
import time
import random
from collections import OrderedDict
from openai.error import OpenAIError
from langchain.docstore.document import Document
from langchain.callbacks.base import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from components.sidebar import sidebar
from utils import (
    get_search_results,
    embed_docs,
    get_answer,
    get_sources,
    search_docs,
    num_tokens_from_string,
    model_tokens_limit
)
st.set_page_config(page_title="GPT Smart Search", page_icon="📖", layout="wide")
# Add custom CSS styles to adjust padding
st.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                }
        </style>
        """, unsafe_allow_html=True)

st.header("GPT Smart Search Engine")

AZURE_OPENAI_API_VERSION = "2023-03-15-preview"

# setting encoding for GPT3.5 / GPT4 models
encoding_name ='cl100k_base'

def clear_submit():
    st.session_state["submit"] = False


with st.sidebar:
    st.markdown("""# Instructions""")
    st.markdown("""
Ask a question that you think can be answered with the information in about 10k Arxiv Computer Science publications from 2020-2021 or in 52k Medical Covid-19 Publications from 2020.

For example:
- What are markov chains?
- List the authors that talk about Boosting Algorithms
- How does random forest work?
- What kind of problems can I solve with reinforcement learning? Give me some real life examples
- What kind of problems Turing Machines solve?
- What are the main risk factors for Covid-19?
- What medicine reduces inflammation in the lungs?
- Why Covid doesn't affect kids that much compared to adults?
    
    \nYou will notice that the answers to these questions are diferent from the open ChatGPT, since these papers are the only possible context. This search engine does not look at the open internet to answer these questions. If the context doesn't contain information, the engine will respond: I don't know.
    """)
    st.markdown("""
            - ***Quick Answer***: GPT model only uses, as context, the captions of the results coming from Azure Search
            - ***Best Answer***: GPT model uses, as context. all of the content of the documents coming from Azure Search
            """)

coli1, coli2 = st.columns([2,1])
with coli1:
    query = st.text_input("Ask a question to your enterprise data lake", value= "What is CLP?", on_change=clear_submit)
with coli2:
    temp = st.slider('Temperature :thermometer:', min_value=0.0, max_value=1.0, step=0.1, value=0.5)

# options = ['English', 'Spanish', 'Portuguese', 'French', 'Russian']
# selected_language = st.selectbox('Answer Language:', options, index=0)

col1, col2, col3 = st.columns([1,1,3])
with col1:
    qbutton = st.button('Quick Answer')
with col2:
    bbutton = st.button('Best Answer')


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


    if qbutton or bbutton or st.session_state.get("submit"):
        if not query:
            st.error("Please enter a question!")
        else:
            # Azure Search

            try:
                index1_name = "cogsrch-index-files"
                index2_name = "cogsrch-index-csv"
                indexes = [index1_name, index2_name]
                agg_search_results = get_search_results(query, indexes)

                file_content = OrderedDict()
                content = dict()

                for search_results in agg_search_results:
                    for result in search_results['value']:
                        if result['@search.rerankerScore'] > 1: # Show results that are at least 25% of the max possible score=4
                            content[result['id']]={
                                                    "title": result['title'],
                                                    "chunks": result['pages'],
                                                    "language": result['language'],
                                                    "caption": result['@search.captions'][0]['text'],
                                                    "score": result['@search.rerankerScore'],
                                                    "name": result['metadata_storage_name'],
                                                    "location": result['metadata_storage_path']                  
                                                }
                            
                #After results have been filtered we will Sort and add them as an Ordered list
                for id in sorted(content, key= lambda x: content[x]["score"], reverse=True):
                    file_content[id] = content[id]

                st.session_state["submit"] = True
                # Output Columns
                placeholder = st.empty()

            except Exception as e:
                st.markdown("Not data returned from Azure Search, check connection..")
                st.markdown(e)
            
            if "file_content" in locals():
                try:
                    docs = []
                    for key,value in file_content.items():

                        if qbutton:
                            docs.append(Document(page_content=value['caption'], metadata={"source": value["location"]}))
                            add_text = "Coming up with a quick answer... ⏳"

                        if bbutton:
                            for page in value["chunks"]:
                                docs.append(Document(page_content=page, metadata={"source": value["location"]}))
                            add_text = "Reading the source documents to provide the best answer... ⏳"

                    if "add_text" in locals():
                        with st.spinner(add_text):
                            if(len(docs)>0):
                                gpt_tokens_limit = model_tokens_limit('gpt-35-turbo')
                                num_token = 0
                                for i in range(len(docs)):
                                    num_token += num_tokens_from_string(docs[i].page_content,encoding_name)
                                # if the token count >3000 then only doing the embedding.
                                if num_token > gpt_tokens_limit:
                                    language = random.choice(list(file_content.items()))[1]["language"]
                                    index = embed_docs(docs, language)
                                    sources = search_docs(index,query)
                                    if qbutton:
                                        answer = get_answer(sources, query, deployment="gpt-35-turbo", chain_type = "stuff", temperature=temp, max_tokens=256)
                                    if bbutton: 
                                        answer = get_answer(sources, query, deployment="gpt-35-turbo", chain_type = "map_reduce", temperature=temp, max_tokens=500)
                                else:
                                    answer = get_answer(docs, query, deployment="gpt-35-turbo", chain_type = "stuff", temperature=temp, max_tokens=256)
                            else:
                                answer = {"output_text":"No results found" }
                    else:
                        answer = {"output_text":"No results found" }


                    with placeholder.container():

                        st.markdown("#### Answer")
                        answer_text = answer["output_text"].split("SOURCES:")[0]
                        st.markdown(answer_text)
                        try:
                            sources_list = answer["output_text"].split("SOURCES:")[1].replace(" ","").split(",")
                            sources_markdown = "Sources: "
                            for index, value in enumerate(sources_list):
                                sources_markdown += "[[" + str(index+1) + "]](" + value + os.environ.get("DATASOURCE_SAS_TOKEN") + ")"
                            st.markdown(sources_markdown)
                        except Exception as e:
                            st.markdown("Sources: N/A")
                            
                        st.markdown("---")
                        st.markdown("#### Search Results")

                        if(len(docs)>0):
                            for key, value in file_content.items():
                                url = value['location'] + os.environ.get("DATASOURCE_SAS_TOKEN")
                                title = str(value['title']) if (value['title']) else value['name']
                                score = str(round(value['score']*100/4,2))
                                st.markdown("[" + title +  "](" + url + ")" + "  (Score: " + score + "%)")
                        st.markdown(answer["output_text"].split("SOURCES:")[0])
                        st.markdown("Sources:")
                        try: 
                            for s in answer["output_text"].split("SOURCES:")[1].replace(" ","").split(","):
                                st.markdown(s) 
                        except:
                            st.markdown("N/A")
                        st.markdown("---")
                        st.markdown("#### Search Results")

                        if(len(docs)>1):
                            for key, value in file_content.items():
                                st.markdown(str(value["title"]) + '  (Score: ' + str(round(value["score"]*100/4,2)) + '%)')
                                st.markdown(value["caption"])
                                st.markdown("---")

                except OpenAIError as e:
                    st.error(e)
