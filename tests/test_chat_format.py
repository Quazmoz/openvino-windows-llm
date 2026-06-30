from app.chat_format import (
    StopStreamer,
    build_prompt_within_budget,
    normalize_messages,
    normalize_stop,
    render_chatml,
    responses_input_to_messages,
    truncate_at_stop,
)
from app.openai_api import ChatMessage


def _count_words(text: str) -> int:
    return len(text.split())


def test_normalize_basic():
    msgs = [ChatMessage(role="user", content="hi")]
    assert normalize_messages(msgs) == [{"role": "user", "content": "hi"}]


def test_normalize_system_override_replaces_leading_system():
    msgs = [
        ChatMessage(role="system", content="original"),
        ChatMessage(role="user", content="hello"),
    ]
    out = normalize_messages(msgs, system_override="TOOLS")
    # The override is appended to the original system prompt, preserving both
    # user-provided instructions and server-injected tool-calling instructions.
    assert out[0] == {"role": "system", "content": "original\n\nTOOLS"}
    assert {"role": "system", "content": "original"} not in out
    assert out[-1]["content"] == "hello"


def test_normalize_tool_message_mapped_to_user():
    msgs = [ChatMessage(role="tool", content="42", tool_call_id="call-1")]
    out = normalize_messages(msgs)
    assert out[0]["role"] == "user"
    assert "42" in out[0]["content"]
    assert "call-1" in out[0]["content"]


def test_normalize_assistant_tool_calls_flattened():
    msgs = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{"id": "c1", "function": {"name": "f", "arguments": '{"a":1}'}}],
        )
    ]
    out = normalize_messages(msgs)
    assert out[0]["role"] == "assistant"
    assert '"name": "f"' in out[0]["content"]


def test_render_chatml_adds_generation_prompt():
    text = render_chatml([{"role": "user", "content": "hi"}], add_generation_prompt=True)
    assert text.endswith("<|im_start|>assistant\n")
    assert "<|im_start|>user\nhi<|im_end|>" in text


def test_build_prompt_fits_within_budget():
    msgs = [{"role": "user", "content": "short message"}]
    prompt, tokens = build_prompt_within_budget(
        msgs, render_chatml, _count_words, max_prompt_len=100
    )
    assert tokens <= 100
    assert "short message" in prompt


def test_build_prompt_slides_window_dropping_oldest():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "old " * 40},
        {"role": "assistant", "content": "reply " * 40},
        {"role": "user", "content": "NEWEST question"},
    ]
    prompt, tokens = build_prompt_within_budget(
        msgs, render_chatml, _count_words, max_prompt_len=30
    )
    assert tokens <= 30
    # The system prompt and the newest user turn are always retained.
    assert "sys" in prompt
    assert "NEWEST question" in prompt
    # An old turn should have been dropped to fit the budget.
    assert "old old old" not in prompt


def test_build_prompt_keeps_last_even_if_oversized():
    msgs = [{"role": "user", "content": "word " * 200}]
    prompt, _ = build_prompt_within_budget(msgs, render_chatml, _count_words, max_prompt_len=10)
    assert "word" in prompt  # newest turn is never dropped entirely


def test_responses_input_string():
    out = responses_input_to_messages("hello", instructions="be nice")
    assert out[0] == {"role": "system", "content": "be nice"}
    assert out[-1] == {"role": "user", "content": "hello"}


def test_responses_input_list():
    out = responses_input_to_messages([{"role": "user", "content": "x"}])
    assert out == [{"role": "user", "content": "x"}]


# --- stop sequences --------------------------------------------------------


def test_normalize_stop_handles_str_list_and_none():
    assert normalize_stop(None) == []
    assert normalize_stop("") == []
    assert normalize_stop("STOP") == ["STOP"]
    assert normalize_stop(["a", "", "b", 3]) == ["a", "b"]  # drops empties / non-strings


def test_truncate_at_stop_cuts_at_earliest_match():
    text, hit = truncate_at_stop("hello END world STOP", ["STOP", "END"])
    assert hit is True
    assert text == "hello "  # earliest of the two wins, stop text excluded


def test_truncate_at_stop_no_match_returns_input():
    text, hit = truncate_at_stop("nothing to cut", ["ZZZ"])
    assert hit is False
    assert text == "nothing to cut"


def test_stop_streamer_passthrough_without_stops():
    s = StopStreamer([])
    assert s.feed("abc") == "abc"
    assert s.feed("def") == "def"
    assert s.flush() == ""
    assert s.stopped is False


def test_stop_streamer_detects_sequence_split_across_chunks():
    # "STOP" is split across three feeds; the streamer must withhold, detect it,
    # emit only the text before it, and stop.
    s = StopStreamer(["STOP"])
    out = "".join(s.feed(p) for p in ["he", "llo ST", "OP and more"])
    out += s.flush()
    assert out == "hello "
    assert s.stopped is True
    # Once stopped, further input is ignored.
    assert s.feed("extra") == ""


def test_build_prompt_within_budget_binary_search_exact():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
        {"role": "assistant", "content": "four"},
        {"role": "user", "content": "five"},
    ]
    # Verify large budget keeps everything
    prompt, tokens = build_prompt_within_budget(
        msgs, render_chatml, _count_words, max_prompt_len=100
    )
    assert "one" in prompt
    assert "five" in prompt

    # Verify dropping only system-only messages works when rest is empty
    system_only = [{"role": "system", "content": "sys"}]
    prompt_sys, tokens_sys = build_prompt_within_budget(
        system_only, render_chatml, _count_words, max_prompt_len=2
    )
    assert "sys" in prompt_sys

    # Verify monotonic dropping and correctness for multiple budget limits
    for max_len in range(5, 50):
        prompt, tokens = build_prompt_within_budget(
            msgs, render_chatml, _count_words, max_prompt_len=max_len
        )
        # It must fit, or if even keeping just the newest turn exceeds budget, it keeps that newest turn
        newest_only_len = _count_words(
            render_chatml([msgs[0], msgs[-1]], add_generation_prompt=True)
        )
        assert tokens <= max_len or tokens == newest_only_len
        assert "sys" in prompt
        assert "five" in prompt
