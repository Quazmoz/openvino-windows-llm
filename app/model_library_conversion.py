"""Compatibility metadata and safe filesystem inspection for converted models."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

from app import __version__, model_registry as registry
from app.model_library_schema import major_minor, package_version, utc_now
from app.paths import packaged_resource_root

CONVERSION_SCHEMA_VERSION = 1


def _runtime_package_version(name: str) -> str | None:
    public_module = sys.modules.get("app.model_library")
    resolver = getattr(public_module, "_package_version", package_version)
    return resolver(name)


def conversion_marker_path(cfg: registry.ModelConfig) -> Path:
    return cfg.abs_path(packaged_resource_root()) / ".ovllm-conversion.json"


def record_conversion_metadata(cfg: registry.ModelConfig, settings: Any) -> None:
    model_dir = cfg.abs_path(packaged_resource_root())
    if not registry.is_openvino_model_dir(model_dir):
        return
    marker = {
        "schema_version": CONVERSION_SCHEMA_VERSION,
        "model_id": cfg.id,
        "source_model": cfg.source_model,
        "backend": cfg.backend,
        "weight_format": cfg.weight_format,
        "application_version": __version__,
        "openvino_version": _runtime_package_version("openvino"),
        "openvino_genai_version": _runtime_package_version("openvino-genai"),
        "recorded_at": utc_now(),
    }
    temp = conversion_marker_path(cfg).with_suffix(".json.tmp")
    temp.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    temp.replace(conversion_marker_path(cfg))


def _invalid_metadata(details: str) -> dict[str, Any]:
    return {
        "status": "invalid_metadata",
        "label": "Conversion metadata damaged",
        "details": details,
    }


def conversion_health(cfg: registry.ModelConfig) -> dict[str, Any]:
    model_dir = cfg.abs_path(packaged_resource_root())
    if not model_dir.exists():
        return {"status": "not_converted", "label": "Not converted", "details": ""}
    if not registry.is_openvino_model_dir(model_dir):
        return {
            "status": "incomplete",
            "label": "Incomplete conversion",
            "details": "The directory exists but required OpenVINO IR files are missing.",
        }
    marker_path = conversion_marker_path(cfg)
    if not marker_path.is_file():
        return {
            "status": "legacy_untracked",
            "label": "Converted, compatibility unknown",
            "details": "This conversion predates compatibility metadata. Reconvert or validate it locally.",
        }
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _invalid_metadata(
            "The OpenVINO IR exists but its compatibility marker is unreadable."
        )
    if not isinstance(marker, dict):
        return _invalid_metadata(
            "The OpenVINO IR exists but its compatibility marker is not a JSON object."
        )
    if marker.get("schema_version") != CONVERSION_SCHEMA_VERSION:
        return _invalid_metadata("The conversion compatibility marker uses an unsupported schema.")
    required_fields = (
        "model_id",
        "source_model",
        "backend",
        "weight_format",
        "application_version",
        "openvino_version",
        "openvino_genai_version",
        "recorded_at",
    )
    missing = [field for field in required_fields if field not in marker]
    if missing:
        return _invalid_metadata(
            f"The conversion compatibility marker is missing: {', '.join(missing)}."
        )

    expected_fields = {
        "model_id": cfg.id,
        "source_model": cfg.source_model,
        "backend": cfg.backend,
        "weight_format": cfg.weight_format,
    }
    mismatches = [
        field
        for field, expected in expected_fields.items()
        if str(marker.get(field)) != str(expected)
    ]
    if mismatches:
        return {
            "status": "incompatible_definition",
            "label": "Definition changed",
            "details": f"Conversion metadata differs for: {', '.join(mismatches)}.",
        }

    runtime_changes = []
    for label, marker_field, package_name in (
        ("OpenVINO", "openvino_version", "openvino"),
        ("OpenVINO GenAI", "openvino_genai_version", "openvino-genai"),
    ):
        recorded_version = str(marker.get(marker_field) or "")
        current_version = _runtime_package_version(package_name)
        recorded_runtime = major_minor(recorded_version)
        current_runtime = major_minor(current_version)
        if recorded_runtime and current_runtime and recorded_runtime != current_runtime:
            runtime_changes.append(
                f"{label} {recorded_version or 'unknown'} to {current_version or 'unknown'}"
            )
    if runtime_changes:
        return {
            "status": "stale_runtime",
            "label": "Runtime changed",
            "details": (
                "Conversion runtime changed ("
                + "; ".join(runtime_changes)
                + "). Validate or reconvert before relying on it."
            ),
        }
    return {
        "status": "compatible",
        "label": "Conversion metadata matches",
        "details": (
            f"Recorded with OpenVINO {marker.get('openvino_version') or 'unknown'} and "
            f"OpenVINO GenAI {marker.get('openvino_genai_version') or 'unknown'}."
        ),
    }


def is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return path.is_symlink()
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def directory_size_bytes(path: Path) -> int:
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        root_path = Path(root)
        if is_reparse_point(root_path):
            raise ValueError(
                "Imported model directories may not contain symbolic links or junctions."
            )
        for name in dirs:
            if is_reparse_point(root_path / name):
                raise ValueError(
                    "Imported model directories may not contain symbolic links or junctions."
                )
        for name in files:
            candidate = root_path / name
            if is_reparse_point(candidate):
                raise ValueError(
                    "Imported model directories may not contain symbolic links or junctions."
                )
            total += candidate.stat().st_size
    return total
