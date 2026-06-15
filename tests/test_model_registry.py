import json

from app.model_registry import (
    is_downloaded,
    load_catalog,
    make_catalog_entry,
)


def _write_catalog(tmp_path, data):
    path = tmp_path / "models.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_catalog_parses_entries(tmp_path):
    path = _write_catalog(
        tmp_path,
        {
            "m1": {
                "name": "Model One",
                "model_path": "models/openvino/m1",
                "source_model": "org/model-one",
                "max_context_len": 4096,
                "max_output_tokens": 1024,
            }
        },
    )
    catalog = load_catalog(path)
    assert "m1" in catalog
    cfg = catalog["m1"]
    assert cfg.name == "Model One"
    assert cfg.max_prompt_len == 4096 - 1024


def test_load_catalog_missing_file_returns_empty(tmp_path):
    assert load_catalog(tmp_path / "nope.json") == {}


def test_load_catalog_skips_malformed_entries(tmp_path):
    path = _write_catalog(tmp_path, {"good": {"name": "G"}, "bad": "not-an-object"})
    catalog = load_catalog(path)
    assert "good" in catalog
    assert "bad" not in catalog


def test_is_downloaded_detects_ir_markers(tmp_path):
    path = _write_catalog(tmp_path, {"m1": {"name": "M1", "model_path": "ir/m1"}})
    cfg = load_catalog(path)["m1"]
    assert not is_downloaded(cfg, tmp_path)

    model_dir = tmp_path / "ir" / "m1"
    model_dir.mkdir(parents=True)
    (model_dir / "openvino_model.xml").write_text("<xml/>")
    assert is_downloaded(cfg, tmp_path)


def test_make_catalog_entry_status_precedence(tmp_path):
    path = _write_catalog(tmp_path, {"m1": {"name": "M1"}})
    cfg = load_catalog(path)["m1"]

    loaded = make_catalog_entry(cfg, loaded=True, queued=False, loading=False, downloaded=True)
    assert loaded["status"] == "loaded"
    assert loaded["can_unload"] is True
    assert loaded["can_load"] is False

    error = make_catalog_entry(cfg, loaded=False, queued=False, loading=False, downloaded=True, error="boom")
    assert error["status"] == "error"
    assert error["error"] == "boom"

    ready = make_catalog_entry(cfg, loaded=False, queued=False, loading=False, downloaded=True)
    assert ready["status"] == "ready_to_load"
    assert ready["can_delete"] is True

    missing = make_catalog_entry(cfg, loaded=False, queued=False, loading=False, downloaded=False)
    assert missing["status"] == "not_downloaded"
    assert missing["can_delete"] is False
