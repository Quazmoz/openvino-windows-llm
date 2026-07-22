# Desktop troubleshooting

## Application does not open

Run `OpenVINOWindowsLLM.exe --diagnostic` and review `%LOCALAPPDATA%\OpenVINOWindowsLLM\logs\launcher.log` and `desktop.log`. Startup failures are also shown in a Windows dialog.

## Port conflict

The launcher tries port 8000 first and then asks Windows for an available loopback port. Connection examples in the Ready screen use the selected port rather than assuming 8000.

## Application data is not writable

Move the portable package to a writable directory or set `OV_LLM_DATA_DIR` to a writable absolute path. Do not use a protected installation directory for model storage.

## NPU not available

Use the wizard's NPU readiness explanation and official Intel support action. Rescan after changing a driver. A driver installation cannot add unsupported hardware and does not guarantee that a model works on NPU. CPU or Intel GPU remains a valid fallback when OpenVINO reports it.

## Download or conversion fails

Check network access, Hugging Face model access, accepted license terms, available disk space, and managed-network TLS inspection. Remote model code remains disabled unless the catalog entry was reviewed and the user explicitly opts in.

Incomplete conversion output is not treated as a valid model. New partial output may be moved under `diagnostics\incomplete-models` for inspection.

## Compilation or load fails

Retry, select a different OpenVINO-visible device, or use CPU fallback. A requested device is not proof of actual execution. Successful measured generation and the runtime's reported actual device are the evidence shown by the benchmark step.

## Setup state is corrupt

The unreadable state is copied to a `.corrupt` file when possible, existing models are retained, and the wizard restarts with safe defaults.
