"""Curated, evidence-aware model library and import/export services.

The library intentionally separates maintained recommendations from the mutable
runtime model catalog. Official metadata is accepted only from the project's
fixed GitHub release asset and only after its canonical catalog checksum passes.
The bundled manifest remains the offline fallback.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import secrets
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, field_validator

from app import __version__
from app import model_registry as registry
from app.openai_api import ModelRegisterRequest
from app.paths import packaged_resource_root
from runtime import device_check

MANIFEST_SCHEMA_VERSION = 1
CONVERSION_SCHEMA_VERSION = 1
OFFICIAL_MANIFEST_URL = (
    "https://github.com/Quazmoz/openvino-windows-llm/"
    "releases/latest/download/model-library-manifest.json"
)
MAX_MANIFEST_BYTES = 1_000_000
MAX_IMPORTED_DEFINITIONS = 50
_ALLOWED_RELEASE_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_ALLOWED_PROFILES = {"fastest", "balanced", "best_quality", "lowest_memory"}
_ALLOWED_DEVICES = ("CPU", "GPU", "NPU")


class ModelDefinitionImportRequest(BaseModel):
    payload: dict[str, Any]
    overwrite: bool = False


class ConvertedModelImportRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=128, pattern=_MODEL_ID_RE.pattern)
    name: str = Field(min_length=1, max_length=160)
    source_path: str = Field(min_length=1, max_length=1024)
    source_model: str = Field(default="", max_length=240)
    description: str = Field(default="Imported converted OpenVINO model.", max_length=2000)
    backend: str = Field(
        default="openvino-genai",
        pattern=r"^(openvino-genai|openvino-embeddings|openvino-vlm)$",
    )
    weight_format: str = Field(default="fp16", pattern=r"^(int4|int8|fp16)$")
    recommended_device: str = Field(default="CPU", min_length=1, max_length=64)
    max_context_len: int = Field(default=2048, ge=128, le=262144)
    max_output_tokens: int = Field(default=512, ge=0, le=65536)
    overwrite: bool = False

    @field_validator("recommended_device")
    @classmethod
    def validate_device(cls, value: str) -> str:
        return device_check.validate_device_expression(value)


class ManifestValidationError(ValueError):
    """Raised when a remote or cached model-library manifest is invalid."""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def catalog_checksum(catalog: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(catalog)).hexdigest()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _optional_nonnegative_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return max(float(value), 0.0)
    except (TypeError, ValueError, OverflowError):
        return None


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return max(int(value), 0)
    except (TypeError, ValueError, OverflowError):
        return None


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _major_minor(version: str | None) -> tuple[int, int] | None:
    if not version:
        return None
    match = re.match(r"^(\d+)\.(\d+)", version)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _normalize_certifications(raw: Any) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {device: [] for device in _ALLOWED_DEVICES}
    if not isinstance(raw, dict):
        return output
    for device in _ALLOWED_DEVICES:
        records = raw.get(device)
        if not isinstance(records, list):
            continue
        for record in records[:20]:
            if not isinstance(record, dict) or record.get("status") != "verified":
                continue
            certified_at = str(record.get("certified_at") or "")[:32]
            openvino_version = str(record.get("openvino_version") or "")[:64]
            driver_version = str(record.get("driver_version") or "")[:128]
            if not certified_at or not openvino_version:
                continue
            output[device].append(
                {
                    "status": "verified",
                    "certified_at": certified_at,
                    "openvino_version": openvino_version,
                    "openvino_genai_version": str(
                        record.get("openvino_genai_version") or ""
                    )[:64],
                    "driver_version": driver_version,
                    "load_time_ms": _optional_nonnegative_float(record.get("load_time_ms")),
                    "tokens_sec": _optional_nonnegative_float(record.get("tokens_sec")),
                    "time_to_first_token_ms": _optional_nonnegative_float(
                        record.get("time_to_first_token_ms")
                    ),
                    "max_tested_context": _optional_nonnegative_int(
                        record.get("max_tested_context")
                    ),
                    "evidence_url": str(record.get("evidence_url") or "")[:500],
                }
            )
        output[device].sort(key=lambda item: item["certified_at"])
    return output


def validate_manifest_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ManifestValidationError("Model library manifest must be a JSON object.")
    if document.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ManifestValidationError("Unsupported model library manifest schema.")
    catalog = document.get("catalog")
    if not isinstance(catalog, dict) or not catalog or len(catalog) > MAX_IMPORTED_DEFINITIONS:
        raise ManifestValidationError("Manifest catalog must contain between 1 and 50 models.")
    expected = str(document.get("catalog_sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ManifestValidationError("Manifest catalog checksum is missing or malformed.")
    actual = catalog_checksum(catalog)
    if not secrets.compare_digest(actual, expected):
        raise ManifestValidationError("Manifest catalog checksum verification failed.")

    normalized: dict[str, Any] = {}
    for model_id, raw in catalog.items():
        if not isinstance(model_id, str) or not _MODEL_ID_RE.fullmatch(model_id):
            raise ManifestValidationError(f"Unsafe model id in manifest: {model_id!r}.")
        if not isinstance(raw, dict):
            raise ManifestValidationError(f"Manifest entry '{model_id}' must be an object.")
        definition_raw = dict(raw.get("definition") or {})
        definition_raw["model_id"] = model_id
        try:
            definition = ModelRegisterRequest.model_validate(definition_raw)
        except Exception as exc:
            raise ManifestValidationError(f"Manifest definition for '{model_id}' is invalid.") from exc
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        profiles = [
            value
            for value in metadata.get("profiles", [])
            if isinstance(value, str) and value in _ALLOWED_PROFILES
        ]
        max_tested_context = min(
            max(_safe_int(metadata.get("max_tested_context")), 0),
            definition.max_context_len,
        )
        normalized[model_id] = {
            "definition": definition.model_dump(),
            "metadata": {
                "curated": bool(metadata.get("curated", True)),
                "profiles": list(dict.fromkeys(profiles)),
                "minimum_ram_gb": max(_safe_float(metadata.get("minimum_ram_gb")), 0.0),
                "minimum_disk_gb": max(_safe_float(metadata.get("minimum_disk_gb")), 0.0),
                "license": str(metadata.get("license") or "Unknown")[:120],
                "gated": bool(metadata.get("gated", False)),
                "quality_score": min(max(_safe_float(metadata.get("quality_score")), 0.0), 100.0),
                "speed_score": min(max(_safe_float(metadata.get("speed_score")), 0.0), 100.0),
                "max_tested_context": max_tested_context,
                "maintainer_note": str(metadata.get("maintainer_note") or "")[:500],
                "certifications": _normalize_certifications(metadata.get("certifications")),
            },
        }
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": str(document.get("generated_at") or "")[:40],
        "source": str(document.get("source") or "")[:200],
        "catalog": normalized,
        "catalog_sha256": catalog_checksum(normalized),
    }


def parse_manifest_bytes(payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ManifestValidationError("Model library manifest exceeds the 1 MB limit.")
    try:
        document = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestValidationError("Model library manifest is not valid UTF-8 JSON.") from exc
    return validate_manifest_document(document)


def _definition_to_config(definition: dict[str, Any], model_path: Path) -> registry.ModelConfig:
    request = ModelRegisterRequest.model_validate(definition)
    return registry.ModelConfig(
        id=request.model_id,
        name=request.name,
        description=request.description or "",
        backend=request.backend,
        model_path=str(model_path.resolve()),
        source_model=request.source_model,
        weight_format=request.weight_format,
        recommended_device=request.recommended_device,
        max_context_len=request.max_context_len,
        max_output_tokens=request.max_output_tokens,
        trust_remote_code=request.trust_remote_code,
    )


def model_definition(cfg: registry.ModelConfig) -> dict[str, Any]:
    return {
        "model_id": cfg.id,
        "name": cfg.name,
        "description": cfg.description,
        "source_model": cfg.source_model,
        "backend": cfg.backend,
        "weight_format": cfg.weight_format,
        "recommended_device": cfg.recommended_device,
        "max_context_len": cfg.max_context_len,
        "max_output_tokens": cfg.max_output_tokens,
        "trust_remote_code": cfg.trust_remote_code,
    }


def _conversion_marker_path(cfg: registry.ModelConfig) -> Path:
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
        "openvino_version": _package_version("openvino"),
        "openvino_genai_version": _package_version("openvino-genai"),
        "recorded_at": _utc_now(),
    }
    temp = _conversion_marker_path(cfg).with_suffix(".json.tmp")
    temp.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    temp.replace(_conversion_marker_path(cfg))


def _invalid_conversion_metadata(details: str) -> dict[str, Any]:
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
    marker_path = _conversion_marker_path(cfg)
    if not marker_path.is_file():
        return {
            "status": "legacy_untracked",
            "label": "Converted, compatibility unknown",
            "details": "This conversion predates compatibility metadata. Reconvert or validate it locally.",
        }
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _invalid_conversion_metadata(
            "The OpenVINO IR exists but its compatibility marker is unreadable."
        )
    if not isinstance(marker, dict):
        return _invalid_conversion_metadata(
            "The OpenVINO IR exists but its compatibility marker is not a JSON object."
        )
    if marker.get("schema_version") != CONVERSION_SCHEMA_VERSION:
        return _invalid_conversion_metadata(
            "The conversion compatibility marker uses an unsupported schema."
        )
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
        return _invalid_conversion_metadata(
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
        current_version = _package_version(package_name)
        recorded_runtime = _major_minor(recorded_version)
        current_runtime = _major_minor(current_version)
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


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return path.is_symlink()
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _directory_size_bytes(path: Path) -> int:
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        root_path = Path(root)
        if _is_reparse_point(root_path):
            raise ValueError(
                "Imported model directories may not contain symbolic links or junctions."
            )
        for name in dirs:
            if _is_reparse_point(root_path / name):
                raise ValueError(
                    "Imported model directories may not contain symbolic links or junctions."
                )
        for name in files:
            candidate = root_path / name
            if _is_reparse_point(candidate):
                raise ValueError(
                    "Imported model directories may not contain symbolic links or junctions."
                )
            total += candidate.stat().st_size
    return total


class ModelLibraryService:
    def __init__(self, settings: Any, manager: Any) -> None:
        self.settings = settings
        self.manager = manager
        self.cache_file = Path(settings.models_file).parent / "model-library-manifest.json"
        self.user_file = Path(settings.models_file).parent / "model-library-user.json"
        self.bundled_file = packaged_resource_root() / "model_library_manifest.json"

    def _read_manifest(self) -> tuple[dict[str, Any], str]:
        for path, source in ((self.cache_file, "official-cache"), (self.bundled_file, "bundled")):
            try:
                return parse_manifest_bytes(path.read_bytes()), source
            except (OSError, ManifestValidationError):
                continue
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": "",
            "source": "empty-fallback",
            "catalog": {},
            "catalog_sha256": catalog_checksum({}),
        }, "empty-fallback"

    def _read_user_ids(self) -> set[str]:
        try:
            data = json.loads(self.user_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        values = data.get("model_ids") if isinstance(data, dict) else []
        return {value for value in values if isinstance(value, str) and _MODEL_ID_RE.fullmatch(value)}

    def _write_user_ids(self, values: set[str]) -> None:
        self.user_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.user_file.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(
                {"schema_version": 1, "model_ids": sorted(values), "updated_at": _utc_now()},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temp.replace(self.user_file)

    async def refresh_official(self) -> dict[str, Any]:
        source_url = OFFICIAL_MANIFEST_URL
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            async with client.stream(
                "GET",
                OFFICIAL_MANIFEST_URL,
                headers={
                    "Accept": "application/json",
                    "User-Agent": f"OpenVINO-Windows-LLM/{__version__}",
                },
            ) as response:
                response.raise_for_status()
                source_url = str(response.url)
                host = (urlparse(source_url).hostname or "").lower()
                if host not in _ALLOWED_RELEASE_HOSTS:
                    raise ManifestValidationError(
                        "Official manifest redirected to an untrusted host."
                    )
                content_length = response.headers.get("Content-Length")
                try:
                    declared_length = int(content_length) if content_length else None
                except (TypeError, ValueError):
                    declared_length = None
                if declared_length is not None and declared_length > MAX_MANIFEST_BYTES:
                    raise ManifestValidationError(
                        "Model library manifest exceeds the 1 MB limit."
                    )
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > MAX_MANIFEST_BYTES:
                        raise ManifestValidationError(
                            "Model library manifest exceeds the 1 MB limit."
                        )
                manifest = parse_manifest_bytes(bytes(payload))

        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.cache_file.with_suffix(".json.tmp")
        temp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        try:
            merge = self.apply_official_definitions(manifest)
            temp.replace(self.cache_file)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        return {"source": source_url, "manifest": manifest, **merge}

    def apply_official_definitions(self, manifest: dict[str, Any]) -> dict[str, Any]:
        added: list[str] = []
        updated: list[str] = []
        conflicts: list[str] = []
        user_ids = self._read_user_ids()
        staged_catalog = dict(self.manager.catalog)
        for model_id, entry in manifest.get("catalog", {}).items():
            definition = entry["definition"]
            existing = staged_catalog.get(model_id)
            target = Path(self.settings.models_dir) / model_id
            cfg = _definition_to_config(definition, target)
            if existing is not None:
                if model_definition(existing) == model_definition(cfg):
                    continue
                if model_id in user_ids or (
                    existing.source_model and existing.source_model != definition["source_model"]
                ):
                    conflicts.append(model_id)
                    continue
                updated.append(model_id)
            else:
                added.append(model_id)
            staged_catalog[model_id] = cfg
        if added or updated:
            registry.save_catalog(self.settings.models_file, staged_catalog)
            self.manager.reload_catalog()
        return {"added": added, "updated": updated, "conflicts": conflicts}

    def _local_evidence(self, model_id: str) -> dict[str, dict[str, Any]]:
        advisor = getattr(self.manager, "advisor", None)
        evidence: dict[str, dict[str, Any]] = {}
        if advisor is None:
            return evidence
        snapshot = advisor.hardware_snapshot()
        details = snapshot.get("devices", [])
        for device in _ALLOWED_DEVICES:
            row = advisor._latest_benchmark(model_id, device)
            if not row:
                continue
            device_info = next(
                (item for item in details if str(item.get("base") or "").upper() == device),
                {},
            )
            evidence[device] = {
                "status": "locally_verified",
                "actual_device": row.get("actual_device"),
                "openvino_version": snapshot.get("runtime", {}).get("openvino"),
                "driver_version": device_info.get("driver_version") or "Unavailable",
                "load_time_ms": row.get("load_time_ms"),
                "tokens_sec": row.get("tokens_sec"),
                "time_to_first_token_ms": row.get("time_to_first_token_ms"),
                "tested_at": row.get("created_at") or row.get("timestamp"),
            }
        return evidence

    def _verification(self, metadata: dict[str, Any], local: dict[str, Any]) -> dict[str, Any]:
        output = {}
        certifications = metadata.get("certifications", {})
        for device in _ALLOWED_DEVICES:
            official = list(certifications.get(device) or [])
            if official:
                latest = max(
                    official,
                    key=lambda record: str(record.get("certified_at") or ""),
                )
                output[device] = {"status": "verified", "label": f"Verified on {device}", **latest}
            elif device in local:
                output[device] = {
                    "status": "locally_verified",
                    "label": f"Verified on this PC ({device})",
                    **local[device],
                }
            else:
                output[device] = {
                    "status": "expected_unverified",
                    "label": f"Expected on {device}, unverified",
                }
        return output

    def _quantization(
        self,
        cfg: registry.ModelConfig,
        estimate: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> dict[str, str]:
        available = {
            str(value).split(".", 1)[0].upper() for value in snapshot.get("available_devices", [])
        }
        ram = _safe_float(snapshot.get("memory", {}).get("total_gb"))
        params = _safe_float(estimate.get("parameter_count_b"))
        preferred = str(cfg.recommended_device or "CPU").split(":", 1)[0].upper()
        target = preferred if preferred in available else ("GPU" if "GPU" in available else "CPU")
        if target == "NPU" and params <= 4.5:
            return {
                "format": "fp16",
                "device": target,
                "reason": "FP16 is the conservative compatibility choice for the maintained NPU set.",
            }
        if (ram and ram < 12) or params >= 3:
            return {
                "format": "int4",
                "device": target,
                "reason": "INT4 reduces memory and disk pressure for this model and hardware.",
            }
        if target == "GPU" and ram >= 24 and params <= 3:
            return {
                "format": "fp16",
                "device": target,
                "reason": "Available memory supports the higher-fidelity FP16 path.",
            }
        return {
            "format": "int8",
            "device": target,
            "reason": "INT8 is a balanced default when no stronger local evidence is available.",
        }

    def _entry(
        self, model_id: str, manifest_entry: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        cfg = self.manager.catalog.get(model_id)
        if cfg is None:
            return None
        runtime_entry = self.manager.catalog_entry(model_id)
        advisor = getattr(self.manager, "advisor", None)
        snapshot = (
            advisor.hardware_snapshot()
            if advisor
            else {"memory": {}, "disk": {}, "available_devices": []}
        )
        estimate = advisor.estimate_model(cfg) if advisor else {}
        metadata = dict((manifest_entry or {}).get("metadata") or {})
        local = self._local_evidence(model_id)
        verification = self._verification(metadata, local)
        measured = next(
            (
                local[device]
                for device in (
                    cfg.recommended_device.split(":", 1)[0],
                    "NPU",
                    "GPU",
                    "CPU",
                )
                if device in local
            ),
            {},
        )
        official_records = [
            record
            for records in metadata.get("certifications", {}).values()
            for record in records
        ]
        latest_official = max(
            official_records,
            key=lambda record: str(record.get("certified_at") or ""),
            default={},
        )
        local_measurement = any(
            measured.get(field) is not None
            for field in ("load_time_ms", "tokens_sec", "time_to_first_token_ms")
        )

        def metric(field: str) -> Any:
            value = measured.get(field)
            return value if value is not None else latest_official.get(field)

        maximum_tested_context = latest_official.get("max_tested_context")
        if maximum_tested_context is None:
            maximum_tested_context = metadata.get("max_tested_context") or None
        min_ram = _safe_float(metadata.get("minimum_ram_gb"))
        min_disk = _safe_float(metadata.get("minimum_disk_gb"))
        available_ram = _safe_float(snapshot.get("memory", {}).get("available_gb"))
        free_disk = _safe_float(snapshot.get("disk", {}).get("free_gb"))
        profiles = list(metadata.get("profiles") or [])
        return {
            "id": model_id,
            "name": cfg.name,
            "description": cfg.description,
            "source_model": cfg.source_model,
            "backend": cfg.backend,
            "weight_format": cfg.weight_format,
            "recommended_device": cfg.recommended_device,
            "max_context_len": cfg.max_context_len,
            "runtime": runtime_entry,
            "conversion_health": conversion_health(cfg),
            "requirements": {
                "minimum_ram_gb": min_ram or estimate.get("runtime_memory_gb"),
                "minimum_disk_gb": min_disk or estimate.get("converted_size_gb"),
                "available_ram_gb": available_ram,
                "free_disk_gb": free_disk,
                "ram_ok": not min_ram or available_ram >= min_ram,
                "disk_ok": not min_disk or free_disk >= min_disk,
            },
            "estimate": estimate,
            "license": metadata.get("license") or "Unknown",
            "gated": bool(metadata.get("gated")),
            "verification": verification,
            "metrics": {
                "time_to_first_load_ms": metric("load_time_ms"),
                "tokens_sec": metric("tokens_sec"),
                "time_to_first_token_ms": metric("time_to_first_token_ms"),
                "maximum_tested_context": maximum_tested_context,
                "tested_openvino_version": (
                    measured.get("openvino_version")
                    if local_measurement
                    else latest_official.get("openvino_version")
                ),
                "tested_driver_version": (
                    measured.get("driver_version")
                    if local_measurement
                    else latest_official.get("driver_version")
                ),
                "last_certification_date": latest_official.get("certified_at") or None,
                "measurement_source": (
                    "local" if local_measurement else "official" if latest_official else None
                ),
            },
            "profiles": profiles,
            "quality_score": _safe_float(metadata.get("quality_score")),
            "speed_score": _safe_float(metadata.get("speed_score")),
            "maintainer_note": metadata.get("maintainer_note") or "",
            "recommended_quantization": self._quantization(cfg, estimate, snapshot),
            "curated": bool(metadata.get("curated", False)),
        }

    def snapshot(
        self,
        *,
        profile: str = "balanced",
        query: str = "",
        include_all: bool = False,
    ) -> dict[str, Any]:
        if profile not in _ALLOWED_PROFILES:
            raise ValueError(f"Unknown model-library profile '{profile}'.")
        manifest, source = self._read_manifest()
        curated = manifest.get("catalog", {})
        selected_ids = set(curated)
        selected_ids.update(self._read_user_ids())
        if include_all:
            selected_ids.update(self.manager.catalog)
        items = [
            entry
            for model_id in selected_ids
            if (entry := self._entry(model_id, curated.get(model_id))) is not None
        ]
        needle = query.strip().lower()
        if needle:
            items = [
                item
                for item in items
                if needle
                in " ".join(
                    [item["id"], item["name"], item["description"], item["source_model"]]
                ).lower()
            ]
        if not include_all:
            profiled = [
                item
                for item in items
                if profile in item.get("profiles", []) or not item.get("curated")
            ]
            if profiled:
                items = profiled

        if profile == "fastest":
            items.sort(
                key=lambda item: (
                    -_safe_float(item["metrics"].get("tokens_sec")),
                    -item["speed_score"],
                    _safe_float(item["estimate"].get("runtime_memory_gb"), 9999),
                    item["id"],
                )
            )
        elif profile == "best_quality":
            items.sort(
                key=lambda item: (-item["quality_score"], -item["max_context_len"], item["id"])
            )
        elif profile == "lowest_memory":
            items.sort(
                key=lambda item: (
                    _safe_float(item["estimate"].get("runtime_memory_gb"), 9999),
                    -item["quality_score"],
                    item["id"],
                )
            )
        else:
            items.sort(
                key=lambda item: (
                    -(item["quality_score"] * 0.55 + item["speed_score"] * 0.45),
                    _safe_float(item["estimate"].get("runtime_memory_gb"), 9999),
                    item["id"],
                )
            )
        return {
            "schema_version": 1,
            "profile": profile,
            "manifest": {
                "source": source,
                "generated_at": manifest.get("generated_at"),
                "catalog_sha256": manifest.get("catalog_sha256"),
                "official_url": OFFICIAL_MANIFEST_URL,
            },
            "profiles": ["fastest", "balanced", "best_quality", "lowest_memory"],
            "items": items,
            "count": len(items),
            "include_all": include_all,
            "caveat": (
                "Bundled recommendations are expected-but-unverified until a retained certification "
                "record or local benchmark provides evidence for a specific model and device."
            ),
        }

    def export_definitions(self, *, include_all: bool = False) -> dict[str, Any]:
        manifest, _ = self._read_manifest()
        ids = set(manifest.get("catalog", {})) | self._read_user_ids()
        if include_all:
            ids.update(self.manager.catalog)
        models = {
            model_id: model_definition(self.manager.catalog[model_id])
            for model_id in sorted(ids)
            if model_id in self.manager.catalog
        }
        return {
            "schema_version": 1,
            "application": "OpenVINO Windows LLM",
            "exported_at": _utc_now(),
            "models": models,
        }

    def import_definitions(self, request: ModelDefinitionImportRequest) -> dict[str, Any]:
        payload = request.payload
        raw_models = payload.get("models") if isinstance(payload.get("models"), dict) else payload
        if (
            not isinstance(raw_models, dict)
            or not raw_models
            or len(raw_models) > MAX_IMPORTED_DEFINITIONS
        ):
            raise ValueError("Definition import must contain between 1 and 50 models.")
        added: list[str] = []
        updated: list[str] = []
        unchanged: list[str] = []
        seen_ids: set[str] = set()
        staged_catalog = dict(self.manager.catalog)
        for key, raw in raw_models.items():
            if not isinstance(raw, dict):
                raise ValueError(f"Definition '{key}' must be an object.")
            definition = dict(raw)
            definition.setdefault("model_id", key)
            parsed = ModelRegisterRequest.model_validate(definition)
            if parsed.model_id in seen_ids:
                raise ValueError(f"Definition import contains duplicate model id '{parsed.model_id}'.")
            seen_ids.add(parsed.model_id)
            existing = staged_catalog.get(parsed.model_id)
            target = Path(self.settings.models_dir) / parsed.model_id
            candidate = _definition_to_config(parsed.model_dump(), target)
            if existing is not None:
                if model_definition(existing) == model_definition(candidate):
                    unchanged.append(parsed.model_id)
                    continue
                if not request.overwrite:
                    raise ValueError(
                        f"Model '{parsed.model_id}' already exists with a different definition."
                    )
                updated.append(parsed.model_id)
            else:
                added.append(parsed.model_id)
            staged_catalog[parsed.model_id] = candidate
        if added or updated:
            registry.save_catalog(self.settings.models_file, staged_catalog)
            self.manager.reload_catalog()
        user_ids = self._read_user_ids()
        user_ids.update(added)
        user_ids.update(updated)
        user_ids.update(unchanged)
        self._write_user_ids(user_ids)
        return {"added": added, "updated": updated, "unchanged": unchanged}

    def import_converted(self, request: ConvertedModelImportRequest) -> dict[str, Any]:
        if request.overwrite:
            raise ValueError(
                "Converted-model replacement is intentionally disabled. Import with a new model ID."
            )
        source_input = Path(request.source_path).expanduser()
        if not source_input.is_absolute():
            raise ValueError("Converted model source_path must be absolute.")
        if _is_reparse_point(source_input):
            raise ValueError(
                "Imported model directories may not be symbolic links or junctions."
            )
        source = source_input.resolve()
        if not source.is_dir() or not registry.is_openvino_model_dir(source):
            raise ValueError("source_path is not a converted OpenVINO model directory.")
        size_bytes = _directory_size_bytes(source)
        models_root = Path(self.settings.models_dir)
        models_root.mkdir(parents=True, exist_ok=True)
        models_root = models_root.resolve()
        target = (models_root / request.model_id).resolve()
        if target.parent != models_root:
            raise ValueError("Imported model target escaped the managed model directory.")
        if request.model_id in self.manager.catalog:
            raise ValueError(f"Model ID '{request.model_id}' is already registered.")
        if target.exists() or source == target:
            raise ValueError(f"Managed model directory already exists for '{request.model_id}'.")
        free_bytes = shutil.disk_usage(models_root).free
        if free_bytes < size_bytes + 256 * 1024 * 1024:
            raise ValueError("Not enough free disk space to import this converted model safely.")

        temp = models_root / f".{request.model_id}.import-{secrets.token_hex(6)}"
        previous_user_ids = self._read_user_ids()
        user_file_existed = self.user_file.exists()
        try:
            shutil.copytree(source, temp, symlinks=False)
            if not registry.is_openvino_model_dir(temp):
                raise ValueError("Copied model failed OpenVINO IR validation.")
            temp.replace(target)
            definition = {
                "model_id": request.model_id,
                "name": request.name,
                "description": request.description,
                "source_model": request.source_model or f"local-openvino:{source.name}",
                "backend": request.backend,
                "weight_format": request.weight_format,
                "recommended_device": request.recommended_device,
                "max_context_len": request.max_context_len,
                "max_output_tokens": request.max_output_tokens,
                "trust_remote_code": False,
            }
            cfg = _definition_to_config(definition, target)
            record_conversion_metadata(cfg, self.settings)
            user_ids = set(previous_user_ids)
            user_ids.add(request.model_id)
            self._write_user_ids(user_ids)
            staged_catalog = dict(self.manager.catalog)
            staged_catalog[request.model_id] = cfg
            registry.save_catalog(self.settings.models_file, staged_catalog)
            self.manager.reload_catalog()
        except Exception:
            shutil.rmtree(temp, ignore_errors=True)
            shutil.rmtree(target, ignore_errors=True)
            try:
                if user_file_existed:
                    self._write_user_ids(previous_user_ids)
                else:
                    self.user_file.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return {
            "model_id": request.model_id,
            "target_path": str(target),
            "size_bytes": size_bytes,
            "conversion_health": conversion_health(cfg),
        }
