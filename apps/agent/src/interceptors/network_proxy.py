from __future__ import annotations

import json
import re
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

def _find_root():
    curr = Path(__file__).resolve().parent
    for _ in range(10):
        if (curr / "apps").exists() or (curr / "packages").exists():
            return curr
        if curr.parent == curr:
            break
        curr = curr.parent
    return curr

sys.path.insert(0, str(_find_root()))

from packages.schemas.events import LLMReasoningContext, NetworkIntercept
from apps.agent.src.core.buffer import LocalSQLiteBuffer

from mitmproxy import http

TARGET_DOMAINS = frozenset({
    "api.anthropic.com",
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "googleapis.com",
    "localhost",
    "127.0.0.1",
    "::1",
})

_RE_THINKING = re.compile(
    r"<(?:thinking|thought)>(.*?)</(?:thinking|thought)>",
    re.DOTALL | re.IGNORECASE,
)

_buffer = LocalSQLiteBuffer()


def _is_target(host: str) -> bool:
    host = host.lower().split(":")[0]
    return host in TARGET_DOMAINS or any(host.endswith("." + d) for d in TARGET_DOMAINS)


def _extract_request_body(flow: http.HTTPFlow) -> str | None:
    try:
        return flow.request.get_text(strict=False) or None
    except Exception:
        return None


def _extract_prompt(req_body: str | None) -> str | None:
    if not req_body:
        return None
    try:
        data = json.loads(req_body)
        parts: list[str] = []
        
        # Gemini shape
        contents = data.get("contents")
        if isinstance(contents, list):
            for content in contents:
                role = content.get("role", "")
                c_parts = content.get("parts", [])
                for p in c_parts:
                    if isinstance(p, dict) and "text" in p:
                        parts.append(f"[{role}] {p['text']}")
            if parts:
                return "\n".join(parts)

        # OpenAI / Anthropic shape
        messages = data.get("messages") or []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(f"[{role}] {content}")
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(f"[{role}] {block.get('text', '')}")
        return "\n".join(parts) if parts else None
    except Exception:
        return None


def _identify_llm(host: str, path: str) -> str:
    if "anthropic" in host:
        return "claude"
    if "openai" in host:
        if "gpt-4" in path:
            return "gpt-4"
        if "gpt-3" in path:
            return "gpt-3.5"
        return "openai"
    if "google" in host:
        return "gemini"
    return "local"


def _extract_response_text(data: dict) -> str | None:
    # Gemini shape
    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p]
        if text_parts:
            return "\n".join(text_parts)

    # Anthropic shape
    content = data.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "thinking":
                    parts.append(block.get("thinking", ""))
        if parts:
            return "\n".join(parts)

    # OpenAI shape
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message", {})
        return msg.get("content") or msg.get("reasoning_content") or None

    return None


def _extract_thinking(text: str | None) -> str | None:
    if not text:
        return None
    matches = _RE_THINKING.findall(text)
    return "\n---\n".join(m.strip() for m in matches) if matches else None


def _extract_tool_calls(data: dict) -> list[dict]:
    tool_calls: list[dict] = []

    # Anthropic tool_use blocks
    content = data.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_calls.append({
                    "name": block.get("name"),
                    "id": block.get("id"),
                    "input": block.get("input"),
                })

    # OpenAI tool_calls
    choices = data.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            msg = choice.get("message", {})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                args = fn.get("arguments")
                try:
                    args = json.loads(args) if isinstance(args, str) else args
                except Exception:
                    pass
                tool_calls.append({
                    "name": fn.get("name"),
                    "id": tc.get("id"),
                    "input": args,
                })

    return tool_calls


def _build_and_push(flow: http.HTTPFlow) -> None:
    try:
        import os as _os
        pid = _os.getpid()

        resp_text: str | None = None
        data: dict = {}
        raw_text: str | None = None
        thinking: str | None = None
        tool_calls: list[dict] = []
        reasoning: LLMReasoningContext | None = None

        if flow.response:
            try:
                resp_text = flow.response.get_text(strict=False) or None
            except Exception:
                pass

        if resp_text:
            try:
                parsed_json = json.loads(resp_text)
                if isinstance(parsed_json, dict):
                    data = parsed_json
                    raw_text   = _extract_response_text(data)
                    thinking   = _extract_thinking(raw_text)
                    tool_calls = _extract_tool_calls(data)
            except Exception:
                pass

        req_body = _extract_request_body(flow)
        prompt   = _extract_prompt(req_body)

        parsed_url = urlparse(flow.request.pretty_url)
        host       = parsed_url.hostname or ""
        target     = _identify_llm(host, parsed_url.path)

        if raw_text or thinking or prompt:
            reasoning = LLMReasoningContext(
                prompt=prompt,
                raw_response=raw_text,
                extracted_thinking=thinking,
                target_llm=target,
            )

        event = NetworkIntercept(
            source_process="mitmproxy",
            pid=pid,
            event_type="network_intercept",
            url=flow.request.pretty_url,
            method=flow.request.method,
            status_code=flow.response.status_code if flow.response else None,
            request_body=req_body,
            response_body=resp_text[:8192] if resp_text else None,
            reasoning_context=reasoning,
            tool_calls=tool_calls,
        )

        _buffer.push_event(event)
        print(f"[PROXY] Captured {flow.request.method} {flow.request.pretty_url[:80]} → {flow.response.status_code if flow.response else '?'}", flush=True)

    except Exception as exc:
        print(f"[PROXY] Error in _build_and_push: {exc}", flush=True)


class AgentInferenceInterceptor:
    def response(self, flow: http.HTTPFlow) -> None:
        host = (flow.request.host or "").lower()
        if not _is_target(host):
            return

        ct = flow.response.headers.get("content-type", "") if flow.response else ""
        if "json" not in ct and "text" not in ct and ct != "":
            return

        threading.Thread(target=_build_and_push, args=(flow,), daemon=True).start()


addons = [AgentInferenceInterceptor()]