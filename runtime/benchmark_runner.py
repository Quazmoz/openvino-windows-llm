"""Benchmark runner compatibility layer with a shared per-file store lock."""

from __future__ import annotations

from app.file_locks import path_lock
from runtime import benchmark_runner_core as _core
from runtime.benchmark_runner_core import *  # noqa: F401,F403 - preserve public API


class BenchmarkStore(_core.BenchmarkStore):
    """JSON benchmark store serialized with advisor background writes."""

    def __init__(self, path, *, max_runs: int = 100) -> None:
        super().__init__(path, max_runs=max_runs)
        self._lock = path_lock(self.path)


# Functions defined in the retained implementation resolve this global at runtime.
_core.BenchmarkStore = BenchmarkStore


def __getattr__(name: str):
    return getattr(_core, name)


if __name__ == "__main__":  # pragma: no cover - exercised by the CLI
    raise SystemExit(_core.main())
