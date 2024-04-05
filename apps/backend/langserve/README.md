<h1 align="center">
Backend Web Application - LangServe FastAPI 
</h1>

This bot has been created using [LangServe](https://python.langchain.com/docs/langserve)

## Deploy Bot To Azure Web App

Below are the steps to run the LangServe Bot API as an Azure Wep App:

1. We don't need to deploy again the Azure infrastructure, we did that already for the Bot Service API (Notebook 12). We are going to use the same App Service and just change the code.

3. Zip the code of the bot by executing the following command in the terminal (**you have to be inside the apps/backend/langserve/ folder**):
```bash
(cd ../../../ && zip -r apps/backend/langserve/backend.zip common) && zip -j backend.zip ./* && zip -j backend.zip ../../../common/requirements.txt && zip -j backend.zip app/*
```
4. Using the Azure CLI deploy the bot code to the Azure App Service created on Step 2
```bash
az login -i
az webapp deployment source config-zip --resource-group "<resource-group-name>" --name "<name-of-backend-app-service>" --src "backend.zip"
```

5. **Wait around 5 minutes** and test your bot by running the next Notebook.


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
