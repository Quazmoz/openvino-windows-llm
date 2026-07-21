"""OpenVINO Windows LLM application package.

A Windows-first, OpenAI-compatible local LLM and VLM server built on OpenVINO
GenAI. Pure request/response logic remains importable in mock mode without an
OpenVINO runtime.
"""

__version__ = "0.2.1"

__all__ = [
    "__version__",
    "body_limit",
    "chat_format",
    "config",
    "errors",
    "model_load_target",
    "model_manager",
    "model_registry",
    "multimodal",
    "openai_api",
    "rate_limit",
    "server",
    "telemetry",
    "tools",
    "ui_extension",
]


def _install_runtime_extensions() -> None:
    # Install after the package version is defined. The installer imports and
    # patches ModelManager once, before server/application instances are created.
    from app.model_load_target import install_model_load_target_routing

    install_model_load_target_routing()


_install_runtime_extensions()
del _install_runtime_extensions
