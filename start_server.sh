#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$SCRIPT_DIR"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"
DEPS_MARKER="$REPO_ROOT/.deps_installed"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ERROR: virtual environment not found at $REPO_ROOT/.venv" >&2
    echo "Run setup first:" >&2
    echo "  ./setup.sh --minimal" >&2
    exit 1
fi

cd "$REPO_ROOT"

if [ ! -f "$DEPS_MARKER" ]; then
    echo "Installing runtime dependencies (first run only)..."
    "$VENV_PYTHON" -m pip install -r "$REPO_ROOT/requirements.txt"
    printf 'installed\n' > "$DEPS_MARKER"
fi

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

exec "$VENV_PYTHON" -m app.server "$@"
