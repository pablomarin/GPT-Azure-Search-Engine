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
param sku string = 'S3'

@description('Optional. The name of the App Service Plan.')
param AppServicePlanName string = 'AppServicePlan-Frontend-${uniqueString(resourceGroup().id)}'

@description('Required. The name of your Bot Service.')
param BOT_SERVICE_NAME string

@description('Required. The secret key of the Direct Line Channel of the Bot Service.')
@secure()
param BOT_DIRECTLINE_SECRET_KEY string

@description('Required. The SAS token for the Azure Storage Account hosting your data')
@secure()
param DATASOURCE_SAS_TOKEN string 

@description('Required. The endpoint of the Azure Search.')
param AZURE_SEARCH_ENDPOINT string

@description('Required. The key of the Azure Search.')
@secure()
param AZURE_SEARCH_KEY string

@description('Optional. The API version of the Azure Search.')
param AZURE_SEARCH_API_VERSION string = '2021-04-30-Preview'

@description('Required. The endpoint of the Azure OpenAI.')
param AZURE_OPENAI_ENDPOINT string

@description('Required. The key of the Azure OpenAI.')
@secure()
param AZURE_OPENAI_API_KEY string

@description('Optional. The model name of the Azure OpenAI.')
param AZURE_OPENAI_MODEL_NAME string = 'gpt-35-turbo'

@description('Optional. The API version of the Azure OpenAI.')
param AZURE_OPENAI_API_VERSION string = '2023-03-15-preview'

@description('Optional, defaults to resource group location. The location of the resources.')
param resourcesLocation string = resourceGroup().location

// Create a new Linux App Service Plan.
resource appServicePlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: AppServicePlanName
  location: resourcesLocation
  sku: {
    name: sku
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// Create a Web App using a Linux App Service Plan.
resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: webAppName
  location: resourcesLocation
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      appSettings: [
        {
          name: 'BOT_SERVICE_NAME'
          value: BOT_SERVICE_NAME
        }
        {
          name: 'BOT_DIRECTLINE_SECRET_KEY'
          value: BOT_DIRECTLINE_SECRET_KEY
        }
        {
          name: 'DATASOURCE_SAS_TOKEN'
          value: DATASOURCE_SAS_TOKEN
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: AZURE_SEARCH_ENDPOINT
        }
        {
          name: 'AZURE_SEARCH_KEY'
          value: AZURE_SEARCH_KEY
        }
        {
          name: 'AZURE_SEARCH_API_VERSION'
          value: AZURE_SEARCH_API_VERSION
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: AZURE_OPENAI_ENDPOINT
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: AZURE_OPENAI_API_KEY
        }
        {
          name: 'AZURE_OPENAI_MODEL_NAME'
          value: AZURE_OPENAI_MODEL_NAME
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: AZURE_OPENAI_API_VERSION
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
