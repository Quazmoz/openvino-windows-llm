from app.config import Settings  # noqa: F401 - installs composed UI extensions
from app.ui_extension import inject_multimodal_ui


def test_progress_extension_is_injected_after_base_ui_once():
    html = '<html><head></head><body><select id="model-select"></select></body></html>'

    rendered = inject_multimodal_ui(html)
    rendered_twice = inject_multimodal_ui(rendered)

    extension_ids = (
        "ovllm-vision-extension",
        "ovllm-model-progress-extension",
        "ovllm-model-progress-dock-extension",
    )
    for extension_id in extension_ids:
        assert rendered.count(f'id="{extension_id}"') == 1
        assert rendered_twice.count(f'id="{extension_id}"') == 1


def test_progress_extension_exposes_determinate_and_indeterminate_states():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "ov-progress-panel" in rendered
    assert "ov-progress-track" in rendered
    assert "indeterminate" in rendered
    assert "aria-valuenow" in rendered
    assert "1. Download" in rendered
    assert "2. Convert" in rendered
    assert "3. Load" in rendered
    assert "Elapsed" in rendered
    assert "Recent preparation activity" in rendered
    assert "/v1/system/status" in rendered


def test_progress_dock_stays_available_outside_empty_state():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "ov-progress-dock" in rendered
    assert "chatColumn.insertBefore(dock, chatArea)" in rendered
    assert "dock.classList.add('visible')" in rendered
    assert "dock.classList.remove('visible')" in rendered


def test_progress_extension_uses_text_content_for_dynamic_server_values():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "message.textContent" in rendered
    assert "output.textContent = logs.join" in rendered
    assert "title.textContent" in rendered
