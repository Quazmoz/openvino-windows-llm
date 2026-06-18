#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"
MODEL_ID=""
LOAD_AFTER=0

usage() {
    cat <<'EOF'
Convert a catalog model to OpenVINO IR on Ubuntu.

Usage:
  ./setup/convert_model.sh --id <model_id> [--load-after]

Options:
  --id <model_id>   Model id from models.json.
  --load-after      Accepted for compatibility; the current CLI converter does not auto-load.
  -h, --help        Show this help.

Example:
  ./setup/convert_model.sh --id tinyllama-1.1b-chat-fp16
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --id)
            if [ "$#" -lt 2 ]; then
                echo "ERROR: --id requires a model id." >&2
                exit 1
            fi
            MODEL_ID="$2"
            shift 2
            ;;
        --load-after)
            LOAD_AFTER=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [ -z "$MODEL_ID" ]; then
    echo "ERROR: --id <model_id> is required." >&2
    usage >&2
    exit 1
fi

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ERROR: venv not found. Run ./setup.sh first." >&2
    exit 1
fi

cd "$REPO_ROOT"
"$VENV_PYTHON" -m runtime.model_converter --id "$MODEL_ID"

if [ "$LOAD_AFTER" -eq 1 ]; then
    echo
    echo "--load-after was requested, but the current CLI converter does not auto-load models."
    echo "Start the server after conversion with:"
    echo "  ./start_server.sh --model $MODEL_ID --device CPU"
fi
