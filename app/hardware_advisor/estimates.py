"""Composed estimate and compatibility mixins."""

from .evidence import EvidenceMixin
from .model_estimates import ModelEstimateMixin
from .preflight import PreflightMixin
from .snapshot import SnapshotMixin


class EstimateMixin(PreflightMixin, ModelEstimateMixin, EvidenceMixin, SnapshotMixin):
    """Provide snapshots, estimates, evidence, and compatibility evaluation."""
