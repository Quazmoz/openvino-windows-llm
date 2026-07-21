"""Server configuration resolved from environment variables (and CLI overrides).

All paths are resolved relative to the repository root so the server behaves the
same regardless of the working directory it is launched from.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from app.chat_context_ui import install_chat_context_extension
from app.chat_guard_ui import install_chat_guard_extension
from app.chat_queue_ui import install_chat_queue_extension
from app.progress_dock import install_progress_dock_extension
from app.progress_semantics import install_progress_semantics_extension
from app.progress_ui import install_progress_ui_extension
from app.ui_polish import install_ui_polish_extension
from runtime.device_check import normalize_device
from runtime.npu_compat import install_openvino_genai_compat

# Install compatibility and UI composition before app.model_manager/app.server
# bind their imported engine and browser-injection functions.
install_openvino_genai_compat()
install_progress_ui_extension()
install_progress_dock_extension()
install_progress_semantics_extension()
install_chat_context_extension()
install_chat_queue_extension()
install_chat_guard_extension()
install_ui_polish_extension()

logger = logging.getLogger("ov-llm.config")

# Repository root: .../openvino-windows-llm  (parent of the app/ package).
BASE_DIR = Path(__file__).resolve().parent.parent

VALID_DEVICES = ("CPU", "GPU", "NPU", "AUTO")  # Simple UI/default choices; parser accepts more.

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
    benchmark_results_file: Path = BASE_DIR / "benchmark" / "results" / "benchmarks.json"
    default_model: str | None = None
    api_key: str | None = None
    force_mock: bool = False
    auto_convert: bool = False
    cors_origins: str = ""
    rate_limit: int = 0  # requests per minute per IP; 0 = disabled
    max_request_body_mb: int = 40

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=os.environ.get("OV_LLM_HOST", "127.0.0.1"),
            port=int(os.environ.get("OV_LLM_PORT", "8000")),
            device=normalize_device(os.environ.get("OV_LLM_DEVICE", "NPU")),
            models_file=_resolve(os.environ.get("OV_LLM_MODELS_FILE", "models.json")),
            models_dir=_resolve(os.environ.get("OV_LLM_MODELS_DIR", "models/openvino")),
            cache_dir=_resolve(os.environ.get("OV_LLM_CACHE_DIR", "models/cache")),
            benchmark_results_file=_resolve(
                os.environ.get("OV_LLM_BENCHMARK_RESULTS", "benchmark/results/benchmarks.json")
            ),
            default_model=(os.environ.get("OV_LLM_MODEL") or "").strip() or None,
            api_key=(os.environ.get("OV_LLM_API_KEY") or "").strip() or None,
            force_mock=_bool_env("OV_LLM_MOCK"),
            auto_convert=_bool_env("OV_LLM_AUTO_CONVERT"),
            cors_origins=os.environ.get("OV_LLM_CORS_ORIGINS", ""),
            rate_limit=int(os.environ.get("OV_LLM_RATE_LIMIT", "0")),
            max_request_body_mb=int(os.environ.get("OV_LLM_MAX_REQUEST_BODY_MB", "40")),
        )

    def replace(self, **changes) -> Settings:
        """Return a copy with the given fields overridden (drops None values)."""
        clean = {k: v for k, v in changes.items() if v is not None}
        return dataclasses.replace(self, **clean)

    def validate(self, catalog: dict | None = None) -> list[str]:
        """Check for common misconfigurations. Returns a list of warning strings."""
        warnings: list[str] = []

        if not self.models_file.exists():
            warnings.append(f"Models catalog not found at {self.models_file}")

        if self.port < 1 or self.port > 65535:
            warnings.append(f"Port {self.port} is out of the valid range (1-65535)")

        if self.default_model and catalog is not None:
            if self.default_model not in catalog:
                warnings.append(
                    f"Default model '{self.default_model}' is not in the catalog. "
                    f"Available: {', '.join(catalog) or '(none)'}"
                )

        if self.rate_limit < 0:
            warnings.append(f"Rate limit {self.rate_limit} is negative; treating as disabled (0)")

        if self.max_request_body_mb < 1:
            warnings.append(
                f"Request body limit {self.max_request_body_mb} MiB is invalid; use at least 1 MiB"
            )

        origins = {origin.strip() for origin in self.cors_origins.split(",") if origin.strip()}
        if "*" in origins and not self.api_key:
            warnings.append(
                "Wildcard CORS allows arbitrary websites to call the local API. Set explicit "
                "OV_LLM_CORS_ORIGINS values or configure OV_LLM_API_KEY."
            )

        if self.host.strip() in {"0.0.0.0", "::"} and not self.api_key:
            warnings.append(
                f"OV_LLM_HOST is set to {self.host!r}, which can expose the server beyond "
                "localhost, but OV_LLM_API_KEY is not set. Set OV_LLM_API_KEY before "
                "exposing the server beyond a trusted local machine/network."
            )

        for warning in warnings:
            logger.warning("Config: %s", warning)
        return warnings
