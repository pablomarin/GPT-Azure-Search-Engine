import streamlit as st
from components.sidebar import sidebar
from openai.error import OpenAIError
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


def clear_submit():
    st.session_state["submit"] = False


st.set_page_config(page_title="GPT Smart Search", page_icon="📖", layout="wide")
st.header("Smart Search GPT")

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

query = st.text_area("Ask a question about the document", on_change=clear_submit)
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

        file_content = dict()
        for result in search_results['value']:
            if result['@search.rerankerScore'] > 0.3:
                file_content[result['metadata_storage_path']]=result['pages']

        
        st.session_state["submit"] = True
        # Output Columns
        placeholder = st.empty
        placeholder.empty()
        
        try:
            docs = []
            for key,value in file_content.items():
                for page in value:
                    docs.append(Document(page_content=page, metadata={"source": key}))
            
            with st.spinner("Comming up with an answer... ⏳"):
                index = embed_docs(docs)
                sources = search_docs(index,query)
                answer = get_answer(sources, query)
                sources = get_sources(answer, docs)

            with placeholder.container():
                st.markdown("#### Answer")
                st.markdown(answer["output_text"].split("SOURCES: ")[0])
                st.markdown("---")
                st.markdown("#### Sources")
                for source in sources:
                    st.markdown(source.metadata["source"])
                    st.markdown(source.page_content)
                    st.markdown("---")

        except OpenAIError as e:
            st.error(e._message)
