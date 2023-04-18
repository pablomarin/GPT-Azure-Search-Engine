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
2. Set the environmental variales needed by the app
```bash
export AZURE_SEARCH_ENDPOINT=<Enter your value>
export AZURE_SEARCH_KEY=<Enter your value>
export AZURE_OPENAI_ENDPOINT=<Enter your value>
export AZURE_OPENAI_API_KEY=<Enter your value>
```
3. Run the Streamlit server🚀
```bash
cd app
streamlit run Home.py
```
4. If you are working on an Azure ML compute instance, go to:<br>
https://{Your-AMLCompute-Name}-{port}.{your-region}.instances.azureml.ms/ 
  
Example: https://myComputeInstance-8501.southcentralus.instances.azureml.ms/ 
 
## To Deploy in Azure Web App Service

### Deploy via Github
[![Deploy To Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpablomarin%2FGPT-Azure-Search-Engine%2Fmain%2Fapp%2Fazuredeploy.json)

1. Make Sure that once the ARM template is ready to be created in the Azure portal, you change the ***Repo Url*** variable to your own repo:
"https://github.com/<YOUR_GITHUB_NAME>/GPT-Azure-Search-Engine.git"

2. Once the deployment is done, go to **Azure Portal -> Your Web App Service -> Settings -> Congiguration -> Application Settings** and set the values of the enviromental variables needed. **Don't forget to click the SAVE button on the top**.

3. Your App should be working now.

4. Everytime you commit changes to your branch it will kick in CI/CD and deploy your changes to the web app

### Deploy from local Git Repo
1. Follow steps 1 and 2 from <b>Deploy via Github</b>
2. [Local Git deployment to Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/deploy-local-git?tabs=cli)


## Troubleshoot

- If WebApp deployed succesfully but the Application didn't start
1. Go to Azure portal -> Your Webapp -> Settings -> Configuration -> General Settings
2. Make sure that StartUp Command has:  python -m streamlit run app/Home.py --server.port 8000 --server.address 0.0.0.0

- If deployment fails with error "Cannot find SourceControlToken with name Github" you can try the following
1. Wait 20 mins and Retry
2. Delete the browser cache and retry
3. Go to the deployed WebApp and Authorize azure to deploy and build code directly from Github 

![Authorize Github](../images/error-authorize-github.jpeg "Authorize Github" )

- If running locally fails with error "TypeError: unsupported operand type(s) for |: 'type' and '_GenericAlias'"
Check your list of conda environments and activate one with Python 3.10 or higher
For example, if you are running the app on an Azure ML compute instance:
```
conda env list
conda activate azureml_py310_sdkv2
```




