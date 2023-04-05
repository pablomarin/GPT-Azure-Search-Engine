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
    search_docs
)
from credentials import (
    DATASOURCE_CONNECTION_STRING,
    AZURE_SEARCH_API_VERSION,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_KEY,
    COG_SERVICES_NAME,
    COG_SERVICES_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_KEY,
    AZURE_OPENAI_API_VERSION

)

os.environ["OPENAI_API_BASE"] = os.environ["AZURE_OPENAI_ENDPOINT"] = st.session_state["AZURE_OPENAI_ENDPOINT "] = AZURE_OPENAI_ENDPOINT
os.environ["OPENAI_API_KEY"] = os.environ["AZURE_OPENAI_API_KEY"] = st.session_state["AZURE_OPENAI_API_KEY"] = AZURE_OPENAI_KEY
os.environ["OPENAI_API_VERSION"] = os.environ["AZURE_OPENAI_API_VERSION"] = AZURE_OPENAI_API_VERSION



def clear_submit():
    st.session_state["submit"] = False

#@st.cache_data()
def get_search_results(query, indexes):
    
    headers = {'Content-Type': 'application/json','api-key': AZURE_SEARCH_KEY}
    params = {'api-version': AZURE_SEARCH_API_VERSION}

    agg_search_results = []
    for index in indexes:
        url = AZURE_SEARCH_ENDPOINT + '/indexes/'+ index + '/docs'
        url += '?api-version={}'.format(AZURE_SEARCH_API_VERSION)
        url += '&search={}'.format(query)
        url += '&select=*'
        url += '&$top=5'  # You can change this to anything you need/want
        url += '&queryLanguage=en-us'
        url += '&queryType=semantic'
        url += '&semanticConfiguration=my-semantic-config'
        url += '&$count=true'
        url += '&speller=lexicon'
        url += '&answers=extractive|count-3'
        url += '&captions=extractive|highlight-false'

        resp = requests.get(url, headers=headers)
        print(url)
        print(resp.status_code)

        search_results = resp.json()
        agg_search_results.append(search_results)
    
    return agg_search_results
    

st.set_page_config(page_title="GPT Smart Search", page_icon="📖", layout="wide")
st.header("GPT Smart Search Engine")

sidebar()



with st.expander("Instructions"):
    st.markdown("""
                Ask a question that you think can be answered with the information in about 10k Arxiv Computer Science publications from 2020-2021.
                
                For example:
                - What are markov chains?
                - List the authors that talk about Gradient Boosting Machines
                - What is CLP?
                - How does random forest work?
                - Give me an example of a Reinforcement learning problem
                - What kind of problems Turing Machines solve?
                
                You will notice that the answers to these questions are diferent from the open ChatGPT, since these papers are the only possible context. This search engine does not look at the open internet to answer these questions. If the context doesn't contain information, the engine will respond: I don't know.
                
                - Quick Answer: GPT model only uses, as context, the captions of the results coming from Azure Search
                - Best Answer: GPT model uses, as context. all of the content of the documents coming from Azure Search
                """)

query = st.text_area("Ask a question to your enterprise data lake", value= "What is CLP?", on_change=clear_submit)

# options = ['English', 'Spanish', 'Portuguese', 'French', 'Russian']
# selected_language = st.selectbox('Answer Language:', options, index=0)


col1, col2, col3 = st.columns([1,1,3])
with col1:
    qbutton = st.button('Quick Answer')
with col2:
    bbutton = st.button('Best Answer')

if qbutton or bbutton or st.session_state.get("submit"):
    if not query:
        st.error("Please enter a question!")
    else:
        # Azure Search
        
        index1_name = "cogsrch-index-files"
        index2_name = "cogsrch-index-csv"
        indexes = [index1_name, index2_name]
        agg_search_results = get_search_results(query, indexes)

        file_content = OrderedDict()
                    
        for search_results in agg_search_results:
            for result in search_results['value']:
                if result['@search.rerankerScore'] > 0.4: # Show results that are at least 10% of the max possible score=4
                    file_content[result['id']]={
                                            "content": result['pages'],  # result['chunks'] can be used here as well
                                            "caption": result['@search.captions'][0]['text'],
                                            "score": result['@search.rerankerScore'],
                                            "location": result['metadata_storage_path']                  
                                        }

        
        st.session_state["submit"] = True
        # Output Columns
        placeholder = st.empty()
        
        try:
            docs = []
            for key,value in file_content.items():
                
                if qbutton:
                    docs.append(Document(page_content=value['caption'], metadata={"source": value["location"]}))
                    add_text = "Coming up with a quick answer... ⏳"
                
                if bbutton:
                    for page in value["content"]:
                        docs.append(Document(page_content=page, metadata={"source": value["location"]}))
                    add_text = "Reading the source documents to provide the best answer... ⏳"
                
            if "add_text" in locals():
                with st.spinner(add_text):
                    if(len(docs)>1):
                        index = embed_docs(docs)
                        sources = search_docs(index,query)
                        if qbutton:
                            answer = get_answer(sources, query, deployment="gpt-35-turbo", chain_type = "stuff", temperature=0.3, max_tokens=256)
                        if bbutton: 
                            answer = get_answer(sources, query, deployment="gpt-35-turbo", chain_type = "map_reduce", temperature=0.3, max_tokens=500)

                    else:
                        answer = {"output_text":"No results found" }
            else:
                answer = {"output_text":"No results found" }


            with placeholder.container():
                st.markdown("#### Answer")
                st.markdown(answer["output_text"].split("SOURCES:")[0])
                st.markdown("Sources:")
                for s in answer["output_text"].split("SOURCES:")[1].replace(" ","").split(","):
                    st.markdown(s) 
                st.markdown("---")
                st.markdown("#### Search Results")

                if(len(docs)>1):
                    for key, value in file_content.items():
                        st.markdown(value["location"] + '  (Score: ' + str(round(value["score"]*100/4,2)) + '%)')
                        st.markdown(value["caption"])
                        st.markdown("---")

        except OpenAIError as e:
            st.error(e._message)
            st.error(e._status_code)
