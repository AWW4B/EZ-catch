from __future__ import annotations

import json
import re
import sys
import time
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

# ─── Configuration ────────────────────────────────────────────────────────────

TARGET_DOMAINS = frozenset({
    "api.anthropic.com",
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "googleapis.com",
    "localhost",
    "127.0.0.1",
    "::1",
})

_buffer = LocalSQLiteBuffer()

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _is_target(host: str) -> bool:
    host = host.lower().split(":")[0]
    return host in TARGET_DOMAINS or any(host.endswith("." + d) for d in TARGET_DOMAINS)


def _extract_text_from_content_block(block: object) -> str:
    """Extract display text from an Anthropic content block (str or list-of-blocks)."""
    if isinstance(block, str):
        return block
    if isinstance(block, list):
        parts: list[str] = []
        for b in block:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    parts.append(b.get("text", ""))
        return "\n".join(parts)
    return ""


# ─── Request parsing ──────────────────────────────────────────────────────────

def _parse_request(body_text: str) -> tuple[str | None, str | None, str | None]:
    """
    Parse an Anthropic /v1/messages (or OpenAI /v1/chat/completions) request body.

    Returns: (model, system_prompt, user_prompt)
    """
    try:
        data = json.loads(body_text)
    except Exception:
        return None, None, None

    model: str | None = data.get("model")

    # ── System prompt ──────────────────────────────────────────────────────────
    system_raw = data.get("system")
    system_prompt: str | None = None
    if isinstance(system_raw, str):
        system_prompt = system_raw
    elif isinstance(system_raw, list):
        # Anthropic system can be a list of content blocks
        parts = [b.get("text", "") for b in system_raw if isinstance(b, dict) and b.get("type") == "text"]
        system_prompt = "\n".join(parts) if parts else None

    # ── User prompt ────────────────────────────────────────────────────────────
    messages = data.get("messages") or []
    user_prompt: str | None = None

    # Prefer the last user-role message
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_prompt = _extract_text_from_content_block(msg.get("content", ""))
            break

    # Gemini shape fallback
    if user_prompt is None:
        contents = data.get("contents")
        if isinstance(contents, list):
            parts_list: list[str] = []
            for content in contents:
                role = content.get("role", "")
                for p in content.get("parts", []):
                    if isinstance(p, dict) and "text" in p:
                        parts_list.append(f"[{role}] {p['text']}")
            user_prompt = "\n".join(parts_list) if parts_list else None

    return model, system_prompt, user_prompt


# ─── SSE / Response parsing ───────────────────────────────────────────────────

def _parse_sse_body(body_text: str) -> tuple[str | None, str | None, list[dict]]:
    """
    Reassemble a full Anthropic SSE streamed response body.

    Anthropic streaming sends lines like:
      data: {"type":"content_block_delta","delta":{"type":"thinking_delta","thinking":"..."}}
      data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}

    Returns: (reasoning_text, response_text, tool_calls)
    """
    thinking_parts: list[str] = []
    text_parts: list[str] = []
    tool_calls: list[dict] = []

    # Track active tool_use blocks by index
    tool_use_blocks: dict[int, dict] = {}
    tool_input_strs: dict[int, str] = {}

    for raw_line in body_text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line.startswith("data:"):
            continue
        payload = raw_line[5:].strip()
        if payload in ("[DONE]", ""):
            continue
        try:
            event = json.loads(payload)
        except Exception:
            continue

        etype = event.get("type", "")

        # ── Block start: register tool_use blocks ──────────────────────────────
        if etype == "content_block_start":
            idx = event.get("index", -1)
            cb = event.get("content_block", {})
            if cb.get("type") == "tool_use":
                tool_use_blocks[idx] = {"name": cb.get("name"), "id": cb.get("id")}
                tool_input_strs[idx] = ""

        # ── Block delta: accumulate text/thinking/tool input ───────────────────
        elif etype == "content_block_delta":
            idx = event.get("index", -1)
            delta = event.get("delta", {})
            dtype = delta.get("type", "")

            if dtype == "thinking_delta":
                thinking_parts.append(delta.get("thinking", ""))
            elif dtype == "text_delta":
                text_parts.append(delta.get("text", ""))
            elif dtype == "input_json_delta":
                tool_input_strs[idx] = tool_input_strs.get(idx, "") + delta.get("partial_json", "")

        # ── Block stop: finalise tool_use ──────────────────────────────────────
        elif etype == "content_block_stop":
            idx = event.get("index", -1)
            if idx in tool_use_blocks:
                raw_input = tool_input_strs.get(idx, "")
                try:
                    parsed_input = json.loads(raw_input) if raw_input else {}
                except Exception:
                    parsed_input = raw_input
                tool_calls.append({
                    "name": tool_use_blocks[idx].get("name"),
                    "id": tool_use_blocks[idx].get("id"),
                    "input": parsed_input,
                })

    reasoning = "".join(thinking_parts) or None
    response  = "".join(text_parts)    or None
    return reasoning, response, tool_calls


def _parse_json_body(body_text: str) -> tuple[str | None, str | None, list[dict]]:
    """
    Parse a non-streamed Anthropic / OpenAI JSON response body.
    Returns: (reasoning_text, response_text, tool_calls)
    """
    try:
        data = json.loads(body_text)
    except Exception:
        return None, None, []

    thinking_parts: list[str] = []
    text_parts: list[str] = []
    tool_calls: list[dict] = []

    # Anthropic non-stream shape
    content = data.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "thinking":
                thinking_parts.append(block.get("thinking", ""))
            elif btype == "text":
                text_parts.append(block.get("text", ""))
            elif btype == "tool_use":
                tool_calls.append({
                    "name": block.get("name"),
                    "id": block.get("id"),
                    "input": block.get("input"),
                })

    # OpenAI shape
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message", {})
        rc = msg.get("reasoning_content") or msg.get("content")
        if rc:
            text_parts.append(rc)
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments")
            try:
                args = json.loads(args) if isinstance(args, str) else args
            except Exception:
                pass
            tool_calls.append({"name": fn.get("name"), "id": tc.get("id"), "input": args})

    # Gemini shape
    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates:
        parts_list = candidates[0].get("content", {}).get("parts", [])
        for p in parts_list:
            if isinstance(p, dict) and "text" in p:
                text_parts.append(p["text"])

    reasoning = "".join(thinking_parts) or None
    response  = "".join(text_parts)    or None
    return reasoning, response, tool_calls


# ─── Core build-and-push ──────────────────────────────────────────────────────

def _build_and_push(flow: http.HTTPFlow, start_time: float) -> None:
    try:
        import os as _os
        pid = _os.getpid()

        duration_ms: float | None = None
        if flow.response:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)

        # ── Parse request ──────────────────────────────────────────────────────
        req_body: str | None = None
        try:
            req_body = flow.request.get_text(strict=False) or None
        except Exception:
            pass

        model: str | None        = None
        system_prompt: str | None = None
        user_prompt: str | None  = None

        if req_body:
            model, system_prompt, user_prompt = _parse_request(req_body)

        # ── Parse response ─────────────────────────────────────────────────────
        resp_text: str | None = None
        if flow.response:
            try:
                resp_text = flow.response.get_text(strict=False) or None
            except Exception:
                pass

        reasoning: str | None  = None
        response: str | None   = None
        tool_calls: list[dict] = []

        if resp_text:
            ct = (flow.response.headers.get("content-type", "") if flow.response else "").lower()
            is_sse = "text/event-stream" in ct or resp_text.lstrip().startswith("data:")

            if is_sse:
                reasoning, response, tool_calls = _parse_sse_body(resp_text)
            else:
                reasoning, response, tool_calls = _parse_json_body(resp_text)

        # ── Build legacy reasoning_context (backwards compat) ──────────────────
        llm_ctx: LLMReasoningContext | None = None
        if user_prompt or reasoning or response:
            parsed_url = urlparse(flow.request.pretty_url)
            host = parsed_url.hostname or ""
            target = (
                model or
                ("claude"  if "anthropic" in host else
                 "openai"  if "openai"    in host else
                 "gemini"  if "google"    in host else "local")
            )
            llm_ctx = LLMReasoningContext(
                prompt=user_prompt,
                raw_response=response,
                extracted_thinking=reasoning,
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
            duration_ms=duration_ms,
            reasoning_context=llm_ctx,
            tool_calls=tool_calls,
            # Flat LLM fields
            model=model,
            prompt=user_prompt,
            system_prompt=system_prompt,
            reasoning=reasoning,
            response=response,
        )

        _buffer.push_event(event)
        status = flow.response.status_code if flow.response else "?"
        print(
            f"[PROXY] {flow.request.method} {flow.request.pretty_url[:80]} → {status}"
            + (f"  model={model}" if model else "")
            + (f"  {duration_ms:.0f}ms" if duration_ms else ""),
            flush=True,
        )

    except Exception as exc:
        print(f"[PROXY] Error in _build_and_push: {exc}", flush=True)


# ─── mitmproxy addon ──────────────────────────────────────────────────────────

class AgentInferenceInterceptor:
    """mitmproxy addon that captures LLM API calls and pushes them to the local SQLite buffer."""

    def __init__(self) -> None:
        # Map flow id → monotonic start time so we can compute duration_ms
        self._start_times: dict[str, float] = {}

    def request(self, flow: http.HTTPFlow) -> None:
        host = (flow.request.host or "").lower()
        if _is_target(host):
            self._start_times[flow.id] = time.monotonic()

    def response(self, flow: http.HTTPFlow) -> None:
        host = (flow.request.host or "").lower()
        if not _is_target(host):
            return

        ct = flow.response.headers.get("content-type", "") if flow.response else ""
        # Accept JSON and SSE (text/event-stream); skip binary content types
        if ct and "json" not in ct and "text" not in ct:
            return

        start_time = self._start_times.pop(flow.id, time.monotonic())
        threading.Thread(
            target=_build_and_push,
            args=(flow, start_time),
            daemon=True,
        ).start()


addons = [AgentInferenceInterceptor()]