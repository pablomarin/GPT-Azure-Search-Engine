@description('Optional. Service name must only contain lowercase letters, digits or dashes, cannot use dash as the first two or last one characters, cannot contain consecutive dashes, and is limited between 2 and 60 characters in length.')
@minLength(2)
@maxLength(60)
param Azure_Search_Name string = 'cog-search-${uniqueString(resourceGroup().id)}'

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
param Azure_Search_SKU string = 'standard'

@description('Optional, defaults to 1. Replicas distribute search workloads across the service. You need at least two replicas to support high availability of query workloads (not applicable to the free tier). Must be between 1 and 12.')
@minValue(1)
@maxValue(12)
param Azure_Search_replicaCount int = 1

@description('Optional, defaults to 1. Partitions allow for scaling of document count as well as faster indexing by sharding your index over multiple search units. Allowed values: 1, 2, 3, 4, 6, 12.')
@allowed([
  1
  2
  3
  4
  6
  12
])
param Azure_Search_partitionCount int = 1

@description('Optional, defaults to default. Applicable only for SKUs set to standard3. You can set this property to enable a single, high density partition that allows up to 1000 indexes, which is much higher than the maximum indexes allowed for any other SKU.')
@allowed([
  'default'
  'highDensity'
])
param Azure_Search_hostingMode string = 'default'

@description('Optional. The name of our application. It has to be unique. Type a name followed by your resource group name. (<name>-<resourceGroupName>)')
param Cognitive_Service_Name string = 'cognitive-service-${uniqueString(resourceGroup().id)}'

@description('Optional. The name of the SQL logical server.')
param SQLserver_Name string = 'sql-server-${uniqueString(resourceGroup().id)}'

@description('Optional. The name of the SQL Database.')
param SQLDB_Name string = 'SampleDB'

@description('Required. The administrator username of the SQL logical server.')
param SQLadministratorLogin string

@description('Required. The administrator password of the SQL logical server.')
@secure()
param SQLadministratorLoginPassword string

@description('Optional. The name of the Bing Search API service')
param Bing_Search_API_Name string = 'bing-search-${uniqueString(resourceGroup().id)}'

@description('Optional. Cosmos DB account name, max length 44 characters, lowercase')
param Cosmos_Account_Name string = 'cosmosdb-account-${uniqueString(resourceGroup().id)}'

@description('Optional. The name for the CosmosDB database')
param Cosmos_Database_Name string = 'cosmosdb-db-${uniqueString(resourceGroup().id)}'

@description('Optional. The name for the CosmosDB database container')
param Cosmos_Container_Name string = 'cosmosdb-container-${uniqueString(resourceGroup().id)}'

@description('Optional, defaults to resource group location. The location of the resources.')
param resourcesLocation string = resourceGroup().location

var Cognitive_Service_SKU = 'S0'

resource azureSearch 'Microsoft.Search/searchServices@2021-04-01-Preview' = {
  name: Azure_Search_Name
  location: resourcesLocation
  sku: {
    name: Azure_Search_SKU
  }
  properties: {
    replicaCount: Azure_Search_replicaCount
    partitionCount: Azure_Search_partitionCount
    hostingMode: Azure_Search_hostingMode
    semanticSearch: 'free'
  }
}

resource cognitiveService 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: Cognitive_Service_Name
  location: resourcesLocation
  sku: {
    name: Cognitive_Service_SKU
  }
  kind: 'CognitiveServices'
  properties: {
    apiProperties: {
      statisticsEnabled: false
    }
  }
}

resource SQLServer 'Microsoft.Sql/servers@2022-11-01-preview' = {
  name: SQLserver_Name
  location: resourcesLocation
  properties: {
    administratorLogin: SQLadministratorLogin
    administratorLoginPassword: SQLadministratorLoginPassword
  }
}

resource SQLDatabase 'Microsoft.Sql/servers/databases@2022-11-01-preview' = {
  parent: SQLServer
  name: SQLDB_Name
  location: resourcesLocation
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

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: Cosmos_Account_Name
  location: resourcesLocation
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: resourcesLocation
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

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosAccount
  name: Cosmos_Database_Name
  location: resourcesLocation
  properties: {
    resource: {
      id: Cosmos_Database_Name
    }
  }
}

resource cosmosContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: Cosmos_Container_Name
  location: resourcesLocation
  properties: {
    resource: {
      id: Cosmos_Container_Name
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
  name: Bing_Search_API_Name
  location: 'global'
  sku: {
    name: 'S1'
  }
}
