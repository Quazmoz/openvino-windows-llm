from scripts.validate_api_contract import Check, markdown, parse_sse, sanitize


def test_parse_sse_extracts_events_payloads_and_done():
    events, payloads, done = parse_sse(
        'event: response.created\n'
        'data: {"type":"response.created"}\n\n'
        'data: [DONE]\n\n'
    )
    assert events == ["response.created"]
    assert payloads == [{"type": "response.created"}]
    assert done is True


def test_sanitize_redacts_secrets_and_local_paths():
    text = sanitize(
        r"Bearer sk-secret hf_abcdefghijklmnopqrstuvwxyz token=abc C:\\Users\\Quinn\\model"
    )
    assert "sk-secret" not in text
    assert "hf_" not in text
    assert "Quinn" not in text
    assert "[redacted]" in text
    assert "[local-path]" in text


def test_markdown_contains_summary_and_checks():
    report = {
        "generated_at": "2026-07-16T12:00:00+00:00",
        "profile": "full",
        "model": "test-model",
        "requested_device": "CPU",
        "summary": {"pass": 1, "warn": 0, "skip": 0, "fail": 0},
        "checks": [
            {
                "name": "Health",
                "status": "pass",
                "duration_ms": 2.5,
                "detail": "mock=False",
            }
        ],
    }
    result = markdown(report)
    assert "# OpenVINO Windows LLM API Validation" in result
    assert "1 passed" in result
    assert "test-model" in result
    assert "Health" in result


def test_check_dataclass_shape_is_report_safe():
    check = Check("Contract", "pass", 1.2, "ok")
    assert check.name == "Contract"
    assert check.status == "pass"
