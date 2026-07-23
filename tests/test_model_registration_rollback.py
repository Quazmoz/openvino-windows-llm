import json

import pytest

from app import model_manager as manager_module
from app.config import Settings
from app.model_manager import ModelManager
from app.openai_api import ModelRegisterRequest


def test_failed_catalog_write_does_not_leave_model_registered(tmp_path, monkeypatch):
    models_file = tmp_path / "models.json"
    models_file.write_text(json.dumps({}), encoding="utf-8")
    settings = Settings(
        models_file=models_file,
        models_dir=tmp_path / "models",
        cache_dir=tmp_path / "cache",
        benchmark_results_file=tmp_path / "benchmarks.json",
        force_mock=True,
    )
    manager = ModelManager(settings)
    request = ModelRegisterRequest(
        model_id="failed-registration",
        name="Failed Registration",
        source_model="example/failed-registration",
        weight_format="int4",
        recommended_device="CPU",
        max_context_len=2048,
        max_output_tokens=512,
    )

    def fail_save(*_args, **_kwargs):
        raise OSError("catalog write failed")

    monkeypatch.setattr(manager_module.registry, "save_catalog", fail_save)
    with pytest.raises(OSError, match="catalog write failed"):
        manager.register_model(request)

    assert "failed-registration" not in manager.catalog
    assert json.loads(models_file.read_text(encoding="utf-8")) == {}
