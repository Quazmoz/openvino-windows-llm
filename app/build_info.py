"""Runtime build metadata loaded from packaged release output."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.version import (
    DATA_SCHEMA_VERSION,
    MINIMUM_SUPPORTED_DATA_SCHEMA_VERSION,
    __version__,
)


class BuildInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_version: str
    source_commit: str
    build_channel: str
    build_date: datetime
    source_tree_clean: bool
    dependency_inventory_filename: str | None = None
    dependency_inventory_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    data_schema_version: int = DATA_SCHEMA_VERSION
    minimum_supported_data_schema: int = MINIMUM_SUPPORTED_DATA_SCHEMA_VERSION


def load_build_info(resource_root: Path) -> BuildInfo:
    path = resource_root / "build-info.json"
    if path.is_file():
        payload = BuildInfo.model_validate_json(path.read_text(encoding="utf-8-sig"))
        if payload.application_version != __version__:
            raise RuntimeError("Packaged build metadata does not match the application version.")
        return payload
    return BuildInfo(
        application_version=__version__,
        source_commit=os.environ.get("OV_LLM_BUILD_COMMIT", "development"),
        build_channel=os.environ.get("OV_LLM_BUILD_CHANNEL", "development"),
        build_date=datetime.now(UTC),
        source_tree_clean=False,
        dependency_inventory_filename=None,
        dependency_inventory_sha256=None,
    )
