"""End-to-end smoke tests of the server running on the built-in mock engine.

These exercise the full FastAPI stack (routing, lifecycle, the model manager, and
the streaming bridge) without OpenVINO, so they run anywhere — including macOS.
"""

import asyncio
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
        device="CPU",
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


def test_devices_endpoint(client):
    body = client.get("/v1/devices").json()
    assert body["mock"] is True
    assert "devices" in body


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


def test_chat_on_unloaded_model_returns_409(client):
    resp = client.post(
        "/v1/chat/completions",
        json={"model": MODEL_ID, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code in (409, 503)


def test_unknown_model_load_404(client):
    resp = client.post("/v1/models/load", json={"model": "does-not-exist"})
    assert resp.status_code == 404


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
