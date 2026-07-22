"""Strict diagnostics allowlists, redaction, and bounded support-data helpers."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MAX_LOG_LINES = 300
MAX_LOG_BYTES = 256 * 1024
SECRET_KEY_RE = re.compile(
    r"(?:api[_-]?key|authorization|bearer|hf[_-]?token|access[_-]?token|secret|password|certificate|private[_-]?key)",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(?:hf_[A-Za-z0-9_=-]{8,}|Bearer\s+[A-Za-z0-9._~+/=-]+|(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+)",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
WINDOWS_USER_RE = re.compile(r"(?i)([A-Z]:\\Users\\)[^\\/\s]+")
POSIX_HOME_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users)/[^/\s]+")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SENSITIVE_CONTENT_LINE_RE = re.compile(
    r"(?:raw\s+request|request\s+body|prompt(?:_text)?\s*[:=]|chat\s+history|messages?\s*[:=]|source\s+image)",
    re.IGNORECASE,
)
NON_SECRET_OPERATIONAL_KEYS = {"api_key_configured"}


def diagnostics_confirmation_summary() -> str:
    return (
        "The diagnostics ZIP will include application, Windows, hardware, OpenVINO, "
        "device, model-state, benchmark, configuration, and sanitized operational-log "
        "information.\n\nPrompts, chat history, API keys, Hugging Face tokens, source images, "
        "model files, caches, certificates, and browser localStorage are excluded.\n\n"
        "The ZIP remains local until you choose to attach it to a support request."
    )


def safe_archive_name(name: str) -> str:
    raw = str(name).replace("\\", "/")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:/", raw):
        raise ValueError("Unsafe diagnostics archive path.")
    parts = [part for part in raw.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("Unsafe diagnostics archive path.")
    safe_parts = [re.sub(r"[^A-Za-z0-9_.-]", "_", part)[:120] for part in parts]
    if any(not part for part in safe_parts):
        raise ValueError("Unsafe diagnostics archive path.")
    return "/".join(safe_parts)


def sanitize_text(value: Any, *, redactions: set[str] | None = None, limit: int = 64 * 1024) -> str:
    text = CONTROL_RE.sub("", str(value or ""))
    replaced = SECRET_VALUE_RE.sub("[redacted-secret]", text)
    if replaced != text and redactions is not None:
        redactions.add("secret patterns")
    text = replaced
    replaced = EMAIL_RE.sub("[redacted-email]", text)
    if replaced != text and redactions is not None:
        redactions.add("email addresses")
    text = replaced
    replaced = WINDOWS_USER_RE.sub(r"\1<redacted-user>", text)
    if replaced != text and redactions is not None:
        redactions.add("Windows user directory names")
    text = replaced
    replaced = POSIX_HOME_RE.sub("/home/<redacted-user>", text)
    if replaced != text and redactions is not None:
        redactions.add("home directory names")
    return replaced[:limit]


def redact_path(path: Path | str, redactions: set[str] | None = None) -> str:
    return sanitize_text(str(path), redactions=redactions, limit=2048)


def sanitize_value(value: Any, *, redactions: set[str] | None = None) -> Any:
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            safe_key = sanitize_text(key, redactions=redactions, limit=120)
            if SECRET_KEY_RE.search(safe_key) and safe_key not in NON_SECRET_OPERATIONAL_KEYS:
                result[safe_key] = "[redacted-secret]"
                if redactions is not None:
                    redactions.add("secret fields")
                continue
            result[safe_key] = sanitize_value(item, redactions=redactions)
        return result
    if isinstance(value, list | tuple | set | frozenset):
        return [sanitize_value(item, redactions=redactions) for item in list(value)[:500]]
    if isinstance(value, Path):
        return redact_path(value, redactions)
    if isinstance(value, str):
        return sanitize_text(value, redactions=redactions)
    if value is None or isinstance(value, bool | int | float):
        return value
    return sanitize_text(value, redactions=redactions)


def bounded_log_text(path: Path) -> str:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > MAX_LOG_BYTES:
            handle.seek(max(size - MAX_LOG_BYTES, 0))
            handle.readline()
        raw = handle.read(MAX_LOG_BYTES)
    lines = raw.decode("utf-8", errors="replace").splitlines()[-MAX_LOG_LINES:]
    filtered = [
        "[redacted-content-line]" if SENSITIVE_CONTENT_LINE_RE.search(line) else line
        for line in lines
    ]
    return "\n".join(filtered) + ("\n" if filtered else "")


def benchmark_summary(run: Mapping[str, Any]) -> Mapping[str, Any]:
    result_keys = {
        "model_id",
        "requested_device",
        "actual_device",
        "load_time_ms",
        "time_to_first_token_ms",
        "total_latency_ms",
        "completion_tokens",
        "tokens_sec",
        "success",
        "error",
        "timestamp",
        "runs",
        "score",
    }
    results = []
    for item in list(run.get("results") or [])[:50]:
        if isinstance(item, Mapping):
            results.append({key: item.get(key) for key in result_keys if key in item})
    return {
        key: run.get(key)
        for key in (
            "run_id",
            "created_at",
            "finished_at",
            "max_tokens",
            "runs_per_combo",
            "mock",
            "recommendation",
            "caveat",
        )
        if key in run
    } | {"results": results}


def local_hardware_snapshot(models_dir: Path) -> Mapping[str, Any]:
    snapshot: dict[str, Any] = {
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "edition": windows_edition(),
            "architecture": platform.machine(),
        },
        "cpu": {},
        "memory": {},
        "disk": {},
        "runtime": {},
        "available_devices": [],
        "devices": [],
    }
    try:
        from app.hardware_advisor.hardware import cpu_details, device_details, package_version

        snapshot["cpu"] = cpu_details()
        snapshot["devices"] = device_details()
        snapshot["available_devices"] = [
            str(item.get("device")) for item in snapshot["devices"] if item.get("device")
        ]
        snapshot["runtime"] = {
            "openvino": package_version("openvino"),
            "openvino_genai": package_version("openvino-genai"),
            "mock": False,
        }
    except Exception:
        snapshot["cpu"] = {
            "name": platform.processor() or "Unknown CPU",
            "architecture": platform.machine() or "unknown",
            "physical_cores": 0,
            "logical_cores": os.cpu_count() or 0,
        }
    try:
        import psutil

        memory = psutil.virtual_memory()
        snapshot["memory"] = {
            "total_gb": round(float(memory.total) / (1024**3), 2),
            "available_gb": round(float(memory.available) / (1024**3), 2),
        }
    except Exception:
        pass
    snapshot["disk"] = dict(safe_disk_payload({}, models_dir))
    try:
        from app.hardware_advisor.hardware import fingerprint

        snapshot["fingerprint"] = fingerprint(snapshot)
    except Exception:
        snapshot["fingerprint"] = None
    return snapshot


def safe_disk_payload(raw: Mapping[str, Any], models_dir: Path) -> Mapping[str, Any]:
    payload = {
        key: raw.get(key) for key in ("free_gb", "total_gb", "used_gb", "percent") if key in raw
    }
    try:
        usage = shutil.disk_usage(models_dir if models_dir.exists() else models_dir.parent)
        payload.setdefault("free_gb", round(usage.free / (1024**3), 2))
        payload.setdefault("total_gb", round(usage.total / (1024**3), 2))
    except OSError:
        pass
    return payload


def windows_edition() -> str | None:
    try:
        return platform.win32_edition()
    except (AttributeError, OSError):
        return None


def certification_summary(parsed: Any) -> Mapping[str, Any]:
    if not isinstance(parsed, Mapping):
        return {"status": "unavailable", "reason": "Certification report was not an object."}
    summary = {
        key: parsed.get(key)
        for key in ("schema_version", "created_at", "status", "summary", "hardware_fingerprint")
        if key in parsed
    }
    device_keys = {
        "device",
        "base",
        "full_name",
        "driver_version",
        "architecture",
        "optimization_capabilities",
    }
    result_keys = {
        "test",
        "name",
        "status",
        "success",
        "model_id",
        "requested_device",
        "actual_device",
        "load_time_ms",
        "time_to_first_token_ms",
        "total_latency_ms",
        "completion_tokens",
        "tokens_sec",
        "score",
        "error",
    }
    summary["devices"] = [
        {key: item.get(key) for key in device_keys if key in item}
        for item in list(parsed.get("devices") or [])[:20]
        if isinstance(item, Mapping)
    ]
    summary["results"] = [
        {key: item.get(key) for key in result_keys if key in item}
        for item in list(parsed.get("results") or [])[:100]
        if isinstance(item, Mapping)
    ]
    for key in ("failures", "warnings"):
        values = []
        for item in list(parsed.get(key) or [])[:100]:
            text = str(item)
            values.append(
                "[redacted-content]"
                if SENSITIVE_CONTENT_LINE_RE.search(text)
                else sanitize_text(text, limit=1000)
            )
        summary[key] = values
    return summary


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
