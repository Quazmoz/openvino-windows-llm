"""Hardware snapshot collection for the model advisor."""

from __future__ import annotations

import platform
import shutil
import time
from pathlib import Path
from typing import Any

from app.telemetry import memory_stats
from runtime import device_check

from .common import SNAPSHOT_TTL_SECONDS, utc_now
from .hardware import cpu_details, device_details, fingerprint, package_version


class SnapshotMixin:
    def hardware_snapshot(self, *, refresh: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if (
            not refresh
            and self._snapshot is not None
            and now - self._snapshot_at < SNAPSHOT_TTL_SECONDS
        ):
            return self._snapshot

        memory = memory_stats()
        models_dir = Path(self.settings.models_dir)
        disk_target = models_dir
        while not disk_target.exists() and disk_target != disk_target.parent:
            disk_target = disk_target.parent
        try:
            usage = shutil.disk_usage(disk_target)
            disk = {
                "total_gb": round(usage.total / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
            }
        except OSError:
            disk = {"total_gb": 0.0, "free_gb": 0.0}
        devices = device_details()
        gpu_device = next((item for item in devices if item.get("base") == "GPU"), None)
        gpu = gpu_device or None
        snapshot: dict[str, Any] = {
            "generated_at": utc_now(),
            "os": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
            },
            "cpu": cpu_details(),
            "memory": memory,
            "disk": {
                **disk,
                "models_dir": str(models_dir.resolve()),
            },
            "gpu": gpu,
            "devices": devices,
            "available_devices": device_check.available_devices(),
            "runtime": {
                "openvino": package_version("openvino"),
                "openvino_genai": package_version("openvino-genai"),
                "mock": self.force_mock,
            },
        }
        snapshot["fingerprint"] = fingerprint(snapshot)
        self._snapshot = snapshot
        self._snapshot_at = now
        return snapshot
