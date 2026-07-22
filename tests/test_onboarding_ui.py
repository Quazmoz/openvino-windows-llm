from app.config import Settings  # noqa: F401 - installs composed UI extensions
from app.ui_extension import inject_multimodal_ui


def test_desktop_wizard_is_injected_once_without_forcing_npu():
    html = "<html><head></head><body></body></html>"
    rendered = inject_multimodal_ui(html)
    rendered_twice = inject_multimodal_ui(rendered)
    marker = 'id="ovllm-desktop-onboarding-extension"'
    assert rendered.count(marker) == 1
    assert rendered_twice.count(marker) == 1
    assert "ovllm.first-npu-ready.v1" not in rendered
    assert "JSON.stringify({ model: FIRST_TEST_MODEL_ID, device: 'NPU' })" not in rendered


def test_wizard_has_accessible_stages_and_real_connection_configuration():
    rendered = inject_multimodal_ui("<html><head></head><body></body></html>")
    for label in (
        "System scan",
        "NPU readiness",
        "Recommended model",
        "Downloading model files",
        "Converting or quantizing to OpenVINO",
        "Compiling for the selected device",
        "Running a short benchmark",
        "OpenAI Python client",
        "Open WebUI",
        "n8n",
    ):
        assert label in rendered
    assert "aria-live" in rendered
    assert "role', 'progressbar" in rendered
    assert "https://" not in rendered
