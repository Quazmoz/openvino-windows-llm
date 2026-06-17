"""Live model lifecycle: loading, unloading, deleting, and serving engines.

Holds all mutable runtime state (which engines are loaded on which device, the
per-model generation locks, and transient load status) and orchestrates
background loads without blocking request handling. Heavy work (building an
``LLMPipeline``) runs in a thread-pool executor, serialized so two large models
don't load into memory at once.
"""

from __future__ import annotations

import asyncio
import contextlib
import gc
import logging
import shutil
import time
from pathlib import Path

from app import errors
from app import model_registry as registry
from app.config import BASE_DIR, Settings
from runtime import device_check
from runtime.openvino_engine import BaseEngine, GenParams, GenResult, StreamHandle, create_engine

logger = logging.getLogger("ov-llm.manager")


# --- Resolution errors (mapped to HTTP status codes by the server) ---------


class ModelResolutionError(Exception):
    """Base class for failures resolving a model to a ready engine."""


class UnknownModel(ModelResolutionError):
    pass


class ModelNotLoaded(ModelResolutionError):
    pass


class ModelLoading(ModelResolutionError):
    pass


class NoModelsLoaded(ModelResolutionError):
    pass


class ModelManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.catalog: dict[str, registry.ModelConfig] = registry.load_catalog(settings.models_file)
        # OpenVINO absent or explicitly disabled -> everything runs on the mock engine.
        self.force_mock: bool = settings.force_mock or not device_check.is_openvino_available()

        self.engines: dict[str, BaseEngine] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.devices: dict[str, str] = {}
        self.load_tasks: dict[str, asyncio.Task] = {}
        self.status_overrides: dict[str, dict] = {}
        self._load_lock = asyncio.Lock()

    # --- status helpers ----------------------------------------------------

    def _set_status(self, model_id: str, status: str, error: str | None = None) -> None:
        self.status_overrides[model_id] = {
            "status": status,
            "error": error,
            "updated_at": int(time.time()),
        }

    def _clear_status(self, model_id: str) -> None:
        self.status_overrides.pop(model_id, None)

    # --- queries -----------------------------------------------------------

    def is_loaded(self, model_id: str) -> bool:
        return model_id in self.engines

    def get_lock(self, model_id: str) -> asyncio.Lock:
        return self.locks.setdefault(model_id, asyncio.Lock())

    def any_busy(self) -> bool:
        return any(lock.locked() for lock in self.locks.values())

    def loading_count(self) -> int:
        return sum(
            1
            for ov in self.status_overrides.values()
            if ov.get("status") in {"queued", "loading"}
        )

    def resolve_engine(self, model_id: str) -> BaseEngine:
        """Return the engine for a request, with sensible fallbacks.

        Raises a :class:`ModelResolutionError` subclass the server maps to a 4xx/5xx.
        """
        if model_id in self.engines:
            return self.engines[model_id]

        if model_id in self.catalog:
            override = self.status_overrides.get(model_id, {})
            if override.get("status") in {"queued", "loading"}:
                raise ModelLoading(f"Model '{model_id}' is still loading")
            raise ModelNotLoaded(f"Model '{model_id}' is not loaded")

        # Unknown id: fall back to the configured default, then any loaded model.
        default = self.settings.default_model
        if default and default in self.engines:
            return self.engines[default]
        if self.engines:
            return next(iter(self.engines.values()))
        raise NoModelsLoaded("No models are loaded")

    def config_for(self, model_id: str) -> registry.ModelConfig | None:
        return self.catalog.get(model_id)

    # --- catalog entries (UI/API) -----------------------------------------

    def catalog_entry(self, model_id: str) -> dict:
        cfg = self.catalog[model_id]
        loaded = model_id in self.engines
        override = self.status_overrides.get(model_id, {})
        status = override.get("status")
        queued = status == "queued"
        loading = status == "loading"
        error = override.get("error") if status == "error" else None
        downloaded = self.force_mock or registry.is_downloaded(cfg, BASE_DIR)
        lock = self.locks.get(model_id)
        busy = bool(lock and lock.locked())
        return registry.make_catalog_entry(
            cfg,
            loaded=loaded,
            queued=queued,
            loading=loading,
            downloaded=downloaded,
            device=self.devices.get(model_id),
            busy=busy,
            error=error,
        )

    def catalog_entries(self) -> list[dict]:
        return [self.catalog_entry(model_id) for model_id in self.catalog]

    # --- loading -----------------------------------------------------------

    def _build_engine(self, model_id: str, device: str) -> BaseEngine:
        cfg = self.catalog[model_id]
        return create_engine(
            model_id=model_id,
            model_path=str(cfg.abs_path(BASE_DIR)),
            device=device,
            max_prompt_len=cfg.max_prompt_len,
            force_mock=self.force_mock,
        )

    async def _load_task(self, model_id: str, device: str) -> None:
        cfg = self.catalog[model_id]
        try:
            async with self._load_lock:
                if model_id in self.engines:
                    self._clear_status(model_id)
                    return

                self._set_status(model_id, "loading")

                # Validate device + on-disk model for real (non-mock) loads.
                if not self.force_mock:
                    available = device_check.available_devices()
                    if not device_check.is_device_available(device, available):
                        raise RuntimeError(errors.format_device_error(device, available))
                    if not registry.is_downloaded(cfg, BASE_DIR):
                        raise RuntimeError(
                            errors.format_model_not_converted(
                                cfg.name, str(cfg.abs_path(BASE_DIR)), cfg.source_model
                            )
                        )

                loop = asyncio.get_running_loop()
                engine = await loop.run_in_executor(None, self._build_engine, model_id, device)

                self.engines[model_id] = engine
                self.locks[model_id] = asyncio.Lock()
                self.devices[model_id] = engine.device
                self._clear_status(model_id)
                logger.info("Loaded '%s' on %s", model_id, engine.device)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a status
            self.engines.pop(model_id, None)
            self.locks.pop(model_id, None)
            self.devices.pop(model_id, None)
            message = errors.format_model_load_error(exc)
            self._set_status(model_id, "error", error=message)
            logger.exception("Failed to load '%s': %s", model_id, message)

    def schedule_load(self, model_id: str, device: str | None = None) -> asyncio.Task | None:
        if model_id not in self.catalog:
            logger.warning("Refusing to load unknown model '%s'", model_id)
            return None
        if model_id in self.engines:
            self._clear_status(model_id)
            return None

        existing = self.load_tasks.get(model_id)
        if existing and not existing.done():
            return existing

        device = device_check.normalize_device(device or self.settings.device)
        self._set_status(model_id, "queued")
        task = asyncio.create_task(self._load_task(model_id, device))
        self.load_tasks[model_id] = task
        return task

    # --- unload / delete ---------------------------------------------------

    def unload(self, model_id: str) -> bool:
        engine = self.engines.pop(model_id, None)
        self.locks.pop(model_id, None)
        self.devices.pop(model_id, None)
        self._clear_status(model_id)
        if engine is None:
            return False
        with contextlib.suppress(Exception):
            engine.close()
        gc.collect()
        return True

    def delete(self, model_id: str) -> dict:
        """Delete a model's on-disk OpenVINO IR directory. Returns freed-space info."""
        from app.telemetry import dir_size_bytes

        cfg = self.catalog[model_id]
        model_dir = cfg.abs_path(BASE_DIR)
        freed = 0
        deleted = False

        if model_dir.exists():
            self._ensure_within_models_dir(model_dir)
            freed = dir_size_bytes(model_dir)
            shutil.rmtree(model_dir)
            deleted = True

        self._clear_status(model_id)
        self.load_tasks.pop(model_id, None)
        return {"deleted": deleted, "freed_bytes": freed}

    def _ensure_within_models_dir(self, path: Path) -> None:
        root = self.settings.models_dir.resolve()
        resolved = path.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"Refusing to delete a path outside {root}: {resolved}")

    # --- lifecycle ---------------------------------------------------------

    def reload_catalog(self) -> None:
        self.catalog = registry.load_catalog(self.settings.models_file)

    async def startup(self) -> None:
        if self.settings.default_model:
            if self.settings.default_model in self.catalog:
                self.schedule_load(self.settings.default_model)
            else:
                logger.warning(
                    "Default model '%s' is not in the catalog; skipping auto-load",
                    self.settings.default_model,
                )

    async def shutdown(self) -> None:
        for task in list(self.load_tasks.values()):
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for model_id in list(self.engines):
            self.unload(model_id)
        self.load_tasks.clear()
        self.status_overrides.clear()

    # --- generation bridges (sync engine -> asyncio) -----------------------

    async def generate(self, engine: BaseEngine, prompt: str, params: GenParams) -> GenResult:
        loop = asyncio.get_running_loop()
        lock = self.get_lock(engine.model_id)
        async with lock:
            return await loop.run_in_executor(None, engine.generate, prompt, params)

    async def stream(self, engine: BaseEngine, prompt: str, params: GenParams):
        """Async generator yielding text chunks; holds the model lock throughout."""
        loop = asyncio.get_running_loop()
        lock = self.get_lock(engine.model_id)
        async with lock:
            handle: StreamHandle = engine.stream(prompt, params)
            try:
                while True:
                    chunk = await loop.run_in_executor(None, handle.next_chunk)
                    if chunk is None:
                        break
                    yield chunk
                if handle.error is not None:
                    raise handle.error
            finally:
                # If the consumer stopped early (client disconnect), signal the
                # worker and wait for it to finish before releasing the lock, so a
                # later request can't call generate() on the same pipeline while a
                # stale worker is still running on it.
                handle.request_stop()
                await loop.run_in_executor(None, handle.wait_closed)
