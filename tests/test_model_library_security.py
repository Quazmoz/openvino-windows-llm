from fastapi.testclient import TestClient

from app.config import Settings
from app.model_library_routes import _RouteModelLibraryService
from app.model_manager import ModelManager
from app.server import create_app


def _settings(tmp_path):
    models_file = tmp_path / "config" / "models.json"
    models_file.parent.mkdir(parents=True)
    models_file.write_text("{}\n", encoding="utf-8")
    return Settings(
        host="127.0.0.1",
        port=8000,
        device="CPU",
        models_file=models_file,
        models_dir=tmp_path / "models",
        cache_dir=tmp_path / "cache",
        benchmark_results_file=tmp_path / "benchmarks" / "benchmarks.json",
        default_model=None,
        api_key=None,
        force_mock=True,
    )


def test_official_manifest_cannot_enable_remote_code(tmp_path):
    settings = _settings(tmp_path)
    manager = ModelManager(settings)
    service = _RouteModelLibraryService(settings, manager)

    service.apply_official_definitions(
        {
            "catalog": {
                "safe-official-model": {
                    "definition": {
                        "model_id": "safe-official-model",
                        "name": "Safe Official Model",
                        "source_model": "example/safe-official-model",
                        "backend": "openvino-genai",
                        "weight_format": "fp16",
                        "recommended_device": "CPU",
                        "max_context_len": 2048,
                        "max_output_tokens": 512,
                        "trust_remote_code": True,
                    },
                    "metadata": {},
                }
            }
        }
    )

    assert manager.catalog["safe-official-model"].trust_remote_code is False


def test_converted_model_overwrite_is_refused(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/v1/model-library/import-converted",
            json={
                "model_id": "overwrite-refused",
                "name": "Overwrite Refused",
                "source_path": str(tmp_path.resolve()),
                "backend": "openvino-genai",
                "weight_format": "fp16",
                "recommended_device": "CPU",
                "max_context_len": 2048,
                "max_output_tokens": 512,
                "overwrite": True,
            },
        )

    assert response.status_code == 400
    assert "replacement is intentionally disabled" in response.json()["detail"]
