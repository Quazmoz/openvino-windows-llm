# OpenVINO Windows LLM

A Windows-first local LLM server built around **OpenVINO GenAI** for Intel PCs. This project is intended to replace the older [`npu-windows`](https://github.com/Quazmoz/npu-windows) IPEX-LLM experiment with a cleaner OpenVINO-native architecture.

> **Status:** early successor repo. This README defines the target product, setup flow, architecture, and implementation plan. Runtime code will be added incrementally.

---

## Why this project exists

The original `npu-windows` repo proved that a local OpenAI-compatible LLM server on an Intel Windows laptop is useful, but it was tightly coupled to the IPEX-LLM / BigDL stack:

- `ipex-llm[npu]` install flow
- `ipex-npu` conda environment naming
- Torch / Transformers pins tied to IPEX compatibility
- `neural-compressor` and `setuptools` compatibility workarounds
- `IPEX_LLM_NPU_MTL` startup handling
- IPEX-specific low-bit conversion and model cache layout

This repo starts fresh with **OpenVINO GenAI as the only backend**. The goal is a simpler, cleaner, more maintainable Windows local AI server that can target Intel CPU, Intel GPU, and Intel NPU through OpenVINO devices.

---

## Goals

- Run local LLMs on Windows through OpenVINO GenAI
- Provide an OpenAI-compatible API for tools such as Open WebUI, LangChain, Continue, n8n, and custom agents
- Include a built-in browser chat UI for quick testing
- Support model discovery, local model conversion, loading, unloading, and deletion
- Prefer pre-converted OpenVINO IR models where available
- Support CPU first, then GPU/NPU device targeting where hardware and drivers allow it
- Keep setup easier than the older IPEX-based repo
- Avoid Docker for the default path
- Keep all inference local and private

---

## Non-goals

- This is **not** an IPEX-LLM wrapper.
- This is **not** a llama.cpp / GGUF-first project, although OpenVINO GenAI has some GGUF support for selected model families.
- This is **not** intended to target Apple Silicon acceleration. For Apple Silicon, MLX is usually the better native path.
- This is **not** a cloud-hosted inference service.
- This is **not** a production-secured API gateway by default. Bind locally unless you know what you are doing.

---

## Target platform

### Primary target

- Windows 11 64-bit
- Python 3.11 or 3.12
- Intel Core Ultra / Intel AI PC class hardware preferred
- OpenVINO GenAI installed through PyPI

### Target devices

OpenVINO device support depends on your hardware, installed drivers, and OpenVINO build. The planned server device selector will support:

```text
CPU
GPU
NPU
AUTO
```

Recommended bring-up order:

1. `CPU` — easiest baseline
2. `GPU` — useful if Intel GPU drivers are installed and compatible
3. `NPU` — target path for Intel NPU systems after driver validation
4. `AUTO` — convenience mode after explicit devices work

---

## Planned features

### API compatibility

Planned OpenAI-style endpoints:

```text
GET  /health
GET  /v1/models
POST /v1/chat/completions
POST /v1/responses
POST /v1/models/load
POST /v1/models/unload
POST /v1/models/delete
GET  /v1/system/status
```

Initial focus will be `/v1/chat/completions`, `/v1/models`, `/health`, and the built-in web UI.

### Built-in chat UI

The repo will include a lightweight local UI at:

```text
http://localhost:8000
```

Planned UI capabilities:

- Model selector
- Device selector display
- Streaming output
- Local conversation history
- Token / generation timing display
- Basic system telemetry
- Model load status
- Clear error messages for missing models, drivers, and incompatible devices

### Open WebUI support

Once the API is implemented, Open WebUI should be able to connect using:

```text
API Base URL: http://<WINDOWS-PC-IP>:8000/v1
API Key:      sk-dummy
```

For local-only testing:

```text
API Base URL: http://localhost:8000/v1
API Key:      sk-dummy
```

---

## Expected project structure

```text
openvino-windows-llm/
  app/
    server.py              # FastAPI entry point
    openai_api.py          # OpenAI-compatible request/response models
    model_registry.py      # models.json loading and validation
    chat_format.py         # ChatML / prompt formatting helpers
    telemetry.py           # CPU/RAM/disk/device telemetry
    errors.py              # User-facing error formatting

  runtime/
    openvino_engine.py     # OpenVINO GenAI LLMPipeline wrapper
    model_converter.py     # optimum-intel export helper
    device_check.py        # OpenVINO device discovery and validation

  web/
    index.html             # Built-in local chat UI

  setup/
    setup_all.ps1          # Full Windows setup flow
    check_hardware.ps1     # Windows / CPU / GPU / NPU checks
    install_deps.ps1       # Python dependency install
    convert_model.ps1      # Convenience wrapper for model export

  models/
    openvino/              # Local converted models; ignored by git

  models.json              # Model catalog
  requirements.txt
  requirements-convert.txt
  setup.bat
  start_server.bat
  README.md
```

---

## Quick start target flow

> These commands describe the intended flow for the first working version.

### 1. Clone the repo

```powershell
git clone https://github.com/Quazmoz/openvino-windows-llm.git
cd openvino-windows-llm
```

### 2. Create a virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### 3. Install runtime dependencies

```powershell
pip install -r requirements.txt
```

Expected core dependency:

```text
openvino-genai
```

Optional conversion dependencies:

```powershell
pip install -r requirements-convert.txt
```

Expected conversion dependencies:

```text
optimum-intel[openvino]
huggingface_hub
```

### 4. Convert a model to OpenVINO IR

OpenVINO works best with models converted to OpenVINO IR format. A small model should be used first to validate the stack.

Example:

```powershell
optimum-cli export openvino `
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 `
  --weight-format int4 `
  --trust-remote-code `
  models\openvino\tinyllama-1.1b-chat-int4
```

For a Qwen test model:

```powershell
optimum-cli export openvino `
  --model Qwen/Qwen2.5-1.5B-Instruct `
  --weight-format int4 `
  --trust-remote-code `
  models\openvino\qwen2.5-1.5b-instruct-int4
```

### 5. Start the server

```powershell
.\start_server.bat --model tinyllama-1.1b-chat --device CPU
```

Later NPU test:

```powershell
.\start_server.bat --model qwen2.5-1.5b --device NPU
```

### 6. Test the API

```powershell
curl http://localhost:8000/v1/models
```

```powershell
curl http://localhost:8000/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"tinyllama-1.1b-chat","messages":[{"role":"user","content":"Give me a one-sentence explanation of OpenVINO."}],"max_tokens":64}'
```

---

## Minimal OpenVINO GenAI runtime example

The core runtime should stay much smaller than the older IPEX implementation:

```python
import openvino_genai as ov_genai

model_path = "models/openvino/tinyllama-1.1b-chat-int4"
device = "CPU"  # CPU, GPU, NPU, AUTO

pipe = ov_genai.LLMPipeline(model_path, device)
result = pipe.generate("The benefit of local AI is", max_new_tokens=100)
print(result)
```

Streaming target:

```python
import openvino_genai as ov_genai

pipe = ov_genai.LLMPipeline(model_path, device)
streamer = lambda token: print(token, end="", flush=True)
pipe.generate("Explain Intel NPUs in simple terms.", streamer=streamer, max_new_tokens=100)
```

---

## Model catalog design

`models.json` should describe local OpenVINO model directories instead of raw IPEX/Hugging Face runtime entries.

Example:

```json
{
  "tinyllama-1.1b-chat": {
    "name": "TinyLlama 1.1B Chat INT4",
    "description": "Small first-run validation model for OpenVINO GenAI.",
    "backend": "openvino-genai",
    "model_path": "models/openvino/tinyllama-1.1b-chat-int4",
    "source_model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "weight_format": "int4",
    "recommended_device": "CPU",
    "max_context_len": 2048,
    "max_output_tokens": 512
  },
  "qwen2.5-1.5b": {
    "name": "Qwen2.5 1.5B Instruct INT4",
    "description": "Small Qwen instruct model for local OpenVINO testing.",
    "backend": "openvino-genai",
    "model_path": "models/openvino/qwen2.5-1.5b-instruct-int4",
    "source_model": "Qwen/Qwen2.5-1.5B-Instruct",
    "weight_format": "int4",
    "recommended_device": "CPU",
    "max_context_len": 2048,
    "max_output_tokens": 512
  }
}
```

---

## Environment variables

Planned environment variables:

```powershell
$env:OV_LLM_HOST = "127.0.0.1"
$env:OV_LLM_PORT = "8000"
$env:OV_LLM_DEVICE = "CPU"
$env:OV_LLM_MODEL = "tinyllama-1.1b-chat"
$env:OV_LLM_MODELS_FILE = "models.json"
$env:OV_LLM_MODELS_DIR = "models\openvino"
$env:HF_TOKEN = "hf_..."   # optional, only needed for gated Hugging Face models
```

This repo should avoid legacy IPEX-specific variables such as:

```text
IPEX_LLM_NPU_MTL
NPU_CONDA_ENV=ipex-npu
```

---

## Windows setup philosophy

The setup should be boring and repeatable:

```powershell
.\setup.bat
.\start_server.bat
```

Setup should eventually handle:

- Python version check
- venv creation
- OpenVINO GenAI install
- optional model conversion dependencies
- Hugging Face token setup
- device discovery
- helpful diagnostics bundle

Unlike the old IPEX repo, this project should not need fragile Torch / Transformers / neural-compressor pin juggling for normal runtime inference.

---

## Implementation roadmap

### Phase 1 — Foundation

- [ ] Add FastAPI server shell
- [ ] Add `/health`
- [ ] Add OpenVINO device discovery
- [ ] Add `models.json`
- [ ] Add OpenVINO GenAI `LLMPipeline` wrapper
- [ ] Add `/v1/models`
- [ ] Add basic non-streaming `/v1/chat/completions`
- [ ] Add `start_server.bat`

### Phase 2 — Usability

- [ ] Add built-in chat UI
- [ ] Add streaming responses
- [ ] Add `/v1/system/status`
- [ ] Add model load/unload flow
- [ ] Add clearer error handling for missing model directories
- [ ] Add support bundle script

### Phase 3 — Model workflow

- [ ] Add `setup/convert_model.ps1`
- [ ] Add one-command TinyLlama conversion
- [ ] Add one-command Qwen conversion
- [ ] Add Hugging Face token helper
- [ ] Add model deletion / disk cleanup
- [ ] Add conversion status documentation

### Phase 4 — OpenAI compatibility polish

- [ ] Add `/v1/responses`
- [ ] Add OpenAI-compatible streaming chunks
- [ ] Add tool/function calling prompt helper
- [ ] Add usage accounting where possible
- [ ] Add Open WebUI validation
- [ ] Add n8n validation

### Phase 5 — Device-specific validation

- [ ] CPU baseline benchmarks
- [ ] Intel GPU validation
- [ ] Intel NPU validation
- [ ] AUTO device validation
- [ ] Document known driver issues
- [ ] Document model/device compatibility matrix

---

## Relationship to `npu-windows`

| Area | `npu-windows` | `openvino-windows-llm` |
|---|---|---|
| Primary backend | IPEX-LLM / BigDL | OpenVINO GenAI |
| Setup style | Conda + IPEX pins | venv + OpenVINO packages |
| Model format | IPEX low-bit cache | OpenVINO IR model directory |
| Runtime API | Torch-style `model.generate()` | `openvino_genai.LLMPipeline` |
| Default target | Intel NPU via IPEX | Intel CPU/GPU/NPU via OpenVINO |
| Long-term direction | Legacy/reference | Successor project |

---

## Troubleshooting notes to preserve from the old project

The older project surfaced several Windows-local-AI issues that should be handled better here:

### Hugging Face TLS / enterprise certificates

Windows machines on managed networks may fail Hugging Face downloads because Python does not trust the enterprise root certificate. The new setup should include clear guidance for:

```powershell
pip install python-certifi-win32
```

or:

```powershell
$env:REQUESTS_CA_BUNDLE = "C:\path\to\company-root-ca.pem"
$env:SSL_CERT_FILE = "C:\path\to\company-root-ca.pem"
```

### Gated models

Llama and other gated models require:

1. Accepting the model license on Hugging Face
2. Creating a Hugging Face token
3. Setting `HF_TOKEN`

```powershell
$env:HF_TOKEN = "hf_your_token_here"
```

### First-run model conversion takes time

Model conversion is expected to take much longer than normal server startup. Conversion should be treated as a separate explicit step rather than hidden inside server boot.

### Device errors should be actionable

If `NPU` does not work, the server should tell the user:

- whether OpenVINO sees the NPU device
- whether the Intel NPU driver appears installed
- whether the selected model is missing or incompatible
- whether to retry with `--device CPU`

---

## Security notes

By default, the server should bind to localhost:

```text
127.0.0.1:8000
```

Only bind to the LAN when intentionally connecting from another machine:

```powershell
.\start_server.bat --host 0.0.0.0 --port 8000
```

If binding to the LAN:

- Use a trusted private network only
- Add firewall rules intentionally
- Do not expose the server directly to the internet
- Add API key enforcement before any shared/networked use

---

## Useful commands

List models:

```powershell
.\start_server.bat --list
```

Start on CPU:

```powershell
.\start_server.bat --model tinyllama-1.1b-chat --device CPU
```

Start on NPU:

```powershell
.\start_server.bat --model qwen2.5-1.5b --device NPU
```

Use a different port:

```powershell
.\start_server.bat --port 8001
```

Run diagnostics:

```powershell
.\start_server.bat --diagnose
```

---

## References

- OpenVINO GenAI install docs: https://docs.openvino.ai/2025/get-started/install-openvino/install-openvino-genai.html
- OpenVINO GenAI inference docs: https://docs.openvino.ai/2025/openvino-workflow-generative/inference-with-genai.html
- OpenVINO generative model preparation: https://docs.openvino.ai/2025/openvino-workflow-generative/genai-model-preparation.html
- OpenVINO system requirements: https://docs.openvino.ai/2025/about-openvino/release-notes-openvino/system-requirements.html
- Optimum Intel: https://github.com/huggingface/optimum-intel
- OpenVINO Toolkit: https://github.com/openvinotoolkit/openvino
- OpenVINO GenAI: https://github.com/openvinotoolkit/openvino.genai
- Legacy repo: https://github.com/Quazmoz/npu-windows

---

## License

Add a license before publishing this as a reusable open-source project. Recommended default: MIT or Apache-2.0.
