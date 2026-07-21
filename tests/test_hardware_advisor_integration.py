from __future__ import annotations

import pytest

from app.model_manager import ModelManager, NoModelsLoaded, UnknownModel
from app.ui_extension import inject_multimodal_ui


class FakeAdvisor:
    def __init__(self, selected=None):
        self.selected = selected

    def select_loaded_model(self, profile, engines, devices):
        assert profile in {"fastest", "balanced", "best-quality", "lowest-memory", "lowest-power"}
        return self.selected


def bare_manager(selected=None):
    manager = ModelManager.__new__(ModelManager)
    manager.engines = {"text-model": object()}
    manager.devices = {"text-model": "NPU"}
    manager.advisor = FakeAdvisor(selected)
    return manager


def test_model_manager_resolves_auto_profile_to_loaded_engine():
    manager = bare_manager("text-model")
    assert manager.resolve_engine("auto:fastest") is manager.engines["text-model"]


def test_model_manager_rejects_auto_when_no_generation_model_is_loaded():
    manager = bare_manager(None)
    with pytest.raises(NoModelsLoaded, match="advisor profile 'balanced'"):
        manager.resolve_engine("auto")


def test_model_manager_rejects_unknown_auto_profile():
    manager = bare_manager(None)
    with pytest.raises(UnknownModel, match="Unknown advisor profile"):
        manager.resolve_engine("auto:impossible")


def test_ui_composes_vision_and_hardware_advisor_extensions_once():
    rendered = inject_multimodal_ui("<html><body></body></html>")
    rendered_twice = inject_multimodal_ui(rendered)

    assert 'id="ovllm-vision-extension"' in rendered
    assert 'id="ovllm-hardware-advisor-extension"' in rendered
    assert "Best model for this PC" in rendered
    assert "bodyData.model = `auto:${autoRoutingProfile}`" in rendered
    assert "short hardware benchmark" in rendered
    assert rendered_twice.count('id="ovllm-hardware-advisor-extension"') == 1
