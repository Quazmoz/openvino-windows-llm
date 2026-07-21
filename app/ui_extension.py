"""Compose the vision and hardware-advisor browser extensions."""

from __future__ import annotations

from app import ui_extension_vision as _vision
from app.advisor_ui import ADVISOR_EXTENSION_JS
from app.ui_extension_vision import VISION_EXTENSION_JS
from app.ui_extension_vision import inject_multimodal_ui as _inject_vision_ui

__all__ = ["VISION_EXTENSION_JS", "inject_multimodal_ui"]

_ADVISOR_EXTENSION_ID = "ovllm-hardware-advisor-extension"


def inject_multimodal_ui(html: str) -> str:
    """Inject the existing multimodal controls and the hardware advisor exactly once."""

    html = _inject_vision_ui(html)
    if f'id="{_ADVISOR_EXTENSION_ID}"' in html:
        return html
    script = f'\n<script id="{_ADVISOR_EXTENSION_ID}">\n{ADVISOR_EXTENSION_JS}\n</script>\n'
    if "</body>" in html:
        return html.replace("</body>", f"{script}</body>", 1)
    return html + script


def __getattr__(name: str):
    """Forward legacy attributes to the original vision extension module."""

    return getattr(_vision, name)
