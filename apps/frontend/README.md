<h1 align="center">
Frontend Web Application - Search + Web Bot Channel
</h1>

Simple UI using Streamlit to expose the Bot Service Channel.
Also includes a Search experience.
 
## Deploy in Azure Web App Service

1. Deploy the Frontend Azure Web Application by clicking the Button below

[![Deploy To Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpablomarin%2FGPT-Azure-Search-Engine%2Fmain%2Fapps%2Ffrontend%2Fazuredeploy-frontend.json)

2. Zip the code of the bot by executing the following command in the terminal (you have to be inside the folder: apps/frontend/ ):

```bash
(zip frontend.zip ./app/* ./app/pages/* ./app/helpers/* && zip -j frontend.zip ../../common/*) && (cd ../../ && zip -r apps/frontend/frontend.zip common)
```

3. Using the Azure CLI deploy the frontend code to the Azure App Service created on Step 2

```bash
az login -i
az webapp deployment source config-zip --resource-group "<resource-group-name>" --name "<name-of-frontend-app-service>" --src "frontend.zip"
```

**Note**: Some FDPO Azure Subscriptions disable Azure Web Apps Basic Authentication every minute (don't know why). So before running the above `az webapp deployment` command, make sure that your frontend azure web app has Basic Authentication ON. In the Azure Portal, you can find this settting in: `Configuration->General Settings`. Don't worry if after running the command it says retrying many times, the zip files already uploaded and is building.

4. In a few minutes (5-10) your App should be working now. Go to the Azure Portal and get the URL.

## (Optional) Running the Frontend app Locally

- Run the followin comand on the console to export the env variables (at the /frontend folder level)
```bash
export FAST_API_SERVER = "<your-fastAPI-server-url>"
export $(grep -v '^#' ../../credentials.env | sed -E '/^\s*$/d;s/#.*//' | xargs)
```
- Run the stramlit server on port 8500
```bash
python -m streamlit run app/Home.py --server.port 8500 --server.address 0.0.0.0
```
- If you are working on an AML compute instance you can accces the frontend here:
```bash
https://<your_compute_name>-8500.<your_region>.instances.azureml.ms/
```


## Troubleshoot

1. If WebApp deployed succesfully but the Application didn't start
   1. Go to Azure portal -> Your Webapp -> Settings -> Configuration -> General Settings
   2. Make sure that StartUp Command has:  python -m streamlit run Home.py --server.port 8000 --server.address 0.0.0.0







