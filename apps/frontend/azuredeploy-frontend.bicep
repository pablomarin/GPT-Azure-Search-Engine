@description('Optional. Web app name must be between 2 and 60 characters.')
@minLength(2)
@maxLength(60)
param webAppName string = 'webApp-Frontend-${uniqueString(resourceGroup().id)}'

@description('Optional, defaults to S3. The SKU of App Service Plan. The allowed values are B3, S3 and P2v3.')
@allowed([
  'B3'
  'S3'
  'P2v3'
])
param appServicePlanSKU string = 'S3'

@description('Optional. The name of the App Service Plan.')
param appServicePlanName string = 'AppServicePlan-Frontend-${uniqueString(resourceGroup().id)}'

@description('Required. The name of your Bot Service.')
param botDirectLineChannelName string

@description('Optional. The name of the resource group where the backend resources (bot etc.) where deployed previously. Defaults to current resource group.')
param resourceGroupBackend string = resourceGroup().name

@description('Required. The SAS token for the Azure Storage Account hosting your data')
@secure()
param datasourceSASToken string 

@description('Optional. The name of the resource group where the resources (Azure Search etc.) where deployed previously. Defaults to current resource group.')
param resourceGroupSearch string = resourceGroup().name

@description('Required. The name of the Azure Search service deployed previously.')
param azureSearchName string 

@description('Optional. The API version of the Azure Search.')
param azureSearchAPIVersion string = '2021-04-30-Preview'

@description('Required. The name of the resource group where Azure Open AI was deployed previously. Defaults to current resource group.')
param resourceGroupOpenAI string = resourceGroup().name

@description('Required. The name of the Azure OpenAI resource deployed previously.')
param azureOpenAIName string 

@description('Optional. The model name of the Azure OpenAI.')
param azureOpenAIModelName string = 'gpt-35-turbo'

@description('Optional. The API version of the Azure OpenAI.')
param azureOpenAIAPIVersion string = '2023-03-15-preview'

@description('Optional, defaults to resource group location. The location of the resources.')
param location string = resourceGroup().location

// Existing direct line channel of bot.
resource botDirectLineChannel 'Microsoft.BotService/botServices/channels@2022-09-15' existing = {
  name: botDirectLineChannelName
  scope: resourceGroup(resourceGroupBackend)
}

// Existing Azure Search service.
resource azureSearch 'Microsoft.Search/searchServices@2021-04-01-preview' existing = {
  name: azureSearchName
  scope: resourceGroup(resourceGroupSearch)
}

// Existing Azure OpenAI resource.
resource azureOpenAI 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: azureOpenAIName
  scope: resourceGroup(resourceGroupOpenAI)
}

// Create a new Linux App Service Plan.
resource appServicePlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: appServicePlanSKU
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// Create a Web App using a Linux App Service Plan.
resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: webAppName
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      appSettings: [
        {
          name: 'BOT_SERVICE_NAME'
          value: botDirectLineChannelName
        }
        {
          name: 'BOT_DIRECTLINE_SECRET_KEY'
          value: botDirectLineChannel.listChannelWithKeys().properties.sites.key
        }
        {
          name: 'DATASOURCE_SAS_TOKEN'
          value: datasourceSASToken
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: 'https://${azureSearchName}.search.windows.net'
        }
        {
          name: 'AZURE_SEARCH_KEY'
          value: azureSearch.listAdminKeys().primaryKey
        }
        {
          name: 'AZURE_SEARCH_API_VERSION'
          value: azureSearchAPIVersion
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: 'https://${azureOpenAIName}.openai.azure.com/'
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: azureOpenAI.listKeys().key1
        }
        {
          name: 'AZURE_OPENAI_MODEL_NAME'
          value: azureOpenAIModelName
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: azureOpenAIAPIVersion
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
      ]
    }
  }
}

resource webAppConfig 'Microsoft.Web/sites/config@2022-09-01' = {
  parent: webApp
  name: 'web'
  properties: {
    linuxFxVersion: 'PYTHON|3.10'
    alwaysOn: true
    appCommandLine: 'python -m streamlit run Home.py --server.port 8000 --server.address 0.0.0.0'
  }
}
