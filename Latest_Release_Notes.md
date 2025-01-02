## Release Notes
### Version: 4.0.0

- Updated API versions:
  - Azure AI Search: 2024-11-01-preview
  - Azure OpenAI: 2024-10-01-preview
- Datasets are now included in the github repo
  - Dataset for Notebook 1 is now the diaglogues of each episode of the TV Show: Friends
  - This will make the VBD delivery more fun for the attendees
- Added latest compression techniques to Indexes
  - Notebooks 1 and 2 now compress vector indexes size up to 90%
- Every notebook and agents are updated to work with gpt-4o and gpt-4o-mini models.
- Environments has been updated to use Python 3.12
- All Notebooks has been updated to use agents with LangGraph
- Added CosmosDB Checkpointer for LangGraph (in process to be added to Langchain official repo)
- Bot Framework code updated to the latest version
- Bot Service is now Single-Tenant (based on user's feedback regarding security)
- Multi-Modality Notebook 11 Added. 
  - audio_utils.py contains all the functions to add Whisper, TTS and Azure Speech Service capabilities
  - Images and Audio input are now included on the notebooks and on the supervisor architecture
- Remove dependency of LangServe. Now it is FastAPI native only.
  - Based on customer's feedback. The FastAPI does not use LangServe code. It is only FastAPI code.
  - Implemented /stream endpoint using the Standard SSE Format (Servers side Events).
- Web App frontend now allows for the user to speak to the Agent via the microphone
  
