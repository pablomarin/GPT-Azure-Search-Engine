# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

Write-Host "Ensuring Azure dependencies are installed."
if (!(Get-Module -Name Az)) {
    Write-Host "Installing Az PowerShell..."
    Install-Module -Name Az
    Import-Module -Name Az
}
if (!(Get-Module -Name Az.Search)) {
    Write-Host "Installing Az.Search PowerShell..."
    Install-Module -Name Az.Search
    Import-Module -Name Az.Search
}

Write-Host @"

------------------------------------------------------------
Guidance for choosing parameters for resource deployment:
 uniqueName: Choose a name that is globally unique and less than 12 characters. This name will be used as a prefix for the resources created and the resultant name must not confict with any other Azure resource. 
   Ex: FabrikamTestPilot1
 
 resourceGroup: Please create a resource group in your Azure account and retrieve it's resource group name.
   Ex: testpilotresourcegroup

 subscriptionId: Your subscription id.
   Ex: 123456-7890-1234-5678-9012345678
------------------------------------------------------------

"@

function Deploy
{
    # Read parameters from user.
    Write-Host "Press enter to use [default] value."
    Write-Host "For uniqueName, please enter a string with 10 or less characters."
    while (!($uniqueName = Read-Host "uniqueName")) { Write-Host "You must provide a uniqueName."; }
    while (!($resourceGroupName = Read-Host "resourceGroupName")) { Write-Host "You must provide a resourceGroupName."; }
    while (!($subscriptionId = Read-Host "subscriptionId")) { Write-Host "You must provide a subscriptionId."; }

    $defaultLocation = "SouthCentralUS"
    if (!($location = Read-Host "location [$defaultLocation]")) { $location = $defaultLocation }
    $defaultSearchSku = "basic"
    if (!($searchSku = Read-Host "searchSku [$defaultSearchSku]")) { $searchSku = $defaultSearchSku }
        
    # Generate derivative parameters.
    $searchServiceName = $uniqueName + "search";
    $webappname = $uniqueName + "app";
    $cogServicesName = $uniqueName + "cog";
    $appInsightsName = $uniqueName + "insights";
    $storageAccountName = $uniqueName + "str";
    $storageContainerName = "documents";
        
    $dataSourceName = $uniqueName + "-datasource";
    $skillsetName = $uniqueName + "-skillset";
    $indexName = $uniqueName + "-index";
    $indexerName = $uniqueName + "-indexer";
 
    # These values are extracted by this process automatically. Do not set values here.
    $global:storageAccountKey = "";
    $global:searchServiceKey = "";
    $global:storageConnectionString = "";
    $global:cogServicesKey = "";
 
    function ValidateParameters
    {
        Write-Host "------------------------------------------------------------";
        Write-Host "Here are the values of all parameters:";
        Write-Host "uniqueName: '$uniqueName'";
        Write-Host "resourceGroupName: '$resourceGroupName'";
        Write-Host "subscriptionId: '$subscriptionId'";
        Write-Host "location: '$location'";
        Write-Host "searchSku: '$searchSku'";
        Write-Host "searchServiceName: '$searchServiceName'";
        Write-Host "webappname: '$webappname'";
        Write-Host "cogServicesName: '$cogServicesName'";
        Write-Host "appInsightsName: '$appInsightsName'";
        Write-Host "storageAccountName: '$storageAccountName'";
        Write-Host "storageContainerName: '$storageContainerName'";
        Write-Host "dataSourceName: '$dataSourceName'";
        Write-Host "skillsetName: '$skillsetName'";
        Write-Host "indexName: '$indexName'";
        Write-Host "indexerName: '$indexerName'";
        Write-Host "------------------------------------------------------------";
	}

    ValidateParameters;
 

    function Signin
    {
        # Sign in
        Write-Host "Logging in for '$subscriptionId'";
        Connect-AzAccount;
	#Use "Connect-AzAccount -UseDeviceAuthentication;" instead of just "Connect-AzAccount" if you would like to be signed in with the account that is already logged on.

        # Select subscription
        Write-Host "Selecting subscription '$subscriptionId'";
        Select-AzSubscription -SubscriptionID $subscriptionId;
	}

    Signin;
    
 
    function PrepareSubscription
    {
        # Register RPs
        $resourceProviders = @("microsoft.cognitiveservices", "microsoft.insights", "microsoft.search", "microsoft.storage");
        if ($resourceProviders.length) {
            Write-Host "Registering resource providers"
            foreach ($resourceProvider in $resourceProviders) {
                Register-AzResourceProvider -ProviderNamespace $resourceProvider;
            }
        }
	}

    PrepareSubscription;
    
    
    function FindOrCreateResourceGroup
    {
        # Create or check for existing resource group
        $resourceGroup = Get-AzResourceGroup -Name $resourceGroupName -ErrorAction SilentlyContinue
        if (!$resourceGroup) {
            Write-Host "Resource group '$resourceGroupName' does not exist.";
            if (!$location) {
                $location = Read-Host "please enter a location:";
            }
            Write-Host "Creating resource group '$resourceGroupName' in location '$location'";
            New-AzResourceGroup -Name $resourceGroupName -Location $location
        }
        else {
            Write-Host "Using existing resource group '$resourceGroupName'";
        }
	}

    FindOrCreateResourceGroup;

    function CreateSearchServices
    {
        # Display and accept RAI and Face Legal Terms and agreement before continue running this script
        Write-Host "One of the Azure resources that is created when deploying this script is a [Cognitive Services multi-service account](https://docs.microsoft.com/azure/cognitive-services/cognitive-services-apis-create-account). You must acknowledge that you have read, understood and agree to the Responsible AI (RAI) Legal Terms and Face Legal Tems so the script can run successfully. Otherwise, the script execution will be cancelled.

        Below are the RAI and Face Legal Terms. For more recent Terms that may be added after this sample is published, review Cognitive Services Terms of Use documentation:

        **Responsible AI Notice**

        Microsoft provides technical documentation regarding the appropriate operation applicable to this Cognitive Service that is made available by Microsoft. Customer acknowledges and agrees that they have reviewed this documentation and will use this service in accordance with it. This Cognitive Services is intended to process Customer Data that includes Biometric Data (as may be further described in product documentation) that Customer may incorporate into its own systems used for personal identification or other purposes. Customer acknowledges and agrees that it is responsible for complying with the Biometric Data obligations contained in the Online Services DPA.

        [Online Services DPA](https://aka.ms/DPA)

        [Responsible Use of AI documentation for Spatial Analysis](https://go.microsoft.com/fwlink/?linkid=2162377)

        [Responsible Use of AI documentation for Text Analytics for Health](https://go.microsoft.com/fwlink/?linkid=2161275)

        [Responsible Use of AI documentation for Text Analytics PII](https://go.microsoft.com/fwlink/?linkid=2162376)


        **Face Notice**

        This service or any Face service that is being created by this Subscription Id, is not by or for a police department in the United States."

        $aiterms = Read-Host "Do you agree with the RAI and Face Legal Terms displayed above? (Y/N)"

        if($aiterms -eq "y") {
            # Register features for RAI and Face Terms after they have been accepted
            Register-AzProviderFeature -FeatureName LegalTerms.ComputerVision.SpatialAnaysisRAITermsAccepted -ProviderNamespace Microsoft.CognitiveServices
            # Create a cognitive services resource
            Write-Host "Creating Cognitive Services";
            $cogServices = New-AzCognitiveServicesAccount `
                -ResourceGroupName $resourceGroupName `
                -Name $cogServicesName `
                -Location $location `
                -SkuName S0 `
                -Type CognitiveServices
            $global:cogServicesKey = (Get-AzCognitiveServicesAccountKey -ResourceGroupName $resourceGroupName -name $cogServicesName).Key1   
            Write-Host "Cognitive Services Key: '$global:cogServicesKey'";
            
            # Create a new search service
            # Alternatively, you can now use the Az.Search module: https://docs.microsoft.com/en-us/azure/search/search-manage-powershell 
            Write-Host "Creating Search Service";
            $searchService = New-AzSearchService  `
                -ResourceGroupName $resourceGroupName `
                -Name $searchServiceName `
                -Sku $searchSku -Location $location `
                -PartitionCount 1 `
                -ReplicaCount 1

            $global:searchServiceKey = (Get-AzSearchAdminKeyPair -ResourceGroupName $resourceGroupName -ServiceName $searchServiceName).Primary         
            Write-Host "Search Service Key: '$global:searchServiceKey'";
        }else {
            #RAI and Face Legal Terms were not accepted
            Write-Host "RAI and Face Legal Terms were not accepted. Script execution can't continue unless they are read and accepted";
            Exit
        }
        
        
        
	}

    CreateSearchServices;

    
    function CreateStorageAccountAndContainer
    {
        # Create a new storage account
        Write-Host "Creating Storage Account";

        # Create the resource using the API
        $storageAccount = New-AzStorageAccount `
            -ResourceGroupName $resourceGroupName `
            -Name $storageAccountName `
            -Location $location `
            -SkuName Standard_LRS `
            -Kind StorageV2 
        
        $global:storageAccountKey = (Get-AzStorageAccountKey -ResourceGroupName $resourceGroupName -StorageAccountName $storageAccountName)[0].Value        
        $global:storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=' + $storageAccountName + ';AccountKey=' + $global:storageAccountKey + ';EndpointSuffix=core.windows.net' 
        Write-Host "Storage Account Key: '$global:storageAccountKey'";
                
        $storageContext = New-AzStorageContext `
            -StorageAccountName $storageAccountName `
            -StorageAccountKey $global:storageAccountKey
        
        Write-Host "Creating Storage Container";
        $storageContainer = New-AzStorageContainer `
            -Name $storageContainerName `
            -Context $storageContext `
            -Permission Off

        Write-Host "Uploading sample_documents directory";
        Push-Location "../sample_documents"
        ls -File -Recurse | Set-AzStorageBlobContent -Container $storageContainerName -Context $storageContext -Force
        Pop-Location
	}

    CreateStorageAccountAndContainer;
    

        

    function CreateSearchIndex
    {
        Write-Host "Creating Search Index"; 
        
        function CallSearchAPI
        {
            param (
                [string]$url,
                [string]$body
            )

            $headers = @{
                'api-key' = $global:searchServiceKey
                'Content-Type' = 'application/json' 
                'Accept' = 'application/json' 
            }
            $baseSearchUrl = "https://"+$searchServiceName+".search.windows.net"
            $fullUrl = $baseSearchUrl + $url
        
            Write-Host "Calling api: '"$fullUrl"'";
            Invoke-RestMethod -Uri $fullUrl -Headers $headers -Method Put -Body $body | ConvertTo-Json
		}; 

        # Create the datasource
        $dataSourceBody = Get-Content -Path .\templates\base-datasource.json  
        $dataSourceBody = $dataSourceBody -replace "{{env_storage_connection_string}}", $global:storageConnectionString      
        $dataSourceBody = $dataSourceBody -replace "{{env_storage_container}}", $storageContainerName        
        CallSearchAPI -url ("/datasources/"+$dataSourceName+"?api-version=2019-05-06") -body $dataSourceBody

        # Create the skillset
        $skillBody = Get-Content -Path .\templates\base-skills.json
        $skillBody = $skillBody -replace "{{cog_services_key}}", $global:cogServicesKey  
        CallSearchAPI -url ("/skillsets/"+$skillsetName+"?api-version=2019-05-06") -body $skillBody

        # Create the index
        $indexBody = Get-Content -Path .\templates\base-index.json 
        CallSearchAPI -url ("/indexes/"+$indexName+"?api-version=2019-05-06") -body $indexBody
        
        # Create the indexer
        $indexerBody = Get-Content -Path .\templates\base-indexer.json
        $indexerBody = $indexerBody -replace "{{datasource_name}}", $dataSourceName
        $indexerBody = $indexerBody -replace "{{skillset_name}}", $skillsetName   
        $indexerBody = $indexerBody -replace "{{index_name}}", $indexName   
        CallSearchAPI -url ("/indexers/"+$indexerName+"?api-version=2019-05-06") -body $indexerBody
	}

    CreateSearchIndex;


    function CreateWebApp
    {
        # Create an App Service plan
        Write-Host "Creating App Service Plan";
        $appService = New-AzAppServicePlan `
            -Name $webappname `
            -Location $location `
            -ResourceGroupName $resourceGroupName `
            -Tier Standard


        # Create a web app.
        Write-Host "Creating Web App";
        $webApp = New-AzWebApp `
            -Name $webappname `
            -Location $location `
            -AppServicePlan $webappname `
            -ResourceGroupName $resourceGroupName `
            -WarningAction SilentlyContinue


        # Create an application insights instance
        Write-Host "Creating App Insights";
        $appInsights = New-AzResource `
            -ResourceName $appInsightsName `
            -ResourceGroupName $resourceGroupName `
            -Tag @{ applicationType = "web"; applicationName = $webappname } `
            -ResourceType "Microsoft.Insights/components" `
            -Location $location `
            -PropertyObject @{"Application_Type" = "web" } `
            -Force


        # Setting App Insights Key in Web app
        Write-Host "Connecting App Insights with Web App";
        $appSetting = @{'APPINSIGHTS_INSTRUMENTATIONKEY' = $appInsights.Properties.InstrumentationKey }
        $updateSettings = Set-AzWebApp `
            -Name $webappname `
            -ResourceGroupName $resourceGroupName `
            -AppSettings $appSetting
	}

    CreateWebApp;

    function PrintAppsettings
    {
        Write-Host "Copy and paste the following values to update the appsettings.json file described in the next folder:";
        Write-Host "------------------------------------------------------------";
        Write-Host "SearchServiceName: '$searchServiceName'";
        Write-Host "SearchApiKey: '$global:searchServiceKey'";
        Write-Host "SearchIndexName: '$indexName'";
        Write-Host "SearchIndexerName: '$indexerName'";
        Write-Host "StorageAccountName: '$storageAccountName'";
        Write-Host "StorageAccountKey: '$global:storageAccountKey'";
        $StorageContainerAddress = ("https://"+$storageAccountName+".blob.core.windows.net/"+$storageContainerName)
        Write-Host "StorageContainerAddress: '$StorageContainerAddress'";
        Write-Host "------------------------------------------------------------";
	}
    PrintAppsettings;
}

Deploy;
