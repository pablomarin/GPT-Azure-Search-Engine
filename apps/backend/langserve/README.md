<h1 align="center">
Backend Web Application - LangServe FastAPI 
</h1>

This bot has been created using [LangServe](https://python.langchain.com/docs/langserve)

## Deploy Bot To Azure Web App

Below are the steps to run the LangServe Bot API as an Azure Wep App:

1. We don't need to deploy again the Azure infrastructure, we did that already for the Bot Service API (Notebook 12). We are going to use the same App Service, but we just need to add another SLOT to the service and have both APIs running at the same time. Note: the slot can have any name, we are using "staging".<br> In the terminal run:

```bash
az login -i
az webapp deployment slot create --name "<name-of-backend-app-service>" --resource-group "<resource-group-name>" --slot staging --configuration-source "<name-of-backend-app-service>"
```

2. Zip the code of the bot by executing the following command in the terminal (**you have to be inside the apps/backend/langserve/ folder**):

```bash
(cd ../../../ && zip -r apps/backend/langserve/backend.zip common) && zip -j backend.zip ./* && zip -j backend.zip ../../../common/requirements.txt && zip -j backend.zip app/*
```

3. Using the Azure CLI deploy the bot code to the Azure App Service new SLOT created on Step 1:

```bash
az webapp deployment source config-zip --resource-group "<resource-group-name>" --name "<name-of-backend-app-service>" --src "backend.zip" --slot staging
```

4. Wait around 5 minutes and test your bot by running Notebook 14. Your Swagger (OpenAPI) definition should show here:

```html
https://<name-of-backend-app-service>-staging.azurewebsites.net/
```

5. Once you confirm that the API is working on step 4, you need to add the endpoint to the frontend page code. Go to `apps/frontend/pages`   and edit   `3_FastAPI_Chat.py`:

```python
    # ENTER HERE YOUR LANGSERVE FASTAPI ENDPOINT
    # for example: "https://webapp-backend-botid-zf4fwhz3gdn64-staging.azurewebsites.net"

    url = "https://<name-of-backend-app-service>-staging.azurewebsites.net" + "/agent/stream_events"
```

6. Re-deploy FrontEnd code: Zip the code of the bot by executing the following command in the terminal (you have to be inside the folder: **apps/frontend/** ):

```bash
zip frontend.zip ./* && zip frontend.zip ./pages/* && zip -j frontend.zip ../../common/*
az webapp deployment source config-zip --resource-group "<resource-group-name>" --name "<name-of-frontend-app-service>" --src "frontend.zip"
```

## (optional) Running in Docker

This project folder includes a Dockerfile that allows you to easily build and host your LangServe app.

### Building the Image

To build the image, you simply:

```shell
docker build . -t my-langserve-app
```

If you tag your image with something other than `my-langserve-app`,
note it for use in the next step.

### Running the Image Locally

To run the image, you'll need to include any environment variables
necessary for your application.

In the below example, we inject the environment variables in `credentials.env`

We also expose port 8080 with the `-p 8080:8080` option.

```shell
docker run $(cat ../../../credentials.env | sed 's/^/-e /') -p 8080:8080 my-langserve-app

```
