# Packaging and release

## Prerequisites

- Windows 11 x64-compatible build host
- Python 3.11 or newer
- Inno Setup 6 for installer output
- Adequate disk space for OpenVINO, conversion dependencies, PyInstaller analysis, and final artifacts

## Reproducible build command

```powershell
.\scripts\build_windows_distribution.ps1
```

The script installs the project with `convert` and `distribution` extras, creates third-party redistribution notices, builds a PyInstaller one-directory distribution, stages a portable ZIP, optionally compiles the Inno Setup installer, and writes SHA-256 checksums.

The build does not bundle model weights.

## Validation

After building:

```powershell
.\scripts\smoke_test_packaged.ps1 -DistributionPath .\dist\OpenVINOWindowsLLM
```

The smoke test uses the deterministic mock engine. It verifies executable startup, desktop identity, liveness, readiness, static UI, onboarding, recommendation, distinct preparation stages, benchmark completion, `/v1/models`, chat completions, Responses API, streaming, portable data paths, and controlled shutdown.

Mock validation is not CPU, GPU, or NPU certification. Run the repository Windows certification harness with mock mode disabled on suitable Intel hardware before making hardware support claims.

## Release checklist

1. Run `ruff check .`.
2. Run `ruff format --check .`.
3. Run `pytest`.
4. Run the external API contract validator in mock mode.
5. Build the directory distribution, portable ZIP, and installer.
6. Run the packaged mock smoke test.
7. Inspect artifacts for models, caches, credentials, certificates, or local paths.
8. Verify SHA-256 checksums.
9. Sign release artifacts when a legitimate certificate is available.
10. Run real Windows CPU, GPU, and NPU certification separately where supported.
