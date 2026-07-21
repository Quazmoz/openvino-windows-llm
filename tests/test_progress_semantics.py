from app.config import Settings  # noqa: F401 - installs composed browser extensions
from app.ui_extension import inject_multimodal_ui


def test_progress_semantics_extension_is_injected_once():
    html = "<html><body></body></html>"
    rendered = inject_multimodal_ui(html)
    rendered_twice = inject_multimodal_ui(rendered)

    marker = 'id="ovllm-model-progress-semantics-extension"'
    assert rendered.count(marker) == 1
    assert rendered_twice.count(marker) == 1


def test_progress_semantics_treats_null_as_indeterminate():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "value === null || value === undefined || value === ''" in rendered
    assert "track.classList.toggle('indeterminate', !determinate)" in rendered
    assert "track.removeAttribute('aria-valuenow')" in rendered
    assert "Working…" in rendered


def test_progress_semantics_prefers_aggregate_multi_file_percentage():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "function aggregateDownloadPercent" in rendered
    assert "fetching|downloading" in rendered
    assert "aggregateDownloadPercent(progress)" in rendered
    assert "phaseRanges" in rendered


def test_progress_semantics_patches_all_progress_surfaces():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "patchDetailedPanel(selected)" in rendered
    assert "patchInline(active)" in rendered
    assert "patchDock(active)" in rendered
    assert "new MutationObserver" in rendered
