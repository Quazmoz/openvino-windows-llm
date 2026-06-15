"""End-to-end smoke tests of the server running on the built-in mock engine.

These exercise the full FastAPI stack (routing, lifecycle, the model manager, and
the streaming bridge) without OpenVINO, so they run anywhere — including macOS.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import BASE_DIR, Settings
from app.server import create_app

MODEL_ID = "tinyllama-1.1b-chat"


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
