from app.ui_extension import inject_multimodal_ui


def test_release_extension_is_injected_once():
    html = "<html><body><main>chat</main></body></html>"
    first = inject_multimodal_ui(html)
    second = inject_multimodal_ui(first)
    assert first.count('id="ovllm-release-extension"') == 1
    assert second.count('id="ovllm-release-extension"') == 1
    assert "About & Updates" in first
