from app.desktop_onboarding import actual_device_is_unresolved, sanitize_system_scan
from app.onboarding_models import SystemScanResponse


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


def test_composite_device_is_not_accepted_as_actual_hardware():
    assert actual_device_is_unresolved(None) is True
    assert actual_device_is_unresolved("AUTO") is True
    assert actual_device_is_unresolved("AUTO:NPU,GPU,CPU") is True
    assert actual_device_is_unresolved("MULTI:NPU,GPU,CPU") is True
    assert actual_device_is_unresolved("CPU") is False
    assert actual_device_is_unresolved("GPU.0") is False
    assert actual_device_is_unresolved("NPU") is False
