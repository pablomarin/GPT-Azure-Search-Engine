# app.py
# -----------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

import os
import sys
import asyncio
import traceback
from datetime import datetime

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import TurnContext
from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ActivityTypes

from bot import MyBot
from config import DefaultConfig

# ---- Imports for CosmosDB checkpointer usage
from common.cosmosdb_checkpointer import AsyncCosmosDBSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

CONFIG = DefaultConfig()

# Create adapter.
# See https://aka.ms/about-bot-adapter to learn more about how bots work.
ADAPTER = CloudAdapter(ConfigurationBotFrameworkAuthentication(CONFIG))

# Catch-all for errors
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    # NOTE: In production environment, you should consider logging this to Azure
    #       application insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # Send a message to the user
    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity(
        "To continue to run this bot, please fix the bot source code."
    )
    # Send a trace activity if we're talking to the Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        # Create a trace activity that contains the error object
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        # Send a trace activity, which will be displayed in Bot Framework Emulator
        await context.send_activity(trace_activity)

ADAPTER.on_turn_error = on_error

# -----------------------------------------------------------------------------
# 1) Create a single, shared AsyncCosmosDBSaver instance for the entire service.
# -----------------------------------------------------------------------------

checkpointer_async = AsyncCosmosDBSaver(
    endpoint=os.environ.get("AZURE_COSMOSDB_ENDPOINT"),
    key=os.environ.get("AZURE_COSMOSDB_KEY"),
    database_name=os.environ.get("AZURE_COSMOSDB_NAME"),
    container_name=os.environ.get("AZURE_COSMOSDB_CONTAINER_NAME"),
    serde=JsonPlusSerializer(),
)

# Setup the checkpointer (async). We can do so using run_until_complete here:
loop = asyncio.get_event_loop()
loop.run_until_complete(checkpointer_async.setup())

# -----------------------------------------------------------------------------
# 2) Pass that single checkpointer to the bot.
# -----------------------------------------------------------------------------
BOT = MyBot(cosmos_checkpointer=checkpointer_async)

# Listen for incoming requests on /api/messages
async def messages(req: Request) -> Response:
    return await ADAPTER.process(req, BOT)


APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        web.run_app(APP, host="localhost", port=CONFIG.PORT)
    except Exception as error:
        raise error