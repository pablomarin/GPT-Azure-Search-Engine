# GPT-Azure-Search-Engine
Azure Cognitive Search + Azure OpenAI Accelerator

0- Dataset: ~10k pdfs from the Arxiv dataset, specifically computer science
https://www.kaggle.com/datasets/Cornell-University/arxiv

1- Copy the dataset from GCP cloud to your azure blob storage using this command (you will need a GCP free account)
```
azcopy copy 'https://storage.cloud.google.com/arxiv-dataset/arxiv/cs/pdf/*' 'https://<YOUR_BLOB_NAME?.blob.core.windows.net/<YOUR_CONTAINTER_NAME> --recursive=true
```
2- Create an Azure Cognitive Search Service clicking below
[![Deploy To Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpablomarin%2FGPT-Azure-Search-Engine%2Fmain%2Fazuredeploy.json)

3-

