"""Reject new heavyweight model work once packaged desktop shutdown begins."""

from __future__ import annotations

_INSTALL_FLAG = "_DESKTOP_SHUTDOWN_SAFETY_INSTALLED"
_SHUTTING_DOWN_ATTR = "_model_manager_shutting_down"


def install_desktop_shutdown_safety() -> None:
    from app import model_manager as manager_module

    manager_class = manager_module.ModelManager
    if getattr(manager_class, _INSTALL_FLAG, False):
        return

    original_schedule_load = manager_class.schedule_load
    original_schedule_convert = manager_class.schedule_convert
    original_register_model = manager_class.register_model

    def reject_if_shutting_down(self) -> None:
        if getattr(self, _SHUTTING_DOWN_ATTR, False):
            raise ValueError("The desktop server is shutting down and cannot start new model work.")

    def guarded_schedule_load(self, *args, **kwargs):
        reject_if_shutting_down(self)
        return original_schedule_load(self, *args, **kwargs)

    def guarded_schedule_convert(self, *args, **kwargs):
        reject_if_shutting_down(self)
        return original_schedule_convert(self, *args, **kwargs)

    def guarded_register_model(self, *args, **kwargs):
        reject_if_shutting_down(self)
        return original_register_model(self, *args, **kwargs)

    manager_class.schedule_load = guarded_schedule_load
    manager_class.schedule_convert = guarded_schedule_convert
    manager_class.register_model = guarded_register_model
    setattr(manager_class, _INSTALL_FLAG, True)
