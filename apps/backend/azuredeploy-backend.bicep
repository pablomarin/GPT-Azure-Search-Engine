@description('Required. Active Directory App ID.')
param MicrosoftAppId string

@description('Required. Active Directory App Secret Value.')
@secure()
param MicrosoftAppPassword string

@description('Optional. The SAS token for the Azure Storage Account')
param DATASOURCE_SAS_TOKEN string = '?sv=2022-11-02&ss=bf&srt=sco&sp=rltfx&se=2023-11-29T01:50:59Z&st=2023-05-10T16:50:59Z&spr=https&sig=ZT7MLy%2BnlvAxUKKj5v0RwoWObXaab3gO4ec2%2Fci6iL0%3D'

// Reference to existing Azure Search service
param resourceGroupSearch string
param Azure_Search_Name string 

resource azureSearch 'Microsoft.Search/searchServices@2021-04-01-preview' existing = {
  name: Azure_Search_Name
  scope: resourceGroup(resourceGroupSearch)
}

// End reference to existing Azure Search service

@description('Optional. The API version for the Azure Search service.')
param AZURE_SEARCH_API_VERSION string = '2021-04-30-Preview'

@description('Required. The endpoint of the Azure OpenAI service.')
param AZURE_OPENAI_ENDPOINT string

@description('Required. The API key for the Azure OpenAI service.')
@secure()
param AZURE_OPENAI_API_KEY string

@description('Optional. The model name for the Azure OpenAI service.')
param AZURE_OPENAI_MODEL_NAME string = 'gpt-4'

@description('Optional. The API version for the Azure OpenAI service.')
param AZURE_OPENAI_API_VERSION string = '2023-03-15-preview'

@description('Optional. The URL for the Bing Search service.')
param BING_SEARCH_URL string = 'https://api.bing.microsoft.com/v7.0/search'

@description('Required. The subscription key for the Bing Search service.')
@secure()
param BING_SUBSCRIPTION_KEY string

@description('Required. The endpoint of the SQL Server.')
param SQL_SERVER_ENDPOINT string

@description('Required. The name of the SQL Server database.')
param SQL_SERVER_DATABASE string = 'SampleDB'

@description('Required. The username for the SQL Server.')
param SQL_SERVER_USERNAME string

@description('Required. The password for the SQL Server.')
@secure()
param SQL_SERVER_PASSWORD string

@description('Required. The endpoint of the Azure CosmosDB.')
param AZURE_COSMOSDB_ENDPOINT string

@description('Required. The name of the Azure CosmosDB.')
param AZURE_COSMOSDB_NAME string

@description('Required. The name of the Azure CosmosDB container.')
param AZURE_COSMOSDB_CONTAINER_NAME string

@description('Required. The connection string of the Azure CosmosDB.')
@secure()
param AZURE_COMOSDB_CONNECTION_STRING string

@description('Optional. The globally unique and immutable bot ID. Also used to configure the displayName of the bot, which is mutable.')
param botId string = 'BotId-${uniqueString(resourceGroup().id)}'

@description('Optional, defaults to F0. The pricing tier of the Bot Service Registration. Acceptable values are F0 and S1.')
@allowed([
  'F0'
  'S1'
])
param botSku string = 'F0'

@description('Optional. The name of the new App Service Plan.')
param newAppServicePlanName string = 'AppServicePlan-Backend-${uniqueString(resourceGroup().id)}'

@description('Optional, defaults to S3. The SKU of the App Service Plan. Acceptable values are B3, S3 and P2v3.')
@allowed([
  'B3'
  'S3'
  'P2v3'
])
param newAppServicePlanSku string = 'S3'

@description('Optional, defaults to resource group location. The location of the resources.')
param resourcesLocation string = resourceGroup().location

var servicePlanName = newAppServicePlanName
var publishingUsername = '$${botId}'
var webAppName = 'webApp-Backend-${botId}'
var siteHost = '${webAppName}.azurewebsites.net'
var botEndpoint = 'https://${siteHost}/api/messages'

// Create a new Linux App Service Plan if no existing App Service Plan name was passed in.
resource appServicePlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: servicePlanName
  location: resourcesLocation
  sku: {
    name: newAppServicePlanSku
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
  kind: 'app,linux'
  properties: {
    enabled: true
    hostNameSslStates: [
      {
        name: '${webAppName}.azurewebsites.net'
        sslState: 'Disabled'
        hostType: 'Standard'
      }
      {
        name: '${webAppName}.scm.azurewebsites.net'
        sslState: 'Disabled'
        hostType: 'Repository'
      }
    ]
    serverFarmId: appServicePlan.id
    reserved: true
    scmSiteAlsoStopped: false
    clientAffinityEnabled: false
    clientCertEnabled: false
    hostNamesDisabled: false
    containerSize: 0
    dailyMemoryTimeQuota: 0
    httpsOnly: false
    siteConfig: {
      appSettings: [
        {
          name: 'MicrosoftAppId'
          value: MicrosoftAppId
        }
        {
          name: 'MicrosoftAppPassword'
          value: MicrosoftAppPassword
        }
        {
          name: 'DATASOURCE_SAS_TOKEN'
          value: DATASOURCE_SAS_TOKEN
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: 'https://${Azure_Search_Name}.search.windows.net'
        }
        {
          name: 'AZURE_SEARCH_KEY'
          value: azureSearch.listKeys().keys[0].value
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
          name: 'BING_SEARCH_URL'
          value: BING_SEARCH_URL
        }
        {
          name: 'BING_SUBSCRIPTION_KEY'
          value: BING_SUBSCRIPTION_KEY
        }
        {
          name: 'SQL_SERVER_ENDPOINT'
          value: SQL_SERVER_ENDPOINT
        }
        {
          name: 'SQL_SERVER_DATABASE'
          value: SQL_SERVER_DATABASE
        }
        {
          name: 'SQL_SERVER_USERNAME'
          value: SQL_SERVER_USERNAME
        }
        {
          name: 'SQL_SERVER_PASSWORD'
          value: SQL_SERVER_PASSWORD
        }
        {
          name: 'AZURE_COSMOSDB_ENDPOINT'
          value: AZURE_COSMOSDB_ENDPOINT
        }
        {
          name: 'AZURE_COSMOSDB_NAME'
          value: AZURE_COSMOSDB_NAME
        }
        {
          name: 'AZURE_COSMOSDB_CONTAINER_NAME'
          value: AZURE_COSMOSDB_CONTAINER_NAME
        }
        {
          name: 'AZURE_COMOSDB_CONNECTION_STRING'
          value: AZURE_COMOSDB_CONNECTION_STRING
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
      ]
      cors: {
        allowedOrigins: [
          'https://botservice.hosting.portal.azure.net'
          'https://hosting.onecloud.azure-test.net/'
        ]
      }
    }
  }
}

resource webAppConfig 'Microsoft.Web/sites/config@2022-09-01' = {
  parent: webApp
  name: 'web'
  properties: {
    numberOfWorkers: 1
    defaultDocuments: [
      'Default.htm'
      'Default.html'
      'Default.asp'
      'index.htm'
      'index.html'
      'iisstart.htm'
      'default.aspx'
      'index.php'
      'hostingstart.html'
    ]
    netFrameworkVersion: 'v4.0'
    phpVersion: ''
    pythonVersion: ''
    nodeVersion: ''
    linuxFxVersion: 'PYTHON|3.10'
    requestTracingEnabled: false
    remoteDebuggingEnabled: false
    remoteDebuggingVersion: 'VS2017'
    httpLoggingEnabled: true
    logsDirectorySizeLimit: 35
    detailedErrorLoggingEnabled: false
    publishingUsername: publishingUsername
    scmType: 'None'
    use32BitWorkerProcess: true
    webSocketsEnabled: false
    alwaysOn: true
    appCommandLine: 'gunicorn --bind 0.0.0.0 --worker-class aiohttp.worker.GunicornWebWorker --timeout 600 app:APP'
    managedPipelineMode: 'Integrated'
    virtualApplications: [
      {
        virtualPath: '/'
        physicalPath: 'site\\wwwroot'
        preloadEnabled: false
        virtualDirectories: null
      }
    ]
    winAuthAdminState: 0
    winAuthTenantState: 0
    customAppPoolIdentityAdminState: false
    customAppPoolIdentityTenantState: false
    loadBalancing: 'LeastRequests'
    routingRules: []
    experiments: {
      rampUpRules: []
    }
    autoHealEnabled: false
    vnetName: ''
    minTlsVersion: '1.2'
    ftpsState: 'AllAllowed'
    reservedInstanceCount: 0
  }
}

resource bot 'Microsoft.BotService/botServices@2022-09-15' = {
  name: botId
  location: 'global'
  kind: 'azurebot'
  sku: {
    name: botSku
  }
  properties: {
    displayName: botId
    iconUrl: 'https://docs.botframework.com/static/devportal/client/images/bot-framework-default.png'
    endpoint: botEndpoint
    msaAppId: MicrosoftAppId
    luisAppIds: []
    schemaTransformationVersion: '1.3'
    isCmekEnabled: false
  }
  dependsOn: [
    webApp
  ]
}
