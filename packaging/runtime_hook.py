"""Restore redirected standard streams for the PyInstaller windowed executable."""

from __future__ import annotations

import os
import sys


def _restore_output(name: str, descriptor: int) -> None:
    if getattr(sys, name, None) is not None:
        return
    try:
        duplicate = os.dup(descriptor)
        stream = os.fdopen(
            duplicate,
            "w",
            buffering=1,
            encoding="utf-8",
            errors="backslashreplace",
        )
    except OSError:
        return
    setattr(sys, name, stream)


def _restore_input() -> None:
    if sys.stdin is not None:
        return
    try:
        sys.stdin = open(os.devnull, encoding="utf-8")
    except OSError:
        pass


_restore_output("stdout", 1)
_restore_output("stderr", 2)
_restore_input()
