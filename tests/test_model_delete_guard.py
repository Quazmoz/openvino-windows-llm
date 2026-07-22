from types import SimpleNamespace

import pytest

from app.model_manager import ModelManager


class ActiveTask:
    def done(self) -> bool:
        return False


def manager_stub() -> ModelManager:
    manager = object.__new__(ModelManager)
    manager.catalog = {"test-model": SimpleNamespace(name="Test Model")}
    manager.engines = {}
    manager.load_tasks = {}
    manager.convert_tasks = {}
    return manager


def test_delete_rejects_active_conversion():
    manager = manager_stub()
    manager.convert_tasks["test-model"] = ActiveTask()

    with pytest.raises(ValueError, match="still converting"):
        manager.delete("test-model")


def test_delete_rejects_active_load():
    manager = manager_stub()
    manager.load_tasks["test-model"] = ActiveTask()

    with pytest.raises(ValueError, match="still loading"):
        manager.delete("test-model")


def test_delete_rejects_loaded_model():
    manager = manager_stub()
    manager.engines["test-model"] = object()

    with pytest.raises(ValueError, match="Unload it before deleting"):
        manager.delete("test-model")
