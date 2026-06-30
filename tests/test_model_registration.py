import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.model_manager import ModelManager
from app.model_registry import load_catalog
from app.openai_api import ModelRegisterRequest
from app.server import create_app


@pytest.fixture()
def temp_models_file(tmp_path):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({}), encoding="utf-8")
    return path


@pytest.fixture()
def client(temp_models_file):
    settings = Settings(
        host="127.0.0.1",
        port=8000,
        device="CPU",
        models_file=temp_models_file,
        default_model=None,
        api_key=None,
        force_mock=True,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def test_register_model_success(temp_models_file):
    settings = Settings(
        models_file=temp_models_file,
        force_mock=True,
    )
    manager = ModelManager(settings)

    req = ModelRegisterRequest(
        model_id="custom-m1",
        name="Custom Model One",
        source_model="org/custom-m1",
        weight_format="int4",
        recommended_device="CPU",
        max_context_len=2048,
        max_output_tokens=512,
        description="A nice custom model",
    )

    cfg = manager.register_model(req)
    assert cfg.id == "custom-m1"
    assert cfg.name == "Custom Model One"
    assert cfg.source_model == "org/custom-m1"
    assert cfg.weight_format == "int4"
    assert cfg.recommended_device == "CPU"
    assert cfg.max_context_len == 2048
    assert cfg.max_output_tokens == 512
    assert cfg.description == "A nice custom model"

    # Verify persistence
    reloaded = load_catalog(temp_models_file)
    assert "custom-m1" in reloaded
    assert reloaded["custom-m1"].name == "Custom Model One"


def test_register_model_duplicate_raises(temp_models_file):
    settings = Settings(
        models_file=temp_models_file,
        force_mock=True,
    )
    manager = ModelManager(settings)

    req = ModelRegisterRequest(
        model_id="custom-m1",
        name="Custom Model One",
        source_model="org/custom-m1",
    )
    manager.register_model(req)

    with pytest.raises(ValueError) as exc:
        manager.register_model(req)
    assert "already registered" in str(exc.value)


def test_register_endpoint_success(client, temp_models_file):
    payload = {
        "model_id": "custom-endpoint-model",
        "name": "Endpoint Custom Model",
        "source_model": "org/endpoint-model",
        "weight_format": "int8",
        "recommended_device": "GPU",
        "max_context_len": 4096,
        "max_output_tokens": 1024,
        "description": "Registered via endpoint test",
    }

    resp = client.post("/v1/models/register", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "registered"
    assert data["model"]["id"] == "custom-endpoint-model"
    assert data["model"]["name"] == "Endpoint Custom Model"
    assert data["model"]["source_model"] == "org/endpoint-model"
    assert data["model"]["weight_format"] == "int8"
    assert data["model"]["recommended_device"] == "GPU"
    assert data["model"]["max_context_len"] == 4096
    assert data["model"]["max_output_tokens"] == 1024

    # Verify listing includes the new model
    list_resp = client.get("/v1/models")
    assert list_resp.status_code == 200
    ids = {m["id"] for m in list_resp.json()["data"]}
    assert "custom-endpoint-model" in ids


def test_register_endpoint_duplicate_returns_400(client):
    payload = {
        "model_id": "duplicate-model",
        "name": "Dup Model",
        "source_model": "org/dup",
    }

    resp1 = client.post("/v1/models/register", json=payload)
    assert resp1.status_code == 200

    resp2 = client.post("/v1/models/register", json=payload)
    assert resp2.status_code == 400
    assert "already registered" in resp2.json()["detail"]


def test_register_endpoint_rejects_unsafe_model_id(client):
    payload = {
        "model_id": "../escape hatch",
        "name": "Unsafe Model",
        "source_model": "org/unsafe",
    }

    resp = client.post("/v1/models/register", json=payload)
    assert resp.status_code == 422
    assert "model_id" in resp.text


def test_register_endpoint_rejects_invalid_recommended_device(client):
    payload = {
        "model_id": "bad-device-model",
        "name": "Bad Device Model",
        "source_model": "org/bad-device",
        "recommended_device": "BANANA",
    }

    resp = client.post("/v1/models/register", json=payload)
    assert resp.status_code == 422
    assert "recommended_device" in resp.text
