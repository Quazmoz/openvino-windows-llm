"""Typed contracts for the desktop first-run workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemStatus(StrEnum):
    READY = "ready"
    WARNING = "warning"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class NpuState(StrEnum):
    USABLE = "usable"
    HARDWARE_PLUGIN_UNAVAILABLE = "hardware_plugin_unavailable"
    NOT_DETECTED = "not_detected"
    DRIVER_UNKNOWN = "driver_unknown"
    NOT_EXPECTED = "not_expected"
    MOCK = "mock"


class PreparationStage(StrEnum):
    PREPARING = "preparing"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    VALIDATING = "validating"
    COMPILING = "compiling"
    LOADING = "loading"
    BENCHMARKING = "benchmarking"
    READY = "ready"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SystemItem(BaseModel):
    key: str
    label: str
    status: ItemStatus
    value: str | int | float | bool | None = None
    detail: str | None = None


class SystemScanResponse(BaseModel):
    schema_version: int = 1
    generated_at: str
    fingerprint: str
    mock: bool
    items: list[SystemItem]
    hardware: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class NpuReadinessResponse(BaseModel):
    schema_version: int = 1
    state: NpuState
    usable: bool
    title: str
    explanation: str
    available_devices: list[str]
    fallback_device: str | None = None
    driver_version: str | None = None
    support_url: str
    rescan_supported: bool = True
    mock: bool = False


class RecommendationWarning(BaseModel):
    code: str
    severity: Literal["info", "warning", "blocking"]
    message: str


class ModelRecommendationResponse(BaseModel):
    schema_version: int = 1
    profile: str
    model_id: str
    model_name: str
    description: str
    requested_device: str
    expected_actual_device: str | None = None
    precision: str
    download_size_gb: float | None = None
    converted_size_gb: float | None = None
    runtime_memory_gb: float | None = None
    first_load_seconds: float | None = None
    required_free_disk_gb: float | None = None
    context_length: int
    output_tokens: int
    compatibility: Literal["compatible", "caution", "blocked"]
    fit_score: float
    reason: str
    warnings: list[RecommendationWarning] = Field(default_factory=list)
    requires_confirmation: bool = False
    license_confirmation_required: bool = True
    trust_remote_code: bool = False


class OnboardingStatusResponse(BaseModel):
    schema_version: int = 1
    completed: bool
    restart_requested: bool = False
    selected_model: str | None = None
    selected_device: str | None = None
    actual_device: str | None = None
    model_storage_location: str | None = None
    last_hardware_fingerprint: str | None = None
    last_benchmark_reference: str | None = None
    completed_app_version: str | None = None
    state_recovered: bool = False
    recovery_message: str | None = None
    rerun_scan_recommended: bool = False
    recommendation_reason: str | None = None


class PrepareModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    device: str = Field(min_length=1, max_length=160)
    model_storage_location: str | None = Field(default=None, max_length=1024)
    confirm_license: bool
    confirm_disk_requirement: bool
    acknowledge_warnings: bool = False
    trust_remote_code: bool = False

    @field_validator("device")
    @classmethod
    def no_control_characters(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or any(ord(char) < 32 for char in cleaned):
            raise ValueError("Device expression is invalid.")
        return cleaned


class PreparationStageSnapshot(BaseModel):
    stage: PreparationStage
    label: str
    status: Literal["pending", "active", "complete", "failed", "cancelled"]
    started_at: str | None = None
    finished_at: str | None = None


class BenchmarkSummary(BaseModel):
    run_id: str | None = None
    model_id: str
    requested_device: str
    actual_device: str | None = None
    load_time_ms: float | None = None
    time_to_first_token_ms: float | None = None
    tokens_sec: float | None = None
    completion_tokens: int = 0
    success: bool
    error: str | None = None
    mock: bool


class PreparationProgressResponse(BaseModel):
    schema_version: int = 1
    job_id: str
    model_id: str
    requested_device: str
    actual_device: str | None = None
    stage: PreparationStage
    stage_label: str
    status: Literal["running", "ready", "failed", "cancelled"]
    determinate: bool = False
    percent: float | None = Field(default=None, ge=0, le=100)
    message: str
    elapsed_seconds: int = 0
    can_cancel: bool = False
    can_retry: bool = False
    can_fallback_to_cpu: bool = False
    stages: list[PreparationStageSnapshot]
    safe_log_tail: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_detail: str | None = None
    benchmark: BenchmarkSummary | None = None


class CancelPreparationResponse(BaseModel):
    job_id: str
    status: Literal["cancelling", "cancelled", "not_cancellable"]
    message: str


class CompleteOnboardingRequest(BaseModel):
    job_id: str


class ConnectionConfigurationResponse(BaseModel):
    schema_version: int = 1
    chat_url: str
    base_url: str
    health_url: str
    active_model_id: str
    actual_device: str
    api_key_state: Literal["disabled", "configured"]
    api_key_placeholder: str
    openai_python: str
    environment_variables: str
    open_webui: dict[str, str]
    n8n: dict[str, str]


class RestartOnboardingResponse(BaseModel):
    completed: bool = False
    message: str
