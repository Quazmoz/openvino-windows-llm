# Packaging and release

## Prerequisites

- Windows 11 x64-compatible build host
- Python 3.11 or newer
- Inno Setup 6 for installer output
- adequate disk space for OpenVINO, conversion dependencies, PyInstaller analysis, and artifacts

## Build

```powershell
.\scripts\build_windows_distribution.ps1
```

The project dependency set includes `pystray` and Pillow for the lightweight notification-area controller. The PyInstaller specification explicitly collects pystray's dynamically selected Windows backend while retaining a one-directory, hidden-console artifact.

The build installs conversion and distribution extras, creates third-party notices, produces the directory distribution and portable ZIP, optionally compiles the installer, and writes SHA-256 checksums. No model weights are bundled.

## Validation

```powershell
.\scripts\smoke_test_packaged.ps1 -DistributionPath .\dist\OpenVINOWindowsLLM
```

The packaged mock smoke test should validate child-server startup, instance identity, loopback control-token enforcement, operations status, first-run preparation, Chat Completions, Responses API, hardware scan, short benchmark, diagnostics export, and graceful shutdown.

Source integration tests also run the tray-owned controller in headless mock mode. Neither path proves the native Windows tray icon, HKCU startup registration, packaged native DLL discovery, signing, or real CPU/GPU/NPU execution until run on Windows.

## Release checks

1. Run `ruff check .`.
2. Run `ruff format --check .`.
3. Run `pytest`.
4. Run the external mock API contract validator.
5. Build installer and portable artifacts on Windows.
6. Run packaged mock and headless-tray smoke tests.
7. Inspect a generated diagnostics ZIP for privacy leaks.
8. Verify Start with Windows enable/disable behavior in HKCU.
9. Verify tray states, menus, tooltips, crash recovery, and browser survival manually.
10. Inspect packaged OpenVINO CPU, GPU, and NPU plugins.
11. Verify checksums and Authenticode signatures.
12. Run real hardware certification before publishing device claims.
