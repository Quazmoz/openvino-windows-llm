"""Composed automatic benchmark support."""

from .auto_benchmark import AutoBenchmarkRunnerMixin
from .benchmark_store import AdvisorBenchmarkStoreMixin


class AutomaticBenchmarkMixin(AutoBenchmarkRunnerMixin, AdvisorBenchmarkStoreMixin):
    """Schedule, execute, and persist short post-load benchmarks."""

