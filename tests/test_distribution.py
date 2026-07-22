import pytest

from app.distribution import artifact_names, signing_configuration, validate_version


def test_artifact_names_are_versioned_and_truthful():
    unsigned = artifact_names("0.3.0", signed=False)
    signed = artifact_names("0.3.0", signed=True)
    assert unsigned["portable"].endswith("portable-unsigned.zip")
    assert unsigned["installer"].endswith("setup-unsigned.exe")
    assert signed["installer"].endswith("setup-signed.exe")


def test_invalid_version_is_rejected():
    with pytest.raises(ValueError):
        validate_version("0.3")


def test_signing_requires_tool_and_certificate_without_exposing_secrets():
    disabled = signing_configuration({"OV_LLM_SIGNTOOL_PATH": "signtool.exe"})
    enabled = signing_configuration(
        {"OV_LLM_SIGNTOOL_PATH": "signtool.exe", "OV_LLM_SIGN_CERT_SHA1": "ABC123"}
    )
    assert disabled.enabled is False
    assert enabled.enabled is True
