"""Regression checks for the one-time first-test NPU bootstrap."""

from app.config import Settings  # noqa: F401 - installs composed UI extensions
from app.ui_extension import inject_multimodal_ui


def test_first_run_npu_bootstrap_is_injected_once_and_before_base_state() -> None:
    html = """<html><head></head><body>
    <script>let selectedDevice = localStorage.getItem('ovllm.device.v1') || 'NPU';</script>
    </body></html>"""

    rendered = inject_multimodal_ui(html)
    rendered_twice = inject_multimodal_ui(rendered)

    bootstrap = 'id="ovllm-first-run-npu-bootstrap"'
    extension = 'id="ovllm-first-run-npu-extension"'
    assert rendered.count(bootstrap) == 1
    assert rendered.count(extension) == 1
    assert rendered_twice.count(bootstrap) == 1
    assert rendered_twice.count(extension) == 1
    assert rendered.index(bootstrap) < rendered.index("let selectedDevice")


def test_first_run_bootstrap_repairs_legacy_cpu_preference() -> None:
    rendered = inject_multimodal_ui("<html><head></head><body></body></html>")

    assert "ovllm.first-npu-ready.v1" in rendered
    assert "localStorage.setItem(DEVICE_KEY, 'NPU')" in rendered
    assert "before the base UI reads its device preference" in rendered


def test_first_test_model_is_selected_and_retargeted_to_npu() -> None:
    rendered = inject_multimodal_ui("<html><head></head><body></body></html>")

    assert "const FIRST_TEST_MODEL_ID = 'tinyllama-1.1b-chat-fp16'" in rendered
    assert "modelSelect.value = FIRST_TEST_MODEL_ID" in rendered
    assert "modelSelect.dispatchEvent(new Event('change', { bubbles: true }))" in rendered
    assert "target.path === '/v1/system/status'" in rendered
    assert "previousFetch('/v1/models/load'" in rendered
    assert "JSON.stringify({ model: FIRST_TEST_MODEL_ID, device: 'NPU' })" in rendered


def test_first_run_bootstrap_waits_for_user_before_downloading() -> None:
    rendered = inject_multimodal_ui("<html><head></head><body></body></html>")
    extension = rendered.split('id="ovllm-first-run-npu-extension"', maxsplit=1)[1]

    assert "if (model.is_loading || model.is_loaded)" in extension
    assert "'/v1/models/convert'" not in extension
    assert "markComplete();" in extension
