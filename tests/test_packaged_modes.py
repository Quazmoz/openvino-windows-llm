from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_packaged_smoke_supports_installed_and_portable_modes():
    smoke = (ROOT / "scripts" / "smoke_test_packaged.ps1").read_text(encoding="utf-8")
    release = (ROOT / "scripts" / "build_release.ps1").read_text(encoding="utf-8")

    assert '[ValidateSet("installed", "portable")]' in smoke
    assert '$IsPortable = $ExpectedMode -eq "portable"' in smoke
    assert "Installed-mode smoke test refuses a distribution containing portable.flag." in smoke
    assert "Portable-mode smoke test requires portable.flag" in smoke
    assert "$Release.installation_mode -ne $ExpectedMode" in smoke

    assert "Run installed-mode packaged mock smoke test" in release
    assert "-ExpectedMode installed" in release
    assert "Run portable packaged mock smoke test" in release
    assert "-ExpectedMode portable" in release
    assert "packaged_installed_mode_smoke_test" in release
    assert "packaged_portable_mode_smoke_test" in release
