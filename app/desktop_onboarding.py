"""Desktop-only onboarding hardening around the shared orchestration service."""

from __future__ import annotations

import contextlib

from app.onboarding_models import (
    OnboardingStatusResponse,
    PreparationStage,
    SystemScanResponse,
)
from app.onboarding_service import OnboardingService, PreparationJob
from runtime import device_check

_COMPOSITE_DEVICE_KINDS = {"AUTO", "MULTI", "HETERO"}


def sanitize_system_scan(scan: SystemScanResponse) -> SystemScanResponse:
    """Remove machine-specific writable paths from the browser-facing scan payload."""

    hardware = dict(scan.hardware)
    disk = dict(hardware.get("disk") or {})
    disk.pop("models_dir", None)
    hardware["disk"] = disk
    return scan.model_copy(update={"hardware": hardware})


def actual_device_is_unresolved(actual_device: str | None) -> bool:
    """Return true when a benchmark did not identify one concrete OpenVINO device."""

    if not str(actual_device or "").strip():
        return True
    try:
        parsed = device_check.parse_device_expression(str(actual_device))
    except device_check.DeviceValidationError:
        return True
    return parsed.kind in _COMPOSITE_DEVICE_KINDS


class DesktopOnboardingService(OnboardingService):
    """Add packaged-desktop privacy and recovery guarantees without duplicating lifecycle logic."""

    def system_scan(self, *, refresh: bool = False) -> SystemScanResponse:
        return sanitize_system_scan(super().system_scan(refresh=refresh))

    def status(self) -> OnboardingStatusResponse:
        status = super().status()
        model_id = status.selected_model
        if not status.completed or not model_id:
            return status

        try:
            entry = self.manager.catalog_entry(model_id)
        except (KeyError, ValueError):
            entry = None
        if entry and entry.get("is_loaded"):
            return status
        if entry and entry.get("is_loading"):
            return status

        recovered = self.state_store.update(completed=False, restart_requested=True)
        return OnboardingStatusResponse(
            **recovered,
            state_recovered=True,
            recovery_message=(
                "The previously selected model did not reload successfully. Existing model files "
                "were retained and first-run setup was reopened."
            ),
        )

    def _reject_unresolved_actual_device(self, job: PreparationJob) -> None:
        if job.status != "ready" or not actual_device_is_unresolved(job.actual_device):
            return

        message = (
            "Generation succeeded, but OpenVINO did not report one concrete actual device. "
            "Choose a direct CPU, GPU, or NPU target and retry before completing setup."
        )
        with contextlib.suppress(Exception):
            self.manager.unload(job.model_id)
        self.state_store.update(
            completed=False,
            restart_requested=False,
            actual_device=None,
            last_benchmark_reference=None,
        )
        if job.benchmark is not None:
            job.benchmark = job.benchmark.model_copy(
                update={"success": False, "actual_device": None, "error": message}
            )
        job.error_detail = message
        job.terminal(
            PreparationStage.FAILED,
            message,
            error_code="actual_device_unresolved",
        )

    def progress(self, job_id: str):
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError("Unknown onboarding preparation job.")
        self._reject_unresolved_actual_device(job)
        return super().progress(job_id)

    def complete(self, job_id: str):
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError("Unknown onboarding preparation job.")
        self._reject_unresolved_actual_device(job)
        return super().complete(job_id)
