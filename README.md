# GPT-Azure-Search-Engine
Azure Cognitive Search + Azure OpenAI Accelerator

0- Dataset: ~10k pdfs from the Arxiv dataset, specifically computer science
https://www.kaggle.com/datasets/Cornell-University/arxiv

1- Create a Resource Group were all the assets of this accelerator are going to be.

3- Create an Azure Cognitive Search Service and Cognitive Services Account by clicking below: (this process takes about 15 mins) <br>
[![Deploy To Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpablomarin%2FGPT-Azure-Search-Engine%2Fmain%2Fazuredeploy.json) 

_Note: If you have never created a cognitive service before, please create one manually to read and accept the Responsible AI terms. Once this is deployed, delete this and then use the above deployment button._

4- Enable Semantic Search on your Azure Cognitive Search Service: 
- On the left-nav pane, select Semantic Search (Preview).
- Select either the Free plan or the Standard plan. You can switch between the free plan and the standard plan at any time.

5- Install the dependendies on your machine:

'''
pip install -r ./requirements.txt
'''

5- Load data into Search Engine and create the index with AI skills, by running this notebook:<br>
01-Load-Data-ACogSearch.ipynb

6- Run 02-Quering-AOpenAI.ipynb  and see queries directly from Azure Cognitive Search and how they compare with enhancing the experience with Azure OpenAI

7- Go to the App/ folder and Cling the Deploy to Azure function to deploy the App. It takes a few minutes.


