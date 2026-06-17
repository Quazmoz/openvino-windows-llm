import json

import pytest

from runtime import model_converter as mc


def test_build_export_command_basic():
    cmd = mc.build_export_command("org/model", "out/dir", "int4")
    assert cmd[0] == "optimum-cli"
    assert cmd[1:3] == ["export", "openvino"]
    assert "--model" in cmd and cmd[cmd.index("--model") + 1] == "org/model"
    assert "--weight-format" in cmd and cmd[cmd.index("--weight-format") + 1] == "int4"
    assert "--trust-remote-code" in cmd
    assert cmd[-1] == "out/dir"  # output dir is last


def test_build_export_command_with_task_and_no_trust():
    cmd = mc.build_export_command(
        "org/model", "out", "int8", trust_remote_code=False, task="text-generation"
    )
    assert "--task" in cmd and cmd[cmd.index("--task") + 1] == "text-generation"
    assert "--trust-remote-code" not in cmd
    assert "int8" in cmd


def test_export_model_raises_when_cli_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(mc.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="optimum-cli not found"):
        mc.export_model("org/model", tmp_path / "out")


def test_export_model_runs_command_and_makes_parent(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, check=False):
        captured["cmd"] = cmd
        captured["check"] = check

    monkeypatch.setattr(mc.shutil, "which", lambda name: "/usr/bin/optimum-cli")
    monkeypatch.setattr(mc.subprocess, "run", fake_run)

    out = tmp_path / "ir" / "model"
    result = mc.export_model("org/model", out, "int8")

    assert result == out
    assert out.parent.is_dir()  # parent created before export
    assert captured["check"] is True
    assert "org/model" in captured["cmd"]
    assert "int8" in captured["cmd"]


def test_resolve_from_catalog_reads_models_json(monkeypatch, tmp_path):
    catalog = {
        "m1": {
            "name": "M1",
            "model_path": "models/openvino/m1",
            "source_model": "org/m1",
            "weight_format": "int8",
        }
    }
    catalog_file = tmp_path / "models.json"
    catalog_file.write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setenv("OV_LLM_MODELS_FILE", str(catalog_file))

    source, output_dir, weight_format = mc._resolve_from_catalog("m1")
    assert source == "org/m1"
    assert weight_format == "int8"
    assert output_dir.name == "m1"


def test_main_by_id_uses_catalog_weight_format(monkeypatch, tmp_path, capsys):
    catalog = {
        "m1-fp16": {
            "name": "M1 FP16",
            "model_path": "models/openvino/m1-fp16",
            "source_model": "org/m1",
            "weight_format": "fp16",
        }
    }
    catalog_file = tmp_path / "models.json"
    catalog_file.write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setenv("OV_LLM_MODELS_FILE", str(catalog_file))

    captured = {}

    def fake_export(source_model, output_dir, weight_format, **kwargs):
        captured["source_model"] = source_model
        captured["output_dir"] = output_dir
        captured["weight_format"] = weight_format
        return output_dir

    monkeypatch.setattr(mc, "export_model", fake_export)

    assert mc.main(["--id", "m1-fp16"]) == 0
    assert captured["source_model"] == "org/m1"
    assert captured["weight_format"] == "fp16"
    assert captured["output_dir"].name == "m1-fp16"
    assert "Done." in capsys.readouterr().out


def test_main_by_id_allows_weight_format_override(monkeypatch, tmp_path):
    catalog = {
        "m1-fp16": {
            "model_path": "models/openvino/m1-fp16",
            "source_model": "org/m1",
            "weight_format": "fp16",
        }
    }
    catalog_file = tmp_path / "models.json"
    catalog_file.write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setenv("OV_LLM_MODELS_FILE", str(catalog_file))

    captured = {}
    monkeypatch.setattr(
        mc,
        "export_model",
        lambda source_model, output_dir, weight_format, **kwargs: captured.setdefault(
            "weight_format", weight_format
        )
        or output_dir,
    )

    assert mc.main(["--id", "m1-fp16", "--weight-format", "int8"]) == 0
    assert captured["weight_format"] == "int8"


def test_resolve_from_catalog_unknown_id_exits(monkeypatch, tmp_path):
    catalog_file = tmp_path / "models.json"
    catalog_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OV_LLM_MODELS_FILE", str(catalog_file))

    with pytest.raises(SystemExit):
        mc._resolve_from_catalog("does-not-exist")
