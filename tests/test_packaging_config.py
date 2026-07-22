from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_pyinstaller_is_windowed_one_directory_and_collects_openvino():
    spec = (ROOT / "packaging" / "openvino_windows_llm.spec").read_text(encoding="utf-8")
    assert "console=False" in spec
    assert "COLLECT(" in spec
    assert 'collect_all("openvino")' not in spec
    assert '("openvino", "openvino_genai")' in spec
    assert "models.json" in spec
    assert "web" in spec
    assert "runtime_hook.py" in spec


def test_windowed_runtime_hook_restores_redirected_child_streams():
    hook = (ROOT / "packaging" / "runtime_hook.py").read_text(encoding="utf-8")
    assert 'os.dup(descriptor)' in hook
    assert '_restore_output("stdout", 1)' in hook
    assert '_restore_output("stderr", 2)' in hook


def test_installer_is_per_user_and_preserves_data_by_default():
    script = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in script
    assert "{localappdata}\\Programs\\OpenVINOWindowsLLM" in script
    assert "Create a desktop shortcut" in script
    assert "IDYES" in script
    assert "DelTree" in script


def test_build_script_generates_checksums_and_unsigned_names():
    script = (ROOT / "scripts" / "build_windows_distribution.ps1").read_text(encoding="utf-8")
    assert "Get-FileHash" in script
    assert "SHA256" in script
    assert '"unsigned"' in script
    assert "OV_LLM_SIGN_CERT_SHA1" in script
