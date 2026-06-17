"""Model catalog: loading and validating ``models.json`` plus building the
UI-facing status entries.

This module is intentionally free of any OpenVINO dependency. It only describes
which models exist, where their OpenVINO IR directories live on disk, and how to
present their current state to the web UI / API. Live runtime state (which
engine is loaded on which device) is owned by :mod:`app.model_manager`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("ov-llm.registry")

# Files that indicate a directory holds a converted OpenVINO IR model.
_IR_MARKERS = ("openvino_model.xml", "openvino_language_model.xml", "config.json")

_STATUS_LABELS = {
    "loaded": "Loaded",
    "queued": "Queued…",
    "loading": "Loading…",
    "queued_convert": "Queued conversion…",
    "converting": "Converting…",
    "ready_to_load": "Ready to load",
    "not_downloaded": "Not converted",
    "error": "Load failed",
}


@dataclass(frozen=True)
class ModelConfig:
    """A single entry from ``models.json`` with resolved, validated fields."""

    id: str
    name: str
    description: str
    backend: str
    model_path: str
    source_model: str
    weight_format: str
    recommended_device: str
    max_context_len: int
    max_output_tokens: int

    @property
    def max_prompt_len(self) -> int:
        """Token budget for the prompt, reserving room for the response."""
        return max(self.max_context_len - self.max_output_tokens, 64)

    def abs_path(self, base_dir: Path) -> Path:
        """Absolute path to the model's OpenVINO IR directory."""
        p = Path(self.model_path)
        return p if p.is_absolute() else (base_dir / p)


def _coerce_entry(model_id: str, raw: dict) -> ModelConfig:
    return ModelConfig(
        id=model_id,
        name=raw.get("name", model_id),
        description=raw.get("description", ""),
        backend=raw.get("backend", "openvino-genai"),
        model_path=raw.get("model_path", f"models/openvino/{model_id}"),
        source_model=raw.get("source_model", ""),
        weight_format=raw.get("weight_format", "int4"),
        recommended_device=raw.get("recommended_device", "NPU"),
        max_context_len=int(raw.get("max_context_len", 2048)),
        max_output_tokens=int(raw.get("max_output_tokens", 512)),
    )


def load_catalog(models_file: Path) -> dict[str, ModelConfig]:
    """Load and validate the model catalog. Returns ``{}`` on a missing/invalid file."""
    path = Path(models_file)
    if not path.exists():
        logger.warning("Model catalog not found: %s", path)
        return {}

    try:
        # utf-8-sig tolerates a UTF-8 BOM (a common Windows editor artifact).
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read model catalog %s: %s", path, exc)
        return {}

    if not isinstance(data, dict):
        logger.error("Model catalog %s must be a JSON object of {id: config}", path)
        return {}

    catalog: dict[str, ModelConfig] = {}
    for model_id, raw in data.items():
        if not isinstance(raw, dict):
            logger.warning("Skipping malformed catalog entry %r (not an object)", model_id)
            continue
        try:
            catalog[model_id] = _coerce_entry(model_id, raw)
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping invalid catalog entry %r: %s", model_id, exc)
    return catalog


def is_downloaded(cfg: ModelConfig, base_dir: Path) -> bool:
    """True if a converted OpenVINO IR directory exists for this model."""
    model_dir = cfg.abs_path(base_dir)
    if not model_dir.is_dir():
        return False
    return any((model_dir / marker).exists() for marker in _IR_MARKERS)


def status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, "Unknown")


def make_catalog_entry(
    cfg: ModelConfig,
    *,
    loaded: bool,
    queued: bool,
    loading: bool,
    downloaded: bool,
    converting: bool = False,
    device: str | None = None,
    busy: bool = False,
    error: str | None = None,
) -> dict:
    """Build a single UI/API-facing status entry for a model."""
    if loaded:
        status = "loaded"
    elif error:
        status = "error"
    elif converting:
        status = "converting"
    elif queued:
        status = "queued"
    elif loading:
        status = "loading"
    elif downloaded:
        status = "ready_to_load"
    else:
        status = "not_downloaded"

    is_busy_state = status in {"queued", "loading", "queued_convert", "converting"}
    label = "Conversion failed" if status == "error" and not downloaded else status_label(status)
    return {
        "id": cfg.id,
        "name": cfg.name,
        "description": cfg.description,
        "status": status,
        "status_label": label,
        "is_loaded": loaded,
        "is_loading": is_busy_state,
        "is_downloaded": downloaded,
        "device": device,
        "recommended_device": cfg.recommended_device,
        "weight_format": cfg.weight_format,
        "source_model": cfg.source_model,
        "max_context_len": cfg.max_context_len,
        "max_output_tokens": cfg.max_output_tokens,
        "can_load": (not loaded) and downloaded and not is_busy_state,
        "can_convert": (not loaded) and (not downloaded) and bool(cfg.source_model) and not is_busy_state,
        "can_unload": loaded and not busy,
        "can_delete": (not loaded) and downloaded and not is_busy_state,
        "error": error,
    }
