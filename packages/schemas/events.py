from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_process: str = Field(..., description="Name of the process that generated the event")
    pid: int = Field(..., description="Process ID of the source process")
    event_type: str = Field(..., description="Discriminator string identifying the event kind")

    model_config = {"extra": "allow"}


class LLMReasoningContext(BaseModel):
    prompt: Optional[str] = Field(default=None, description="The prompt sent to the LLM")
    raw_response: Optional[str] = Field(default=None, description="Raw response from the LLM")
    extracted_thinking: Optional[str] = Field(default=None, description="Chain-of-thought or scratchpad extracted from response")
    target_llm: Optional[str] = Field(default=None, description="Identifier for the LLM being called, e.g. 'claude-3-7-sonnet'")

    model_config = {"extra": "allow"}


class NetworkIntercept(BaseEvent):
    event_type: str = Field(default="network_intercept")
    url: str = Field(..., description="Full URL of the intercepted request")
    method: str = Field(..., description="HTTP method, e.g. GET, POST")
    status_code: Optional[int] = Field(default=None, description="HTTP response status code if available")
    request_headers: Optional[dict[str, str]] = Field(default=None)
    response_headers: Optional[dict[str, str]] = Field(default=None)
    request_body: Optional[str] = Field(default=None)
    response_body: Optional[str] = Field(default=None)
    duration_ms: Optional[float] = Field(default=None, description="Round-trip duration in milliseconds")
    reasoning_context: Optional[LLMReasoningContext] = Field(default=None, description="Parsed LLM context if the request targets an LLM API")
    tool_calls: Optional[list[dict[str, Any]]] = Field(default_factory=list, description="Tool/function calls extracted from the LLM response payload")


class TerminalAction(BaseEvent):
    event_type: str = Field(default="terminal_action")
    command_executed: str = Field(..., description="The full command string that was executed")
    working_directory: Optional[str] = Field(default=None, description="CWD at the time of execution")
    user: Optional[str] = Field(default=None, description="OS user that ran the command")
    parent_process: Optional[str] = Field(default=None, description="Name or path of the parent process")
    exit_code: Optional[int] = Field(default=None, description="Exit code of the command if captured")
    stdout: Optional[str] = Field(default=None)
    stderr: Optional[str] = Field(default=None)
    env_snapshot: Optional[dict[str, str]] = Field(default=None, description="Relevant environment variables at execution time")