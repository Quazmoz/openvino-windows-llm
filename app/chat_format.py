"""Prompt construction for chat completions.

Two responsibilities, both pure (they take tokenizer callables, no OpenVINO):

1. Normalize OpenAI-style messages into plain ``{role, content}`` dicts that any
   chat template can render (tool results / assistant tool-calls are flattened
   to text, and tool messages are mapped to the user role for maximum template
   compatibility).
2. Fit the conversation within a token budget using a whole-turn sliding window
   so the most recent context is preserved and older turns are dropped first.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from app.openai_api import ChatMessage

logger = logging.getLogger("ov-llm.chat")

ApplyTemplate = Callable[[list[dict]], str]
CountTokens = Callable[[str], int]


def _content_to_text(content: object) -> str:
    """Convert OpenAI-style message content into text.

    Chat Completions usually sends content as a string, but the Responses API and
    some OpenAI-compatible clients send a list of content parts. Preserve textual
    parts instead of rendering Python reprs such as ``[{'type': 'input_text', ...}]``.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for key in ("text", "content", "value"):
                    value = item.get(key)
                    if isinstance(value, str):
                        parts.append(value)
                        break
        if parts:
            return "\n".join(parts)
    return str(content)


def normalize_messages(
    messages: list[ChatMessage],
    system_override: str = "",
) -> list[dict]:
    """Convert request messages into ``{role, content}`` dicts.

    If ``system_override`` is provided, it is appended to any leading system
    message instead of replacing it. This preserves caller-provided instructions
    while still injecting server-side tool-calling instructions.
    """
    out: list[dict] = []
    msgs = list(messages)
    has_leading_system = bool(msgs) and msgs[0].role == "system"

    if system_override:
        if has_leading_system:
            original_system = _content_to_text(msgs[0].content).strip()
            combined_system = (
                f"{original_system}\n\n{system_override.strip()}"
                if original_system
                else system_override.strip()
            )
            out.append({"role": "system", "content": combined_system})
            msgs = msgs[1:]
        else:
            out.append({"role": "system", "content": system_override})

    for m in msgs:
        content = _content_to_text(m.content)

        if m.role == "tool":
            label = f" (call {m.tool_call_id})" if m.tool_call_id else ""
            out.append({"role": "user", "content": f"[tool result{label}]\n{content}"})

        elif m.role == "assistant" and m.tool_calls:
            calls = [
                {
                    "name": tc.get("function", {}).get("name", ""),
                    "arguments": tc.get("function", {}).get("arguments", "{}"),
                }
                for tc in m.tool_calls
            ]
            merged = (content + "\n" if content else "") + json.dumps(calls)
            out.append({"role": "assistant", "content": merged})

        else:
            out.append({"role": m.role, "content": content})

    return out


def render_chatml(dict_messages: list[dict], add_generation_prompt: bool = True) -> str:
    """Fallback ChatML renderer for engines whose model has no chat template."""
    parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in dict_messages]
    if add_generation_prompt:
        parts.append("<|im_start|>assistant\n")
    return "".join(parts)


def build_prompt_within_budget(
    dict_messages: list[dict],
    apply_template: ApplyTemplate,
    count_tokens: CountTokens,
    max_prompt_len: int,
) -> tuple[str, int]:
    """Render a prompt that fits ``max_prompt_len`` tokens via a sliding window.

    The system message (if any) and the most recent turns are always kept; older
    whole turns are dropped from the front until the prompt fits. The single most
    recent message is never dropped (if it alone exceeds the budget it is kept and
    downstream ``max_new_tokens`` capping absorbs the overflow).

    Returns ``(prompt, token_count)``.
    """
    if not dict_messages:
        prompt = apply_template([])
        return prompt, count_tokens(prompt)

    full = apply_template(dict_messages)
    full_tokens = count_tokens(full)
    if full_tokens <= max_prompt_len:
        return full, full_tokens

    system = [m for m in dict_messages if m["role"] == "system"][:1]
    rest = [m for m in dict_messages if m["role"] != "system"]

    if not rest:
        # Only system messages and they exceed budget. Just return them.
        prompt = apply_template(system)
        return prompt, count_tokens(prompt)

    # Binary search the number of messages to keep from the end of rest (1 to len(rest)).
    low = 1
    high = len(rest)
    best_k = 1  # We must keep at least the single most recent message.

    while low <= high:
        mid = (low + high) // 2
        trial = system + rest[-mid:]
        if count_tokens(apply_template(trial)) <= max_prompt_len:
            best_k = mid
            low = mid + 1
        else:
            high = mid - 1

    dropped = len(rest) - best_k
    if dropped > 0:
        logger.info("Sliding window dropped %d older turn(s) to fit %d tokens", dropped, max_prompt_len)

    final = system + rest[-best_k:]
    prompt = apply_template(final)
    return prompt, count_tokens(prompt)


# --- Stop sequences --------------------------------------------------------


def normalize_stop(stop: str | list[str] | None) -> list[str]:
    """Coerce the OpenAI ``stop`` field (string, list, or None) to a clean list."""
    if stop is None:
        return []
    if isinstance(stop, str):
        return [stop] if stop else []
    return [s for s in stop if isinstance(s, str) and s]


def truncate_at_stop(text: str, stop: list[str]) -> tuple[str, bool]:
    """Cut ``text`` at the earliest occurrence of any stop sequence.

    Returns ``(text, hit)`` where ``hit`` is True if a stop sequence was found
    (and the stop sequence itself is excluded from the returned text).
    """
    earliest = -1
    for s in stop:
        idx = text.find(s)
        if idx != -1 and (earliest == -1 or idx < earliest):
            earliest = idx
    if earliest == -1:
        return text, False
    return text[:earliest], True


class StopStreamer:
    """Incrementally emit streamed text, stopping at the first stop sequence.

    A stop sequence can straddle two streamed chunks, so the streamer withholds
    the last ``max_stop_len - 1`` characters until more text confirms they are
    not the start of a stop sequence. Call :meth:`feed` per chunk and
    :meth:`flush` once the stream ends.
    """

    def __init__(self, stop: list[str]) -> None:
        self.stop = stop
        self._maxlen = max((len(s) for s in stop), default=0)
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
        keep = self._maxlen - 1  # possible partial stop-match to re-check next time
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
    """Convert a Responses-API ``input`` (string or message list) to message dicts."""
    out: list[dict] = []
    if instructions:
        out.append({"role": "system", "content": instructions})

    if isinstance(request_input, str):
        out.append({"role": "user", "content": request_input})
    elif isinstance(request_input, list):
        for msg in request_input:
            if isinstance(msg, dict):
                out.append(
                    {
                        "role": str(msg.get("role", "user")),
                        "content": _content_to_text(msg.get("content", "")),
                    }
                )
    else:
        raise ValueError("Responses 'input' must be a string or a list of messages")
    return out
