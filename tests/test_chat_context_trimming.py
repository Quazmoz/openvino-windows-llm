from app.chat_format import build_prompt_within_budget, render_chatml


def _count_words(text: str) -> int:
    return len(text.split())


def test_context_trimming_drops_complete_tool_exchange_with_old_turn():
    messages = [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "OLD_USER " * 60},
        {"role": "assistant", "content": "TOOL_CALL_MARKER"},
        {"role": "user", "content": "[tool result (call call-1)]\nTOOL_RESULT_MARKER"},
        {"role": "assistant", "content": "TOOL_FINAL_MARKER"},
        {"role": "user", "content": "LATEST_USER"},
    ]

    prompt, tokens = build_prompt_within_budget(
        messages,
        render_chatml,
        _count_words,
        max_prompt_len=12,
    )

    assert tokens <= 12
    assert "SYSTEM" in prompt
    assert "LATEST_USER" in prompt
    assert "OLD_USER" not in prompt
    assert "TOOL_CALL_MARKER" not in prompt
    assert "TOOL_RESULT_MARKER" not in prompt
    assert "TOOL_FINAL_MARKER" not in prompt
