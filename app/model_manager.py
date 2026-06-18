"""Live model lifecycle: loading, unloading, deleting, and serving engines.

Holds all mutable runtime state (which engines are loaded on which device, the
per-model generation locks, and transient load status) and orchestrates
background loads without blocking request handling. Heavy work (building an
``LLMPipeline``) runs in a thread-pool executor, serialized so two large models
don't load into memory at once.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import gc
import logging
import shutil
import sys
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
        self.convert_tasks: dict[str, asyncio.Task] = {}
        self.status_overrides: dict[str, dict] = {}
        # Cumulative per-model request metrics (since server start).
        self.metrics: dict[str, dict] = {}
        # Bounded activity log for the UI (newest last).
        self._events: collections.deque[dict] = collections.deque(maxlen=50)
        self._load_lock = asyncio.Lock()
        self._convert_lock = asyncio.Lock()

    # --- status helpers ----------------------------------------------------

    def _set_status(self, model_id: str, status: str, error: str | None = None) -> None:
        self.status_overrides[model_id] = {
            "status": status,
            "error": error,
            "updated_at": int(time.time()),
        }

    def _clear_status(self, model_id: str) -> None:
        self.status_overrides.pop(model_id, None)

    # --- activity events ---------------------------------------------------

    def _emit(self, level: str, message: str) -> None:
        """Append an event to the bounded activity log.

        *level* is ``"info"``, ``"warning"``, or ``"error"``.
        """
        self._events.append(
            {"timestamp": int(time.time()), "level": level, "message": message}
        )

    def recent_events(self) -> list[dict]:
        """Return the activity log as a plain list (oldest first)."""
        return list(self._events)

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
            if ov.get("status") in {"queued", "loading", "queued_convert", "converting"}
        )

    # --- request metrics ---------------------------------------------------

    def record_request(
        self, model_id: str, prompt_tokens: int, completion_tokens: int, latency_s: float
    ) -> None:
        """Accumulate one served request's token + latency totals for a model."""
        m = self.metrics.setdefault(
            model_id,
            {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_latency_s": 0.0},
        )
        m["requests"] += 1
        m["prompt_tokens"] += int(prompt_tokens)
        m["completion_tokens"] += int(completion_tokens)
        m["total_latency_s"] += max(float(latency_s), 0.0)

        cfg = self.catalog.get(model_id)
        name = cfg.name if cfg else model_id
        tps = round(completion_tokens / latency_s, 1) if latency_s > 0 else 0.0
        self._emit("info", f"Generated {completion_tokens} tokens using {name} ({tps} t/s)")

    def metrics_summary(self) -> dict:
        """Per-model and aggregate request metrics for the status endpoint."""
        per_model: dict[str, dict] = {}
        total_requests = total_prompt = total_completion = 0
        total_latency = 0.0
        for model_id, m in self.metrics.items():
            reqs = m["requests"]
            per_model[model_id] = {
                "requests": reqs,
                "prompt_tokens": m["prompt_tokens"],
                "completion_tokens": m["completion_tokens"],
                "avg_latency_ms": round(m["total_latency_s"] / reqs * 1000, 1) if reqs else 0.0,
            }
            total_requests += reqs
            total_prompt += m["prompt_tokens"]
            total_completion += m["completion_tokens"]
            total_latency += m["total_latency_s"]
        return {
            "totals": {
                "requests": total_requests,
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "avg_latency_ms": round(total_latency / total_requests * 1000, 1)
                if total_requests
                else 0.0,
            },
            "per_model": per_model,
        }

    def resolve_engine(self, model_id: str) -> BaseEngine:
        """Return the engine for a request, with sensible fallbacks.

        Raises a :class:`ModelResolutionError` subclass the server maps to a 4xx/5xx.
        """
        if model_id in self.engines:
            return self.engines[model_id]

        if model_id in self.catalog:
            override = self.status_overrides.get(model_id, {})
            if override.get("status") in {"queued", "loading", "queued_convert", "converting"}:
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
        converting = status in {"queued_convert", "converting"}
        error = override.get("error") if status == "error" else None
        downloaded = self.force_mock or registry.is_downloaded(cfg, BASE_DIR)
        lock = self.locks.get(model_id)
        busy = bool(lock and lock.locked())
        return registry.make_catalog_entry(
            cfg,
            loaded=loaded,
            queued=queued,
            loading=loading,
            converting=converting,
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
            cache_dir=self.settings.cache_dir,
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
                        if self.settings.auto_convert:
                            logger.info(
                                "Model '%s' not found locally. Auto-convert is enabled. Starting conversion...",
                                model_id,
                            )
                            await self._convert_task(model_id, device, load_after=False)
                            self._set_status(model_id, "loading")
                            if not registry.is_downloaded(cfg, BASE_DIR):
                                raise RuntimeError(
                                    f"Auto-conversion failed for '{cfg.name}'. Please check logs."
                                )
                        else:
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
                self._emit("info", f"Loaded {cfg.name} on {engine.device}")
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a status
            self.engines.pop(model_id, None)
            self.locks.pop(model_id, None)
            self.devices.pop(model_id, None)
            message = errors.format_model_load_error(exc)
            self._set_status(model_id, "error", error=message)
            logger.exception("Failed to load '%s': %s", model_id, message)
            self._emit("error", f"Failed to load {cfg.name}: {message}")

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

    # --- conversion --------------------------------------------------------

    async def _convert_task(self, model_id: str, device: str, load_after: bool) -> None:
        cfg = self.catalog[model_id]
        proc: asyncio.subprocess.Process | None = None
        try:
            async with self._convert_lock:
                if registry.is_downloaded(cfg, BASE_DIR):
                    self._clear_status(model_id)
                    if load_after:
                        self.schedule_load(model_id, device)
                    return

                if not cfg.source_model:
                    raise RuntimeError(f"{cfg.name} has no Hugging Face source model configured.")

                self._set_status(model_id, "converting")
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "runtime.model_converter",
                    "--id",
                    model_id,
                    cwd=str(BASE_DIR),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    output = (stderr or stdout).decode(errors="replace").strip()
                    raise RuntimeError(output or f"Conversion exited with code {proc.returncode}")

                self._clear_status(model_id)
                logger.info("Converted '%s' to %s", model_id, cfg.abs_path(BASE_DIR))
                self._emit("info", f"Converted {cfg.name} to OpenVINO IR")
                if load_after:
                    self.schedule_load(model_id, device)
        except asyncio.CancelledError:
            if proc and proc.returncode is None:
                proc.kill()
                with contextlib.suppress(Exception):
                    await proc.wait()
            raise
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a statement/status
            message = errors.format_model_convert_error(exc)
            self._set_status(model_id, "error", error=message)
            logger.exception("Failed to convert '%s': %s", model_id, message)
            self._emit("error", f"Conversion failed for {cfg.name}")

    def schedule_convert(
        self,
        model_id: str,
        device: str | None = None,
        *,
        load_after: bool = True,
    ) -> asyncio.Task | None:
        if model_id not in self.catalog:
            logger.warning("Refusing to convert unknown model '%s'", model_id)
            return None
        if model_id in self.engines:
            self._clear_status(model_id)
            return None

        existing = self.convert_tasks.get(model_id)
        if existing and not existing.done():
            return existing

        cfg = self.catalog[model_id]
        if registry.is_downloaded(cfg, BASE_DIR):
            if load_after:
                return self.schedule_load(model_id, device)
            return None

        device = device_check.normalize_device(device or self.settings.device)
        self._set_status(model_id, "queued_convert")
        task = asyncio.create_task(self._convert_task(model_id, device, load_after))
        self.convert_tasks[model_id] = task
        return task

    # --- unload / delete ---------------------------------------------------

    def unload(self, model_id: str) -> bool:
        engine = self.engines.pop(model_id, None)
        self.locks.pop(model_id, None)
        self.devices.pop(model_id, None)
        self._clear_status(model_id)
        if engine is None:
            return False
        cfg = self.catalog.get(model_id)
        name = cfg.name if cfg else model_id
        with contextlib.suppress(Exception):
            engine.close()
        gc.collect()
        self._emit("info", f"Unloaded {name}")
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
        self.convert_tasks.pop(model_id, None)
        if deleted:
            freed_gb = round(freed / (1024**3), 2)
            self._emit("info", f"Deleted {cfg.name} ({freed_gb} GB freed)")
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
        mode = "mock engine" if self.force_mock else f"device={self.settings.device}"
        self._emit("info", f"Server started ({mode}, {len(self.catalog)} models in catalog)")
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
        for task in list(self.convert_tasks.values()):
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        for model_id in list(self.engines):
            self.unload(model_id)
        self.load_tasks.clear()
        self.convert_tasks.clear()
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
