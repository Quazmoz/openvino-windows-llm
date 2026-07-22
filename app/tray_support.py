"""Shared logging, state-file, and icon helpers for the desktop tray."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.tray_state import TrayPhase

APP_TITLE = "OpenVINO Windows LLM"
POLL_SECONDS = 3.0

def configure_logging(logs_dir: Path) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / "tray.log"
    root = logging.getLogger()
    if not any(getattr(handler, "baseFilename", None) == str(path) for handler in root.handlers):
        handler = RotatingFileHandler(
            path,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    return path


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def tray_icon(phase: TrayPhase):
    from PIL import Image, ImageDraw

    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    background = {
        TrayPhase.STARTING: (42, 108, 176, 255),
        TrayPhase.READY: (25, 132, 87, 255),
        TrayPhase.PREPARING: (139, 92, 26, 255),
        TrayPhase.WARNING: (176, 104, 24, 255),
        TrayPhase.ERROR: (174, 48, 48, 255),
        TrayPhase.STOPPED: (85, 91, 102, 255),
        TrayPhase.UNKNOWN: (91, 74, 132, 255),
    }[phase]
    draw.rounded_rectangle((4, 4, 60, 60), radius=15, fill=background, outline="white", width=3)
    if phase is TrayPhase.READY:
        draw.line((17, 33, 28, 44, 48, 20), fill="white", width=7, joint="curve")
    elif phase is TrayPhase.STARTING:
        draw.ellipse((17, 17, 47, 47), outline="white", width=5)
        draw.line((32, 32, 32, 21), fill="white", width=4)
        draw.line((32, 32, 43, 36), fill="white", width=4)
    elif phase is TrayPhase.PREPARING:
        for x, height in ((18, 18), (30, 30), (42, 23)):
            draw.rounded_rectangle((x, 48 - height, x + 7, 48), radius=2, fill="white")
    elif phase is TrayPhase.WARNING:
        draw.polygon(((32, 13), (53, 50), (11, 50)), outline="white", fill=None)
        draw.line((32, 25, 32, 38), fill="white", width=5)
        draw.ellipse((29, 42, 35, 48), fill="white")
    elif phase is TrayPhase.ERROR:
        draw.line((18, 18, 46, 46), fill="white", width=7)
        draw.line((46, 18, 18, 46), fill="white", width=7)
    elif phase is TrayPhase.STOPPED:
        draw.rectangle((20, 20, 44, 44), outline="white", width=6)
    else:
        draw.ellipse((16, 12, 48, 50), outline="white", width=4)
        draw.line((25, 25, 31, 19, 39, 21, 40, 28, 32, 34, 32, 39), fill="white", width=4)
        draw.ellipse((29, 44, 35, 50), fill="white")
    return image


