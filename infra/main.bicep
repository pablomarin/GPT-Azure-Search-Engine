targetScope = 'subscription'

// The main bicep module to provision Azure resources.
// For a more complete walkthrough to understand how this file works with azd,
// see https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/make-azd-compatible?pivots=azd-create

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
@metadata({
  azd: {
    type: 'location'
  }
})
param location string

param resourceGroupName string = ''

@description('Optional, defaults to S3. The SKU of the App Service Plan. Acceptable values are B3, S3 and P2v3.')
@allowed([
  'B3'
  'S3'
  'P2v3'
])
param HostingPlanSku string = 'P2v3'

@description('The location of the OpenAI resource group.')
@allowed([ 'canadaeast', 'eastus', 'eastus2', 'francecentral', 'switzerlandnorth', 'uksouth', 'japaneast' ])
@metadata({
  azd: {
    type: 'location'
  }
})
param openAiResourceGroupLocation string
param openAiServiceName string // Set in main.parameters.json
param openAiResourceGroupName string

param openAiSkuName string = 'S0'

@description('Optional. The API version of the Azure OpenAI.')
param azureOpenAIAPIVersion string = '2023-05-15'

param chatGptDeploymentName string = '' // Set in main.parameters.json
param chatGptDeploymentCapacity int = 20
param chatGptModelName string = (openAiHost == 'azure') ? 'gpt-4-32k' : 'gpt-3.5-turbo'
param chatGptModelVersion string = '0613'
param embeddingDeploymentName string = '' // Set in main.parameters.json
param embeddingDeploymentCapacity int = 30
param embeddingModelName string = 'text-embedding-ada-002'

@allowed([ 'azure', 'openai' ])
param openAiHost string // Set in main.parameters.json

// tags that should be applied to all resources.
var tags = {
  // Tag all resources with the environment name.
  'azd-env-name': environmentName
}

@description('Required. Active Directory App ID.')
param appId string

@description('Required. Active Directory App Secret Value.')
@secure()
param appSecret string

// infrastructure resources
@description('Required. The administrator username of the SQL logical server.')
param SQLAdministratorLogin string

@description('Required. The administrator password of the SQL logical server.')
@secure()
param SQLAdministratorLoginPassword string

// Generate a unique token to be used in naming resources.
// Remove linter suppression after using.
#disable-next-line no-unused-vars
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

// Organize resources in a resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: !empty(resourceGroupName) ? resourceGroupName : 'rg-${environmentName}'
  location: location
  tags: tags
}

resource openAiResourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' existing = if (!empty(openAiResourceGroupName)) {
  name: !empty(openAiResourceGroupName) ? openAiResourceGroupName : rg.name
}

// create opan ai account if openAiHost is azure
module openAi 'core/ai/cognitiveservices.bicep' = if (openAiHost == 'azure') {
  name: 'openai'
  scope: openAiResourceGroup
  params: {
    name: !empty(openAiServiceName) ? openAiServiceName : 'openai-${resourceToken}'
    location: openAiResourceGroupLocation
    tags: tags
    sku: {
      name: openAiSkuName
    }
    deployments: [
      {
        name: !empty(chatGptDeploymentName) ? chatGptDeploymentName : chatGptModelName
        model: {
          format: 'OpenAI'
          name: chatGptModelName
          version: chatGptModelVersion
        }
        sku: {
          name: 'Standard'
          capacity: chatGptDeploymentCapacity
        }
      }
      {
        name: !empty(embeddingDeploymentName) ? embeddingDeploymentName : embeddingModelName
        model: {
          format: 'OpenAI'
          name: embeddingModelName
          version: '2'
        }
        capacity: embeddingDeploymentCapacity
      }
    ]
  }
}

// Add resources to be provisioned below.
// A full example that leverages azd bicep modules can be seen in the todo-python-mongo template:
// https://github.com/Azure-Samples/todo-python-mongo/tree/main/infra
module infra '../azuredeploy.bicep' = {
  name: 'infra'
  scope: rg
  params: {
    location: location
    SQLAdministratorLogin: SQLAdministratorLogin
    SQLAdministratorLoginPassword: SQLAdministratorLoginPassword
  }
  dependsOn: [
    openAi
  ]
}

module backend '../apps/backend/azuredeploy-backend.bicep' = {
  name: 'backend'
  scope: rg
  params: {
    location: location    
    appId: appId
    appPassword: appSecret
    azureOpenAIAPIKey: openAi.outputs.key
    azureOpenAIName: openAi.outputs.name
    azureSearchName: infra.outputs.azureSearchName
    bingSearchName: infra.outputs.bingSearchAPIName
    blobSASToken: '' // TODO: add blobSASToken
    cosmosDBAccountName: infra.outputs.cosmosDBAccountName
    cosmosDBContainerName: infra.outputs.cosmosDBContainerName
    SQLServerName: infra.outputs.SQLServerName
    SQLServerDatabase: infra.outputs.SQLDatabaseName
    SQLServerUsername: SQLAdministratorLogin
    SQLServerPassword: SQLAdministratorLoginPassword

  }
  dependsOn: [
    infra
    openAi
  ]
}

module frontend '../apps/frontend/azuredeploy-frontend.bicep' = {
  name: 'frontend'
  scope: rg
  params: {
    appServicePlanSKU: HostingPlanSku
    location: location   
    azureOpenAIName: openAi.outputs.name
    azureOpenAIAPIKey: openAi.outputs.key
    azureOpenAIModelName: chatGptModelName
    azureOpenAIAPIVersion: azureOpenAIAPIVersion
    azureSearchName: infra.outputs.azureSearchName
    blobSASToken: '' // TODO: to be added in post deployment
    botDirectLineChannelKey: '' // TODO: to be added in post deployment
    botServiceName: backend.outputs.botServiceName
  }
  dependsOn: [
    openAi
    infra
    backend
  ]
}

// Outputs are automatically saved in the local azd environment .env file.
// To see these outputs, run `azd env get-values`,  or `azd env get-values --output json` for json output.
#disable-next-line outputs-should-not-contain-secrets
output AZURE_APP_SECRET string = appSecret
output AZURE_APP_ID string = appId
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_OPENAI_SERVICE string = openAi.outputs.name
output AZURE_OPENAI_RESOURCE_GROUP string = openAiResourceGroup.name
output AZURE_OPENAI_HOST string = openAiHost
output AZURE_OPENAI_MODEL_NAME string = !empty(chatGptDeploymentName) ? chatGptDeploymentName : chatGptModelName
output AZURE_OPENAI_EMB_DEPLOYMENT string = !empty(embeddingDeploymentName) ? embeddingDeploymentName : embeddingModelName
output AZURE_OPENAI_API_VERSION string = azureOpenAIAPIVersion

output AZURE_BOT_SERVICE string = backend.outputs.botServiceName
output AZURE_FRONTEND_WEBAPP_NAME string = frontend.outputs.webAppName
output AZURE_BACKEND_WEBAPP_NAME string = backend.outputs.webAppName
output AZURE_BLOB_STORAGE_ACCOUNT_NAME string = infra.outputs.blobStorageAccountName
output AZURE_BACKEND_WEBAPP_URL string = backend.outputs.webAppUrl


output BLOB_CONNECTION_STRING  string = infra.outputs.blobConnectionString
output BLOB_SAS_TOKEN string = '' // TODO: add blobSASToken

// Key Variables to put in your Crenetials file
output AZURE_SEARCH_ENDPOINT string = infra.outputs.azureSearchEndpoint
output AZURE_SEARCH_KEY string = infra.outputs.azureSearchKey
output COG_SERVICES_NAME string = infra.outputs.cognitiveServiceName
output COG_SERVICES_KEY string = infra.outputs.cognitiveServiceKey
output FORM_RECOGNIZER_ENDPOINT string = infra.outputs.formrecognizerEndpoint
output FORM_RECOGNIZER_KEY string = infra.outputs.formRecognizerKey
output AZURE_OPENAI_ENDPOINT string = 'https://${openAi.outputs.name}.openai.azure.com/'
output AZURE_OPENAI_API_KEY string = openAi.outputs.key
output BING_SUBSCRIPTION_KEY string = infra.outputs.bingServiceSearchKey
output SQL_SERVER_NAME string = infra.outputs.SQLServerName
output SQL_SERVER_DATABASE string = infra.outputs.SQLDatabaseName
output SQL_SERVER_USERNAME string = SQLAdministratorLogin
#disable-next-line outputs-should-not-contain-secrets
output SQL_SERVER_PASSWORD string = SQLAdministratorLoginPassword
output AZURE_COSMOSDB_ENDPOINT string = infra.outputs.cosmosDBAccountEndpoint
output AZURE_COSMOSDB_NAME string = infra.outputs.cosmosDBAccountName
output AZURE_COSMOSDB_CONTAINER_NAME string = infra.outputs.cosmosDBContainerName
output AZURE_COMOSDB_CONNECTION_STRING string = infra.outputs.cosmosDBConnectionString
