# graph.py
# -----------------------------------------------------------------------------
# All logic for building the multi-agent workflow in one place:
#   1) Create the LLM
#   2) Create specialized agents
#   3) Define agent node and supervisor logic
#   4) Build and return the async StateGraph
# -----------------------------------------------------------------------------

import os
import json
import functools
import operator
import logging
from pathlib import Path
from typing_extensions import TypedDict
from pydantic import BaseModel
from typing import Annotated, Sequence, Literal

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END

# from your project
from common.utils import (
    create_docsearch_agent,
    create_csvsearch_agent,
    create_sqlsearch_agent,
    create_websearch_agent,
    create_apisearch_agent,
    reduce_openapi_spec
)
from common.prompts import (
    CUSTOM_CHATBOT_PREFIX,
    DOCSEARCH_PROMPT_TEXT,
    CSV_AGENT_PROMPT_TEXT,
    MSSQL_AGENT_PROMPT_TEXT,
    BING_PROMPT_TEXT,
    APISEARCH_PROMPT_TEXT,
    SUPERVISOR_PROMPT_TEXT
)

# Set up a logger for this module
logger = logging.getLogger(__name__)

os.environ["OPENAI_API_VERSION"] = os.environ.get("AZURE_OPENAI_API_VERSION", "")

# -----------------------------------------------------------------------------
# 1) The typed dictionary for the agent state
# -----------------------------------------------------------------------------
class AgentState(TypedDict):
    """
    The overall "conversation state" that flows through each node.
    messages: the running conversation (list of HumanMessage, AIMessage, etc.)
    next: indicates the next node to run
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str


# -----------------------------------------------------------------------------
# 2) Supervisor route structure
# -----------------------------------------------------------------------------
class routeResponse(BaseModel):
    next: Literal[
        "FINISH",
        "DocSearchAgent",
        "SQLSearchAgent",
        "CSVSearchAgent",
        "WebSearchAgent",
        "APISearchAgent",
    ]


# -----------------------------------------------------------------------------
# 3) Specialized node calls
# -----------------------------------------------------------------------------
async def agent_node_async(state: AgentState, agent, name: str):
    """
    Invokes a specialized agent with the current conversation state.
    The agent returns a dictionary containing 'messages'.
    We then append its final message to the conversation with name=<agent_name>.
    """
    logger.debug("agent_node_async: Called with agent=%s, name=%s, state=%s", agent, name, state)
    try:
        result = await agent.ainvoke(state)
        last_ai_content = result["messages"][-1].content
        logger.debug("agent_node_async: Agent '%s' responded with: %s", name, last_ai_content)
        return {
            "messages": [AIMessage(content=last_ai_content, name=name)]
        }
    except Exception as e:
        logger.exception("Exception in agent_node_async for agent=%s, name=%s", agent, name)
        raise


async def supervisor_node_async(state: AgentState, llm: AzureChatOpenAI):
    """
    Uses an LLM with structured output to figure out:
      -> which agent node should be invoked next, or
      -> FINISH the workflow.
    """
    logger.debug("supervisor_node_async: Called with state=%s", state)
    supervisor_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SUPERVISOR_PROMPT_TEXT),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next? Or should we FINISH?\n"
                "Select one of: ['DocSearchAgent','SQLSearchAgent','CSVSearchAgent',"
                "'WebSearchAgent','APISearchAgent','FINISH'].\n"
            ),
        ]
    )

    chain = supervisor_prompt | llm.with_structured_output(routeResponse)

    try:
        result = await chain.ainvoke(state)
        logger.debug("supervisor_node_async: LLM routing result: %s", result)
        return result
    except Exception as e:
        logger.exception("Exception in supervisor_node_async.")
        raise


# -----------------------------------------------------------------------------
# 4) Build the entire multi-agent workflow in a single function
# -----------------------------------------------------------------------------
def build_async_workflow(csv_file_path: str ="all-states-history.csv", 
                         api_file_path: str ="openapi_kraken.json"):
    """
    Creates the LLM, specialized agents, and the async StateGraph
    that orchestrates them with a supervisor node. Returns the
    not-yet-compiled workflow. You can then compile it with a checkpointer.
    """
    logger.debug("build_async_workflow: Starting building workflow")

    # ------------------------------------
    # A) Create LLM
    # ------------------------------------
    model_name = os.environ.get("GPT4o_DEPLOYMENT_NAME", "")
    logger.debug("Creating LLM with deployment_name=%s", model_name)

    llm = AzureChatOpenAI(
        deployment_name=model_name,
        temperature=0,
        max_tokens=2000,
        streaming=True,  # set True if you want partial streaming from the LLM
    )

    # ------------------------------------
    # B) Create specialized agents
    # ------------------------------------
    logger.debug("Creating docsearch_agent, csvsearch_agent, sqlsearch_agent, websearch_agent, apisearch_agent")

    docsearch_agent = create_docsearch_agent(
        llm=llm,
        indexes=["srch-index-files", "srch-index-csv", "srch-index-books"],
        k=20,
        reranker_th=1.5,
        prompt=CUSTOM_CHATBOT_PREFIX + DOCSEARCH_PROMPT_TEXT,
        sas_token=os.environ.get("BLOB_SAS_TOKEN", "")
    )

    csvsearch_agent = create_csvsearch_agent(
        llm=llm,
        prompt=CUSTOM_CHATBOT_PREFIX + CSV_AGENT_PROMPT_TEXT.format(
            file_url=str(csv_file_path)
        )
    )

    sqlsearch_agent = create_sqlsearch_agent(
        llm=llm,
        prompt=CUSTOM_CHATBOT_PREFIX + MSSQL_AGENT_PROMPT_TEXT
    )

    websearch_agent = create_websearch_agent(
        llm=llm,
        prompt=CUSTOM_CHATBOT_PREFIX + BING_PROMPT_TEXT
    )

    logger.debug("Reading API openapi_kraken.json from %s", api_file_path)
    with open(api_file_path, "r") as file:
        spec = json.load(file)
    reduced_api_spec = reduce_openapi_spec(spec)

    apisearch_agent = create_apisearch_agent(
        llm=llm,
        prompt=CUSTOM_CHATBOT_PREFIX + APISEARCH_PROMPT_TEXT.format(
            api_spec=reduced_api_spec
        )
    )

    # ------------------------------------
    # C) Build the async LangGraph
    # ------------------------------------
    logger.debug("Building the StateGraph for multi-agent workflow")
    workflow = StateGraph(AgentState)

    sup_node = functools.partial(supervisor_node_async, llm=llm)
    workflow.add_node("supervisor", sup_node)

    doc_node = functools.partial(agent_node_async, agent=docsearch_agent, name="DocSearchAgent")
    csv_node = functools.partial(agent_node_async, agent=csvsearch_agent, name="CSVSearchAgent")
    sql_node = functools.partial(agent_node_async, agent=sqlsearch_agent, name="SQLSearchAgent")
    web_node = functools.partial(agent_node_async, agent=websearch_agent, name="WebSearchAgent")
    api_node = functools.partial(agent_node_async, agent=apisearch_agent, name="APISearchAgent")

    workflow.add_node("DocSearchAgent", doc_node)
    workflow.add_node("CSVSearchAgent", csv_node)
    workflow.add_node("SQLSearchAgent", sql_node)
    workflow.add_node("WebSearchAgent", web_node)
    workflow.add_node("APISearchAgent", api_node)

    for agent_name in ["DocSearchAgent", "CSVSearchAgent", "SQLSearchAgent", "WebSearchAgent", "APISearchAgent"]:
        workflow.add_edge(agent_name, "supervisor")

    conditional_map = {
        "DocSearchAgent": "DocSearchAgent",
        "SQLSearchAgent": "SQLSearchAgent",
        "CSVSearchAgent": "CSVSearchAgent",
        "WebSearchAgent": "WebSearchAgent",
        "APISearchAgent": "APISearchAgent",
        "FINISH": END
    }
    workflow.add_conditional_edges("supervisor", lambda x: x["next"], conditional_map)
    workflow.add_edge(START, "supervisor")

    logger.debug("build_async_workflow: Workflow build complete")
    return workflow
