# Quickstart

This is the shortest path to prove the server works, then run it with a real
OpenVINO model.

## Requirements

- Windows 11
- Python 3.11, 3.12, or 3.13
- Intel CPU; Intel GPU/NPU optional but supported when OpenVINO can see them

If `python` or `py` opens the Microsoft Store or fails from a terminal, install
Python from python.org or pass the full interpreter path to setup:

```powershell
.\setup.bat -Python "C:\Users\<you>\AppData\Local\Python\pythoncore-3.13-64\python.exe"
```

You can also turn off the Windows App Execution Aliases for `python.exe` and
`py.exe` in Windows Settings.

## 1. Install

```powershell
git clone https://github.com/Quazmoz/openvino-windows-llm.git
cd openvino-windows-llm
.\setup.bat
```

For model conversion tools too:

```powershell
.\setup.bat -WithConvert
```

Setup creates `.venv`, installs `requirements.txt`, and writes `.deps_installed`
only after dependency installation succeeds.

## 2. Smoke Test Without a Model

Mock mode exercises the API and web UI without downloading or converting a model:

```powershell
.\start_server.bat --mock
```

Open:

```text
http://localhost:8000
```

Or test the API:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/v1/models
```

## 3. Convert a Small Model

OpenVINO inference needs a local OpenVINO IR model. Start with TinyLlama:

```powershell
.\.venv\Scripts\python.exe -m runtime.model_converter --id tinyllama-1.1b-chat-fp16
```

The output is written under:

```text
models\openvino\tinyllama-1.1b-chat-fp16
```

## 4. Run Real Inference

```powershell
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device NPU
```

Then open the chat UI:

```text
http://localhost:8000
```

On Intel hardware where OpenVINO reports an NPU:

```powershell
.\start_server.bat --model qwen2.5-1.5b-fp16 --device NPU
```

## Useful Checks

List catalog models:

```powershell
.\start_server.bat --list
```

Show OpenVINO devices:

```powershell
.\start_server.bat --check-devices
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```
