"""Keep custom desktop models inside the configured writable model directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app import model_manager_core
from app import model_registry as registry


def install_desktop_model_path_extension() -> None:
    """Patch custom registration once so desktop catalogs never target install files."""

    cls = model_manager_core.ModelManager
    if getattr(cls, "_desktop_model_paths_installed", False):
        return

    original = cls.register_model

    def register_model(self, req: Any) -> registry.ModelConfig:
        models_file = Path(self.settings.models_file).resolve()
        models_dir = Path(self.settings.models_dir).resolve()
        desktop_catalog = (
            models_file.parent.name.lower() == "config"
            and models_dir.parent == models_file.parent.parent
        )
        if not desktop_catalog:
            return original(self, req)
        if req.model_id in self.catalog:
            raise ValueError(f"Model ID '{req.model_id}' is already registered in the catalog.")

        cfg = registry.ModelConfig(
            id=req.model_id,
            name=req.name,
            description=req.description
            or f"Custom model registered via Web UI. Source: {req.source_model}",
            backend=getattr(req, "backend", "openvino-genai"),
            model_path=str((models_dir / req.model_id).resolve()),
            source_model=req.source_model,
            weight_format=req.weight_format,
            recommended_device=req.recommended_device,
            max_context_len=req.max_context_len,
            max_output_tokens=req.max_output_tokens,
            trust_remote_code=getattr(req, "trust_remote_code", False),
        )
        self.catalog[req.model_id] = cfg
        registry.save_catalog(self.settings.models_file, self.catalog)
        self.emit_event("info", f"Registered new custom model: {cfg.name} ({cfg.id})")
        return cfg

    cls.register_model = register_model
    cls._desktop_model_paths_installed = True
