from fastapi.responses import FileResponse

from app.ui_extension import VISION_EXTENSION_JS, inject_multimodal_ui


def test_vision_extension_is_injected_once_before_body_close():
    html = "<html><body><main>chat</main></body></html>"
    injected = inject_multimodal_ui(html)
    assert 'id="ovllm-vision-extension"' in injected
    assert injected.index('id="ovllm-vision-extension"') < injected.index("</body>")
    assert inject_multimodal_ui(injected) == injected


def test_importing_app_does_not_monkey_patch_file_response():
    assert FileResponse.__call__.__module__.startswith("starlette.")


def test_browser_extension_supports_safe_attachment_lifecycle():
    assert "vision-file-input" in VISION_EXTENSION_JS
    assert "dragover" in VISION_EXTENSION_JS
    assert "clipboardData" in VISION_EXTENSION_JS
    assert "event.preventDefault()" in VISION_EXTENSION_JS
    assert "image_url" in VISION_EXTENSION_JS
    assert "openvino-vlm" in VISION_EXTENSION_JS
    assert "image-text-to-text" in VISION_EXTENSION_JS
    assert "supports_vision" in VISION_EXTENSION_JS
    assert "MAX_TOTAL_BYTES" in VISION_EXTENSION_JS
    assert "MAX_TOTAL_PIXELS" in VISION_EXTENSION_JS
    assert "fileQueue" in VISION_EXTENSION_JS
    assert "attachments were kept" in VISION_EXTENSION_JS
    assert "if (sentIds.length && response.ok)" in VISION_EXTENSION_JS
    assert "response.clone()" in VISION_EXTENSION_JS
    assert ".slice(-4096)" in VISION_EXTENSION_JS
    assert "transcript +=" not in VISION_EXTENSION_JS
    assert "attachmentEpoch" in VISION_EXTENSION_JS
    assert "MAX_DIMENSION" in VISION_EXTENSION_JS
    assert "custom-trust-remote-code" in VISION_EXTENSION_JS
    assert "trust_remote_code" in VISION_EXTENSION_JS
    assert "Off by default" in VISION_EXTENSION_JS
    assert "queueMicrotask" in VISION_EXTENSION_JS
    assert "dispatchEvent(new Event('change'))" in VISION_EXTENSION_JS
    assert "customTrustRemoteCode.checked = false" in VISION_EXTENSION_JS
    assert "customTrustRemoteCode.isConnected" in VISION_EXTENSION_JS


def test_browser_extension_does_not_upload_images_to_a_separate_endpoint():
    assert "/v1/images" not in VISION_EXTENSION_JS
    assert "FileReader" in VISION_EXTENSION_JS
    assert "dataUrl" in VISION_EXTENSION_JS
