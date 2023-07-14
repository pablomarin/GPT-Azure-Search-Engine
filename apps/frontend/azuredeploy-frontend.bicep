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
param botName string

@description('Required. The secret key of the Direct Line Channel of the Bot Service.')
@secure()
param botKey string

@description('Required. The SAS token for the Azure Storage Account hosting your data')
@secure()
param datasourceSASToken string 

@description('Required. The endpoint of the Azure Search.')
param azureSearchEndpoint string

@description('Required. The key of the Azure Search.')
@secure()
param azureSearchKey string

@description('Optional. The API version of the Azure Search.')
param azureSearchAPIVersion string = '2021-04-30-Preview'

@description('Required. The endpoint of the Azure OpenAI.')
param azureOpenAIEndpoint string

@description('Required. The key of the Azure OpenAI.')
@secure()
param azureOpenAIAPIKey string

@description('Optional. The model name of the Azure OpenAI.')
param azureOpenAIModelName string = 'gpt-35-turbo'

@description('Optional. The API version of the Azure OpenAI.')
param azureOpenAIAPIVersion string = '2023-03-15-preview'

@description('Optional, defaults to resource group location. The location of the resources.')
param location string = resourceGroup().location

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
          value: botName
        }
        {
          name: 'BOT_DIRECTLINE_SECRET_KEY'
          value: botKey
        }
        {
          name: 'DATASOURCE_SAS_TOKEN'
          value: datasourceSASToken
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: azureSearchEndpoint
        }
        {
          name: 'AZURE_SEARCH_KEY'
          value: azureSearchKey
        }
        {
          name: 'AZURE_SEARCH_API_VERSION'
          value: azureSearchAPIVersion
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: azureOpenAIEndpoint
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: azureOpenAIAPIKey
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
