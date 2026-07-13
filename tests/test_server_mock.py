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
    assert "prefers-reduced-motion" in body
    assert ".icon-btn:focus-visible" in body
    assert ".meta-btn:focus-visible" in body
    assert ".bubble pre:focus-within .code-copy" in body


def test_index_has_multichat_theme_and_regenerate(client):
    body = client.get("/").text
    # Conversation history sidebar with local persistence + v1 migration.
    assert 'id="chats-sidebar"' in body
    assert "ovllm.chats.v2" in body
    assert "ovllm.chat.v1" in body
    # Light/dark theme toggle persisted per browser.
    assert 'id="theme-toggle-btn"' in body
    assert "ovllm.theme.v1" in body
    assert '[data-theme="light"]' in body
    # Per-message actions.
    assert "function regenerateLast" in body
    assert "function formatMsgStat" in body


def test_index_escapes_dynamic_model_card_content(client):
    body = client.get("/").text
    assert "const safeName = escapeHtml(model.name)" in body
    assert "data-model-action" in body
    assert 'onclick="triggerModelPrimaryAction' not in body
    assert "return window.DOMPurify ? DOMPurify.sanitize(raw) : escapeHtml(text || '')" in body
    assert "submitModalBtn.disabled = true" in body


def test_system_status_includes_model_progress(client):
    body = client.get("/v1/system/status").json()
    entry = next(m for m in body["models"]["available"] if m["id"] == MODEL_ID)

    progress = entry["progress"]
    assert set(progress) == {"phase", "message", "percent", "started_at", "updated_at", "log_tail"}
    assert progress["phase"] in {"ready", "idle"}
    assert isinstance(progress["message"], str)
    assert isinstance(progress["log_tail"], list)


def test_progress_message_updates_status_label(client):
    manager = client.app.state.manager
    manager._set_status(MODEL_ID, "loading")
    manager._set_progress(
        MODEL_ID,
        "loading",
        "Loading TinyLlama on GPU...",
        percent=42,
        append_log="Loading TinyLlama on GPU...",
    )

    body = client.get("/v1/system/status").json()
    entry = next(m for m in body["models"]["available"] if m["id"] == MODEL_ID)

    assert entry["status"] == "loading"
    assert entry["is_loading"] is True
    assert entry["status_label"] == "Loading TinyLlama on GPU... (42%)"
    assert entry["progress"]["phase"] == "loading"
    assert entry["progress"]["percent"] == 42
    assert entry["progress"]["log_tail"] == ["Loading TinyLlama on GPU..."]


def test_progress_sanitizes_converter_output(client):
    manager = client.app.state.manager
    manager._set_status(MODEL_ID, "converting")
    manager._set_progress(
        MODEL_ID,
        "downloading",
        "Downloading with Bearer super-secret-token",
        append_log="token = hf_abcdefghijklmnopqrstuvwxyz123456",
    )

    body = client.get("/v1/system/status").json()
    entry = next(m for m in body["models"]["available"] if m["id"] == MODEL_ID)

    assert "[redacted]" in entry["progress"]["message"]
    assert entry["progress"]["log_tail"] == ["[redacted]"]


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
    assert "progress" in resp.json()["model"]

    deadline = time.time() + 10
    while time.time() < deadline:
        body = client.get("/v1/system/status").json()
        entry = next(m for m in body["models"]["available"] if m["id"] == MODEL_ID)
        if entry["is_loaded"]:
            assert entry["device"] == "GPU"
            assert entry["progress"]["phase"] == "ready"
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

    def fake_schedule_convert(model_id, device=None, *, load_after=True, **kwargs):
        calls.append((model_id, device, load_after))
        manager._set_status(model_id, "queued_convert")
        manager._set_progress(model_id, "queued", "Queued conversion...")
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
    assert body["model"]["progress"]["phase"] == "queued"
    assert calls == [("qwen2.5-1.5b-fp16", "NPU", True)]


def test_convert_model_accepts_normalized_composite_device(client):
    manager = client.app.state.manager
    calls = []

    def fake_schedule_convert(model_id, device=None, *, load_after=True, **kwargs):
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


def test_embeddings_endpoint_success(client):
    # First, let's load the embedding model in mock mode
    _load_and_wait(client, model_id="bge-small-en-v1.5")

    # 1. Single string input, float format
    resp = client.post(
        "/v1/embeddings",
        json={"model": "bge-small-en-v1.5", "input": "hello world"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 1
    assert data["data"][0]["index"] == 0
    assert isinstance(data["data"][0]["embedding"], list)
    assert len(data["data"][0]["embedding"]) == 384
    assert data["model"] == "bge-small-en-v1.5"
    assert data["usage"]["prompt_tokens"] > 0

    # 2. List of strings input, base64 format
    resp = client.post(
        "/v1/embeddings",
        json={
            "model": "bge-small-en-v1.5",
            "input": ["hello", "world"],
            "encoding_format": "base64",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["data"]) == 2
    assert isinstance(data["data"][0]["embedding"], str)
    # Base64 decoder check
    import base64
    import struct

    decoded = base64.b64decode(data["data"][0]["embedding"])
    floats = struct.unpack(f"{len(decoded) // 4}f", decoded)
    assert len(floats) == 384


def test_embedding_model_guards(client):
    # Load bge (embedding) and tinyllama (text generation)
    _load_and_wait(client, model_id="bge-small-en-v1.5")
    _load_and_wait(client, model_id=MODEL_ID)

    # 1. Chat completions fails with embedding model
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "bge-small-en-v1.5",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 400
    assert "embedding model" in resp.json()["detail"]

    # 2. Responses API fails with embedding model
    resp = client.post(
        "/v1/responses",
        json={
            "model": "bge-small-en-v1.5",
            "input": "hi",
        },
    )
    assert resp.status_code == 400
    assert "embedding model" in resp.json()["detail"]

    # 3. Embeddings fails with text generation model
    resp = client.post(
        "/v1/embeddings",
        json={
            "model": MODEL_ID,
            "input": "hi",
        },
    )
    assert resp.status_code == 400
    assert "not an embedding model" in resp.json()["detail"]


def test_chat_completions_with_structured_output_format(client):
    _load_and_wait(client)
    # The server accepts response_format in request payload
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "return json please"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "test_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                        },
                        "required": ["name", "age"],
                    },
                },
            },
        },
    )
    assert resp.status_code == 200, resp.text
    content = resp.json()["choices"][0]["message"]["content"]
    assert "Mock engine" in content


def test_search_hf_endpoint(client):
    # Mocking the HTTP request to Hugging Face
    # Let's verify that the endpoint parses the search query and returns results
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(
        return_value=[
            {
                "id": "Qwen/Qwen2.5-0.5B-Instruct",
                "downloads": 15000,
                "likes": 350,
                "pipeline_tag": "text-generation",
                "tags": ["text-generation", "openvino"],
            }
        ]
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        resp = client.get("/v1/models/search-hf?query=qwen")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "Qwen/Qwen2.5-0.5B-Instruct"
        assert data[0]["backend"] == "openvino-genai"
        assert data[0]["suggested_local_id"] == "qwen-qwen2.5-0.5b-instruct"
        mock_get.assert_called_once()


def test_download_custom_endpoint(client):
    # Backup original models.json to avoid polluting the workspace on disk
    from app.config import BASE_DIR

    models_file = BASE_DIR / "models.json"
    backup = models_file.read_text(encoding="utf-8")
    try:
        # Dynamic download/conversion scheduling with custom INT4 options
        resp = client.post(
            "/v1/models/download-custom",
            json={
                "model_id": "smollm2-135m-custom-int4",
                "name": "SmolLM2 135M Custom INT4",
                "source_model": "HuggingFaceTB/SmolLM2-135M-Instruct",
                "backend": "openvino-genai",
                "weight_format": "int4",
                "group_size": -1,
                "ratio": 0.9,
                "sym": True,
                "load_after": False,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] in ("converting", "queued_convert", "ready")
        assert data["model"]["id"] == "smollm2-135m-custom-int4"
        assert data["model"]["backend"] == "openvino-genai"
    finally:
        models_file.write_text(backup, encoding="utf-8")


def test_speculative_decoding_load(client):
    # Speculative decoding draft model parameter passed to /v1/models/load
    from unittest.mock import patch

    manager = client.app.state.manager

    with patch.object(manager, "_build_engine") as mock_build:
        resp = client.post(
            "/v1/models/load",
            json={
                "model": "tinyllama-1.1b-chat-fp16",
                "draft_model": "smollm2-135m-fp16",
            },
        )
        assert resp.status_code == 200
        # Wait for loading to finish
        import time

        for _ in range(50):
            if "tinyllama-1.1b-chat-fp16" not in manager.load_tasks:
                break
            time.sleep(0.02)

        # Verify draft model path was resolved and passed
        mock_build.assert_called_once()
        args = mock_build.call_args[0]
        # First positional argument is model_id, second is device, third is draft_model_path
        assert args[0] == "tinyllama-1.1b-chat-fp16"
        assert "smollm2-135m-instruct-fp16" in args[2]


def test_dynamic_lora_generation(client):
    # Dynamic LoRA parameters inside completions call
    from unittest.mock import patch

    _load_and_wait(client)
    engine = client.app.state.manager.engines[MODEL_ID]

    # Wrap engine.generate to invoke _build_adapters_config (since MockEngine is used in tests)
    orig_generate = engine.generate

    def fake_generate(prompt, params):
        engine._build_adapters_config(params)
        return orig_generate(prompt, params)

    engine.generate = fake_generate

    with patch.object(engine, "_build_adapters_config") as mock_adapters:
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": "hi"}],
                "lora_path": "models/adapters/test-lora",
                "lora_alpha": 0.8,
            },
        )
        assert resp.status_code == 200
        mock_adapters.assert_called_once()
        params = mock_adapters.call_args[0][0]
        assert params.lora_path == "models/adapters/test-lora"
        assert params.lora_alpha == 0.8


def test_multiple_api_keys_and_tracking():
    # Test setting multiple API keys via Settings and tracking metrics
    from fastapi.testclient import TestClient

    from app.config import BASE_DIR, Settings
    from app.server import create_app

    settings = Settings(
        models_file=BASE_DIR / "models.json",
        models_dir=BASE_DIR / "models" / "openvino",
        api_key="key1,key2",
        force_mock=True,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        # Request with key1
        resp = test_client.get("/v1/models", headers={"Authorization": "Bearer key1"})
        assert resp.status_code == 200

        # Request with key2
        resp = test_client.get("/v1/models", headers={"Authorization": "Bearer key2"})
        assert resp.status_code == 200

        # Request with invalid key
        resp = test_client.get("/v1/models", headers={"Authorization": "Bearer key3"})
        assert resp.status_code == 401

        # Verify stats endpoint
        resp = test_client.get("/v1/keys/stats", headers={"Authorization": "Bearer key1"})
        assert resp.status_code == 200
        stats = resp.json()
        assert len(stats) == 2
        # Obfuscated key names should be returned
        names = [s["key_name"] for s in stats]
        assert len(set(names)) == 2
        assert all(name.startswith("ke...") for name in names)
