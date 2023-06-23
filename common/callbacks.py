import sys
from typing import Any, Dict, List, Optional, Union
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult

DEFAULT_ANSWER_PREFIX_TOKENS = ["Final", "Answer", ":"]
        
class MyCustomHandler(BaseCallbackHandler):
    """Callback handler for streaming in agents.
    Only works with agents using LLMs that support streaming.
    Only the final output of the agent will be streamed.
    """
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run on new LLM token. Only available when streaming is enabled."""
        sys.stdout.write(token)
        sys.stdout.flush()

    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> Any:
        """Run when LLM errors."""
        sys.stdout.write(f"LLM Error: {error}\n")

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> Any:
        """Print out that we are entering a chain."""

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> Any:
        sys.stdout.write(f"Tool: {serialized['name']}\n")

    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
        sys.stdout.write(f"{action.log}\n")
        
        
