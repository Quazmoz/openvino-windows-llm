"""Make the repo root importable so `import app` / `import runtime` work under pytest."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    # pyproject sets `--basetemp=.tmp/pytest`; pytest creates that leaf dir but
    # not its parent, so a fresh checkout/CI run errors unless `.tmp/` exists.
    (ROOT / ".tmp").mkdir(parents=True, exist_ok=True)
