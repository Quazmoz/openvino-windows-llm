"""Prompt-based tool/function calling for models that lack native tool support.

Strategy: inject a system instruction describing the available tools and the
expected JSON output format, then parse JSON tool calls back out of the model's
free-form text. This keeps the OpenAI tool-calling API working across any model
the server can run. Pure logic — fully unit-testable without OpenVINO.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.openai_api import FunctionCall, ToolCall, ToolDefinition


def format_tools_for_prompt(
    tools: list[ToolDefinition] | None,
    tool_choice: Any = None,
) -> str:
    """Render a system-prompt section instructing the model how to call tools.

    Returns an empty string when tools are disabled (``tool_choice == "none"``).
    """
    if not tools or tool_choice == "none":
        return ""

    tools_json = [
        {
            "type": tool.type,
            "function": {
                "name": tool.function.name,
                "description": tool.function.description or "",
                "parameters": tool.function.parameters or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]

    forced_tool: str | None = None
    if isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
        forced_tool = tool_choice.get("function", {}).get("name")
        if forced_tool:
            tools_json = [t for t in tools_json if t["function"]["name"] == forced_tool]

    if forced_tool:
        instruction = f"You MUST call the '{forced_tool}' function. Do not respond with anything else."
    elif tool_choice == "required":
        instruction = "You MUST call at least one of the available tools. Do not respond without calling a tool."
    else:
        instruction = "Use the tools when needed. If you don't need a tool, respond normally."

    tools_str = json.dumps(tools_json, indent=2)
    return f"""You are a helpful assistant with access to the following tools. {instruction}

# Available Tools

{tools_str}

# Tool Call Format

When you need to call a tool, respond with a JSON object in this EXACT format:
{{"name": "function_name", "arguments": {{"arg1": "value1"}}}}

For multiple tool calls, use a JSON array:
[{{"name": "func1", "arguments": {{}}}}, {{"name": "func2", "arguments": {{}}}}]

IMPORTANT: Output ONLY the JSON when calling tools, no other text."""


def parse_tool_calls(
    text: str,
    available_tools: list[ToolDefinition] | None = None,
) -> tuple[str, list[ToolCall]]:
    """Extract tool calls from model output.

    Handles single JSON objects, JSON arrays, and fenced code blocks; validates
    against the declared tool names; and deduplicates identical calls.

    Returns ``(remaining_text, tool_calls)``.
    """
    tool_calls: list[ToolCall] = []
    seen: set[str] = set()
    remaining_text = text

    valid_names = {t.function.name for t in available_tools} if available_tools else set()

    def add(name: str, arguments: str) -> bool:
        if valid_names and name not in valid_names:
            return False
        key = f"{name}:{arguments}"
        if key in seen:
            return False
        seen.add(key)
        tool_calls.append(
            ToolCall(
                id=f"call-{uuid.uuid4().hex[:12]}",
                type="function",
                function=FunctionCall(name=name, arguments=arguments),
            )
        )
        return True

    # Strategy 1: full JSON arrays of calls.
    array_pattern = r"\[\s*\{[^[\]]*\}\s*(?:,\s*\{[^[\]]*\}\s*)*\]"
    for match in re.finditer(array_pattern, text, re.DOTALL):
        try:
            arr = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(arr, list) and arr and all(isinstance(i, dict) and "name" in i for i in arr):
            for item in arr:
                args = item.get("arguments", {})
                args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                add(item["name"], args_str)
            remaining_text = remaining_text.replace(match.group(0), "").strip()

    # Strategy 2: individual JSON objects (both key orders).
    object_patterns = [
        (r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[^{}]*\})\s*\}', False),
        (r'\{\s*"arguments"\s*:\s*(\{[^{}]*\})\s*,\s*"name"\s*:\s*"([^"]+)"\s*\}', True),
    ]
    for pattern, reversed_order in object_patterns:
        for match in re.finditer(pattern, text, re.DOTALL):
            try:
                if reversed_order:
                    fn_args, fn_name = match.group(1), match.group(2)
                else:
                    fn_name, fn_args = match.group(1), match.group(2)
                json.loads(fn_args)  # validate
            except (json.JSONDecodeError, IndexError):
                continue
            if add(fn_name, fn_args):
                remaining_text = remaining_text.replace(match.group(0), "").strip()

    # Strategy 3: fenced code blocks containing JSON.
    for pattern in (r"```json\s*([\s\S]*?)\s*```", r"```\s*([\s\S]*?)\s*```"):
        for match in re.finditer(pattern, text, re.DOTALL):
            try:
                parsed = json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue
            items = parsed if isinstance(parsed, list) else [parsed]
            for item in items:
                if isinstance(item, dict) and "name" in item:
                    args = item.get("arguments", {})
                    args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                    if add(item["name"], args_str):
                        remaining_text = remaining_text.replace(match.group(0), "").strip()

    remaining_text = re.sub(r"\s+", " ", remaining_text).strip()
    return remaining_text, tool_calls


def detect_incomplete_tool_call(text: str) -> bool:
    """Heuristic: True if the output looks like a truncated tool-call JSON."""
    if '{"name"' in text or "[{" in text:
        if (text.count("{") - text.count("}")) > 0 or (text.count("[") - text.count("]")) > 0:
            return True
    return False


def get_retry_prompt() -> str:
    return (
        "Your previous response contained a malformed tool call. Please try again.\n"
        'Output ONLY valid JSON in this format:\n'
        '{"name": "function_name", "arguments": {"param": "value"}}'
    )
