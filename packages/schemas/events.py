from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class BaseEvent(BaseModel):
    timestamp: datetime
    source_process: str  # e.g., "claude-code", "vscode", "openclaw"
    pid: Optional[int]
    event_type: str      # "network_inference", "terminal_command", "agent_to_agent"

class LLMReasoningContext(BaseModel):
    prompt: str
    raw_response: str
    extracted_thinking: Optional[str] # What the agent planned to do (from <thinking> or tool args)
    target_llm: str                   # e.g., "claude-3-5-sonnet", "gpt-4o"

class NetworkIntercept(BaseEvent):
    url: str
    method: str
    reasoning_context: Optional[LLMReasoningContext]
    tool_calls: List[Dict[str, Any]] = [] # Functions the agent decided to execute

class TerminalAction(BaseEvent):
    command_executed: str
    working_directory: str
    user: str
    parent_process: str # Crucial for tracing back to the IDE/Agent