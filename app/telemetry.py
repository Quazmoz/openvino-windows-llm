"""System telemetry for the status panel: memory, CPU, model disk footprint."""

from __future__ import annotations

import os
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
