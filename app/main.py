import streamlit as st
import urllib
import os
import time
import requests
from IPython.display import display, HTML
from collections import OrderedDict
from openai.error import OpenAIError
from langchain.docstore.document import Document

from components.sidebar import sidebar
from utils import (
    embed_docs,
    get_answer,
    get_sources,
    parse_docx,
    parse_pdf,
    parse_txt,
    search_docs,
    text_to_docs,
    wrap_text_in_html,
)
from credentials import (
    API_VERSION,
    DATASOURCE_CONNECTION_STRING,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_KEY,
    COG_SERVICES_NAME,
    COG_SERVICES_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_KEY
)


def clear_submit():
    st.session_state["submit"] = False


st.set_page_config(page_title="GPT Smart Search", page_icon="📖", layout="wide")
st.header("GPT Smart Search Engine")

sidebar()

index_name = "cogsrch-index"

os.environ["AZURE_OPENAI_ENDPOINT"] = st.session_state["AZURE_OPENAI_ENDPOINT "] = AZURE_OPENAI_ENDPOINT
os.environ["OPENAI_API_KEY"] = os.environ["AZURE_OPENAI_API_KEY"] = st.session_state["AZURE_OPENAI_API_KEY"] = AZURE_OPENAI_KEY

headers = {'Content-Type': 'application/json','api-key': AZURE_SEARCH_KEY}
params = {'api-version': API_VERSION}

query = st.text_area("Ask a question to your enterprise data lake", help="Try questions like: What is Reinforcement learning? or, tell me about Markov chains" , on_change=clear_submit)

col1, col2, col3 = st.columns([1,1,3])

with col1:
    qbutton = st.button('Quick Answer')
with col2:
    bbutton = st.button('Best Answer')

if qbutton or bbutton or st.session_state.get("submit"):
    if not query:
        st.error("Please enter a question!")
    else:
        url = AZURE_SEARCH_ENDPOINT + '/indexes/'+ index_name + '/docs'
        url += '?api-version={}'.format(API_VERSION)
        url += '&search={}'.format(query)
        url += '&select=pages'
        url += '&$top=5'
        url += '&queryLanguage=en-us'
        url += '&queryType=semantic'
        url += '&semanticConfiguration=my-semantic-config'
        url += '&$count=true'
        url += '&speller=lexicon'
        url += '&answers=extractive|count-3'
        url += '&captions=extractive|highlight-true'
        url += '&highlightPreTag=' + urllib.parse.quote('<span style="background-color: #f5e8a3">', safe='')
        url += '&highlightPostTag=' + urllib.parse.quote('</span>', safe='')

        resp = requests.get(url, headers=headers)
        search_results = resp.json()

        file_content = OrderedDict()
        
        for result in search_results['value']:
            if result['@search.rerankerScore'] > 0.4:
                    file_content[result['metadata_storage_path']]={
                            "content": result['pages'],  
                            "score": result['@search.rerankerScore'], 
                            "caption": result['@search.captions'][0]['text']        
                            }
 
        
        st.session_state["submit"] = True
        # Output Columns
        placeholder = st.empty()
        
        try:
            docs = []
            for key,value in file_content.items():
                
                if qbutton:
                    docs.append(Document(page_content=value['caption'], metadata={"source": key}))
                    add_text = "Coming up with a quick answer... ⏳"
                
                if bbutton:
                    for page in value["content"]:
                        docs.append(Document(page_content=page, metadata={"source": key}))
                    add_text = "Reading the source documents to provide the best answer... ⏳"
                
            if "add_text" in locals():
                with st.spinner(add_text):
                    if(len(docs)>1):
                        index = embed_docs(docs)
                        sources = search_docs(index,query)
                        answer = get_answer(sources, query, language="English", chain_type = "refine", temperature=0.5, max_tokens=500)
                    else:
                        answer = {"output_text":"No results found" }
            else:
                answer = {"output_text":"No results found" }


            with placeholder.container():
                st.markdown("#### Answer")
                st.markdown(answer["output_text"])
                st.markdown("---")
                st.markdown("#### Search Results")

                if(len(docs)>1):
                    for key, value in file_content.items():
                        st.markdown(key + '  (Score: ' + str(round(value["score"],2)*100/4) + '%)')
                        st.markdown(value["caption"])
                        st.markdown("---")

        except OpenAIError as e:
            st.error(e._message)
