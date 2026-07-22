from pathlib import Path

from app.desktop_onboarding import (
    actual_device_is_unresolved,
    augment_windows_scan,
    sanitize_system_scan,
)
from app.onboarding_models import SystemScanResponse


ROOT = Path(__file__).resolve().parent.parent


def test_system_scan_does_not_expose_full_model_storage_path():
    scan = SystemScanResponse(
        generated_at="2026-01-01T00:00:00Z",
        fingerprint="abc",
        mock=False,
        items=[],
        hardware={
            "disk": {
                "free_gb": 100,
                "models_dir": r"C:\Users\private\AppData\Local\OpenVINOWindowsLLM\models",
            }
        },
    )

    sanitized = sanitize_system_scan(scan)

    assert sanitized.hardware["disk"] == {"free_gb": 100}
    assert "models_dir" in scan.hardware["disk"]


def test_windows_10_build_is_a_warning_not_an_unknown_failure():
    scan = SystemScanResponse(
        generated_at="2026-01-01T00:00:00Z",
        fingerprint="abc",
        mock=False,
        items=[],
        hardware={
            "os": {
                "system": "Windows",
                "release": "10",
                "version": "10.0.19045",
            }
        },
    )

    augmented = augment_windows_scan(scan, edition="Professional")
    build = next(item for item in augmented.items if item.key == "windows-build")
    edition = next(item for item in augmented.items if item.key == "windows-edition")

    assert build.status.value == "warning"
    assert edition.value == "Professional"
    assert any("older" in warning.lower() for warning in augmented.warnings)


def test_composite_device_is_not_accepted_as_actual_hardware():
    assert actual_device_is_unresolved(None) is True
    assert actual_device_is_unresolved("AUTO") is True
    assert actual_device_is_unresolved("AUTO:NPU,GPU,CPU") is True
    assert actual_device_is_unresolved("MULTI:NPU,GPU,CPU") is True
    assert actual_device_is_unresolved("CPU") is False
    assert actual_device_is_unresolved("GPU.0") is False
    assert actual_device_is_unresolved("NPU") is False


def test_normal_desktop_launch_cannot_silently_use_mock_runtime():
    source = (ROOT / "app" / "desktop_server.py").read_text(encoding="utf-8")
    assert "app.state.manager.force_mock and not mock" in source
    assert "Mock mode is never enabled" in source
