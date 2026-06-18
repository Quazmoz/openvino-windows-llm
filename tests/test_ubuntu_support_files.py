from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ubuntu_support_scripts_exist_and_use_strict_bash():
    scripts = [
        ROOT / "setup.sh",
        ROOT / "start_server.sh",
        ROOT / "setup" / "install_deps.sh",
        ROOT / "setup" / "check_ubuntu_hardware.sh",
        ROOT / "setup" / "convert_model.sh",
    ]

    for path in scripts:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in text


def test_ubuntu_positioning_is_explicit():
    setup_text = (ROOT / "setup.sh").read_text(encoding="utf-8")
    ubuntu_doc = (ROOT / "docs" / "UBUNTU.md").read_text(encoding="utf-8")
    device_doc = (ROOT / "docs" / "DEVICE_SUPPORT.md").read_text(encoding="utf-8")

    expected = "Linux support is experimental and currently targeted only for Ubuntu."
    assert expected in setup_text
    assert "Linux support is experimental and currently targets Ubuntu only." in ubuntu_doc
    assert "Ubuntu support is experimental" in device_doc


def test_ubuntu_docs_keep_cpu_as_first_validation_target():
    ubuntu_doc = (ROOT / "docs" / "UBUNTU.md").read_text(encoding="utf-8")
    device_doc = (ROOT / "docs" / "DEVICE_SUPPORT.md").read_text(encoding="utf-8")

    assert "CPU inference is the recommended first path." in ubuntu_doc
    assert "| Ubuntu experimental | Basic target | Experimental" in device_doc
    assert "If OpenVINO does not list a device, the app cannot use it." in device_doc
