"""System telemetry for the status panel: memory, CPU, model disk footprint."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is a hard dependency at runtime
    psutil = None  # type: ignore[assignment]


def dir_size_bytes(path: str | Path) -> int:
    """Total size of a directory tree in bytes (0 if missing / unreadable)."""
    total = 0
    try:
        for dirpath, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += (Path(dirpath) / name).stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def dir_size_gb(path: str | Path) -> float:
    return round(dir_size_bytes(path) / (1024**3), 2)


def _first_existing(path: Path) -> Path | None:
    """Walk up from ``path`` to the first directory that exists (for disk_usage)."""
    for candidate in (path, *path.parents):
        if candidate.exists():
            return candidate
    return None


def disk_stats(models_dir: str | Path) -> dict:
    """Converted-model footprint plus the real free/total space on its volume."""
    models_dir = Path(models_dir)
    stats = {"models_gb": dir_size_gb(models_dir), "total_gb": 0.0, "free_gb": 0.0}
    target = _first_existing(models_dir)
    if target is not None:
        try:
            usage = shutil.disk_usage(target)
            stats["total_gb"] = round(usage.total / (1024**3), 2)
            stats["free_gb"] = round(usage.free / (1024**3), 2)
        except OSError:
            pass
    return stats


def memory_stats() -> dict:
    if psutil is None:
        return {"total_gb": 0.0, "available_gb": 0.0, "used_percent": 0.0}
    vm = psutil.virtual_memory()
    return {
        "total_gb": round(vm.total / (1024**3), 2),
        "available_gb": round(vm.available / (1024**3), 2),
        "used_percent": vm.percent,
    }


def cpu_stats() -> dict:
    if psutil is None:
        return {"percent": 0.0}
    return {"percent": psutil.cpu_percent(interval=None)}


def gpu_stats() -> dict | None:
    """Return GPU memory usage statistics if an Intel/AMD GPU is available via OpenVINO.

    Returns a dict with total, free, and used memory in GB, or None if unavailable/fails.
    """
    import importlib.util
    if importlib.util.find_spec("openvino") is None:
        return None

    try:
        from runtime.device_check import _get_core, available_devices
        core = _get_core()
        devices = available_devices()
        gpu_device = next((d for d in devices if d.startswith("GPU")), None)
        if not gpu_device:
            return None

        try:
            total_bytes = core.get_property(gpu_device, "GPU_DEVICE_TOTAL_MEM_SIZE")
        except Exception:
            total_bytes = None

        try:
            stats = core.get_property(gpu_device, "GPU_MEMORY_STATISTICS")
        except Exception:
            stats = {}

        result = {
            "device": gpu_device,
            "full_name": str(core.get_property(gpu_device, "FULL_DEVICE_NAME")),
        }

        if total_bytes is not None:
            result["total_gb"] = round(total_bytes / (1024**3), 2)

        formatted_stats = {}
        for k, v in stats.items():
            if isinstance(v, int):
                formatted_stats[k] = v
                if any(x in k.lower() for x in ("size", "bytes", "free", "used", "total", "allocated", "limit")):
                    formatted_stats[f"{k}_gb"] = round(v / (1024**3), 2)
            else:
                formatted_stats[k] = v

        if formatted_stats:
            result["statistics"] = formatted_stats

        for key in ("used", "allocated"):
            for k in list(formatted_stats.keys()):
                if k.lower() == key and isinstance(formatted_stats[k], int):
                    result["used_gb"] = round(formatted_stats[k] / (1024**3), 2)
        for key in ("free", "available"):
            for k in list(formatted_stats.keys()):
                if k.lower() == key and isinstance(formatted_stats[k], int):
                    result["free_gb"] = round(formatted_stats[k] / (1024**3), 2)

        return result
    except Exception as exc:
        logger = logging.getLogger("ov-llm.telemetry")
        logger.debug("Failed to query GPU telemetry: %s", exc)
        return None

