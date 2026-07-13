"""OpenVINO Windows LLM - application package.

A Windows-first, OpenAI-compatible local LLM server built on OpenVINO GenAI.
The package is split so that the pure request/response logic (prompt building,
tool parsing, the model catalog) has no hard dependency on OpenVINO and can be
imported, tested, and run in mock mode on any platform.
"""

__version__ = "0.1.0"
__all__ = ["__version__", "chat_format", "config", "errors", "model_manager", "model_registry", "openai_api", "rate_limit", "server", "telemetry", "tools"]
