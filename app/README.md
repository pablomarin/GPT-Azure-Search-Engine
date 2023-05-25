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
export DATASOURCE_SAS_TOKEN=<Enter your value>
export BING_SUBSCRIPTION_KEY=<Enter your value>
export SQL_SERVER_ENDPOINT=<Enter your value>
export SQL_SERVER_DATABASE=<Enter your value>
export SQL_SERVER_USERNAME=<Enter your value>
export SQL_SERVER_PASSWORD=<Enter your value>
export BING_SUBSCRIPTION_KEY=<Enter your value>
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

[![Deploy To Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpablomarin%2FGPT-Azure-Search-Engine%2Fmain%2Fapp%2Fazuredeploy.json)

### Deploy via Github

1. Make Sure that once the ARM template is ready to be created in the Azure portal, you change the ***Repo Url*** variable to your own repo:
"https://github.com/<YOUR_GITHUB_NAME>/GPT-Azure-Search-Engine.git"

2. Once the deployment is done, go to **Azure Portal -> Your Web App Service -> Settings -> Configuration -> Application Settings** and set the values of the enviromental variables needed. **Don't forget to click the SAVE button on the top**.

3. Your App should be working now.


### [Local Git deployment to Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/deploy-local-git?tabs=cli)

1. In the Azure portal, navigate to your app's management page. 
2. From the left menu, select Deployment Center > Settings. Select Local Git in Source, then click Save.

![Shows how to enable local Git deployment for App Service in the Azure portal](https://learn.microsoft.com/en-us/azure/app-service/media/deploy-local-git/enable-portal.png)

3. In the Local Git section, copy the Git Clone Uri for later. This Uri doesn't contain any credentials.
4. In a local terminal window, change the directory to the root of your Git repository, and add a Git remote using the URL you got from your app. If your chosen method doesn't give you a URL, use https://<app-name>.scm.azurewebsites.net/<app-name>.git with your app name in <app-name>.
```bash
git remote add azure <url>
```
5. Push to the Azure remote with ```bash
git push azure master```.
6. In the Git Credential Manager window, enter your user-scope or application-scope credentials, not your Azure sign-in credentials.
7. If your Git remote URL already contains the username and password, you won't be prompted.
8. Review the output. You may see runtime-specific automation, such as MSBuild for ASP.NET, npm install for Node.js, and pip install for Python.
9. Browse to your app in the Azure portal to verify that the content is deployed.

## [Docker deployment to Azure Container Instance]([https://learn.microsoft.com/en-us/azure/app-service/deploy-local-git?tabs=cli](https://learn.microsoft.com/en-us/azure/container-instances/container-instances-tutorial-deploy-app))
1. Test app locally
2. Dockerize your Streamlit App
3. Push to Azure Container Registry 
4. Create Container Instance

## Troubleshoot

1. If WebApp deployed succesfully but the Application didn't start
   1. Go to Azure portal -> Your Webapp -> Settings -> Configuration -> General Settings
   2. Make sure that StartUp Command has:  python -m streamlit run app/Home.py --server.port 8000 --server.address 0.0.0.0

2. If running locally fails with error "TypeError: unsupported operand type(s) for |: 'type' and '_GenericAlias'"
Check your list of conda environments and activate one with Python 3.10 or higher
For example, if you are running the app on an Azure ML compute instance:
    ```
    conda env list
    conda activate azureml_py310_sdkv2
    ```

3. If running locally and in Tabular Demo (preview) page you get this error: `AxiosError: Request failed with status code 403` when trying to upload the documment, do this in the shell
    
    ```bash
    mkdir -p ~/.streamlit/
    echo "\
    [server]\n\
    headless = true\n\
    port = 8501\n\
    enableXsrfProtection=false\n\
    enableCORS = false\n\
    \n\
    " > ~/.streamlit/config.toml
    ```
    
4. If deployment fails with error "Cannot find SourceControlToken with name Github" you can try the following
    1. Wait 20 mins and Retry
    2. Delete the browser cache and retry
    3. Go to the deployed WebApp and Authorize azure to deploy and build code directly from Github 

    ![Authorize Github](../images/error-authorize-github.jpeg "Authorize Github" )





