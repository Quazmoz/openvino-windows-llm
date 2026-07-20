from app.ui_extension import VISION_EXTENSION_JS, inject_multimodal_ui


def test_vision_extension_is_injected_once_before_body_close():
    html = "<html><body><main>chat</main></body></html>"
    injected = inject_multimodal_ui(html)
    assert 'id="ovllm-vision-extension"' in injected
    assert injected.index('id="ovllm-vision-extension"') < injected.index("</body>")
    assert inject_multimodal_ui(injected) == injected


def test_browser_extension_supports_file_paste_drop_and_openai_image_parts():
    assert "vision-file-input" in VISION_EXTENSION_JS
    assert "dragover" in VISION_EXTENSION_JS
    assert "clipboardData" in VISION_EXTENSION_JS
    assert "image_url" in VISION_EXTENSION_JS
    assert "openvino-vlm" in VISION_EXTENSION_JS
    assert "image-text-to-text" in VISION_EXTENSION_JS
    assert "supports_vision" in VISION_EXTENSION_JS


def test_browser_extension_does_not_upload_images_to_a_separate_endpoint():
    assert "/v1/images" not in VISION_EXTENSION_JS
    assert "FileReader" in VISION_EXTENSION_JS
    assert "dataUrl" in VISION_EXTENSION_JS
