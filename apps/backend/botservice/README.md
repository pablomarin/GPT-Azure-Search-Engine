<h1 align="center">
Backend Web Application - Bot API + Bot Service
</h1>

This bot has been created using [Bot Framework](https://dev.botframework.com).

Services and tools used:

- Azure App Service (Web App) - Chatbot API Hosting
- Azure Bot Service - A service for managing communication through various channels

## Deploy Bot To Azure Web App

Below are the steps to run the Bot API as an Azure Wep App, connected with the Azure Bot Service that will expose the bot to multiple channels including: Web Chat, MS Teams, Twilio, SMS, Email, Slack, etc..

1. In Azure Portal: In Azure Active Directory->App Registrations, Create an Multi-Tenant App Registration (Service Principal), create a Secret (and take note of the value)

2. Deploy the Bot Web App and the Bot Service by clicking the Button below and type the App Registration ID and Secret Value that you got in Step 1 along with all the other ENV variables you used in the Notebooks

[![Deploy To Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpablomarin%2FGPT-Azure-Search-Engine%2Fmain%2Fapps%2Fbackend%2Fbotservice%2Fazuredeploy-backend.json)

3. Zip the code of the bot by executing the following command in the terminal (**you have to be inside the apps/backend/botservice/ folder**):
```bash
(cd ../../../ && zip -r apps/backend/botservice/backend.zip common) && zip -j backend.zip ./* && zip -j backend.zip ../../../common/requirements.txt
```
4. Using the Azure CLI deploy the bot code to the Azure App Service created on Step 2
```bash
az login -i
az webapp deployment source config-zip --resource-group "<resource-group-name>" --name "<name-of-backend-app-service>" --src "backend.zip"
```
**Note**: If you get this error: `An error occured during deployment. Status Code: 401`. **Cause**: Some FDPO Azure Subscriptions disable Azure Web Apps Basic Authentication every minute (don't know why). **Solution**:  before running the above `az webapp deployment` command, make sure that your backend azure web app has `Basic Authentication ON`. In the Azure Portal, you can find this settting in: `Configuration->General Settings`.
Don't worry if after running the command it says retrying many times, the zip files already uploaded and is building.

5. In the Azure Portal: **Wait around 5 minutes** and test your bot by going to your Azure Bot Service created in Step 2 and clicking on: **Test in Web Chat**

6. In the Azure Portal: In your Bot Service , add multiple channels (Including Teams) by clicking in **Channels**

7. Go to apps/frontend folder and follow the steps in README.md to deploy a Frontend application that uses the bot.

## Reference documentation

- [Bot Framework Documentation](https://docs.botframework.com)
- [Bot Samples code](https://github.com/microsoft/BotBuilder-Samples)
- [Bot Framework Python SDK](https://github.com/microsoft/botbuilder-python/tree/main)
- [Bot Basics](https://docs.microsoft.com/azure/bot-service/bot-builder-basics?view=azure-bot-service-4.0)
- [Azure Bot Service Introduction](https://docs.microsoft.com/azure/bot-service/bot-service-overview-introduction?view=azure-bot-service-4.0)
- [Azure Bot Service Documentation](https://docs.microsoft.com/azure/bot-service/?view=azure-bot-service-4.0)
- [Channels and Bot Connector Service](https://docs.microsoft.com/azure/bot-service/bot-concepts?view=azure-bot-service-4.0)
