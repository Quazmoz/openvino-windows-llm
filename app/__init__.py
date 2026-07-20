"""OpenVINO Windows LLM - application package.

A Windows-first, OpenAI-compatible local LLM server built on OpenVINO GenAI.
The package is split so that the pure request/response logic (prompt building,
tool parsing, the model catalog) has no hard dependency on OpenVINO and can be
imported, tested, and run in mock mode on any platform.
"""

__version__ = "0.2.0"

# The browser client intentionally remains a single checked-in HTML file.  Install a
# narrow FileResponse extension at package import time so multimodal controls can be
# added without duplicating or rewriting that large asset.
from app.ui_extension import install_ui_extension

install_ui_extension()

__all__ = [
    "__version__",
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
