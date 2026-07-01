"""End-to-end smoke tests of the server running on the built-in mock engine.

These exercise the full FastAPI stack (routing, lifecycle, the model manager, and
the streaming bridge) without OpenVINO, so they run anywhere — including macOS.
"""

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.config import BASE_DIR, Settings
from app.model_manager import ModelManager
from app.server import create_app
from runtime.openvino_engine import GenParams, MockEngine

MODEL_ID = "tinyllama-1.1b-chat-fp16"


@pytest.fixture()
def client():
    settings = Settings(
        host="127.0.0.1",
        port=8000,
        device="NPU",
        models_file=BASE_DIR / "models.json",
        models_dir=BASE_DIR / "models" / "openvino",
        default_model=None,  # load explicitly in the tests
        api_key=None,
        force_mock=True,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def _load_and_wait(client, model_id=MODEL_ID, timeout=10.0):
    resp = client.post("/v1/models/load", json={"model": model_id})
    assert resp.status_code == 200, resp.text
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get("/v1/system/status").json()
        if model_id in status["models"]["loaded"]:
            return
        time.sleep(0.05)
    raise AssertionError("model did not load in time")


def test_health_reports_mock(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["mock"] is True


def test_list_models_includes_catalog(client):
    body = client.get("/v1/models").json()
    ids = {m["id"] for m in body["data"]}
    assert MODEL_ID in ids


def test_index_includes_device_selector(client):
    body = client.get("/").text
    assert 'id="device-select"' in body
    assert '<option value="NPU">NPU</option>' in body
    assert '<option value="AUTO">AUTO</option>' in body
    assert '<optgroup label="Advanced / Experimental">' in body
    assert '<option value="AUTO:NPU,GPU,CPU">AUTO:NPU,GPU,CPU</option>' in body
    assert "/v1/models/convert" in body
    assert "Convert & load selected model" in body or "Convert and load selected model" in body


def test_index_constrains_long_model_status(client):
    body = client.get("/").text
    assert "#model-status" in body
    assert "text-overflow: ellipsis" in body
    assert "function setModelStatus" in body


def test_index_has_api_key_and_metrics_ui(client):
    body = client.get("/").text
    # API-key support: input field, auth header helper, 401 handling.
    assert 'id="settings-api-key"' in body
    assert "function authHeaders" in body
    assert "Authorization" in body
    assert "handleAuthRequired" in body
    # Metrics surface in the settings sidebar.
    assert 'id="info-requests"' in body
    assert "data.metrics" in body


def test_index_has_responsive_and_accessible_ui_polish(client):
    body = client.get("/").text
    assert "--shadow-md" in body
    assert "@media (max-width: 700px)" in body
    assert ".icon-btn:focus-visible" in body
    assert ".copy-btn:focus-visible" in body
    assert ".bubble pre:focus-within .code-copy" in body


def test_index_escapes_dynamic_model_card_content(client):
    body = client.get("/").text
    assert "const safeName = escapeHtml(model.name)" in body
    assert "data-model-action" in body
    assert 'onclick="triggerModelPrimaryAction' not in body
    assert "return window.DOMPurify ? DOMPurify.sanitize(raw) : escapeHtml(text || '')" in body
    assert "submitModalBtn.disabled = true" in body


def test_devices_endpoint(client):
    body = client.get("/v1/devices").json()
    assert body["mock"] is True
    assert body["default_device"] == "NPU"
    assert "devices" in body
    assert "available" in body
    assert "suggestions" in body
    assert "AUTO:NPU,GPU,CPU" in body["supported_examples"]


def test_load_model_uses_requested_device(client):
    resp = client.post("/v1/models/load", json={"model": MODEL_ID, "device": "GPU"})
    assert resp.status_code == 200, resp.text

    deadline = time.time() + 10
    while time.time() < deadline:
        body = client.get("/v1/system/status").json()
        entry = next(m for m in body["models"]["available"] if m["id"] == MODEL_ID)
        if entry["is_loaded"]:
            assert entry["device"] == "GPU"
            return
        time.sleep(0.05)
    raise AssertionError("model did not load in time")


def test_load_model_accepts_composite_device_in_mock_mode(client):
    target = "AUTO:NPU,GPU,CPU"
    resp = client.post("/v1/models/load", json={"model": MODEL_ID, "device": target})
    assert resp.status_code == 200, resp.text

    deadline = time.time() + 10
    while time.time() < deadline:
        body = client.get("/v1/system/status").json()
        entry = next(m for m in body["models"]["available"] if m["id"] == MODEL_ID)
        if entry["is_loaded"]:
            assert entry["device"] == target
            assert body["device"]["loaded"][MODEL_ID] == target
            return
        time.sleep(0.05)
    raise AssertionError("model did not load in time")


def test_load_model_rejects_invalid_device(client):
    resp = client.post("/v1/models/load", json={"model": MODEL_ID, "device": "AUTO:NPU,,CPU"})
    assert resp.status_code == 400
    assert "Supported examples" in resp.json()["detail"]

    resp = client.post("/v1/models/load", json={"model": MODEL_ID, "device": ""})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"]


def test_convert_model_endpoint_schedules_background_task(client):
    manager = client.app.state.manager
    calls = []

    def fake_schedule_convert(model_id, device=None, *, load_after=True):
        calls.append((model_id, device, load_after))
        manager._set_status(model_id, "queued_convert")
        return object()

    manager.schedule_convert = fake_schedule_convert
    resp = client.post(
        "/v1/models/convert",
        json={"model": "qwen2.5-1.5b-fp16", "device": "NPU", "load_after": True},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "converting"
    assert body["model"]["is_loading"] is True
    assert calls == [("qwen2.5-1.5b-fp16", "NPU", True)]


def test_convert_model_accepts_normalized_composite_device(client):
    manager = client.app.state.manager
    calls = []

    def fake_schedule_convert(model_id, device=None, *, load_after=True):
        calls.append((model_id, device, load_after))
        manager._set_status(model_id, "queued_convert")
        return object()

    manager.schedule_convert = fake_schedule_convert
    resp = client.post(
        "/v1/models/convert",
        json={"model": "qwen2.5-1.5b-fp16", "device": "auto:npu, gpu, cpu", "load_after": True},
    )

    assert resp.status_code == 200, resp.text
    assert calls == [("qwen2.5-1.5b-fp16", "AUTO:NPU,GPU,CPU", True)]


def test_convert_model_rejects_invalid_device(client):
    resp = client.post(
        "/v1/models/convert",
        json={"model": "qwen2.5-1.5b-fp16", "device": "MULTI:NPU,BOGUS", "load_after": True},
    )

    assert resp.status_code == 400
    assert "BOGUS" in resp.json()["detail"]


def test_load_then_chat_completion(client):
    _load_and_wait(client)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "Hello there"}],
            "stream": False,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "Mock engine" in data["choices"][0]["message"]["content"]
    assert data["usage"]["completion_tokens"] > 0


def test_chat_completion_stop_sequence_truncates(client):
    _load_and_wait(client)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            "stop": ["You said"],
            "seed": 42,
        },
    )
    assert resp.status_code == 200, resp.text
    content = resp.json()["choices"][0]["message"]["content"]
    assert "You said" not in content  # generation cut at the stop sequence
    assert "Mock engine" in content  # text before the stop is preserved


def test_chat_completion_streaming_honors_stop(client):
    _load_and_wait(client)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "stop": ["You said"],
        },
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    # Reassemble the streamed deltas and confirm the stop sequence never appears.
    streamed = ""
    for line in body.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            payload = json.loads(line[6:])
            streamed += (
                payload["choices"][0]["delta"].get("content") or "" if payload["choices"] else ""
            )
    assert "You said" not in streamed
    assert '"finish_reason": "stop"' in body


def test_chat_completion_streaming(client):
    _load_and_wait(client)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "stream please"}],
            "stream": True,
            "stream_options": {"include_usage": True},
        },
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    assert "data: [DONE]" in body
    assert '"delta"' in body
    assert '"usage"' in body


def test_responses_non_streaming(client):
    _load_and_wait(client)
    resp = client.post(
        "/v1/responses",
        json={"model": MODEL_ID, "input": "hello", "stream": False},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["object"] == "response"
    assert "Mock engine" in data["output"][0]["content"][0]["text"]


def test_responses_streaming_emits_events(client):
    _load_and_wait(client)
    with client.stream(
        "POST",
        "/v1/responses",
        json={"model": MODEL_ID, "input": "hello", "stream": True},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())

    assert "event: response.created" in body
    assert "event: response.output_text.delta" in body
    assert "event: response.completed" in body
    assert "data: [DONE]" in body

    # Reassemble the streamed deltas back into the full text.
    streamed = ""
    for line in body.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            payload = json.loads(line[6:])
            if payload.get("type") == "response.output_text.delta":
                streamed += payload["delta"]
    assert "Mock engine" in streamed


def test_metrics_accumulate_after_requests(client):
    _load_and_wait(client)
    # No requests served yet for this model.
    before = client.get("/v1/system/status").json()["metrics"]
    assert before["per_model"].get(MODEL_ID, {}).get("requests", 0) == 0

    for _ in range(2):
        client.post(
            "/v1/chat/completions",
            json={"model": MODEL_ID, "messages": [{"role": "user", "content": "hi"}]},
        )

    metrics = client.get("/v1/system/status").json()["metrics"]
    per_model = metrics["per_model"][MODEL_ID]
    assert per_model["requests"] == 2
    assert per_model["completion_tokens"] > 0
    assert per_model["avg_latency_ms"] >= 0
    assert metrics["totals"]["requests"] >= 2


def test_chat_on_unloaded_model_returns_409(client):
    resp = client.post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code in (409, 503)


def test_unknown_model_load_404(client):
    resp = client.post("/v1/models/load", json={"model": "does-not-exist"})
    assert resp.status_code == 404


@pytest.fixture()
def authed_client():
    settings = Settings(
        models_file=BASE_DIR / "models.json",
        models_dir=BASE_DIR / "models" / "openvino",
        api_key="sk-secret-key",
        force_mock=True,
    )
    with TestClient(create_app(settings)) as c:
        yield c


def test_protected_route_rejects_missing_key(authed_client):
    assert authed_client.get("/v1/models").status_code == 401


def test_protected_route_rejects_wrong_key(authed_client):
    resp = authed_client.get("/v1/models", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_protected_route_accepts_correct_key(authed_client):
    resp = authed_client.get("/v1/models", headers={"Authorization": "Bearer sk-secret-key"})
    assert resp.status_code == 200


def test_health_is_unauthenticated(authed_client):
    # Liveness must stay reachable without a key even when auth is enabled.
    assert authed_client.get("/health").status_code == 200


def test_stream_handle_stop_halts_worker_early():
    """request_stop() must end generation before the full reply is produced, and
    wait_closed() must unblock once the worker thread has actually finished."""
    engine = MockEngine("test-model")
    prompt = "<|im_start|>user\nhi<|im_end|>\n"
    full_reply = engine.generate(prompt, GenParams()).text

    handle = engine.stream(prompt, GenParams())
    handle.next_chunk()  # let generation start
    handle.request_stop()

    while handle.next_chunk() is not None:  # drain to the sentinel
        pass
    handle.wait_closed(timeout=2.0)

    assert handle._done.is_set()  # worker really finished
    assert len(handle.text) < len(full_reply)  # it stopped early, didn't run to completion


def test_stream_cancellation_frees_the_model_lock():
    """Abandoning a stream early must stop the worker and release the lock before
    the next request runs, so two generations never overlap on one pipeline."""
    settings = Settings(
        models_file=BASE_DIR / "models.json",
        models_dir=BASE_DIR / "models" / "openvino",
        force_mock=True,
    )
    manager = ModelManager(settings)
    prompt = "<|im_start|>user\nhi<|im_end|>\n"
    params = GenParams(max_new_tokens=64)

    async def scenario():
        await manager.startup()
        task = manager.schedule_load(MODEL_ID)
        if task:
            await task
        engine = manager.resolve_engine(MODEL_ID)
        lock = manager.get_lock(engine.model_id)

        gen = manager.stream(engine, prompt, params)
        first = await gen.__anext__()  # consume one chunk, then bail out
        assert first
        assert lock.locked()  # held for the duration of the stream

        await gen.aclose()  # client-disconnect path
        assert not lock.locked()  # worker finished, lock released

        # The engine is still usable by a subsequent request.
        result = await manager.generate(engine, prompt, params)
        assert "Mock engine" in result.text
        await manager.shutdown()

    asyncio.run(scenario())


# --- Conversation export tests -----------------------------------------------


def test_chat_export_returns_markdown(client):
    """POST /v1/chat/export with a valid conversation returns a .md attachment."""
    messages = [
        {"role": "user", "content": "Hello there"},
        {"role": "assistant", "content": "Hi! **How can I help?**"},
    ]
    resp = client.post("/v1/chat/export", json={"messages": messages})
    assert resp.status_code == 200, resp.text
    assert "text/markdown" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "chat-export-" in resp.headers["content-disposition"]

    body = resp.text
    # Header present
    assert "# Chat Export" in body
    # User message rendered as blockquote
    assert "> Hello there" in body
    # Assistant content preserved verbatim
    assert "Hi! **How can I help?**" in body


def test_chat_export_empty_messages_returns_400(client):
    """An empty messages list must be rejected."""
    resp = client.post("/v1/chat/export", json={"messages": []})
    assert resp.status_code == 400
    assert "No messages" in resp.json()["detail"]


def test_chat_export_includes_model_metadata(client):
    """Model and device appear in the export header when provided."""
    messages = [{"role": "user", "content": "test"}]
    resp = client.post(
        "/v1/chat/export",
        json={"messages": messages, "model": "tinyllama-1.1b-chat-fp16", "device": "NPU"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "tinyllama-1.1b-chat-fp16" in body
    assert "NPU" in body


def test_chat_export_auth_protected(authed_client):
    """Export must be rejected without a valid API key."""
    resp = authed_client.post(
        "/v1/chat/export",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


# --- Activity event log tests -----------------------------------------------


def test_startup_event_present(client):
    """A fresh server should have a startup event in the activity log."""
    body = client.get("/v1/system/status").json()
    events = body.get("events", [])
    assert any("Server started" in ev["message"] for ev in events)


def test_events_appear_after_model_load(client):
    """Loading a model emits an info event visible in /v1/system/status."""
    _load_and_wait(client)
    body = client.get("/v1/system/status").json()
    events = body.get("events", [])
    loaded = [ev for ev in events if "Loaded" in ev["message"] and "TinyLlama" in ev["message"]]
    assert loaded, f"Expected a load event, got: {events}"
    assert loaded[-1]["level"] == "info"


def test_events_appear_after_model_unload(client):
    """Unloading a model emits an info event."""
    _load_and_wait(client)
    client.post("/v1/models/unload", json={"model": MODEL_ID})
    body = client.get("/v1/system/status").json()
    events = body.get("events", [])
    unloaded = [ev for ev in events if "Unloaded" in ev["message"]]
    assert unloaded, f"Expected an unload event, got: {events}"


def test_events_capped_at_max(client):
    """The event log should never exceed 50 entries."""
    manager = client.app.state.manager
    for i in range(60):
        manager.emit_event("info", f"Event {i}")
    body = client.get("/v1/system/status").json()
    events = body.get("events", [])
    assert len(events) <= 50
    # Oldest events should have been dropped (event 0..9 gone).
    messages = [ev["message"] for ev in events]
    assert "Event 0" not in messages
    assert "Event 59" in messages


def test_events_appear_after_generation(client):
    """Generating a completion emits a generation event."""
    _load_and_wait(client)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        },
    )
    assert resp.status_code == 200
    body = client.get("/v1/system/status").json()
    events = body.get("events", [])
    generated = [ev for ev in events if "Generated" in ev["message"] and "tokens" in ev["message"]]
    assert generated, f"Expected a generation event, got: {events}"
    assert generated[-1]["level"] == "info"


def test_cors_middleware_headers():
    settings = Settings(
        models_file=BASE_DIR / "models.json",
        models_dir=BASE_DIR / "models" / "openvino",
        cors_origins="http://localhost:3000",
        force_mock=True,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        headers = {"Origin": "http://localhost:3000"}
        resp = c.get("/health", headers=headers)
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_auto_convert_triggered_on_load(monkeypatch):
    monkeypatch.setattr("runtime.device_check.is_openvino_available", lambda: True)
    settings = Settings(
        models_file=BASE_DIR / "models.json",
        models_dir=BASE_DIR / "models" / "openvino",
        force_mock=False,
        auto_convert=True,
    )
    manager = ModelManager(settings)

    downloaded_states = [False, True]

    def mock_is_downloaded(cfg, base_dir):
        if downloaded_states:
            return downloaded_states.pop(0)
        return True

    import app.model_registry as registry

    monkeypatch.setattr(registry, "is_downloaded", mock_is_downloaded)

    class FakeEngine:
        model_id = "smollm2-135m-fp16"
        device = "CPU"

        def close(self):
            pass

    monkeypatch.setattr(manager, "_build_engine", lambda mid, dev: FakeEngine())

    convert_calls = []

    async def mock_convert_task(model_id, device, load_after):
        convert_calls.append((model_id, device, load_after))

    monkeypatch.setattr(manager, "_convert_task", mock_convert_task)

    async def run_scenario():
        await manager._load_task("smollm2-135m-fp16", "CPU")

    asyncio.run(run_scenario())

    assert len(convert_calls) == 1
    assert convert_calls[0] == ("smollm2-135m-fp16", "CPU", False)


def test_health_endpoints_live_and_ready(client):
    resp_live = client.get("/health/live")
    assert resp_live.status_code == 200
    assert resp_live.json() == {"status": "ok"}

    resp_ready = client.get("/health/ready")
    assert resp_ready.status_code == 200
    assert resp_ready.json() == {"status": "ready"}

    manager = client.app.state.manager
    manager._set_status(MODEL_ID, "loading")
    try:
        resp_busy = client.get("/health/ready")
        assert resp_busy.status_code == 503
        assert resp_busy.json()["status"] == "busy"
    finally:
        manager._clear_status(MODEL_ID)


def test_request_id_propagation_and_header(client):
    custom_id = "test-req-12345"
    resp = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_id

    resp_auto = client.get("/health")
    assert resp_auto.status_code == 200
    assert "X-Request-ID" in resp_auto.headers
    assert resp_auto.headers["X-Request-ID"].startswith("req-")


def test_success_request_log_keeps_request_id(client, caplog):
    custom_id = "test-req-log-id"
    caplog.set_level("INFO", logger="ov-llm.server")

    resp = client.get("/health", headers={"X-Request-ID": custom_id})

    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_id
    records = [
        record
        for record in caplog.records
        if record.name == "ov-llm.server" and "HTTP GET /health - Status:" in record.getMessage()
    ]
    assert records
    assert records[-1].request_id == custom_id


def test_unsafe_request_id_is_replaced(client):
    """Header values that could forge log lines are swapped for a generated id."""
    resp = client.get("/health", headers={"X-Request-ID": "evil\tid injected"})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"].startswith("req-")

    too_long = "a" * 200
    resp = client.get("/health", headers={"X-Request-ID": too_long})
    assert resp.headers["X-Request-ID"].startswith("req-")


def test_wildcard_cors_does_not_allow_credentials(client):
    resp = client.options(
        "/v1/models",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in resp.headers
