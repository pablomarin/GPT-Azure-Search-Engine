import streamlit as st
from components.sidebar import sidebar
from openai.error import OpenAIError
from langchain.docstore.document import Document
from langchain.chains import VectorDBQAWithSourcesChain
from langchain.llms import AzureOpenAI
from langchain.vectorstores import FAISS
from embeddings import OpenAIEmbeddings
from prompts import STUFF_PROMPT
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
import urllib
import os
import requests
from IPython.display import display, HTML
from collections import OrderedDict


def clear_submit():
    st.session_state["submit"] = False


st.set_page_config(page_title="GPT Smart Search", page_icon="📖", layout="wide")
st.header("GPT Smart Search Engine")

sidebar()

# uploaded_file = st.file_uploader(
#     "Upload a pdf, docx, or txt file",
#     type=["pdf", "docx", "txt"],
#     help="Scanned documents are not supported yet!",
#     on_change=clear_submit,
# )

# index = None
# doc = None
# if uploaded_file is not None:
#     if uploaded_file.name.endswith(".pdf"):
#         doc = parse_pdf(uploaded_file)
#     elif uploaded_file.name.endswith(".docx"):
#         doc = parse_docx(uploaded_file)
#     elif uploaded_file.name.endswith(".txt"):
#         doc = parse_txt(uploaded_file)
#     else:
#         raise ValueError("File type not supported!")
#     text = text_to_docs(doc)
#     try:
#         with st.spinner("Indexing document... This may take a while⏳"):
#             index = embed_docs(text)
#     except OpenAIError as e:
#         st.error(e._message)

api_version = '2021-04-30-Preview'
endpoint = "https://azure-cog-search-pabdyosydd7ta.search.windows.net"
api_key = "DDDUwtXOCSOjm1fPBRLNFofKEEvxXDpGF0Sy4S3ktjAzSeAgbz9Q"
index_name = "cogsrch-index"
api_version = '2021-04-30-Preview'

os.environ["OPENAI_API_KEY"] = os.environ["AZURE_OPENAI_API_KEY"] = st.session_state["AZURE_OPENAI_API_KEY"] = "48e3114b81d1430eb1f3df7fb783f176"
os.environ["AZURE_OPENAI_ENDPOINT"] = st.session_state["AZURE_OPENAI_ENDPOINT "] = "https://pablo.openai.azure.com/"

headers = {'Content-Type': 'application/json','api-key': api_key}
params = {'api-version': api_version}

query = st.text_area("Ask a question to your enterprise data lake", on_change=clear_submit)
button = st.button("Submit")

if button or st.session_state.get("submit"):
    if not query:
        st.error("Please enter a question!")
    else:
        
        url = endpoint + '/indexes/'+ index_name + '/docs'
        url += '?api-version={}'.format(api_version)
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
            if result['@search.rerankerScore'] > 0.3:
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
                for page in value["content"]:
                    docs.append(Document(page_content=page, metadata={"source": key}))
            
            with st.spinner("Comming up with an answer... ⏳"):
                if(len(docs)>1):
                    db = FAISS.from_documents(docs, OpenAIEmbeddings(document_model_name='text-embedding-ada-002'))
                    chain = VectorDBQAWithSourcesChain.from_chain_type(AzureOpenAI(deployment_name="text-davinci-003", model_name="text-davinci-003", temperature=0),chain_type="stuff", vectorstore=db, chain_type_kwargs = {"prompt":STUFF_PROMPT})
                    answer = chain({"question": query})
                else:
                    answer = {"answer":"No results found", "sources":"" }
                # index = embed_docs(docs)
                # sources = search_docs(index,query)
                # answer = get_answer(sources, query)
                

            with placeholder.container():
                st.markdown("#### Answer")
                # st.markdown(answer["output_text"].split("SOURCES: ")[0])
                st.markdown(answer["answer"])
                st.markdown('sources: ' + answer["sources"])
                st.markdown("---")
                st.markdown("#### Sources")
                
                if(len(docs)>1):
                    for key, value in file_content.items():
                        st.markdown(key + '  (Score: ' + str(round(value["score"],2)*100/4) + '%)')
                        st.markdown(value["caption"])
                        st.markdown("---")

        except OpenAIError as e:
            st.error(e._message)
