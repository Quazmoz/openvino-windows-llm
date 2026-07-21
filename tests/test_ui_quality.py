from app.config import Settings  # noqa: F401 - installs composed UI extensions
from app.ui_extension import inject_multimodal_ui
from app.ui_quality import UI_QUALITY_JS


def test_ui_quality_extension_is_injected_once_in_the_expected_order():
    html = "<html><head></head><body></body></html>"

    rendered = inject_multimodal_ui(html)
    rendered_twice = inject_multimodal_ui(rendered)

    assert rendered.count('id="ovllm-ui-quality-extension"') == 1
    assert rendered.count('id="ovllm-ui-quality-extension-styles"') == 1
    assert rendered_twice.count('id="ovllm-ui-quality-extension"') == 1
    assert rendered.index('id="ovllm-ui-polish-extension"') < rendered.index(
        'id="ovllm-ui-quality-extension"'
    )
    assert rendered.index('id="ovllm-ui-quality-extension"') < rendered.index(
        'id="ovllm-model-progress-extension"'
    )


def test_ui_quality_surfaces_connection_recovery_and_coalesces_status_polling():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "ov-connection-banner" in rendered
    assert "Retry connection" in rendered
    assert "statusRequest" in rendered
    assert "if (statusRequest) return statusRequest" in rendered
    assert "clearInterval(statusInterval)" in rendered
    assert "label.includes('connecting')" in rendered


def test_ui_quality_hardens_modal_keyboard_and_focus_behavior():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "appRoot.inert = open" in rendered
    assert "qualitySetCustomModelModalOpen" in rendered
    assert "ArrowRight" in rendered
    assert "focusable[0]" in rendered
    assert "aria-hidden" in rendered


def test_ui_quality_uses_failure_safe_in_place_device_retargeting():
    assert "fetch('/v1/models/load'" in UI_QUALITY_JS
    assert "fetch('/v1/models/unload'" not in UI_QUALITY_JS
    assert "event.stopImmediatePropagation()" in UI_QUALITY_JS
    assert "selectedDevice = previousDevice" in UI_QUALITY_JS
    assert "current model stays available" in UI_QUALITY_JS
    assert "Device switch failed" in UI_QUALITY_JS


def test_ui_quality_refreshes_activity_and_handles_clipboard_failures():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "activityFingerprint" in rendered
    assert "lastEventCount = -1" in rendered
    assert "No events yet" in rendered
    assert "resilientCopy" in rendered
    assert "document.execCommand('copy')" in rendered
    assert "Copy failed" in rendered


def test_ui_quality_retains_local_dependency_free_delivery():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "fonts.googleapis.com" not in rendered
    assert "cdn.jsdelivr.net" not in rendered
    assert "unpkg.com" not in rendered
