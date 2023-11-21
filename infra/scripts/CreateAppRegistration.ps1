$ErrorActionPreference = "Stop"
& $PSScriptRoot\loadenv.ps1

$appName = $env:AZURE_ENV_NAME + '-app'
$appURI = "http://$env:AZURE_ENV_NAME.fdpo.onmicrosoft.com"
$appHomePageUrl = $appURI

$myApp = az ad app list --filter "displayName eq '$appName'" --query "[0]" -o json | ConvertFrom-Json
if ($null -eq $myApp) {
    $myApp = az ad app create --display-name $appName --query "{displayName: displayName, appId: appId}"  -o json | ConvertFrom-Json       
}
else {
    Write-Host "Application already exists"    
}

$credential = az ad app credential reset --id $myApp.appId --display-name 'MSAPP_SECRET' --append --query "password" -o tsv


azd env set AZURE_APP_ID $myApp.appId
azd env set AZURE_APP_SECRET $credential
Write-Host "Application ID: $($myApp.appId) and Secret Saved in azd environment variables" -ForegroundColor Green








