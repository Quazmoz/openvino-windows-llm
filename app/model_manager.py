"""Hardware-advised extension of the core model lifecycle manager.

The original lifecycle implementation is retained verbatim in
:mod:`app.model_manager_core`. This thin subclass adds conservative hardware
preflight metadata, profile-based ``model=auto`` routing, and a short benchmark
after successful real-hardware loads.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app import model_manager_core as _core
from app import model_registry as registry
from app.config import BASE_DIR, Settings
from app.hardware_advisor import HardwareAdvisor, parse_auto_model
from app.model_manager_core import *  # noqa: F401,F403 - preserve the public module contract
from app.model_manager_core import (
    ModelManager as _CoreModelManager,
)
from app.model_manager_core import (
    NoModelsLoaded,
    UnknownModel,
)


class ModelManager(_CoreModelManager):
    """Core lifecycle manager with hardware-aware recommendation services."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.advisor = HardwareAdvisor(settings, self.catalog, force_mock=self.force_mock)
        self._install_advisor_load_hook()

    def _install_advisor_load_hook(self) -> None:
        """Observe the final composed load scheduler without replacing lifecycle guards.

        ``Settings`` installs device-authoritative and cross-operation lifecycle wrappers
        before manager instances are created. Observing the bound scheduler here keeps
        advisor measurements compatible with those newer wrappers and with future
        scheduler composition, instead of competing for the class-level ``_load_task``.
        """

        upstream_schedule_load = self.schedule_load
        observed_tasks: set[asyncio.Task[Any]] = set()

        def schedule_load_with_advisor(
            model_id: str,
            device: str | None = None,
            *,
            draft_model: str | None = None,
        ) -> asyncio.Task[Any] | None:
            cfg = self.catalog.get(model_id)
            previous_engine = self.engines.get(model_id)
            was_downloaded = bool(
                cfg is not None and (self.force_mock or registry.is_downloaded(cfg, BASE_DIR))
            )
            queued_behind_another_load = self._load_lock.locked()
            started = time.perf_counter()

            task = upstream_schedule_load(model_id, device, draft_model=draft_model)
            if task is None or cfg is None or task in observed_tasks:
                return task

            observed_tasks.add(task)

            def after_load(done: asyncio.Task[Any]) -> None:
                observed_tasks.discard(done)
                if done.cancelled():
                    return
                try:
                    done.result()
                except Exception:
                    return

                current_engine = self.engines.get(model_id)
                # Conversion tasks can be returned while a deferred load is queued, and
                # failed device switches intentionally retain the previous engine. Only
                # a newly installed engine represents a successful load worth measuring.
                if current_engine is None or current_engine is previous_engine:
                    return

                elapsed_ms = (time.perf_counter() - started) * 1000.0
                measured_load_ms = (
                    elapsed_ms
                    if was_downloaded and not queued_behind_another_load and not self.force_mock
                    else None
                )
                finalize_task = asyncio.create_task(
                    self._finalize_advisor_load(
                        model_id,
                        cfg,
                        load_time_ms=measured_load_ms,
                    ),
                    name=f"advisor-load-finalize-{model_id}",
                )
                self.advisor._tasks.add(finalize_task)
                finalize_task.add_done_callback(self.advisor._tasks.discard)

            task.add_done_callback(after_load)
            return task

        self.schedule_load = schedule_load_with_advisor  # type: ignore[method-assign]

    async def _finalize_advisor_load(
        self,
        model_id: str,
        cfg: registry.ModelConfig,
        *,
        load_time_ms: float | None,
    ) -> None:
        """Record safe local evidence without allowing advisor work to fail a load."""

        try:
            await asyncio.to_thread(self.advisor.measure_converted_size, cfg)
        except Exception:  # noqa: BLE001 - advisory evidence must not break model loading
            _core.logger.exception("Could not measure converted size for '%s'", model_id)

        try:
            self.advisor.schedule_auto_benchmark(
                self,
                model_id,
                load_time_ms=load_time_ms,
            )
        except Exception:  # noqa: BLE001 - advisory evidence must not break model loading
            _core.logger.exception("Could not schedule advisor benchmark for '%s'", model_id)

    def resolve_engine(self, model_id: str):
        text = str(model_id or "").strip()
        if text.lower().startswith("auto"):
            try:
                profile = parse_auto_model(text)
            except ValueError as exc:
                raise UnknownModel(str(exc)) from exc
            if profile is None:
                return super().resolve_engine(model_id)
            selected = self.advisor.select_loaded_model(profile, self.engines, self.devices)
            if selected is None:
                raise NoModelsLoaded(
                    f"No loaded text-generation model is available for advisor profile '{profile}'. "
                    "Load at least one compatible generation model first."
                )
            return self.engines[selected]
        return super().resolve_engine(model_id)

    def catalog_entry(self, model_id: str) -> dict[str, Any]:
        entry = super().catalog_entry(model_id)
        cfg = self.catalog[model_id]
        entry["advisor"] = self.advisor.evaluate_model(
            cfg,
            downloaded=bool(entry.get("is_downloaded")),
            loaded=bool(entry.get("is_loaded")),
            loaded_device=entry.get("device"),
        )
        return entry

    def metrics_summary(self) -> dict[str, Any]:
        summary = super().metrics_summary()
        summary["advisor"] = self.advisor.summary(self.engines, self.devices)
        return summary

    async def _convert_task(
        self,
        model_id: str,
        device: str,
        load_after: bool,
        weight_format: str | None = None,
        group_size: int | None = None,
        ratio: float | None = None,
        sym: bool | None = None,
        trust_remote_code: bool | None = None,
    ) -> None:
        await super()._convert_task(
            model_id,
            device,
            load_after,
            weight_format=weight_format,
            group_size=group_size,
            ratio=ratio,
            sym=sym,
            trust_remote_code=trust_remote_code,
        )
        cfg = self.catalog.get(model_id)
        if cfg is not None and registry.is_downloaded(cfg, BASE_DIR):
            await asyncio.to_thread(self.advisor.measure_converted_size, cfg)

    def delete(self, model_id: str) -> dict:
        cfg = self.catalog[model_id]
        result = super().delete(model_id)
        self.advisor.forget_model_size(cfg)
        return result

    def reload_catalog(self) -> None:
        super().reload_catalog()
        self.advisor.catalog = self.catalog

    async def shutdown(self) -> None:
        await self.advisor.shutdown()
        await super().shutdown()


def __getattr__(name: str):
    """Preserve access to implementation details used by existing tests/extensions."""

    return getattr(_core, name)
