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
param botServiceName string

@description('Required. The key to the direct line channel of your bot.')
@secure()
param botDirectLineChannelKey string

@description('Required. The SAS token for the Azure Storage Account hosting your data')
@secure()
param blobSASToken string 

@description('Optional. The name of the resource group where the resources (Azure Search etc.) where deployed previously. Defaults to current resource group.')
param resourceGroupSearch string = resourceGroup().name

@description('Required. The name of the Azure Search service deployed previously.')
param azureSearchName string 

@description('Optional. The API version of the Azure Search.')
param azureSearchAPIVersion string = '2024-11-01-preview'

@description('Required. The name of the Azure OpenAI resource deployed previously.')
param azureOpenAIName string 

@description('Required. The API key of the Azure OpenAI resource deployed previously.')
@secure()
param azureOpenAIAPIKey string 

@description('Required. The deployment name of the Azure OpenAI GPT-4o model.')
param gpt4oDeploymentName string = 'gpt-4o'

@description('Required. The deployment name of the Azure OpenAI GPT-4o-mini model.')
param gpt4oMiniDeploymentName string = 'gpt-4o-mini'

@description('Required. The API version of the Azure OpenAI.')
param azureOpenAIAPIVersion string = '2024-10-01-preview'

@description('Required. Select the Speech engine: openai or azure.')
param speechEngine string = 'openai'

@description('Required. Select deployment name for the AOAI whisper model')
param openAIWhisperModelName string = 'whisper'

@description('Required. Select deployment name for the AOAI TTS model')
param openAITTSModelName string = 'tts'

@description('Optional, defaults to resource group location. The location of the resources.')
param location string = resourceGroup().location

// Define Variables
var backendWebAppName = 'webApp-Backend-${botServiceName}'
var fastAPIsiteHost = 'https://${backendWebAppName}-staging.azurewebsites.net'

// Existing Azure Search service.
resource azureSearch 'Microsoft.Search/searchServices@2021-04-01-preview' existing = {
  name: azureSearchName
  scope: resourceGroup(resourceGroupSearch)
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
  tags: { 'azd-service-name': 'frontend' }
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      appSettings: [
        {
          name: 'BOT_SERVICE_NAME'
          value: botServiceName
        }
        {
          name: 'BOT_DIRECTLINE_SECRET_KEY'
          value: botDirectLineChannelKey
        }
        {
          name: 'BLOB_SAS_TOKEN'
          value: blobSASToken
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
          value: azureOpenAIAPIKey
        }
        {
          name: 'GPT4o_DEPLOYMENT_NAME'
          value: gpt4oDeploymentName
        }
        {
          name: 'GPT4oMINI_DEPLOYMENT_NAME'
          value: gpt4oMiniDeploymentName
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: azureOpenAIAPIVersion
        }
        {
          name: 'SPEECH_ENGINE'
          value: speechEngine
        }
        {
          name: 'AZURE_OPENAI_WHISPER_MODEL_NAME'
          value: openAIWhisperModelName
        }
        {
          name: 'AZURE_OPENAI_TTS_MODEL_NAME'
          value: openAITTSModelName
        }
        {
          name: 'FAST_API_SERVER'
          value: fastAPIsiteHost
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
    linuxFxVersion: 'PYTHON|3.12'
    alwaysOn: true
    appCommandLine: 'python -m streamlit run app/Home.py --server.port 8000 --server.address 0.0.0.0'
  }
}

output webAppURL string = webApp.properties.defaultHostName
output webAppName string = webApp.name
