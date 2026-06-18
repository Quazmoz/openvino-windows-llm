"""Server configuration resolved from environment variables (and CLI overrides).

All paths are resolved relative to the repository root so the server behaves the
same regardless of the working directory it is launched from.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from pathlib import Path

# Repository root: .../openvino-windows-llm  (parent of the app/ package).
BASE_DIR = Path(__file__).resolve().parent.parent

VALID_DEVICES = ("CPU", "GPU", "NPU", "AUTO")

_TRUTHY = {"1", "true", "yes", "on"}


def _resolve(path_str: str) -> Path:
    """Resolve a possibly-relative path against the repository root."""
    p = Path(path_str)
    return p if p.is_absolute() else (BASE_DIR / p)


def _bool_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings. Use :meth:`replace` to apply CLI overrides."""

    host: str = "127.0.0.1"
    port: int = 8000
    device: str = "NPU"
    models_file: Path = BASE_DIR / "models.json"
    models_dir: Path = BASE_DIR / "models" / "openvino"
    cache_dir: Path = BASE_DIR / "models" / "cache"
    default_model: str | None = None
    api_key: str | None = None
    force_mock: bool = False
    auto_convert: bool = False
    cors_origins: str = "*"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=os.environ.get("OV_LLM_HOST", "127.0.0.1"),
            port=int(os.environ.get("OV_LLM_PORT", "8000")),
            device=os.environ.get("OV_LLM_DEVICE", "NPU").upper(),
            models_file=_resolve(os.environ.get("OV_LLM_MODELS_FILE", "models.json")),
            models_dir=_resolve(os.environ.get("OV_LLM_MODELS_DIR", "models/openvino")),
            cache_dir=_resolve(os.environ.get("OV_LLM_CACHE_DIR", "models/cache")),
            default_model=(os.environ.get("OV_LLM_MODEL") or "").strip() or None,
            api_key=(os.environ.get("OV_LLM_API_KEY") or "").strip() or None,
            force_mock=_bool_env("OV_LLM_MOCK"),
            auto_convert=_bool_env("OV_LLM_AUTO_CONVERT"),
            cors_origins=os.environ.get("OV_LLM_CORS_ORIGINS", "*"),
        )

    def replace(self, **changes) -> Settings:
        """Return a copy with the given fields overridden (drops None values)."""
        clean = {k: v for k, v in changes.items() if v is not None}
        return dataclasses.replace(self, **clean)
