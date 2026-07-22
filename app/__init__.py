"""OpenVINO Windows LLM application package.

A Windows-first, OpenAI-compatible local LLM and VLM server built on OpenVINO
GenAI. Pure request/response logic remains importable in mock mode without an
OpenVINO runtime.
"""

__version__ = "0.4.0"

__all__ = [
    "__version__",
    "body_limit",
    "chat_format",
    "config",
    "desktop_controller",
    "desktop_launcher",
    "desktop_operations",
    "desktop_server",
    "diagnostics",
    "errors",
    "model_manager",
    "model_registry",
    "multimodal",
    "onboarding_models",
    "onboarding_service",
    "onboarding_state",
    "openai_api",
    "paths",
    "rate_limit",
    "server",
    "startup_registration",
    "telemetry",
    "tools",
    "tray_app",
    "tray_state",
    "ui_extension",
]
