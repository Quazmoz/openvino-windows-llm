#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$SCRIPT_DIR"

MINIMAL=0
SKIP_HARDWARE_CHECK=0
PYTHON_CMD=""

usage() {
    cat <<'EOF'
OpenVINO Windows LLM - Experimental Ubuntu Setup

Usage:
  ./setup.sh [options]

Options:
  --minimal              Install runtime dependencies only.
  --skip-hardware-check  Skip Ubuntu hardware diagnostics and OpenVINO device check.
  --python <command>     Use a specific Python command, for example python3.11.
  -h, --help             Show this help.

Examples:
  ./setup.sh
  ./setup.sh --minimal
  ./setup.sh --skip-hardware-check
  ./setup.sh --python python3.11
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --minimal)
            MINIMAL=1
            shift
            ;;
        --skip-hardware-check)
            SKIP_HARDWARE_CHECK=1
            shift
            ;;
        --python)
            if [ "$#" -lt 2 ]; then
                echo "ERROR: --python requires a command." >&2
                exit 1
            fi
            PYTHON_CMD="$2"
            shift 2
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

echo "=========================================="
echo "  OpenVINO Windows LLM - Ubuntu Setup"
echo "=========================================="
echo
echo "Linux support is experimental and currently targeted only for Ubuntu."
echo
echo "Repo: $REPO_ROOT"

if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "OS: ${PRETTY_NAME:-unknown}"
    if [ "${ID:-}" != "ubuntu" ]; then
        echo "WARNING: This script is tested only for Ubuntu. Continuing best-effort."
    fi
else
    echo "WARNING: /etc/os-release was not found. Continuing best-effort."
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 was not found." >&2
    echo "On Ubuntu, install Python and venv support first:" >&2
    echo "  sudo apt update" >&2
    echo "  sudo apt install -y python3 python3-venv python3-pip git" >&2
    exit 1
fi

INSTALL_ARGS=()
if [ "$MINIMAL" -eq 0 ]; then
    INSTALL_ARGS+=(--with-convert)
fi
if [ -n "$PYTHON_CMD" ]; then
    INSTALL_ARGS+=(--python "$PYTHON_CMD")
fi

"$REPO_ROOT/setup/install_deps.sh" "${INSTALL_ARGS[@]}"

ENV_FILE="$REPO_ROOT/.env"
ENV_EXAMPLE_FILE="$REPO_ROOT/.env.example"
if [ ! -f "$ENV_FILE" ] && [ -f "$ENV_EXAMPLE_FILE" ]; then
    cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
    echo "Created .env from .env.example"
fi

TOKEN_FILE="${HOME:-}/.cache/huggingface/token"
if [ -f "$ENV_FILE" ] && [ -f "$TOKEN_FILE" ]; then
    HF_TOKEN_VALUE="$(tr -d '\r\n' < "$TOKEN_FILE")"
    if [[ "$HF_TOKEN_VALUE" == hf_* ]]; then
        if grep -Eq '^HF_TOKEN=hf_[^[:space:]#]+' "$ENV_FILE"; then
            echo "HF_TOKEN is already configured in .env"
        else
            TMP_ENV="$(mktemp)"
            awk -v token="$HF_TOKEN_VALUE" '
                BEGIN { replaced = 0 }
                replaced == 0 && $0 ~ /^HF_TOKEN=/ {
                    print "HF_TOKEN=" token
                    replaced = 1
                    next
                }
                { print }
                END {
                    if (replaced == 0) {
                        print "HF_TOKEN=" token
                    }
                }
            ' "$ENV_FILE" > "$TMP_ENV"
            mv "$TMP_ENV" "$ENV_FILE"
            echo "Configured HF_TOKEN in .env from ~/.cache/huggingface/token"
        fi
    fi
fi

if [ "$SKIP_HARDWARE_CHECK" -eq 0 ]; then
    echo
    "$REPO_ROOT/setup/check_ubuntu_hardware.sh" || {
        echo "WARNING: Ubuntu hardware diagnostics failed; continuing."
    }

    echo
    echo "OpenVINO device check:"
    if ! "$REPO_ROOT/.venv/bin/python" -m app.server --check-devices; then
        echo "WARNING: OpenVINO device check failed. CPU should be the first Ubuntu validation path."
    fi
else
    echo "Skipping hardware diagnostics and OpenVINO device check."
fi

echo
echo "=========================================="
echo "  Setup complete"
echo "=========================================="
echo
echo "Next steps:"
echo "  1. Verify the app stack without a real model:"
echo "       ./start_server.sh --mock"
echo "  2. Convert a small catalog model when conversion dependencies are installed:"
echo "       ./setup/convert_model.sh --id tinyllama-1.1b-chat-fp16"
echo "  3. Start with CPU first on Ubuntu:"
echo "       ./start_server.sh --model tinyllama-1.1b-chat-fp16 --device CPU"
echo
echo "Ubuntu GPU/NPU use is experimental and depends on compatible Intel Linux drivers."
