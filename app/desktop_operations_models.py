"""Typed request and response contracts for desktop operations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DesktopOperationsStatusResponse(BaseModel):
    application_version: str
    api_contract_version: str
    installation_mode: str
    controller_available: bool
    server_port: int
    live: bool
    ready: bool
    server_status: str
    active_model: dict[str, Any] | None = None
    models: list[dict[str, Any]] = Field(default_factory=list)
    preparation: dict[str, Any] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    benchmark: dict[str, Any] | None = None
    benchmark_running: bool = False
    api_key_configured: bool = False
    start_with_windows: bool = False
    data_directory: str
    last_diagnostics_export: str | None = None
    hardware_fingerprint: str | None = None
    npu_readiness: dict[str, Any] | None = None
    mock: bool = False
    warning: str | None = None
    error: str | None = None


class DiagnosticsExportResponse(BaseModel):
    status: str = "created"
    filename: str
    path: str
    included_categories: list[str]
    excluded_categories: list[str]
    collection_errors: list[str] = Field(default_factory=list)


class DesktopControlResponse(BaseModel):
    status: str
    message: str | None = None


class HardwareScanControlResponse(BaseModel):
    status: str = "complete"
    scan: dict[str, Any]


class BenchmarkControlResponse(BaseModel):
    status: str = "complete"
    benchmark: dict[str, Any]
