# server.py
import os
import sys
import uvicorn
import asyncio
import uuid
import logging
from typing import List

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from pathlib import Path
from dotenv import load_dotenv

csv_file_path = "data/all-states-history.csv"
api_file_path = "data/openapi_kraken.json"

##########################################################
## Uncomment this section to run locally
current_file = Path(__file__).resolve()
library_path = current_file.parents[4]
data_path = library_path / "data"
sys.path.append(str(library_path))   # ensure we can import "common" etc.
load_dotenv(str(library_path) + "/credentials.env")
csv_file_path = data_path / "all-states-history.csv"
api_file_path = data_path / "openapi_kraken.json"
##########################################################

# from the graph module
from common.graph import build_async_workflow

# For CosmosDB checkpointer
from common.cosmosdb_checkpointer import AsyncCosmosDBSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

# SSE
from sse_starlette.sse import EventSourceResponse

# -----------------------------------------------------------------------------
# Logging setup
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,  # or logging.INFO if you want less verbosity
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# CosmosDB and Workflow Initialization
# -----------------------------------------------------------------------------
checkpointer_async = AsyncCosmosDBSaver(
    endpoint=os.environ.get("AZURE_COSMOSDB_ENDPOINT", ""),
    key=os.environ.get("AZURE_COSMOSDB_KEY", ""),
    database_name=os.environ.get("AZURE_COSMOSDB_NAME", ""),
    container_name=os.environ.get("AZURE_COSMOSDB_CONTAINER_NAME", ""),
    serde=JsonPlusSerializer(),
)

workflow = build_async_workflow(csv_file_path,api_file_path )
graph_async = None


# -----------------------------------------------------------------------------
# Lifespan Event Handler
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_async
    logger.info("Running checkpointer_async.setup() at startup.")
    await checkpointer_async.setup()
    
    logger.info("Compiling the graph with the cosmos checkpointer.")
    graph_async = workflow.compile(checkpointer=checkpointer_async)
    logger.info("Graph compilation complete.")
    
    yield  # The app runs while execution is paused here
    
    logger.info("Shutting down application.")



# -----------------------------------------------------------------------------
# FastAPI App Setup
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Multi-Agent GPT Assistant (FastAPI)",
    version="1.0",
    description="GPT Smart Search Engine - FastAPI Backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def redirect_to_docs():
    return RedirectResponse("/docs")


# -----------------------------------------------------------------------------
# Define Pydantic Models
# -----------------------------------------------------------------------------
class AskRequest(BaseModel):
    user_input: str
    thread_id: str = ""

class AskResponse(BaseModel):
    final_answer: str

class BatchRequest(BaseModel):
    questions: List[str]
    thread_id: str = ""

class BatchResponse(BaseModel):
    answers: List[str]



# -----------------------------------------------------------------------------
# Invoke Endpoint
# -----------------------------------------------------------------------------
@app.post("/invoke", response_model=AskResponse)
async def invoke(req: AskRequest):
    logger.info("[/invoke] Called with user_input=%s, thread_id=%s", req.user_input, req.thread_id)

    if not graph_async:
        logger.error("Graph not compiled yet.")
        raise HTTPException(status_code=500, detail="Graph not compiled yet.")

    config = {"configurable": {"thread_id": req.thread_id or str(uuid.uuid4())}}
    inputs = {"messages": [("human", req.user_input)]}

    try:
        logger.debug("[/invoke] Invoking graph_async with config=%s", config)
        result = await graph_async.ainvoke(inputs, config=config)
        final_answer = result["messages"][-1].content
        logger.info("[/invoke] Final answer: %s", final_answer)
        return AskResponse(final_answer=final_answer)
    except Exception as e:
        logger.exception("[/invoke] Exception while running the workflow")
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# Batch Endpoint
# -----------------------------------------------------------------------------
@app.post("/batch", response_model=BatchResponse)
async def batch(req: BatchRequest):
    logger.info("[/batch] Called with thread_id=%s, questions=%s", req.thread_id, req.questions)

    if not graph_async:
        logger.error("Graph not compiled yet.")
        raise HTTPException(status_code=500, detail="Graph not compiled yet.")

    answers = []
    for question in req.questions:
        config = {"configurable": {"thread_id": req.thread_id or str(uuid.uuid4())}}
        inputs = {"messages": [("human", question)]}
        try:
            result = await graph_async.ainvoke(inputs, config=config)
            final_answer = result["messages"][-1].content
            answers.append(final_answer)
        except Exception as e:
            logger.exception("[/batch] Exception while running the workflow for question=%s", question)
            answers.append(f"Error: {str(e)}")

    return BatchResponse(answers=answers)


# -----------------------------------------------------------------------------
# Streaming Endpoint
# -----------------------------------------------------------------------------
@app.post("/stream")
async def stream(req: AskRequest):
    logger.info("[/stream] Called with user_input=%s, thread_id=%s", req.user_input, req.thread_id)

    if not graph_async:
        logger.error("Graph not compiled yet.")
        raise HTTPException(status_code=500, detail="Graph not compiled yet.")

    config = {"configurable": {"thread_id": req.thread_id or str(uuid.uuid4())}}
    inputs = {"messages": [("human", req.user_input)]}

    async def event_generator():
        accumulated_text = ""
        try:
            async for event in graph_async.astream_events(inputs, config, version="v2"):
                if event["event"] == "on_chat_model_stream" and event["metadata"].get("langgraph_node") == "agent":
                    chunk_text = event["data"]["chunk"].content
                    accumulated_text += chunk_text
                    yield {"event": "partial", "data": chunk_text}
                elif event["event"] == "on_tool_start":
                    yield {"event": "tool_start", "data": f"Starting {event.get('name','')}"}
                elif event["event"] == "on_tool_end":
                    yield {"event": "tool_end", "data": f"Done {event.get('name','')}"}
                elif event["event"] == "on_chain_end" and event.get("name") == "LangGraph":
                    if event["data"]["output"].get("next") == "FINISH":
                        yield {"event": "end", "data": accumulated_text}
                    return
        except Exception as ex:
            logger.exception("[/stream] Error streaming events")
            yield {"event": "error", "data": str(ex)}

    return EventSourceResponse(event_generator(), media_type="text/event-stream")


# -----------------------------------------------------------------------------
# Main Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting server via uvicorn")
    uvicorn.run(app, host="127.0.0.1", port=8000)


