![image](https://user-images.githubusercontent.com/113465005/226238596-cc76039e-67c2-46b6-b0bb-35d037ae66e1.png)

# AI Multi-Agent Architecture 3 or 5 days POC: Build Intelligent Agents with Azure Services

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/MSUSAzureAccelerators/Azure-Cognitive-Search-Azure-OpenAI-Accelerator?quickstart=1)
[![Open in VS Code Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Remote%20-%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/MSUSAzureAccelerators/Azure-Cognitive-Search-Azure-OpenAI-Accelerator)


Welcome to the **AI Multi-Agent Architecture Workshop**, designed for organizations seeking to unlock the power of AI-driven intelligent agents. Over this 3-to-5-day interactive workshop, Microsoft architects will guide you step-by-step to build a private, secure AI system tailored to your business needs.

This workshop will teach you how to develop a **multi-agent system** capable of comprehending diverse datasets across various locations. These intelligent agents can answer questions with detailed explanations and source references, providing your organization with a powerful, ChatGPT-like experience designed for enterprise use.

## What You'll Build

This hands-on workshop will walk you through creating a Proof of Concept (POC) for a **Generative AI Multi-Agent Architecture** using Azure Services. By the end of the workshop, you'll have built:

1. **A Scalable Backend**  
   Developed with Bot Framework and FastAPI, the backend serves as the engine connecting AI logic to multiple communication channels, including:
   - Web Chat
   - Microsoft Teams
   - SMS
   - Email
   - Slack, and more!

2. **A User-Friendly Frontend**  
   Build a web application that combines:
   - A **search engine** capable of querying your data intelligently.
   - A **bot UI** for seamless conversational experiences.

3. **A RAG-Based Multi-Agent Architecture**  
   Leverage Retrieval-Augmented Generation (RAG) to enable your agents to retrieve precise information and generate accurate responses.

## Workshop Highlights

- **Step-by-Step Guidance**: Each module builds upon the previous one, progressively introducing you to real-world AI architecture concepts.
- **Custom Enterprise AI**: Create intelligent agents that understand your organization’s data while maintaining privacy and security.
- **Multi-Channel Capabilities**: Deploy your agents across various platforms for broad accessibility.
- **Practical Experience**: Learn by doing, with notebooks and code samples tailored for an enterprise setting.

## Why Attend?

By the end of the workshop, you'll have a working knowledge of how to design, build, and deploy AI agents in a multi-agentic architecture. This hands-on experience will help you understand the value of Azure-powered Generative AI in solving real-world business problems.

---

## For Microsoft Employees

This is a **customer-funded Value-Based Delivery (VBD)**. Below, you'll find all the assets and resources needed for a successful workshop delivery.


| **Item**                   | **Description**                                                                                                     | **Link**                                                                                                                                                |
|----------------------------|---------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| VBD SKU Info and Datasheet                   | CSAM must dispatch it as "Customer Invested" against credits/hours of Unified Support Contract. Customer decides if 3 or 5 days.                                      | [ESXP SKU page](https://esxp.microsoft.com/#/omexplanding/services/14486/geo/USA/details/1)                                                                                              |
| VBD Accreditation for CSAs     | Links for CSAs to get the Accreditation needed to deliver the workshop                                                                      | [Link 1](https://learningplayer.microsoft.com/activity/s9261799/launch) , [Link 2](https://learningplayer.microsoft.com/activity/s9264662/launch) |
| VBD 3-5 day POC Asset (IP)  | The MVP to be delivered  (this GitHub repo)                                     | [Azure-Cognitive-Search-Azure-OpenAI-Accelerator](https://github.com/MSUSAzureAccelerators/Azure-Cognitive-Search-Azure-OpenAI-Accelerator)                |
| VBD Workshop Deck          | The deck introducing and explaining the workshop                                                                    | [Intro AOAI GPT Azure Smart Search Engine Accelerator.pptx](https://github.com/MSUSAzureAccelerators/Azure-Cognitive-Search-Azure-OpenAI-Accelerator/blob/main/Intro%20AOAI%20GPT%20Azure%20Smart%20Search%20Engine%20Accelerator.pptx) |
| CSA Training Video         | 2 Hour Training for Microsoft CSA's                                                                    | [POC VBD Training Recording](https://microsoft-my.sharepoint.com/:v:/p/annagross/ETONCWUYCa5EtpmnYjYy9eABK1JV1yo49HDoYjnry1C8-A) |


---
## **Prerequisites Client 3-5 Days POC**
* Azure subscription
* Microsoft members preferably to be added as Guests in clients Azure AD. If not possible, then customers can issue corporate IDs to Microsoft members
* A Resource Group (RG)  needs to be set for this Workshop POC, in the customer Azure tenant
* The customer team and the Microsoft team must have Contributor permissions to this resource group so they can set everything up 2 weeks prior to the workshop
* Customer Data/Documents must be uploaded to the blob storage account, at least two weeks prior to the workshop date
* A Single-Tenant App Registration (Service Principal) must be created by the customer (save the Client Id and Secret Value).
* Customer must provide the Microsoft Team , 10-20 questions (easy to hard) that they want the Agent/Bot to respond correctly.
* For IDE collaboration and standarization during workshop, AML compute instances with Jupyper Lab will be used, for this, Azure Machine Learning Workspace must be deployed in the RG
   * Note: Please ensure you have enough core compute quota in your Azure Machine Learning workspace 

---
## Architecture 
![Architecture](./images/GPT-Smart-Search-Architecture.jpg "Architecture")

## Flow
1. The user asks a question.
2. In the backend app, an Agent determines which source to use based on the user input
3. Five types of sources are available:
   * 3a. Azure SQL Database - contains COVID-related statistics in the US.
   * 3b. API Endpoints - RESTful OpenAPI 3.0 API from a online currency broker.
   * 3c. Azure Bing Search API - provides access to the internet allowing scenerios like: QnA on public websites .
   * 3d. Azure AI Search - contains AI-enriched documents from Blob Storage:
       - Transcripts of the dialogue of all the episodes of the TV Show: FRIENDS  
       - 90,000 Covid publication abstracts
       - 4 lenghty PDF books
   * 3f. CSV Tabular File - contains COVID-related statistics in the US.
4. The Agent retrieves the result from the correct source and crafts the answer.
5. The Agent state is saved to CosmosDB as persistent memory and for further analysis.
6. The answer is delivered to the user.

---
## Demo

[https://gptsmartsearch-frontend.azurewebsites.net](https://gptsmartsearch-frontend.azurewebsites.net)


---

## 🔧**Features**

   - 100% Python.
   - Uses [Azure Cognitive Services](https://azure.microsoft.com/en-us/products/cognitive-services/) to index and enrich unstructured documents: OCR over images, Chunking and automated vectorization.
   - Uses Hybrid Search Capabilities of Azure AI Search to provide the best semantic answer (Text and Vector search combined).
   - Uses [LangChain](https://langchain.readthedocs.io/en/latest/) as a wrapper for interacting with Azure OpenAI , vector stores, constructing prompts and creating agents.
   - Multi-Agentic Architecture using LangGraph.
   - Multi-Lingual (ingests, indexes and understand any language)
   - Multi-Index -> multiple search indexes
   - Multi-modal input and output (text and audio)
   - Tabular Data Q&A with CSV files and SQL flavor Databases
   - Uses [Azure AI Document Intelligence SDK (former Form Recognizer)](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/overview?view=doc-intel-3.0.0) to parse complex/large PDF documents
   - Uses [Bing Search API](https://www.microsoft.com/en-us/bing/apis) to power internet searches and Q&A over public websites.
   - Connects to API Data sources by converting natural language questions to API calls.
   - Uses CosmosDB as persistent memory to save user's conversations.
   - Uses [Streamlit](https://streamlit.io/) to build the Frontend web application in python.
   - Uses [Bot Framework](https://dev.botframework.com/) and [Bot Service](https://azure.microsoft.com/en-us/products/bot-services/) to Host the Bot API Backend and to expose it to multiple channels including MS Teams.
   - Uses also FastAPI to deploy an alternative backend API with streaming capabilites
   
---

## **Steps to Run the POC/Accelerator**

### **Pre-requisite**
You must have an **Azure OpenAI Service** already created.

### **1. Fork the Repository**
- Fork this repository to your GitHub account.

### **2. Deploy Required Models**
In **Azure OpenAI Studio**, deploy the following models:  
*(Note: Older versions of these models will not work)*

- `gpt-4o`  
- `gpt-4o-mini`  
- `text-embedding-3-large`  
- `tts`  
- `whisper`  

### **3. Create a Resource Group**
- Create a **Resource Group (RG)** to house all the assets for this accelerator.  
  - Note: Azure OpenAI services can exist in a different RG or even a different subscription.

### **4. Deploy Azure Infrastructure**
Click the button below to deploy all necessary Azure infrastructure (e.g., Azure AI Search, Cognitive Services, etc.):

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fpablomarin%2FGPT-Azure-Search-Engine%2Fmain%2Fazuredeploy.json)  

**Important:**  
If this is your first time creating an **Azure AI Services Multi-Service Account**, do the following manually:
1. Go to the Azure portal.
2. Create the account.
3. Read and accept the **Responsible AI Terms**.  
Once done, delete this manually created account and then use the above deployment button.

### **5. Choose Your Development Environment**

#### **Option A: Azure Machine Learning (Preferred)**  
1. **Clone** your forked repository to your AML Compute Instance.  
   - If your repository is private, refer to the **Troubleshooting** section for guidance on cloning private repos.  
2. Install the dependencies in a Conda environment. Run the following commands on the **Python 3.12 Conda environment** you plan to use for the notebooks:

   ```bash
   conda create -n GPTSearch python=3.12
   conda activate GPTSearch
   pip install -r ./common/requirements.txt
   conda install ipykernel
   python -m ipykernel install --user --name=GPTSearch --display-name "GPTSearch (Python 3.12)"
   ```

#### **Option B: Visual Studio Code**  
1. **Create a Python virtual environment (.venv):**
   - When creating the virtual environment, select the `./common/requirements.txt` file.
   - Alternatively, install dependencies manually:
     ```bash
     pip install -r ./common/requirements.txt
     ```
2. **Activate the virtual environment:**
   ```bash
   .venv\scripts\activate
   ```
3. Install `ipykernel`:
   ```bash
   pip install ipykernel
   ```

### **6. Configure Credentials**
Edit the `credentials.env` file with the appropriate values from the services created in Step 4.  
- To obtain `BLOB_SAS_TOKEN` and `BLOB_CONNECTION_STRING`, navigate to:  
  **Storage Account > Security + Networking > Shared Access Signature > Generate SAS**

### **7. Run the Notebooks**
- Execute the notebooks **in order**, as they build on top of each other.  
- Use the appropriate kernel:
  - For **AML**, select: `GPTSearch (Python 3.12)`
  - For **VS Code**, select the `.venv` kernel.

### **Troubleshooting**
- If cloning a private repository: Refer to the detailed guide [here](#).
- For issues with dependency installation: Ensure your Python version matches the required version.

---


<details>

<summary>Troubleshooting</summary>
  
## Troubleshooting

Steps to clone a private repo:
- On your Terminal, Paste the text below, substituting in your GitHub email address. [Generate a new SSH key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent#generating-a-new-ssh-key).
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```
- Copy the SSH public key to your clipboard. [Add a new SSH key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent#generating-a-new-ssh-key).
```bash
cat ~/.ssh/id_ed25519.pub
# Then select and copy the contents of the id_ed25519.pub file
# displayed in the terminal to your clipboard
```
- On GitHub, go to **Settings-> SSH and GPG Keys-> New SSH Key**
- In the "Title" field, add a descriptive label for the new key. "AML Compute". In the "Key" field, paste your public key.
- Clone your private repo
```bash
git clone git@github.com:YOUR-USERNAME/YOUR-REPOSITORY.git
```
</details>

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
