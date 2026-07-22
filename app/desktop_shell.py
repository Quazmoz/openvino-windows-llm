"""Small native Windows shell helpers with safe non-Windows fallbacks."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def show_dialog(title: str, message: str, *, error: bool = False) -> None:
    if os.name == "nt":
        try:
            import ctypes

            flags = 0x10 if error else 0x40
            ctypes.windll.user32.MessageBoxW(None, str(message), str(title), flags)
            return
        except Exception:
            pass
    print(f"{title}: {message}", file=sys.stderr if error else sys.stdout)


def confirm_dialog(title: str, message: str) -> bool:
    if os.name == "nt":
        try:
            import ctypes

            # MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2
            result = ctypes.windll.user32.MessageBoxW(None, str(message), str(title), 0x24 | 0x100)
            return result == 6
        except Exception:
            pass
    return False


def open_browser(url: str) -> bool:
    return bool(webbrowser.open(str(url), new=1, autoraise=True))


def open_path(path: Path) -> bool:
    target = Path(path).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return True
    except OSError:
        return False


def copy_to_clipboard(text: str) -> None:
    if os.name != "nt":
        raise RuntimeError("Clipboard integration is only available in the Windows desktop build.")

    import ctypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13
    payload = (str(text) + "\0").encode("utf-16-le")

    if not user32.OpenClipboard(None):
        raise RuntimeError("The Windows clipboard is currently unavailable.")
    handle = None
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
        if not handle:
            raise RuntimeError("Windows could not allocate clipboard memory.")
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise RuntimeError("Windows could not lock clipboard memory.")
        try:
            ctypes.memmove(pointer, payload, len(payload))
        finally:
            kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise RuntimeError("Windows could not write to the clipboard.")
        handle = None
    finally:
        if handle:
            kernel32.GlobalFree(handle)
        user32.CloseClipboard()
