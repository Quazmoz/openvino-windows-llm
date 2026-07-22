from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_launcher_reinstalls_when_runtime_requirements_change():
    launcher = (ROOT / "start_server.bat").read_text(encoding="utf-8")

    assert "Get-FileHash" in launcher
    assert "$env:REQ_FILE" in launcher
    assert "$env:DEPS_MARKER" in launcher
    assert "$actual -ceq $saved" in launcher
    assert 'python -m pip install -r "%REQ_FILE%"' in launcher
    assert "Dependencies installed, but their version marker could not be updated" in launcher


def test_windows_setup_records_the_installed_requirements_fingerprint():
    installer = (ROOT / "setup" / "windows" / "install_deps.ps1").read_text(
        encoding="utf-8"
    )

    assert "$RequirementsPath" in installer
    assert "$DependencyMarker" in installer
    assert "Get-FileHash -LiteralPath $RequirementsPath -Algorithm SHA256" in installer
    assert "Set-Content -LiteralPath $DependencyMarker" in installer
