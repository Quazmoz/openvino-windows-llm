"""OpenVINO device discovery and validation.

Safe to import anywhere: if OpenVINO is not installed every function degrades to
an empty / "unavailable" result instead of raising.
"""

from __future__ import annotations

import importlib.util
import logging

logger = logging.getLogger("ov-llm.device")


def is_openvino_available() -> bool:
    """True if the OpenVINO GenAI runtime can be imported."""
    return importlib.util.find_spec("openvino_genai") is not None


def normalize_device(device: str | None) -> str:
    return (device or "NPU").strip().upper() or "NPU"


def available_devices() -> list[str]:
    """List OpenVINO device names (e.g. ['CPU', 'GPU', 'NPU']); [] if unavailable."""
    if importlib.util.find_spec("openvino") is None:
        return []
    try:
        import openvino as ov

        return list(ov.Core().available_devices)
    except Exception as exc:  # pragma: no cover - depends on local OpenVINO/drivers
        logger.warning("OpenVINO device discovery failed: %s", exc)
        return []


def device_details() -> list[dict]:
    """List devices with their human-readable full names."""
    if importlib.util.find_spec("openvino") is None:
        return []
    try:
        import openvino as ov

        core = ov.Core()
        details = []
        for dev in core.available_devices:
            try:
                full = core.get_property(dev, "FULL_DEVICE_NAME")
            except Exception:
                full = dev
            details.append({"device": dev, "full_name": str(full)})
        return details
    except Exception as exc:  # pragma: no cover
        logger.warning("OpenVINO device discovery failed: %s", exc)
        return []


def is_device_available(device: str, available: list[str] | None = None) -> bool:
    """Whether ``device`` can be targeted.

    ``AUTO`` always passes. Otherwise matches against discovered devices,
    tolerating indexed names like ``GPU.0``. If discovery returned nothing
    (OpenVINO absent), only CPU/AUTO are considered available.
    """
    device = normalize_device(device)
    if device == "AUTO":
        return True
    if available is None:
        available = available_devices()
    if not available:
        return device == "CPU"
    base = device.split(".")[0]
    return any(a == device or a.split(".")[0] == base for a in available)
