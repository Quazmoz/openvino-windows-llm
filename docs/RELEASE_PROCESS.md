# Production release process

Local Windows release generation is the primary workflow. GitHub Actions performs lightweight source validation, but it does not build, sign, or publish production releases automatically.

## Prerequisites

- Windows 10 2004 or newer, x64
- Python 3.11 or newer
- Git
- Inno Setup 6 when building the installer
- Windows SDK `signtool.exe` only for signed releases
- GitHub CLI only when publishing

Update `app/version.py`, add `docs/releases/<version>.md`, commit the source, and ensure the working tree is clean.

## Build

```powershell
.\scripts\build_release.ps1 -Version <version> -Channel stable -Clean -MockSmokeTest -GenerateChecksums
```

Unsigned local validation:

```powershell
.\scripts\build_release.ps1 -Version <version> -Unsigned -SkipInstaller -MockSmokeTest
```

Tests may be skipped only with the explicit `-SkipTests` flag. Dirty source is rejected unless `-AllowDirty` is supplied, and that state is recorded in the manifest.

Artifacts use deterministic names under `artifacts\release-<version>`:

```text
OpenVINO-Windows-LLM-<version>-windows-x64-installer.exe
OpenVINO-Windows-LLM-<version>-windows-x64-portable.zip
OpenVINO-Windows-LLM-<version>-checksums.txt
OpenVINO-Windows-LLM-<version>-release-manifest.json
OpenVINO-Windows-LLM-<version>-third-party-licenses.zip
OpenVINO-Windows-LLM-<version>-release-notes.md
```

The release environment installs pinned top-level requirements from `requirements/release.txt`. Each build records the fully resolved `pip list` and `pip freeze` results. This records exact release inputs without claiming byte-for-byte reproducibility across Windows SDK, Python, compiler, or timestamp changes.

## Signing

Preferred certificate-store configuration:

```powershell
$env:OV_LLM_SIGNTOOL_PATH = 'C:\Program Files (x86)\Windows Kits\10\bin\...\x64\signtool.exe'
$env:OV_LLM_SIGN_CERT_SHA1 = '<certificate thumbprint>'
$env:OV_LLM_SIGN_TIMESTAMP_URL = 'http://timestamp.digicert.com'
.\scripts\build_release.ps1 -Version <version> -Sign
```

PFX fallback:

```powershell
$env:OV_LLM_SIGN_CERTIFICATE = 'C:\secure\release-signing.pfx'
$env:OV_LLM_SIGN_CERTIFICATE_PASSWORD = '<set only in the current secure environment>'
.\scripts\build_release.ps1 -Version <version> -Sign
```

Certificates and passwords must never enter the repository or logs. The build marks an artifact signed only after `signtool verify /pa /all` succeeds. Timestamp, signing, or verification failure blocks a signed release.

## Verification

```powershell
Get-FileHash .\OpenVINO-Windows-LLM-<version>-windows-x64-installer.exe -Algorithm SHA256
python .\scripts\release_tools.py verify-checksums --path .\OpenVINO-Windows-LLM-<version>-checksums.txt
```

Mock smoke validation proves packaged contracts, not real CPU, GPU, NPU, drivers, installer upgrade behavior, or Authenticode unless those paths were separately executed.

## Publish

```powershell
.\scripts\publish_release.ps1 -Version <version> -Channel stable -DryRun
.\scripts\publish_release.ps1 -Version <version> -Channel stable
```

The publisher validates the canonical version, clean tree, expected artifact names, checksums, duplicate tag, and duplicate GitHub release before creating an annotated tag and release. Beta releases are marked pre-release.
