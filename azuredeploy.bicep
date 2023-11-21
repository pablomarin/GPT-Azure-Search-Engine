@description('Optional. Service name must only contain lowercase letters, digits or dashes, cannot use dash as the first two or last one characters, cannot contain consecutive dashes, and is limited between 2 and 60 characters in length.')
@minLength(2)
@maxLength(60)
param azureSearchName string = 'cog-search-${uniqueString(resourceGroup().id)}'

@description('Optional, defaults to standard. The pricing tier of the search service you want to create (for example, basic or standard).')
@allowed([
  'free'
  'basic'
  'standard'
  'standard2'
  'standard3'
  'storage_optimized_l1'
  'storage_optimized_l2'
])
param azureSearchSKU string = 'standard'

@description('Optional, defaults to 1. Replicas distribute search workloads across the service. You need at least two replicas to support high availability of query workloads (not applicable to the free tier). Must be between 1 and 12.')
@minValue(1)
@maxValue(12)
param azureSearchReplicaCount int = 1

@description('Optional, defaults to 1. Partitions allow for scaling of document count as well as faster indexing by sharding your index over multiple search units. Allowed values: 1, 2, 3, 4, 6, 12.')
@allowed([
  1
  2
  3
  4
  6
  12
])
param azureSearchPartitionCount int = 1

@description('Optional, defaults to default. Applicable only for SKUs set to standard3. You can set this property to enable a single, high density partition that allows up to 1000 indexes, which is much higher than the maximum indexes allowed for any other SKU.')
@allowed([
  'default'
  'highDensity'
])
param azureSearchHostingMode string = 'default'

@description('Optional. The name of our application. It has to be unique. Type a name followed by your resource group name. (<name>-<resourceGroupName>)')
param cognitiveServiceName string = 'cognitive-service-${uniqueString(resourceGroup().id)}'

@description('Optional. The name of the SQL logical server.')
param SQLServerName string = 'sql-server-${uniqueString(resourceGroup().id)}'

@description('Optional. The name of the SQL Database.')
param SQLDBName string = 'SampleDB'

@description('Required. The administrator username of the SQL logical server.')
param SQLAdministratorLogin string

@description('Required. The administrator password of the SQL logical server.')
@secure()
param SQLAdministratorLoginPassword string

@description('Optional. The name of the Bing Search API service')
param bingSearchAPIName string = 'bing-search-${uniqueString(resourceGroup().id)}'

@description('Optional. Cosmos DB account name, max length 44 characters, lowercase')
param cosmosDBAccountName string = 'cosmosdb-account-${uniqueString(resourceGroup().id)}'

@description('Optional. The name for the CosmosDB database')
param cosmosDBDatabaseName string = 'cosmosdb-db-${uniqueString(resourceGroup().id)}'

@description('Optional. The name for the CosmosDB database container')
param cosmosDBContainerName string = 'cosmosdb-container-${uniqueString(resourceGroup().id)}'

@description('Optional. The name of the Form Recognizer service')
param formRecognizerName string = 'form-recognizer-${uniqueString(resourceGroup().id)}'

@description('Optional. The name of the Blob Storage account')
param blobStorageAccountName string = 'blobstorage${uniqueString(resourceGroup().id)}'

@description('Optional, defaults to resource group location. The location of the resources.')
param location string = resourceGroup().location

var cognitiveServiceSKU = 'S0'

resource azureSearch 'Microsoft.Search/searchServices@2021-04-01-Preview' = {
  name: azureSearchName
  location: location
  sku: {
    name: azureSearchSKU
  }
  properties: {
    replicaCount: azureSearchReplicaCount
    partitionCount: azureSearchPartitionCount
    hostingMode: azureSearchHostingMode
    semanticSearch: 'standard'
  }
}

resource cognitiveService 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: cognitiveServiceName
  location: location
  sku: {
    name: cognitiveServiceSKU
  }
  kind: 'CognitiveServices'
  properties: {
    apiProperties: {
      statisticsEnabled: false
    }
  }
}

resource SQLServer 'Microsoft.Sql/servers@2022-11-01-preview' = {
  name: SQLServerName
  location: location
  properties: {
    administratorLogin: SQLAdministratorLogin
    administratorLoginPassword: SQLAdministratorLoginPassword
  }
}

resource SQLDatabase 'Microsoft.Sql/servers/databases@2022-11-01-preview' = {
  parent: SQLServer
  name: SQLDBName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
}

resource SQLFirewallRules 'Microsoft.Sql/servers/firewallRules@2022-11-01-preview' = {
  parent: SQLServer
  name: 'AllowAllAzureIPs'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
}

resource cosmosDBAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosDBAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
      }
    ]
    enableFreeTier: false
    isVirtualNetworkFilterEnabled: false
    publicNetworkAccess: 'Enabled'
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

resource cosmosDBDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosDBAccount
  name: cosmosDBDatabaseName
  location: location
  properties: {
    resource: {
      id: cosmosDBDatabaseName
    }
  }
}

resource cosmosDBContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDBDatabase
  name: cosmosDBContainerName
  location: location
  properties: {
    resource: {
      id: cosmosDBContainerName
      partitionKey: {
        paths: [
          '/user_id'
        ]
        kind: 'Hash'
        version: 2
      }
      defaultTtl: 1000
    }
  }
}

resource bingSearchAccount 'Microsoft.Bing/accounts@2020-06-10' = {
  kind: 'Bing.Search.v7'
  name: bingSearchAPIName
  location: 'global'
  sku: {
    name: 'S1'
  }
}

resource formRecognizerAccount 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: formRecognizerName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'FormRecognizer'
  properties: {
    apiProperties: {
      statisticsEnabled: false
    }
  }
}

resource blobStorageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: blobStorageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
}

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: blobStorageAccount
  name: 'default'
}

resource blobStorageContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = [for containerName in ['books', 'cord19', 'mixed'] : {
  parent: blobServices
  name: containerName
}]


output azureSearchName string = azureSearchName
output azureSearchEndpoint string = 'https://${azureSearchName}.search.windows.net'
output SQLServerName string = SQLServerName
output SQLDatabaseName string = SQLDBName
output cosmosDBAccountName string = cosmosDBAccountName
output cosmosDBDatabaseName string = cosmosDBDatabaseName
output cosmosDBContainerName string = cosmosDBContainerName
output bingSearchAPIName string = bingSearchAPIName
output formRecognizerName string = formRecognizerName
output blobStorageAccountName string = blobStorageAccountName
output formrecognizerEndpoint string = 'https://${formRecognizerName}.cognitiveservices.azure.com'
output formRecognizerKey string = formRecognizerAccount.listKeys().key1
output azureSearchKey string = azureSearch.listAdminKeys().primaryKey
output cosmosDBAccountEndpoint string = cosmosDBAccount.properties.documentEndpoint
output cosmosDBConnectionString string = 'AccountEndpoint=${cosmosDBAccount.properties.documentEndpoint};AccountKey=${cosmosDBAccount.listKeys().primaryMasterKey}' 
output bingServiceSearchKey string = bingSearchAccount.listKeys().key1
output cognitiveServiceName string = cognitiveServiceName
output cognitiveServiceKey string = cognitiveService.listKeys().key1
output blobConnectionString string = 'DefaultEndpointsProtocol=https;AccountName=${blobStorageAccountName};AccountKey=${blobStorageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
