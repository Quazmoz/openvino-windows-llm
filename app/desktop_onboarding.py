"""Desktop-only onboarding hardening around the shared orchestration service."""

from __future__ import annotations

import contextlib
import platform
import re

from app.onboarding_models import (
    ItemStatus,
    OnboardingStatusResponse,
    PreparationStage,
    SystemItem,
    SystemScanResponse,
)
from app.onboarding_service import OnboardingService, PreparationJob
from runtime import device_check

_COMPOSITE_DEVICE_KINDS = {"AUTO", "MULTI", "HETERO"}
_WINDOWS_11_MINIMUM_BUILD = 22000


def _windows_build(version: str | None) -> int | None:
    parts = re.findall(r"\d+", str(version or ""))
    if not parts:
        return None
    try:
        return int(parts[-1])
    except ValueError:
        return None


def augment_windows_scan(
    scan: SystemScanResponse,
    *,
    edition: str | None = None,
) -> SystemScanResponse:
    """Add Windows edition/build status without turning unknown values into failures."""

    os_info = dict(scan.hardware.get("os") or {})
    if str(os_info.get("system") or "").lower() != "windows":
        return scan

    if edition is None:
        try:
            edition = platform.win32_edition()
        except (AttributeError, OSError):
            edition = None
    edition = str(edition or "").strip() or None
    version = str(os_info.get("version") or "").strip()
    build = _windows_build(version)
    build_status = (
        ItemStatus.UNKNOWN
        if build is None
        else ItemStatus.READY
        if build >= _WINDOWS_11_MINIMUM_BUILD
        else ItemStatus.WARNING
    )
    build_detail = (
        "Windows build information is unavailable."
        if build is None
        else "Windows 11 is the primary supported desktop target."
        if build >= _WINDOWS_11_MINIMUM_BUILD
        else "Windows 11 build 22000 or newer is the primary supported desktop target."
    )
    additions = [
        SystemItem(
            key="windows-edition",
            label="Windows edition",
            value=edition or "Unknown",
            status=ItemStatus.READY if edition else ItemStatus.UNKNOWN,
            detail=None if edition else "Windows edition information is unavailable.",
        ),
        SystemItem(
            key="windows-build",
            label="Windows version and build",
            value=version or "Unknown",
            status=build_status,
            detail=build_detail,
        ),
    ]
    keys = {item.key for item in scan.items}
    items = [*scan.items, *(item for item in additions if item.key not in keys)]
    warnings = list(scan.warnings)
    if build is not None and build < _WINDOWS_11_MINIMUM_BUILD:
        message = "This Windows build is older than the primary Windows 11 desktop target."
        if message not in warnings:
            warnings.append(message)
    return scan.model_copy(update={"items": items, "warnings": warnings})


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
        scan = super().system_scan(refresh=refresh)
        return sanitize_system_scan(augment_windows_scan(scan))

    def recommendation(self, *, refresh: bool = False):
        snapshot = self.manager.advisor.hardware_snapshot(refresh=refresh)
        if not snapshot.get("runtime", {}).get("mock") and not snapshot.get("available_devices"):
            raise RuntimeError(
                "OpenVINO did not report a usable CPU, GPU, or NPU device. Review the runtime "
                "and driver diagnostics, then rescan before selecting a model."
            )
        return super().recommendation(refresh=refresh)

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
