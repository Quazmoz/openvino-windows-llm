# Windows Support

Windows is the primary, stable target for this project.

## Common Commands

```powershell
.\setup.bat
.\start_server.bat --mock
.\start_server.bat --check-devices
.\setup\windows\convert_model.ps1 -Id tinyllama-1.1b-chat-fp16
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device NPU
```

Platform-owned setup helpers live under `setup\windows`. The older `setup\*.ps1`
paths remain compatibility wrappers.
