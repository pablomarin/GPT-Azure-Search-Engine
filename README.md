# GPT-Azure-Search-Engine
Azure Cognitive Search + Azure OpenAI Accelerator

0- Dataset: ~10k pdfs from the Arxiv dataset, specifically computer science
https://www.kaggle.com/datasets/Cornell-University/arxiv

1- OPTIONAL: Copy the dataset from GCP cloud to your azure blob storage using this command (you will need a GCP free account)
```
azcopy copy 'https://storage.cloud.google.com/arxiv-dataset/arxiv/cs/pdf/*' 'https://<YOUR_BLOB_NAME?.blob.core.windows.net/<YOUR_CONTAINTER_NAME> --recursive=true
```

2- Create a Resource Group were all the assets of this accelerator are going to be.

3- Create an Azure Cognitive Search Service and Cognitive Services Account by clicking below: (this process takes about 15 mins) <br>
[![Deploy To Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpablomarin%2FGPT-Azure-Search-Engine%2Fmain%2Fazuredeploy.json)

4- Enable Semantic Search on your Azure Cognitive Search Service: 
- On the left-nav pane, select Semantic Search (Preview).
- Select either the Free plan or the Standard plan. You can switch between the free plan and the standard plan at any time.


5-Load data into Search Engine and create the index with AI skills, by running this notebook:<br>
01-Load-Data-ACogSearch.ipynb



