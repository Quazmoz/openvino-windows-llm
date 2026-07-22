"""The legacy forced-NPU bootstrap was replaced by conservative desktop onboarding."""

from app.config import Settings  # noqa: F401
from app.ui_extension import inject_multimodal_ui


def test_legacy_forced_npu_bootstrap_is_not_active():
    rendered = inject_multimodal_ui("<html><head></head><body></body></html>")
    assert "ovllm-first-run-npu-bootstrap" not in rendered
    assert "ovllm-first-run-npu-extension" not in rendered
    assert "ovllm-desktop-onboarding-extension" in rendered
