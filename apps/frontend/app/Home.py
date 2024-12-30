import streamlit as st

st.set_page_config(page_title="GPT Smart Search", page_icon="📖", layout="wide")

st.image("https://user-images.githubusercontent.com/113465005/226238596-cc76039e-67c2-46b6-b0bb-35d037ae66e1.png")

st.header("MSUS OpenAI Accelerator VBD - Web Frontend")


st.markdown("---")
st.markdown("""
    This engine finds information from the following:
    - The entire Dialog from each episode and season of the TV Show "FRIENDS"
    - ~90k [COVID-19 research articles from the CORD19 dataset](https://github.com/allenai/cord19)
    - [Covid Tracking Project Dataset](https://covidtracking.com/). Azure SQL with information of Covid cases and hospitalizations in the US from 2020-2021.
    - 5 Books: "Azure_Cognitive_Search_Documentation.pdf", "Boundaries_When_to_Say_Yes_How_to_Say_No_to_Take_Control_of_Your_Life.pdf", "Fundamentals_of_Physics_Textbook.pdf", "Made_To_Stick.pdf", "Pere_Riche_Pere_Pauvre.pdf" (French version of Rich Dad Poor Dad).
    - [Kraken API](https://docs.kraken.com/rest/#tag/Market-Data). This API provides real-time data for currency and digital coins pricing. 
    
    **👈 Select a demo from the sidebar** to see an example of a Search Interface, and a Bot Interface.

    ### Want to learn more?
    - Check out [Github Repo](https://github.com/MSUSAzureAccelerators/Azure-Cognitive-Search-Azure-OpenAI-Accelerator/)
    - Ask a question or submit a [GitHub Issue!](https://github.com/MSUSAzureAccelerators/Azure-Cognitive-Search-Azure-OpenAI-Accelerator/issues/new)


"""
)
st.markdown("---")
