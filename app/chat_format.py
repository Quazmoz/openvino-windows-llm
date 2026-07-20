"""Prompt construction for chat completions.

Two responsibilities, both pure from the caller's perspective:

1. Normalize OpenAI-style messages into ``{role, content}`` dictionaries. Text
   parts are flattened while validated image parts are retained as private
   transport markers for a vision engine.
2. Fit the conversation within a token budget using a whole-turn sliding window
   so the most recent context is preserved and older turns are dropped first.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from app import multimodal
from app.openai_api import ChatMessage

logger = logging.getLogger("ov-llm.chat")

ApplyTemplate = Callable[[list[dict]], str]
CountTokens = Callable[[str], int]


def _content_to_text(content: object) -> str | multimodal.MultimodalContent:
    """Convert OpenAI content to text plus private multimodal transport markers."""

    return multimodal.content_to_transport_text(content)


def normalize_messages(
    messages: list[ChatMessage],
    system_override: str = "",
) -> list[dict]:
    """Convert request messages into ``{role, content}`` dictionaries."""

    out: list[dict] = []
    msgs = list(messages)
    has_leading_system = bool(msgs) and msgs[0].role == "system"

    if system_override:
        if has_leading_system:
            original_system = multimodal.plain_text(_content_to_text(msgs[0].content)).strip()
            combined_system = (
                f"{original_system}\n\n{system_override.strip()}"
                if original_system
                else system_override.strip()
            )
            out.append({"role": "system", "content": combined_system})
            msgs = msgs[1:]
        else:
            out.append({"role": "system", "content": system_override})

    for message in msgs:
        content = _content_to_text(message.content)
        if message.role == "tool":
            label = f" (call {message.tool_call_id})" if message.tool_call_id else ""
            out.append({"role": "user", "content": f"[tool result{label}]\n{content}"})
        elif message.role == "assistant" and message.tool_calls:
            calls = [
                {
                    "name": call.get("function", {}).get("name", ""),
                    "arguments": call.get("function", {}).get("arguments", "{}"),
                }
                for call in message.tool_calls
            ]
            merged = (content + "\n" if content else "") + json.dumps(calls)
            out.append({"role": "assistant", "content": merged})
        else:
            out.append({"role": message.role, "content": content})
    return out


def render_chatml(dict_messages: list[dict], add_generation_prompt: bool = True) -> str:
    """Fallback ChatML renderer for engines whose model has no chat template."""

    parts = [
        f"<|im_start|>{message['role']}\n{message['content']}<|im_end|>\n"
        for message in dict_messages
    ]
    if add_generation_prompt:
        parts.append("<|im_start|>assistant\n")
    return "".join(parts)


def _count_or_release(prompt: str, count_tokens: CountTokens) -> int:
    """Count a candidate prompt and release its context when counting fails."""

    try:
        return count_tokens(prompt)
    except BaseException:
        multimodal.discard_prompt_context(prompt)
        raise


def build_prompt_within_budget(
    dict_messages: list[dict],
    apply_template: ApplyTemplate,
    count_tokens: CountTokens,
    max_prompt_len: int,
) -> tuple[str, int]:
    """Render a prompt that fits ``max_prompt_len`` via a sliding window.

    Candidate VLM prompts may own temporary in-memory image contexts. Every candidate
    discarded during budgeting is explicitly released; only the returned prompt keeps
    its context for the subsequent generation call.
    """

    if not dict_messages:
        prompt = apply_template([])
        return prompt, _count_or_release(prompt, count_tokens)

    full = apply_template(dict_messages)
    full_tokens = _count_or_release(full, count_tokens)
    if full_tokens <= max_prompt_len:
        return full, full_tokens
    multimodal.discard_prompt_context(full)

    system = [message for message in dict_messages if message["role"] == "system"][:1]
    rest = [message for message in dict_messages if message["role"] != "system"]
    if not rest:
        prompt = apply_template(system)
        return prompt, _count_or_release(prompt, count_tokens)

    low = 1
    high = len(rest)
    best_k = 1
    while low <= high:
        mid = (low + high) // 2
        candidate = apply_template(system + rest[-mid:])
        candidate_tokens = _count_or_release(candidate, count_tokens)
        multimodal.discard_prompt_context(candidate)
        if candidate_tokens <= max_prompt_len:
            best_k = mid
            low = mid + 1
        else:
            high = mid - 1

    dropped = len(rest) - best_k
    if dropped > 0:
        logger.info(
            "Sliding window dropped %d older turn(s) to fit %d tokens", dropped, max_prompt_len
        )

    final = apply_template(system + rest[-best_k:])
    return final, _count_or_release(final, count_tokens)


# --- Stop sequences --------------------------------------------------------


def normalize_stop(stop: str | list[str] | None) -> list[str]:
    """Coerce the OpenAI ``stop`` field to a clean list."""

    if stop is None:
        return []
    if isinstance(stop, str):
        return [stop] if stop else []
    result = []
    for item in stop:
        if isinstance(item, str) and item:
            result.append(item)
        elif item is not None:
            logger.warning("Ignoring non-string stop entry: %r", item)
    return result


def truncate_at_stop(text: str, stop: list[str]) -> tuple[str, bool]:
    """Cut ``text`` at the earliest occurrence of any stop sequence."""

    earliest = -1
    for item in stop:
        index = text.find(item)
        if index != -1 and (earliest == -1 or index < earliest):
            earliest = index
    if earliest == -1:
        return text, False
    return text[:earliest], True


class StopStreamer:
    """Incrementally emit streamed text, stopping at the first stop sequence."""

    def __init__(self, stop: list[str]) -> None:
        self.stop = stop
        self._maxlen = max((len(item) for item in stop), default=0)
        self._buffer = ""
        self.stopped = False

    def feed(self, piece: str) -> str:
        """Return the portion of ``piece`` that is safe to emit now."""

        if not self.stop:
            return piece
        if self.stopped:
            return ""
        self._buffer += piece
        text, hit = truncate_at_stop(self._buffer, self.stop)
        if hit:
            self.stopped = True
            self._buffer = ""
            return text
        keep = self._maxlen - 1
        if keep <= 0:
            out, self._buffer = self._buffer, ""
            return out
        if len(self._buffer) > keep:
            out = self._buffer[:-keep]
            self._buffer = self._buffer[-keep:]
            return out
        return ""

    def flush(self) -> str:
        """Emit any safely-held remainder once the stream has ended."""

        if self.stopped:
            return ""
        out, self._buffer = self._buffer, ""
        return out


def responses_input_to_messages(
    request_input: object,
    instructions: str | None = None,
) -> list[dict]:
    """Convert a Responses-API ``input`` into normalized message dictionaries."""

    out: list[dict] = []
    if instructions:
        out.append({"role": "system", "content": instructions})

    if isinstance(request_input, str):
        out.append({"role": "user", "content": request_input})
    elif isinstance(request_input, list):
        for message in request_input:
            if isinstance(message, dict):
                out.append(
                    {
                        "role": str(message.get("role", "user")),
                        "content": _content_to_text(message.get("content", "")),
                    }
                )
    else:
        raise ValueError("Responses 'input' must be a string or a list of messages")
    return out
