"""
AI IDE CONTEXT:
This is a mitmproxy addon script. 
Goal: Intercept HTTPS traffic from local AI tools (Claude Code, VS Code Copilot, OpenClaw).
We need to capture prompts, tool calls, and especially the model's reasoning/thinking blocks.
Do NOT block traffic yet; this is purely an observation prototype.
"""
from mitmproxy import http
import json
import logging
# In a real environment, this imports from our shared package:
# from packages.schemas.events import NetworkIntercept, LLMReasoningContext

logger = logging.getLogger("AgentProxy")

class AgentInferenceInterceptor:
    def __init__(self):
        # We monitor standard LLM providers and local loopbacks (for inter-agent comms)
        self.target_hosts = ["api.anthropic.com", "api.openai.com", "localhost", "127.0.0.1"]

    def request(self, flow: http.HTTPFlow) -> None:
        """
        AI IDE TODO: Parse outgoing requests.
        Identify if it's an LLM inference request. Extract the system prompt and user messages.
        If it's localhost traffic, it might be Agent A talking to Agent B (e.g., AutoGen/CrewAI).
        """
        if flow.request.pretty_host in self.target_hosts:
            # AI: Add extraction logic here and push to the local core/buffer.py
            pass

    def response(self, flow: http.HTTPFlow) -> None:
        """
        AI IDE TODO: Parse incoming LLM responses.
        1. Extract the raw text.
        2. Regex search for <thinking>, <thought>, or tool_call arguments to capture reasoning.
        3. Identify what action the agent decided to take based on this reasoning.
        """
        if flow.request.pretty_host in self.target_hosts and flow.response.content:
            # AI: Add parsing logic for OpenAI/Anthropic JSON response schemas here
            pass

addons = [
    AgentInferenceInterceptor()
]