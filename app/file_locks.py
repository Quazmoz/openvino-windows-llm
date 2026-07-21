"""Process-local locks shared by JSON stores that target the same path."""

from __future__ import annotations

import threading
from pathlib import Path

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def path_lock(path: str | Path) -> threading.RLock:
    """Return one re-entrant lock for a normalized filesystem path."""

    key = str(Path(path).expanduser().resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())
