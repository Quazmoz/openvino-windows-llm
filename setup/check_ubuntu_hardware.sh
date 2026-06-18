#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"

echo "=========================================="
echo "  Experimental Ubuntu hardware diagnostics"
echo "=========================================="
echo
echo "Linux support is experimental and currently targeted only for Ubuntu."
echo "CPU should be the first Ubuntu validation path."
echo "GPU/NPU require compatible Intel Linux drivers and may need extra system packages."
echo

echo "/etc/os-release:"
if [ -r /etc/os-release ]; then
    sed -n '1,80p' /etc/os-release
else
    echo "  not available"
fi
echo

echo "uname -a:"
uname -a || true
echo

echo "Kernel version:"
uname -r || true
echo

echo "CPU architecture:"
uname -m || true
if command -v lscpu >/dev/null 2>&1; then
    lscpu | sed -n '1,20p' || true
fi
echo

PYTHON_BIN=""
if [ -x "$VENV_PYTHON" ]; then
    PYTHON_BIN="$VENV_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
fi

echo "Python:"
if [ -n "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" --version || true
else
    echo "  python3 not found"
fi
echo

echo "Intel GPU hints:"
if [ -e /dev/dri ]; then
    echo "  /dev/dri exists:"
    ls -la /dev/dri || true
else
    echo "  /dev/dri not found. Intel GPU runtime access is not visible from this shell."
fi

GROUPS_TEXT="$(id -nG 2>/dev/null || true)"
echo "  Current user groups: ${GROUPS_TEXT:-unknown}"
if printf '%s\n' "$GROUPS_TEXT" | tr ' ' '\n' | grep -qx 'render'; then
    echo "  render group: current user is a member"
else
    echo "  WARNING: current user is not in the render group; GPU access may fail."
    echo "  Guidance only: sudo usermod -aG render,video \"$USER\""
fi
echo

PCI_OUTPUT=""
if command -v lspci >/dev/null 2>&1; then
    PCI_OUTPUT="$(lspci 2>/dev/null || true)"
    echo "lspci GPU/display entries:"
    if ! printf '%s\n' "$PCI_OUTPUT" | grep -Ei 'VGA|3D|Display' | grep -Ei 'Intel|ARC|Graphics|Xe' ; then
        echo "  no Intel GPU/display entries found by lspci"
    fi
    echo

    echo "lspci NPU/VPU/AI Boost hints:"
    if printf '%s\n' "$PCI_OUTPUT" | grep -Ei 'NPU|VPU|AI Boost|Neural|Gaussian|GNA' ; then
        echo "  NPU-like PCI entries are hints only. OpenVINO must list NPU before the app can use it."
    else
        echo "  no NPU/VPU/AI Boost hints found by lspci"
    fi
else
    echo "lspci: not installed."
    echo "Guidance only: sudo apt install -y pciutils"
fi
echo

echo "OpenVINO import and device discovery:"
if [ -n "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" - <<'PY'
import importlib.util

has_openvino = importlib.util.find_spec("openvino") is not None
has_genai = importlib.util.find_spec("openvino_genai") is not None
print(f"  openvino importable: {has_openvino}")
print(f"  openvino_genai importable: {has_genai}")

if has_openvino:
    try:
        import openvino as ov

        core = ov.Core()
        devices = list(core.available_devices)
        print("  OpenVINO available devices: " + (", ".join(devices) if devices else "(none detected)"))
        for device in devices:
            try:
                full_name = core.get_property(device, "FULL_DEVICE_NAME")
            except Exception:
                full_name = device
            print(f"    {device}: {full_name}")
    except Exception as exc:
        print(f"  OpenVINO device discovery failed: {exc}")
else:
    print("  Install requirements.txt before expecting OpenVINO device discovery.")
PY
else
    echo "  Skipped: python3 not found"
fi
echo

echo "Notes:"
echo "  - CPU should work once Python/OpenVINO packages install."
echo "  - GPU requires Intel's Linux GPU runtime/driver stack and user permissions for render devices."
echo "  - NPU requires Intel's NPU Linux driver, supported hardware, and a compatible kernel."
echo "  - If OpenVINO does not list GPU or NPU, the app cannot target that device."
echo "  - This script prints sudo commands only as guidance and does not run them."
