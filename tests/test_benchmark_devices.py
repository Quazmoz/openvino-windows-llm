"""Smoke tests for scripts/benchmark_devices.py.

These never require OpenVINO, real GPU/NPU hardware, internet, or model
downloads. When ``openvino_genai`` is absent (as on CI/macOS), the benchmark
must still import, parse device targets, print a result table, and exit 0 with
each device marked as a failure rather than crashing.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import benchmark_devices as bench  # noqa: E402


def test_help_exits_zero_without_openvino():
    with pytest.raises(SystemExit) as exc:
        bench.main(["--help"])
    assert exc.value.code == 0


def test_split_device_targets_simple_and_composite():
    assert bench._split_device_targets("CPU;GPU") == ["CPU", "GPU"]
    # Semicolons keep composite priorities intact.
    assert bench._split_device_targets("CPU;AUTO:NPU,GPU,CPU") == ["CPU", "AUTO:NPU,GPU,CPU"]
    # Comma form still groups the priorities that belong to a composite target.
    assert bench._split_device_targets("CPU,AUTO:NPU,GPU,CPU") == ["CPU", "AUTO:NPU,GPU,CPU"]
    # Casing/spacing is normalized through the shared parser.
    assert bench._split_device_targets("cpu; auto:npu, gpu, cpu") == ["CPU", "AUTO:NPU,GPU,CPU"]


def test_split_device_targets_rejects_invalid():
    for raw in ("CPU;BOGUS", "AUTO:NPU,,CPU", "CPU;;GPU"):
        with pytest.raises(SystemExit):
            bench._split_device_targets(raw)


def test_run_degrades_gracefully_without_hardware(tmp_path):
    """A full run against a catalog model id must not download or require hardware.

    With ``openvino_genai`` unavailable every device is reported as a failure and
    the process exits 0; if it happens to be installed **and** the model exists
    locally, the run may actually succeed — both outcomes are valid.
    """
    out = tmp_path / "bench.json"
    code = bench.main(
        [
            "tinyllama-1.1b-chat-fp16",
            "--devices",
            "CPU",
            "--json",
            str(out),
        ]
    )
    assert code == 0
    results = json.loads(out.read_text(encoding="utf-8"))
    assert len(results) == 1
    entry = results[0]
    assert entry["device"] == "CPU"
    # On machines with real OpenVINO + a local model, the run may succeed.
    # On CI or machines without hardware, it fails gracefully.
    if entry["success"]:
        assert entry.get("error") in (None, "")
    else:
        assert entry["error"]
