# GPT-Azure-Search-Engine
Azure Cognitive Search + Azure OpenAI Accelerator

![Architecture](GPT-Smart-Search-Architecture.jpg "Architecture")


***Steps to run the Accelerator***:

_Note: (Pre-requisite) You need have an Azure OpenAI service already created._

1- Create a Resource Group were all the assets of this accelerator are going to be.

3- Create an Azure Cognitive Search Service and Cognitive Services Account by clicking below: <br>
[![Deploy To Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpablomarin%2FGPT-Azure-Search-Engine%2Fmain%2Fazuredeploy.json) 

_Note: If you have never created a cognitive multi-service account before, please create one manually in the azure portal to read and accept the Responsible AI terms. Once this is deployed, delete this and then use the above deployment button._

4- Enable Semantic Search on your Azure Cognitive Search Service: 
- On the left-nav pane, select Semantic Search (Preview).
- Select either the Free plan or the Standard plan. You can switch between the free plan and the standard plan at any time.

5- Install the dependendies on your machine:
```
pip install -r ./requirements.txt
```
6- Edit app/credentials.py with your environment information

7- Load data into your Search Engine and create the index with AI skills, by running this notebook:<br>
01-Load-Data-ACogSearch.ipynb

8- Run 02-Quering-AOpenAI.ipynb  and see queries directly from Azure Cognitive Search and how they compare with enhancing the experience with Azure OpenAI

9- Go to the app/ folder and click the Deploy to Azure function to deploy the App. It takes a few minutes.


