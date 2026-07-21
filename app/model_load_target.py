"""Keep explicit model load device requests authoritative.

A model can be auto-loaded while the browser is starting, or a second load request
can arrive while the first OpenVINO compilation is still in progress. Historically,
``ModelManager.schedule_load`` treated either case as an unconditional no-op. That
meant a later explicit ``NPU`` request could inherit an earlier ``GPU`` load.

This module installs a narrow lifecycle extension that tracks the latest requested
device per model, safely switches an already-loaded idle engine, and retargets an
in-flight build before publishing it as ready.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

_INSTALL_FLAG = "_DEVICE_AUTHORITATIVE_LOAD_INSTALLED"
_TARGETS_ATTR = "_requested_load_devices"


def _load_targets(manager: Any) -> dict[str, str]:
    targets = getattr(manager, _TARGETS_ATTR, None)
    if targets is None:
        targets = {}
        setattr(manager, _TARGETS_ATTR, targets)
    return targets


def install_model_load_target_routing() -> None:
    """Patch ``ModelManager`` so the newest explicit load target always wins."""

    from app import errors
    from app import model_manager as manager_module
    from app import model_registry as registry
    from app.config import BASE_DIR
    from runtime import device_check

    manager_class = manager_module.ModelManager
    if getattr(manager_class, _INSTALL_FLAG, False):
        return

    original_shutdown = manager_class.shutdown

    async def device_authoritative_load_task(
        self,
        model_id: str,
        device: str,
        draft_model_path: str | None = None,
    ) -> None:
        cfg = self.catalog[model_id]
        targets = _load_targets(self)
        current_device = device_check.normalize_device(device)

        try:
            try:
                async with asyncio.timeout(600):
                    async with self._load_lock:
                        while True:
                            current_device = targets.get(model_id, current_device)
                            loaded_engine = self.engines.get(model_id)

                            if loaded_engine is not None:
                                loaded_device = device_check.normalize_device(loaded_engine.device)
                                if loaded_device == current_device:
                                    self._set_progress(
                                        model_id,
                                        "ready",
                                        f"{cfg.name} is already loaded on {loaded_device}.",
                                        percent=100,
                                    )
                                    self._clear_status(model_id)
                                    return

                                model_lock = self.locks.get(model_id)
                                if model_lock and model_lock.locked():
                                    self._set_status(model_id, "queued")
                                    self._set_progress(
                                        model_id,
                                        "queued",
                                        f"Waiting to switch {cfg.name} from {loaded_device} "
                                        f"to {current_device}…",
                                    )
                                    async with model_lock:
                                        pass

                                # Re-check after waiting because a concurrent unload or
                                # shutdown may have removed the engine.
                                loaded_engine = self.engines.get(model_id)
                                if loaded_engine is not None:
                                    loaded_device = device_check.normalize_device(
                                        loaded_engine.device
                                    )
                                    if loaded_device == current_device:
                                        self._set_progress(
                                            model_id,
                                            "ready",
                                            f"{cfg.name} is already loaded on {loaded_device}.",
                                            percent=100,
                                        )
                                        self._clear_status(model_id)
                                        return
                                    self.unload(model_id)
                                    manager_module.logger.info(
                                        "Switching '%s' from %s to %s",
                                        model_id,
                                        loaded_device,
                                        current_device,
                                    )
                                    self.emit_event(
                                        "info",
                                        f"Switching {cfg.name} from {loaded_device} "
                                        f"to {current_device}",
                                    )

                            self._set_status(model_id, "loading")
                            self._set_progress(
                                model_id,
                                "loading",
                                f"Checking local model files for {cfg.name}…",
                            )

                            if not self.force_mock:
                                available = device_check.available_devices()
                                if not device_check.is_device_available(current_device, available):
                                    raise RuntimeError(
                                        errors.format_device_error(current_device, available)
                                    )
                                if not registry.is_downloaded(cfg, BASE_DIR):
                                    if self.settings.auto_convert:
                                        manager_module.logger.info(
                                            "Model '%s' not found locally. Auto-convert is enabled. "
                                            "Starting conversion...",
                                            model_id,
                                        )
                                        self._set_progress(
                                            model_id,
                                            "downloading",
                                            f"{cfg.name} is not converted yet. Downloading and "
                                            "converting first…",
                                        )
                                        await self._convert_task(
                                            model_id,
                                            current_device,
                                            load_after=False,
                                        )
                                        self._set_status(model_id, "loading")
                                        if not registry.is_downloaded(cfg, BASE_DIR):
                                            raise RuntimeError(
                                                f"Auto-conversion failed for '{cfg.name}'. "
                                                "Please check logs."
                                            )
                                    else:
                                        raise RuntimeError(
                                            errors.format_model_not_converted(
                                                cfg.name,
                                                str(cfg.abs_path(BASE_DIR)),
                                                cfg.source_model,
                                                weight_format=cfg.weight_format,
                                            )
                                        )

                            latest_target = targets.get(model_id, current_device)
                            if latest_target != current_device:
                                manager_module.logger.info(
                                    "Retargeting queued load for '%s' from %s to %s before compile",
                                    model_id,
                                    current_device,
                                    latest_target,
                                )
                                current_device = latest_target
                                continue

                            self._set_progress(
                                model_id,
                                "loading",
                                f"Loading {cfg.name} on {current_device}…",
                            )
                            loop = asyncio.get_running_loop()
                            engine = await loop.run_in_executor(
                                None,
                                self._build_engine,
                                model_id,
                                current_device,
                                draft_model_path,
                            )

                            latest_target = targets.get(model_id, current_device)
                            if latest_target != current_device:
                                manager_module.logger.info(
                                    "Discarding '%s' engine built on %s; newest target is %s",
                                    model_id,
                                    current_device,
                                    latest_target,
                                )
                                with contextlib.suppress(Exception):
                                    engine.close()
                                self._set_progress(
                                    model_id,
                                    "loading",
                                    f"Retargeting {cfg.name} to {latest_target}…",
                                )
                                current_device = latest_target
                                continue

                            self.engines[model_id] = engine
                            self.locks[model_id] = asyncio.Lock()
                            self.devices[model_id] = engine.device
                            self._set_progress(
                                model_id,
                                "ready",
                                f"{cfg.name} is ready on {engine.device}.",
                                percent=100,
                            )
                            self._clear_status(model_id)
                            manager_module.logger.info(
                                "Loaded '%s' on %s", model_id, engine.device
                            )
                            self.emit_event("info", f"Loaded {cfg.name} on {engine.device}")
                            return
            except Exception as exc:  # noqa: BLE001 - surfaced through model status
                self.engines.pop(model_id, None)
                self.locks.pop(model_id, None)
                self.devices.pop(model_id, None)
                message = errors.format_model_load_error(exc)
                self._set_status(model_id, "error", error=message)
                self._set_progress(model_id, "error", f"Load failed: {message}")
                manager_module.logger.exception("Failed to load '%s': %s", model_id, message)
                self.emit_event("error", f"Failed to load {cfg.name}: {message}")
        finally:
            self.load_tasks.pop(model_id, None)
            targets.pop(model_id, None)

    def device_authoritative_schedule_load(
        self,
        model_id: str,
        device: str | None = None,
        *,
        draft_model: str | None = None,
    ) -> asyncio.Task | None:
        if model_id not in self.catalog:
            manager_module.logger.warning("Refusing to load unknown model '%s'", model_id)
            return None

        target_device = device_check.normalize_device(device or self.settings.device)
        cfg = self.catalog[model_id]
        targets = _load_targets(self)
        loaded_engine = self.engines.get(model_id)

        if loaded_engine is not None:
            loaded_device = device_check.normalize_device(loaded_engine.device)
            if loaded_device == target_device:
                self._set_progress(
                    model_id,
                    "ready",
                    f"{cfg.name} is already loaded on {loaded_device}.",
                    percent=100,
                )
                self._clear_status(model_id)
                return None

        existing = self.load_tasks.get(model_id)
        if existing and not existing.done():
            previous_target = targets.get(model_id)
            targets[model_id] = target_device
            if previous_target != target_device:
                self._set_progress(
                    model_id,
                    "loading",
                    f"Retargeting {cfg.name} to {target_device}…",
                )
                manager_module.logger.info(
                    "Updated in-flight load target for '%s' from %s to %s",
                    model_id,
                    previous_target or "unknown",
                    target_device,
                )
            return existing

        draft_model_path = self._resolve_draft_model_path(model_id, draft_model)

        # Switch an idle engine immediately so status and API capability flags no
        # longer report the stale device while the replacement task is queued.
        if loaded_engine is not None:
            model_lock = self.locks.get(model_id)
            if not model_lock or not model_lock.locked():
                loaded_device = device_check.normalize_device(loaded_engine.device)
                self.unload(model_id)
                manager_module.logger.info(
                    "Unloaded '%s' from %s for requested %s load",
                    model_id,
                    loaded_device,
                    target_device,
                )

        targets[model_id] = target_device
        self._set_status(model_id, "queued")
        self._set_progress(
            model_id,
            "queued",
            f"Queued {cfg.name} to load on {target_device}…",
        )
        task = asyncio.create_task(
            self._load_task(
                model_id,
                target_device,
                draft_model_path=draft_model_path,
            )
        )
        self.load_tasks[model_id] = task
        return task

    async def shutdown_with_target_cleanup(self) -> None:
        try:
            await original_shutdown(self)
        finally:
            _load_targets(self).clear()

    manager_class._load_task = device_authoritative_load_task
    manager_class.schedule_load = device_authoritative_schedule_load
    manager_class.shutdown = shutdown_with_target_cleanup
    setattr(manager_class, _INSTALL_FLAG, True)
