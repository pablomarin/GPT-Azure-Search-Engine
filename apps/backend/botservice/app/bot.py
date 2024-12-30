# bot.py
from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount, Activity, ActivityTypes
from common.cosmosdb_checkpointer import AsyncCosmosDBSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from common.graph import build_async_workflow 
from common.prompts import WELCOME_MESSAGE


class MyBot(ActivityHandler):
    def __init__(self, cosmos_checkpointer=None):
        super().__init__()
        self.checkpointer = cosmos_checkpointer

        csv_file_path = "data/all-states-history.csv"
        api_file_path = "data/openapi_kraken.json"

        # 1) Build the multi-agent workflow
        workflow = build_async_workflow(csv_file_path,api_file_path)

        # 2) Compile with the checkpointer
        self.graph_async = workflow.compile(checkpointer=self.checkpointer)
        
        
    # Function to show welcome message to new users
    async def on_members_added_activity(self, members_added: ChannelAccount, turn_context: TurnContext):
        for member_added in members_added:
            if member_added.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(WELCOME_MESSAGE)
                

    # See https://aka.ms/about-bot-activity-message to learn more about the message and other activity types.
    async def on_message_activity(self, turn_context: TurnContext):
        session_id = turn_context.activity.conversation.id
        user_text = turn_context.activity.text or ""
        
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        config_async = {"configurable": {"thread_id": session_id}}
        inputs = {"messages": [("human", user_text)]}

        # 3) Invoke the multi-agent workflow
        result = await self.graph_async.ainvoke(inputs, config=config_async)

        # 4) The final answer is in the last message
        final_answer = result["messages"][-1].content
        
        await turn_context.send_activity(final_answer)
