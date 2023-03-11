<h1 align="center">
GPT Smart Search
</h1>

Accurate answers and instant citations from documents in your Azure Data Lake.

## 🔧 Features

- Queries Azure Cognitive Search and uses OpenAI to provide an acurate answer.
- Translate the answer in any language
- Provides a Quick Answer and a Best Answer

## 💻 To run it Locally
1. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the Streamlit server🚀

```bash
cd App
streamlit run main.py
```

# To Deploy in Azure Web App Service

[![Deploy To Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpablomarin%2FGPT-Azure-Search-Engine%2Fmain%2FApp%2Fazuredeploy.json)

1. Make Sure that once the ARM template is ready to be created you change the Variable:
"https://github.com/<YOUR_GITHUB_NAME>/GPT-Azure-Search-Engine.git" to your own repo

2. Everytime you commit changes to your branch it will kick in CI/CD and deploy your changes to the web app

