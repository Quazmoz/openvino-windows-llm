"""Regression tests for explicit device selection during model loading."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import BASE_DIR, Settings
from app.server import create_app
from runtime.openvino_engine import MockEngine

MODEL_ID = "tinyllama-1.1b-chat-fp16"


def _client() -> TestClient:
    settings = Settings(
        host="127.0.0.1",
        port=8000,
        device="GPU",
        models_file=BASE_DIR / "models.json",
        models_dir=BASE_DIR / "models" / "openvino",
        default_model=None,
        api_key=None,
        force_mock=True,
    )
    return TestClient(create_app(settings))


def _wait_for_device(client: TestClient, expected_device: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last_entry: dict = {}
    while time.time() < deadline:
        status = client.get("/v1/system/status").json()
        last_entry = next(
            model for model in status["models"]["available"] if model["id"] == MODEL_ID
        )
        if last_entry["is_loaded"] and last_entry["device"] == expected_device:
            return last_entry
        time.sleep(0.02)
    raise AssertionError(
        f"{MODEL_ID} did not load on {expected_device}; last status was {last_entry}"
    )


def test_explicit_npu_load_switches_model_already_loaded_on_gpu() -> None:
    with _client() as client:
        first = client.post(
            "/v1/models/load",
            json={"model": MODEL_ID, "device": "GPU"},
        )
        assert first.status_code == 200, first.text
        _wait_for_device(client, "GPU")

        switch = client.post(
            "/v1/models/load",
            json={"model": MODEL_ID, "device": "NPU"},
        )
        assert switch.status_code == 200, switch.text

        entry = _wait_for_device(client, "NPU")
        assert entry["progress"]["phase"] == "ready"
        assert client.app.state.manager.devices[MODEL_ID] == "NPU"


def test_newest_device_request_retargets_in_flight_first_load() -> None:
    first_build_started = threading.Event()
    release_first_build = threading.Event()
    build_devices: list[str] = []

    with _client() as client:
        manager = client.app.state.manager

        def blocking_build(
            model_id: str,
            device: str,
            draft_model_path: str | None = None,
        ) -> MockEngine:
            build_devices.append(device)
            if len(build_devices) == 1:
                first_build_started.set()
                if not release_first_build.wait(timeout=5):
                    raise TimeoutError("Test did not release the first mock engine build")
            return MockEngine(
                model_id,
                str(Path("models") / model_id),
                device,
            )

        manager._build_engine = blocking_build

        first = client.post(
            "/v1/models/load",
            json={"model": MODEL_ID, "device": "GPU"},
        )
        assert first.status_code == 200, first.text
        assert first_build_started.wait(timeout=2), "GPU build did not start"

        try:
            retarget = client.post(
                "/v1/models/load",
                json={"model": MODEL_ID, "device": "NPU"},
            )
            assert retarget.status_code == 200, retarget.text
        finally:
            release_first_build.set()

        entry = _wait_for_device(client, "NPU")
        assert entry["device"] == "NPU"
        assert build_devices == ["GPU", "NPU"]
