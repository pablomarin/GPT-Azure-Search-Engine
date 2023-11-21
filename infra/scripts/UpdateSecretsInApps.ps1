
$ErrorActionPreference = "Stop"

& $PSScriptRoot\loadenv.ps1

$jsonObject = az bot directline show --name $env:AZURE_BOT_SERVICE --resource-group $env:AZURE_RESOURCE_GROUP --with-secrets true | ConvertFrom-Json
$defaultSite = $jsonObject.properties.properties.sites | Where-Object { $_.siteName -eq "Default Site" }
$defaultSiteKey = $defaultSite.key.ToString()

# Generate SAS for BlobStorage to access the container
$expiry=(Get-Date).AddDays(7).ToString('yyyy-MM-ddTHH:mm:ssZ')
$SAS_TOKEN=az storage container generate-sas --account-name $env:AZURE_BLOB_STORAGE_ACCOUNT_NAME --name 'cord19' --permissions dlrw --expiry $expiry --auth-mode login --as-user
azd env set BLOB_SAS_TOKEN $SAS_TOKEN

# Write value to Azure App Service configuration
write-host "Update Frontend APP configuration" -ForegroundColor Gray
az webapp config appsettings set --name $env:AZURE_FRONTEND_WEBAPP_NAME --resource-group $env:AZURE_RESOURCE_GROUP --settings BOT_DIRECTLINE_SECRET_KEY=$defaultSiteKey BLOB_SAS_TOKEN=$SAS_TOKEN
# Write value to Azure App Service configuration
write-host "Update Backend APP configuration" -ForegroundColor Gray
az webapp config appsettings set --name $env:AZURE_BACKEND_WEBAPP_NAME --resource-group $env:AZURE_RESOURCE_GROUP --settings BLOB_SAS_TOKEN=$SAS_TOKEN

Write-host "Generate Service Principal for Github actin deployment" -ForegroundColor Gray
az ad sp create-for-rbac --name $env:AZURE_ENV_NAME --role contributor --scopes "/subscriptions/$env:AZURE_SUBSCRIPTION_ID/resourceGroups/$env:AZURE_RESOURCE_GROUP"



