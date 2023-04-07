import streamlit as st
import os
import pandas as pd
from langchain.llms import AzureOpenAI
from langchain.chat_models import AzureChatOpenAI
from langchain.agents import create_pandas_dataframe_agent
from langchain.agents import create_csv_agent


def sidebar():
    with st.sidebar:
        st.markdown("""# Instructions""")
        st.markdown("---")
        st.markdown("""
            **GPT GPT Tabular data Q&A** allows you to ask questions to your Tabular CSV files.
        """
        )
        st.markdown("**Note**: GPT-4 is in preview and with limited availability. There is a lot of limitation on the API, so it takes longer than needed and it fails some times. Retry if it fails.")
        st.markdown("---")
        
        st.session_state["AZURE_OPENAI_GPT4_NAME"] = st.text_input("Enter your GPT-4 deployment name:")
        st.session_state["AZURE_OPENAI_ENDPOINT"] = st.text_input("Enter your Azure OpenAI Endpoint:")
        st.session_state["AZURE_OPENAI_API_KEY"] = st.text_input("Enter Azure OpenAI Key:", type="password")
                
preffix = 'First set the pandas display options to show all the columns, then get the column names, then answer the question: '
suffix = '. ALWAYS before giving the Final Answer, reflect on the answer and ask yourself if it answers correctly the original question. If you are not sure, try another method. \n If the two runs does not give the same result, reflect again two more times until you have two runs that have the same result. If you still cannot arrive to a consistent result, say that you are not sure of the answer. But, if you are sure of the correct answer, create a beautiful and thorough response. ALWAYS, as part of your final answer, explain how you got to the answer. Format the final answer in Markdown language'

max_retries = 5

st.set_page_config(page_title="GPT Tabular data Q&A", page_icon="📖", layout="wide")
st.header("GPT Tabular data Q&A (preview)")

sidebar()

def clear_submit():
    st.session_state["submit"] = False
    
    
# col1, col2 = st.columns([1,1])
# with col1:
#     uploaded_file  = st.file_uploader(label = "Upload your tabular CSV file", type="csv", accept_multiple_files=False, key=None, help="Upload your CSV file that contains tabular data, make sure that the first row corresponds to the columns", on_change=None, disabled=False)
# with col2:
#     st.markdown("Or pick from these sample datasets:")
#     st.markdown("[Covid Tracking Project](https://learn.microsoft.com/en-us/azure/open-datasets/dataset-covid-tracking?tabs=azure-storage) ")
#     ingest_button = st.button("Load Sample CSV") # Give button a variable name

# if ingest_button: # Make button a condition.
#     uploaded_file = "https://pandemicdatalake.blob.core.windows.net/public/curated/covid-19/covid_tracking/latest/covid_tracking.csv"

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("Here is the first two rows of your file:", df.head(2))
    
    query_str = st.text_input("Ask a question:", on_change=clear_submit)

    qbutton = st.button('Generate Answer')


    if (qbutton or st.session_state.get("submit")) and uploaded_file:
        if not query_str:
            st.error("Please enter a question")
        else:
            st.session_state["submit"] = True
            placeholder = st.empty()
            
            if not st.session_state.get("AZURE_OPENAI_ENDPOINT"):
                st.error("Please set your Azure OpenAI API Endpoint on the side bar!")
            elif not st.session_state.get("AZURE_OPENAI_API_KEY"):
                st.error("Please configure your Azure OpenAI API key on the side bar!")
            elif not st.session_state.get("AZURE_OPENAI_GPT4_NAME"):
                st.error("Please configure your GPT-4 Deployment Name in the sidebar") 
            
            else:
                
                os.environ["OPENAI_API_BASE"] = os.environ["AZURE_OPENAI_ENDPOINT"] = st.session_state["AZURE_OPENAI_ENDPOINT"]
                os.environ["OPENAI_API_KEY"] = os.environ["AZURE_OPENAI_API_KEY"] = st.session_state["AZURE_OPENAI_API_KEY"]
                os.environ["OPENAI_API_VERSION"] = os.environ["AZURE_OPENAI_API_VERSION"] = "2023-03-15-preview"
                
                llm = AzureChatOpenAI(deployment_name=st.session_state["AZURE_OPENAI_GPT4_NAME"], temperature=0.5, max_tokens=999)
                agent = create_pandas_dataframe_agent(llm, df, verbose=True)


                try:
                    
                    with st.spinner("Coming up with an answer... ⏳"):
                        for i in range(max_retries):
                            try:
                                response = agent.run(preffix + query_str + suffix) 
                                break
                            except:
                                response = "Error too many failed retries - GPT-4 still in preview and just for testing"
                                continue  


                    with placeholder.container():
                        st.markdown("#### Answer")
                        st.markdown(response.replace("$","\$"))

                except Exception as e:
                    st.error(e)