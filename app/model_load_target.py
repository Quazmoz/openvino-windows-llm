"""Keep explicit model load device requests authoritative and failure-safe.

The newest explicit device request wins, including when a startup load or a previous
OpenVINO compilation is already in flight. A working engine is retained until its
replacement has compiled successfully so a bad target or driver failure does not
silently take the model offline.
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

    async def _preflight(
        self,
        model_id: str,
        current_device: str,
    ) -> None:
        cfg = self.catalog[model_id]
        self._set_status(model_id, "loading")
        self._set_progress(
            model_id,
            "loading",
            f"Checking local model files and {current_device} availability for {cfg.name}…",
        )

        if self.force_mock:
            return

        available = device_check.available_devices()
        if not device_check.is_device_available(current_device, available):
            raise RuntimeError(errors.format_device_error(current_device, available))

        if registry.is_downloaded(cfg, BASE_DIR):
            return

        if not self.settings.auto_convert:
            raise RuntimeError(
                errors.format_model_not_converted(
                    cfg.name,
                    str(cfg.abs_path(BASE_DIR)),
                    cfg.source_model,
                    weight_format=cfg.weight_format,
                )
            )

        manager_module.logger.info(
            "Model '%s' is not available locally; starting automatic conversion",
            model_id,
        )
        self._set_progress(
            model_id,
            "downloading",
            f"{cfg.name} is not converted yet. Downloading and converting first…",
        )
        await self._convert_task(model_id, current_device, load_after=False)
        self._set_status(model_id, "loading")
        if not registry.is_downloaded(cfg, BASE_DIR):
            raise RuntimeError(
                f"Auto-conversion failed for '{cfg.name}'. Review the preparation details."
            )

    async def _build_engine_cancellation_safe(
        self,
        model_id: str,
        current_device: str,
        draft_model_path: str | None,
    ):
        """Do not leak a compiled engine when an asyncio task is cancelled.

        ``run_in_executor`` cannot stop an OpenVINO compilation after it has begun.
        During shutdown, wait for that worker to finish and close its result before
        propagating cancellation.
        """

        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            None,
            self._build_engine,
            model_id,
            current_device,
            draft_model_path,
        )
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                engine = await future
                engine.close()
            raise

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

                # Validate the requested target and perform any required conversion
                # before blocking the currently loaded engine. Existing generations
                # remain usable throughout a long first-time download/conversion.
                async with self._load_lock:
                    await _preflight(self, model_id, current_device)

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

                loaded_engine = self.engines.get(model_id)
                model_lock = self.locks.get(model_id) if loaded_engine is not None else None
                if model_lock is not None and model_lock.locked():
                    loaded_device = device_check.normalize_device(loaded_engine.device)
                    self._set_status(model_id, "queued")
                    self._set_progress(
                        model_id,
                        "queued",
                        f"Waiting for the active request before switching {cfg.name} "
                        f"from {loaded_device} to {current_device}…",
                    )

                # Acquire the per-model lock before the global load lock. This keeps a
                # busy model from blocking unrelated model loads while we wait.
                if model_lock is not None:
                    await model_lock.acquire()

                replacement = None
                try:
                    async with self._load_lock:
                        latest_target = targets.get(model_id, current_device)
                        if latest_target != current_device:
                            current_device = latest_target
                            continue

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

                        # Device availability can change while a long generation was
                        # draining. Recheck the cheap preflight before compiling.
                        await _preflight(self, model_id, current_device)
                        latest_target = targets.get(model_id, current_device)
                        if latest_target != current_device:
                            current_device = latest_target
                            continue

                        self._set_status(model_id, "loading")
                        self._set_progress(
                            model_id,
                            "loading",
                            f"Compiling {cfg.name} for {current_device}…",
                        )
                        replacement = await _build_engine_cancellation_safe(
                            self,
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
                                replacement.close()
                            replacement = None
                            self._set_progress(
                                model_id,
                                "loading",
                                f"Retargeting {cfg.name} to {latest_target}…",
                            )
                            current_device = latest_target
                            continue

                        previous_engine = self.engines.get(model_id)
                        previous_device = (
                            device_check.normalize_device(previous_engine.device)
                            if previous_engine is not None
                            else None
                        )

                        self.engines[model_id] = replacement
                        self.locks[model_id] = asyncio.Lock()
                        self.devices[model_id] = replacement.device
                        replacement = None

                        if previous_engine is not None:
                            with contextlib.suppress(Exception):
                                previous_engine.close()
                            manager_module.logger.info(
                                "Switched '%s' from %s to %s",
                                model_id,
                                previous_device,
                                self.devices[model_id],
                            )
                            self.emit_event(
                                "info",
                                f"Switched {cfg.name} from {previous_device} "
                                f"to {self.devices[model_id]}",
                            )
                        else:
                            manager_module.logger.info(
                                "Loaded '%s' on %s",
                                model_id,
                                self.devices[model_id],
                            )
                            self.emit_event(
                                "info",
                                f"Loaded {cfg.name} on {self.devices[model_id]}",
                            )

                        self._set_progress(
                            model_id,
                            "ready",
                            f"{cfg.name} is ready on {self.devices[model_id]}.",
                            percent=100,
                        )
                        self._clear_status(model_id)
                        return
                finally:
                    if replacement is not None:
                        with contextlib.suppress(Exception):
                            replacement.close()
                    if model_lock is not None and model_lock.locked():
                        model_lock.release()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - surfaced through model status
            message = errors.format_model_load_error(exc)
            existing = self.engines.get(model_id)
            if existing is not None:
                existing_device = device_check.normalize_device(existing.device)
                self._clear_status(model_id)
                self._set_progress(
                    model_id,
                    "ready",
                    f"Could not switch {cfg.name} to {current_device}. "
                    f"Continuing on {existing_device}. {message}",
                    percent=100,
                )
                manager_module.logger.warning(
                    "Failed to switch '%s' to %s; retained %s: %s",
                    model_id,
                    current_device,
                    existing_device,
                    message,
                )
                self.emit_event(
                    "warning",
                    f"Could not switch {cfg.name} to {current_device}; "
                    f"continuing on {existing_device}",
                )
            else:
                self.engines.pop(model_id, None)
                self.locks.pop(model_id, None)
                self.devices.pop(model_id, None)
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
        targets[model_id] = target_device

        # A new attempt must not inherit elapsed time or a nearly-complete progress
        # bar from a previous failed/finished attempt.
        self._clear_progress(model_id)
        self._set_status(model_id, "queued")
        if loaded_engine is not None:
            loaded_device = device_check.normalize_device(loaded_engine.device)
            message = (
                f"Queued {cfg.name} to switch from {loaded_device} to {target_device}. "
                f"The current model remains available until the replacement is ready."
            )
        else:
            message = f"Queued {cfg.name} to load on {target_device}…"
        self._set_progress(model_id, "queued", message)

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
