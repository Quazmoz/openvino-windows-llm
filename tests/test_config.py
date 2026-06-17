from pathlib import Path

import pytest

from app.config import BASE_DIR, Settings, _bool_env, _resolve

_ENV_VARS = [
    "OV_LLM_HOST",
    "OV_LLM_PORT",
    "OV_LLM_DEVICE",
    "OV_LLM_MODELS_FILE",
    "OV_LLM_MODELS_DIR",
    "OV_LLM_CACHE_DIR",
    "OV_LLM_MODEL",
    "OV_LLM_API_KEY",
    "OV_LLM_MOCK",
]


@pytest.fixture()
def clean_env(monkeypatch):
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_from_env_defaults(clean_env):
    s = Settings.from_env()
    assert s.host == "127.0.0.1"
    assert s.port == 8000
    assert s.device == "NPU"
    assert s.models_file == BASE_DIR / "models.json"
    assert s.models_dir == BASE_DIR / "models" / "openvino"
    assert s.cache_dir == BASE_DIR / "models" / "cache"
    assert s.default_model is None
    assert s.api_key is None
    assert s.force_mock is False


def test_from_env_parses_overrides(clean_env):
    clean_env.setenv("OV_LLM_HOST", "0.0.0.0")
    clean_env.setenv("OV_LLM_PORT", "9001")
    clean_env.setenv("OV_LLM_DEVICE", "npu")  # lower-cased input
    clean_env.setenv("OV_LLM_CACHE_DIR", "custom_cache")
    clean_env.setenv("OV_LLM_MODEL", "  tinyllama-1.1b-chat-fp16  ")  # trimmed
    clean_env.setenv("OV_LLM_API_KEY", " sk-secret ")
    clean_env.setenv("OV_LLM_MOCK", "yes")

    s = Settings.from_env()
    assert s.host == "0.0.0.0"
    assert s.port == 9001
    assert s.device == "NPU"
    assert s.cache_dir == BASE_DIR / "custom_cache"
    assert s.default_model == "tinyllama-1.1b-chat-fp16"
    assert s.api_key == "sk-secret"
    assert s.force_mock is True


def test_from_env_blank_optional_values_become_none(clean_env):
    clean_env.setenv("OV_LLM_MODEL", "   ")
    clean_env.setenv("OV_LLM_API_KEY", "")
    s = Settings.from_env()
    assert s.default_model is None
    assert s.api_key is None


def test_resolve_relative_against_base_dir():
    assert _resolve("models.json") == BASE_DIR / "models.json"


def test_resolve_absolute_kept_as_is(tmp_path):
    abs_path = tmp_path / "elsewhere.json"
    assert _resolve(str(abs_path)) == Path(str(abs_path))


def test_bool_env_truthy_and_falsy(monkeypatch):
    for truthy in ("1", "true", "YES", "On"):
        monkeypatch.setenv("FLAG", truthy)
        assert _bool_env("FLAG") is True
    for falsy in ("0", "false", "no", "", "maybe"):
        monkeypatch.setenv("FLAG", falsy)
        assert _bool_env("FLAG") is False


def test_replace_drops_none_and_applies_overrides(clean_env):
    s = Settings.from_env()
    out = s.replace(port=1234, device=None, force_mock=True)
    assert out.port == 1234
    assert out.device == s.device  # None ignored
    assert out.force_mock is True
    assert s.port == 8000  # original is frozen / unchanged
