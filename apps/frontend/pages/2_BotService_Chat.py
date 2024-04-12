import os
import streamlit as st
import streamlit.components.v1 as components

# From here down is all the StreamLit UI.
st.set_page_config(page_title="BotService Backend Bot", page_icon="🤖", layout="wide")
# Add custom CSS styles to adjust padding
st.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                }
        </style>
        """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("""# Instructions""")
    st.markdown("""

This Chatbot is hosted in an independent Backend Azure Web App and was created using the Bot Framework SDK.
The Bot Interface is just a window to a Bot Service app hosted in Azure.

It has access to the following tools/pluggins:

- Bing Search (***use @bing in your question***)
- ChatGPT for common knowledge (***use @chatgpt in your question***)
- Azure SQL for covid statistics data (***use @sqlsearch in your question***)
- Azure Search for documents knowledge - Arxiv papers and Covid Articles (***use @docsearch in your question***)
- Azure Search for books knowledge - 5 PDF books (***use @booksearch in your question***)
- API Search for real-time covid statistics for US States, Countries and Continents (***use @apisearch in your question***)

Note: If you don't use any of the tool names beginning with @, the bot will try to use it's own knowledge or tool available to answer the question.

Example questions:

- Hello, my name is Bob, what's yours?
- @bing, What's the main economic news of today?
- @chatgpt, How do I cook a chocolate cake?
- @booksearch, what normally rich dad do that is different from poor dad?
- @docsearch, Why Covid doesn't affect kids that much compared to adults?
- @apisearch, What is the state with most covid deaths in USA?
- @sqlsearch, How many people where hospitalized in Arkansas in June 2020?
- @docsearch, List the authors that talk about Boosting Algorithms
- @bing, what movies are showing tonight in Seattle?
- Please tell me a joke
    """)

st.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                }
        </style>
        """, unsafe_allow_html=True)


BOT_DIRECTLINE_SECRET_KEY = os.environ.get("BOT_DIRECTLINE_SECRET_KEY")

components.html(
f"""
<html>
  <head>
    <script
      crossorigin="anonymous"
      src="https://cdn.botframework.com/botframework-webchat/latest/webchat.js"
    ></script>
    <script crossorigin="anonymous" src="https://unpkg.com/markdown-it@10.0.0/dist/markdown-it.min.js"></script>
     <style>
      html,
      body {{
          height: 100%;
          background-image: linear-gradient( #343541,#525468);
          color: antiquewhite;
          font-family: 'Segoe UI', Calibri, sans-serif;
      }}

      body {{
        padding-left: 5px;
      }}

      #webchat {{
        height: 85%;
        width: 100%;
      }}
      .webchat__stacked-layout--from-user{{
        background-color: rgba(32,33,35, .2);
      }}
      
    </style>
  </head>
  <body>
    <h1><img src='https://logos-world.net/wp-content/uploads/2021/02/Microsoft-Azure-Emblem.png' height="40">Bot Service + Azure OpenAI</h1> 
    <div id="webchat" role="main"></div>
    <script>
      // Set  the CSS rules.
      const styleSet = window.WebChat.createStyleSet({{
          bubbleBackground: 'transparent',
          bubbleBorderColor: 'darkslategrey',
          bubbleBorderRadius: 5,
          bubbleBorderStyle: 'solid',
          bubbleBorderWidth: 0,
          bubbleTextColor: 'antiquewhite',

          userAvatarBackgroundColor: 'rgba(53, 55, 64, .3)',
          bubbleFromUserBackground: 'transparent', 
          bubbleFromUserBorderColor: '#E6E6E6',
          bubbleFromUserBorderRadius: 5,
          bubbleFromUserBorderStyle: 'solid',
          bubbleFromUserBorderWidth: 0,
          bubbleFromUserTextColor: 'antiquewhite',

          notificationText: 'white',

          bubbleMinWidth: 400,
          bubbleMaxWidth: 720,

          botAvatarBackgroundColor: 'antiquewhite',
          avatarBorderRadius: 2,
          avatarSize: 40,

          rootHeight: '100%',
          rootWidth: '100%',
          backgroundColor: 'rgba(70, 130, 180, .2)',

          hideUploadButton: 'true'
      }});
      // After generated, you can modify the CSS rules.
      // Change font family and weight. 
      styleSet.textContent = {{
          ...styleSet.textContent,
          fontWeight: 'regular'
      }};

      // Set the avatar options. 
      const avatarOptions = {{
          botAvatarInitials: '.',
          userAvatarInitials: 'Me',
          botAvatarImage: 'https://dwglogo.com/wp-content/uploads/2019/03/1600px-OpenAI_logo-1024x705.png',
          
          }};
      const markdownIt = window.markdownit({{html:true}});
      window.WebChat.renderWebChat(
        {{
          directLine: window.WebChat.createDirectLine({{
            token: '{BOT_DIRECTLINE_SECRET_KEY}'
          }}),
          renderMarkdown: markdownIt.render.bind(markdownIt),
          styleSet, styleOptions: avatarOptions,
          locale: 'en-US'
        }},
        document.getElementById('webchat')
      );
    </script>
  </body>
</html>
""", height=800)
