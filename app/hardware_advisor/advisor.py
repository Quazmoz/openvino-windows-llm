"""Public hardware advisor implementation."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

from app.file_locks import path_lock

from .automatic import AutomaticBenchmarkMixin
from .estimates import EstimateMixin
from .profiles import ProfileMixin


class HardwareAdvisor(AutomaticBenchmarkMixin, ProfileMixin, EstimateMixin):
    def __init__(self, settings: Any, catalog: Mapping[str, Any], *, force_mock: bool = False) -> None:
        self.settings = settings
        self.catalog = catalog
        self.force_mock = bool(force_mock)
        self._snapshot = None
        self._snapshot_at = 0.0
        self._store_lock = path_lock(settings.benchmark_results_file)
        self._tasks: set[asyncio.Task[Any]] = set()
        self._benchmark_cache: list[dict[str, Any]] = []
        self._benchmark_cache_at = 0.0
        self._benchmark_cache_mtime_ns = -1
        self._size_cache: dict[str, tuple[float, float | None]] = {}
