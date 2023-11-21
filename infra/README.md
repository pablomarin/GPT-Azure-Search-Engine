## Table of Contents

- [Setup Local environment](#setup-local-environment)
  - [Installing PowerShell](#installing-powershell)
  - [Installing Azure Developer CLI (azd)](#installing-azure-developer-cli)
- [Provision infrastructure](#provision-infrastructure)
- [Deploying from scratch](#deploying-from-scratch)
- [Deploying with existing Azure resources](#deploying-with-existing-azure-resources)
- [Troubleshooting](#troubleshooting)

### Define environment variables for running services

1. Modify or add environment variables to configure the running application. Environment variables can be configured by updating the `settings` node(s) for each service in [main.parameters.json](./infra/main.parameters.json).
2. For services using a database, environment variables have been pre-configured under the `env` node in the following files to allow connection to the database. Modify the name of these variables as needed to match your application.
   - [app/common.bicep](./infra/app/common.bicep)
3. For services using Redis, environment variables will not show up under `env` explicitly, but are available as: `REDIS_ENDPOINT`, `REDIS_HOST`, `REDIS_PASSWORD`, and `REDIS_PORT`.

### Setup Local environment

First install the required tools:

- [Azure Developer CLI](https://aka.ms/azure-dev/install)
- [Python 3.9, 3.10, or 3.11](https://www.python.org/downloads/)
  - **Important**: Python and the pip package manager must be in the path in Windows for the setup scripts to work.
  - **Important**: Ensure you can run `python --version` from console. On Ubuntu, you might need to run `sudo apt install python-is-python3` to link `python` to `python3`.
- [Git](https://git-scm.com/downloads)
- [Powershell 7+ (pwsh)](https://github.com/powershell/powershell) - For Windows users only.
  - **Important**: Ensure you can run `pwsh.exe` from a PowerShell terminal. If this fails, you likely need to upgrade PowerShell.

#### Installing PowerShell

PowerShell is a cross-platform task automation solution consisting of a command-line shell, a scripting language, and a configuration management framework. PowerShell runs on Windows, Linux, and macOS.

##### Windows

- PowerShell comes pre-installed on Windows 10 and later.
- To update or install the latest version, visit [Microsoft's PowerShell GitHub page](https://github.com/PowerShell/PowerShell).

##### Linux (PowerShell 7+)

- For Ubuntu and other Linux distributions, follow the instructions in the [official guide](https://learn.microsoft.com/en-us/powershell/scripting/install/install-ubuntu?view=powershell-7.3).

##### macOS (PowerShell 7+)

- For macOS, use Homebrew to install PowerShell:

  ```bash
  brew install --cask powershell
  ```

#### Installing Azure Developer CLI

The Azure Developer CLI (azd) is a command-line tool for building, deploying, and managing Azure resources in a repeatable and predictable manner.

##### Windows OS

- Install using winget:

  ```bash
  winget install AzureDeveloperCLI
  ```

##### macOS

- Install using Homebrew:

  ```bash
  brew install azure-developer-cli
  ```

##### Linux

- Install using the script method:

  ```bash

  curl -fsSL https://aka.ms/install-azd.sh | bash
  ```

- For more details, refer to the [installation guide](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd?tabs=winget-windows%2Cbrew-mac%2Cscript-linux&pivots=os-linux).

### Provision infrastructure

1. Run `azd auth login` to conect to your azure tenant

2. Run `azd up` to provision your infrastructure and deploy to Azure in one step (or run `azd provision` then `azd deploy` to accomplish the tasks separately). Visit the service endpoints listed to see your application up-and-running!

To troubleshoot any issues, see [troubleshooting](#troubleshooting).

### Deploying from scratch

Execute the following command, if you don't have any pre-existing Azure services and want to start from a fresh deployment.

1. Open the terminal.

2. Run `azd auth login` to conect to your azure tenant

    * note : if your using Azure Machine Learning Compute to run the deployement you need to use `azd auth login --use-device-code` and follow the instruction to connect to Azure.
      - **Important**: for Microsoft FTE using fdpo tenant and Azure Machine Learning Studio Compute. This will not work as fdpo policies don't allow --use-device-code option.

3. Run `azd up` - This will provision Azure resources and deploy this sample to those resources.
   - **Important**: Beware that the resources created by this command will incur immediate costs, primarily from the Cognitive Search resource. These resources may accrue costs even if you interrupt the command before it is fully executed. You can run `azd down` or delete the resources manually to avoid unnecessary spending.
   - You will be prompted to select two locations, one for the majority of resources and one for the OpenAI resource, which is currently a short list. That location list is based on the [OpenAI model availability table](https://learn.microsoft.com/azure/cognitive-services/openai/concepts/models#model-summary-table-and-region-availability) and may become outdated as availability changes.

4. After the application has been successfully deployed you will see a backend and frontend URL printed to the console. Click that frontend URL to interact with the application in your browser.

> NOTE: It may take 5 minutes for the application to be fully deployed. If you see a "Python Developer" welcome screen or an error page, then wait a bit and refresh the page.

### Deploying with existing Azure resources

If you already have existing Azure resources, you can re-use those by setting `azd` environment values.

#### Existing resource group

1. Run `azd env set AZURE_RESOURCE_GROUP {Name of existing resource group}`
1. Run `azd env set AZURE_LOCATION {Location of existing resource group}`

#### Existing Azure OpenAI resource

1. Run `azd env set AZURE_OPENAI_SERVICE {Name of existing OpenAI service}`
1. Run `azd env set AZURE_OPENAI_RESOURCE_GROUP {Name of existing resource group that OpenAI service is provisioned to}`
1. Run `azd env set AZURE_OPENAI_CHATGPT_DEPLOYMENT {Name of existing ChatGPT deployment}`. Only needed if your ChatGPT deployment is not the default model name.
1. Run `azd env set AZURE_OPENAI_EMB_DEPLOYMENT {Name of existing GPT embedding deployment}`. Only needed if your embeddings deployment is not the default model name.

When you run `azd up` after and are prompted to select a value for `openAiResourceGroupLocation`, make sure to select the same location as the existing OpenAI resource group.

## Troubleshooting

Q: I visited the service endpoint listed, and I'm seeing a blank or error page.

A: Your service may have failed to start or misconfigured. To investigate further:

1. Click on the resource group link shown to visit Azure Portal.
2. Navigate to the specific Azure Container App resource for the service.
3. Select _Monitoring -> Log stream_ under the navigation pane.
4. Observe the log output to identify any errors.
5. If logs are written to disk, examine the local logs or debug the application by using the _Console_ to connect to a shell within the running container.

For additional information about setting up your `azd` project, visit our official [docs](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/make-azd-compatible?pivots=azd-convert).
