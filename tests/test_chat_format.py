from app.chat_format import (
    build_prompt_within_budget,
    normalize_messages,
    render_chatml,
    responses_input_to_messages,
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
    assert out[0] == {"role": "system", "content": "TOOLS"}
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
    prompt, tokens = build_prompt_within_budget(msgs, render_chatml, _count_words, max_prompt_len=100)
    assert tokens <= 100
    assert "short message" in prompt


def test_build_prompt_slides_window_dropping_oldest():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "old " * 40},
        {"role": "assistant", "content": "reply " * 40},
        {"role": "user", "content": "NEWEST question"},
    ]
    prompt, tokens = build_prompt_within_budget(msgs, render_chatml, _count_words, max_prompt_len=30)
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
