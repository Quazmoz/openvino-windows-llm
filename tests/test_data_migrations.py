import json
from types import SimpleNamespace

import pytest

from app.data_migrations import ensure_data_schema


def paths(tmp_path):
    config = tmp_path / "config"
    onboarding = tmp_path / "onboarding"
    config.mkdir()
    onboarding.mkdir()
    return SimpleNamespace(
        data_root=tmp_path,
        config_dir=config,
        models_file=config / "models.json",
        onboarding_file=onboarding / "state.json",
    )


def test_data_schema_creation_is_idempotent(tmp_path):
    value = paths(tmp_path)
    assert ensure_data_schema(value) == 1
    first = (tmp_path / "data-schema.json").read_text()
    assert ensure_data_schema(value) == 1
    second = (tmp_path / "data-schema.json").read_text()
    assert json.loads(first)["schema_version"] == json.loads(second)["schema_version"] == 1


def test_newer_data_schema_is_rejected(tmp_path):
    value = paths(tmp_path)
    (tmp_path / "data-schema.json").write_text('{"schema_version": 2}')
    with pytest.raises(RuntimeError, match="older than the persistent data schema"):
        ensure_data_schema(value)
