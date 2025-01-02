<h1 align="center">
Backend Web Application - FastAPI 
</h1>

## Deploy Bot To Azure Web App

Below are the steps to run the FastAPI Bot API as an Azure Wep App:

1. We don't need to deploy again the Azure infrastructure, we did that already for the Bot Service API (Notebook 13). We are going to use the same App Service, but we just need to add another SLOT to the service and have both APIs running at the same time. Note: the slot can have any name, we are using "staging".<br> In the terminal run:

```bash
az login -i
az webapp deployment slot create --name "<name-of-backend-app-service>" --resource-group "<resource-group-name>" --slot staging --configuration-source "<name-of-backend-app-service>"
```

2. Zip the code of the bot by executing the following command in the terminal (**you have to be inside the apps/backend/fastapi/ folder**):

```bash
(cd ../../../ && zip -r apps/backend/fastapi/backend.zip common data/openapi_kraken.json data/all-states-history.csv) && zip -j backend.zip ../../../common/requirements.txt app/*
```

3. Using the Azure CLI deploy the bot code to the Azure App Service new SLOT created on Step 1:

```bash
az webapp deployment source config-zip --resource-group "<resource-group-name>" --name "<name-of-backend-app-service>" --src "backend.zip" --slot staging
```

4. Wait around 5 minutes and test your bot by running Notebook 15. Your Swagger (OpenAPI) definition should show here:

```html
https://<name-of-backend-app-service>-staging.azurewebsites.net/
```

<br><br>

## (Optional) Run the FastAPI server Locally

You can also run the server locally for testing.

### **Steps to Run Locally:**

1. Open `apps/backend/fastapi/app/server.py` and uncomment the following section:
```python
## Uncomment this section to run locally
# current_file = Path(__file__).resolve()
# library_path = current_file.parents[4]
# data_path = library_path / "data"
# sys.path.append(str(library_path))   # ensure we can import "common" etc.
# load_dotenv(str(library_path) + "/credentials.env")
# csv_file_path = data_path / "all-states-history.csv"
# api_file_path = data_path / "openapi_kraken.json"

```
2. Open a terminal, activate the right conda environment, then go to this folder `apps/backend/fastapi/app` and run this command:
    
```bash
python server.py
```

This will run the backend server API in localhost port 8000. 

3. If you are working on an Azure ML compute instance you can access the OpenAPI (Swagger) definition in this address:

    https:\<your_compute_name\>-8000.\<your_region\>.instances.azureml.ms/
    
    for example:
    https://pabmar1-8000.australiaeast.instances.azureml.ms/


