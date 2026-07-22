# Windows installer guide

The installer is defined in `packaging/installer.iss` and targets Windows 11 x64-compatible systems.

## Installation behavior

- Per-user installation under `%LOCALAPPDATA%\Programs\OpenVINOWindowsLLM`
- No administrator rights required for the normal path
- Start Menu shortcut
- Optional desktop shortcut
- Windows uninstall entry
- Same application ID across releases for in-place upgrades
- User models and data stored outside the installation directory
- User data preserved by default during upgrades and uninstall

The application binds to `127.0.0.1`. It does not expose a public or LAN endpoint unless an operator deliberately uses the server CLI with a different host and appropriate API-key controls.

## Build

From a Windows PowerShell environment with Python 3.11 or newer and Inno Setup 6:

```powershell
.\scripts\build_windows_distribution.ps1
```

Use `-SkipInstaller` to create only the portable ZIP when Inno Setup is unavailable.

Artifacts are written to `artifacts` with deterministic versioned names. A SHA-256 manifest is generated for every release artifact.

## Upgrade and uninstall

Installer upgrades replace application files only. Mutable data remains under `%LOCALAPPDATA%\OpenVINOWindowsLLM`.

During interactive uninstall, the user is asked whether to retain downloaded models, settings, logs, and benchmarks. Preservation is the default. Silent uninstall preserves user data.
