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
