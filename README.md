# OpenVINO Windows LLM

A lightweight, **Windows-first local LLM server** built on **OpenVINO GenAI** for Intel
PCs. It exposes an **OpenAI-compatible API** (so Open WebUI, n8n, LangChain, Continue,
and your own agents just work) plus a built-in browser chat UI — targeting Intel
**CPU, GPU, and NPU** through OpenVINO.

> **Status: working.** The server, OpenAI-compatible API, streaming, web UI, model
> lifecycle (load/unload/delete), device discovery, conversion helper, and Windows
> setup scripts are all implemented. The full test suite (69 tests) passes against a
> built-in mock engine, so the stack runs end-to-end on any OS. Real OpenVINO
> inference runs on Windows/Intel hardware once you've converted a model.

---

## Visual Preview

### 1. Main Chat Interface
![OpenVINO Windows LLM Chat Interface](screenshots/chat_preview.png)
*Sleek, dark-mode chat interface with real-time tokens/second tracking, device indicators, and system telemetry (RAM/Disk footprint).*

### 2. Collapsible Settings & System Info
![OpenVINO Windows LLM Settings](screenshots/settings_preview.png)
*Deep control over system prompt instructions, model parameters (temperature, token limits), and loaded engine properties.*

### 3. Clean Setup & Onboarding
![OpenVINO Windows LLM Empty State](screenshots/empty_state.png)
*Simple, high-tech onboarding screen offering single-click quickstart suggestion chips that auto-run prompts.*

---

For the shortest setup path, see [QUICKSTART.md](QUICKSTART.md).

This is the successor to the older [`npu-windows`](https://github.com/Quazmoz/npu-windows)
IPEX-LLM experiment, rebuilt on a cleaner OpenVINO-native architecture.

---

## Why use this instead of...

This project is not a wrapper — `openvino_genai.LLMPipeline` is a *Python library*
(`pipe.generate("...")`), not a server. To get what's in this repo, you'd otherwise have
to build the HTTP API, streaming, multi-model lifecycle, tool-call shim, prompt budgeting,
device-error handling, a chat UI, and Windows setup yourself.

| You could instead use… | …but here's the gap this fills |
|---|---|
| **Plain OpenVINO GenAI** | It's a library, not a server. No OpenAI API, no UI, no model management, no setup flow. |
| **OpenVINO Model Server (OVMS)** | Official and powerful, but Docker/C++-heavy, no built-in chat UI, no one-command convert + catalog. This is laptop-friendly and zero-Docker. |
| **Ollama / LM Studio** | llama.cpp/GGUF-based — **no real Intel NPU path**. Intel NPU/GPU acceleration is exactly what OpenVINO does well, and what this server targets. |

**The niche:** a small, no-Docker, Windows-first, **Intel-NPU-capable**, OpenAI-compatible
local server with the UI, model conversion, catalog, and setup scripts all included.

---

## What it does

- Runs local LLMs on Windows through **OpenVINO GenAI** (CPU / GPU / NPU / AUTO)
- Serves an **OpenAI-compatible API** — `/v1/chat/completions` (streaming + non-streaming),
  `/v1/models`, `/v1/responses`
- Includes a **built-in browser chat UI** at `http://localhost:8000`
- **Model lifecycle:** discover, load, unload, delete, with background loading and
  per-model locks so requests never block and two big models don't load at once
- **Function/tool calling** via a prompt shim (OpenVINO GenAI has no native tool calling)
  with malformed-call retry
- **Actionable device errors** (e.g. "OpenVINO doesn't see the NPU — retry with `--device CPU`")
- A **conversion helper** that exports Hugging Face models to OpenVINO IR
- A chat UI with one-click catalog model conversion/loading plus a CPU / GPU / NPU device selector
- A **mock engine** that runs the entire stack (API, streaming, UI) on machines without
  OpenVINO — so you can develop/test on macOS or Linux and CI stays green everywhere
- A **mock engine** that runs the entire stack (API, streaming, UI) on machines without
  OpenVINO — so you can develop/test on macOS or Linux and CI stays green everywhere
- Optional **API-key enforcement** for shared/LAN use

### Non-goals

- Not an IPEX-LLM wrapper, not a llama.cpp/GGUF-first project, not an Apple-Silicon
  accelerator (use MLX there), not a cloud service, and **not a hardened public gateway** —
  bind to localhost unless you know what you're doing.

---

## Quick start

### 1. Setup

Clone the repository and run the setup script to create the Python virtual environment and install all server and model-conversion dependencies:

```powershell
git clone https://github.com/Quazmoz/openvino-windows-llm.git
cd openvino-windows-llm
.\setup.bat
```
*(To install only runtime dependencies and skip conversion tools, run `.\setup.bat -Minimal` instead).*

### 2. Convert a catalog model

Convert a model from Hugging Face to local OpenVINO IR format using the wrapper script:

```powershell
.\setup\convert_model.ps1 -Id tinyllama-1.1b-chat-fp16
```

### 3. Start the server

Run the server and load your model on your target hardware device:

```powershell
# Run TinyLlama on Intel NPU
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device NPU

# Fallback to CPU if needed
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device CPU
```

Open **http://localhost:8000** for the browser chat UI, or connect external API tools.

### Try it without OpenVINO (Mock Mode)

If you don't have Intel hardware or are developing on macOS/Linux, run the server with mock mode enabled:

```powershell
.\start_server.bat --mock
```

---

## CLI Options

```text
start_server.bat [args]            # activates the venv, passes args to python -m app.server

  --model <id>        Model id from models.json to auto-load on startup
  --device <dev>      CPU | GPU | NPU | AUTO
  --host <host>       Bind host (default 127.0.0.1)
  --port <port>       Bind port (default 8000)
  --mock              Force the mock engine (no OpenVINO needed)
  --list              List catalog models and exit
  --check-devices     Show the OpenVINO devices this machine sees and exit
```

---

## API Endpoints

```text
GET  /                       Built-in chat UI
GET  /health                 Liveness + mock/device/openvino/loaded-count
GET  /v1/models              OpenAI-style model list (with load status)
POST /v1/chat/completions    Chat (streaming SSE + non-streaming), tool calls
POST /v1/responses           OpenAI Responses API (used by n8n)
POST /v1/models/convert      Background-convert a catalog model, optionally auto-loading it
POST /v1/models/load         Background-load a converted model (optional device override)
POST /v1/models/unload       Unload a model and free memory
POST /v1/models/delete       Delete a model's on-disk IR directory (frees disk)
GET  /v1/devices             OpenVINO device discovery + details
GET  /v1/system/status       CPU / RAM / disk / device / model telemetry
```

### Connecting Open WebUI

```text
API Base URL: http://localhost:8000/v1          (or http://<WINDOWS-PC-IP>:8000/v1 over LAN)
API Key:      sk-dummy                           (any value, unless OV_LLM_API_KEY is set)
```

---

## Configuration

Copy `.env.example` to `.env`, or set environment variables directly:

```powershell
$env:OV_LLM_HOST        = "127.0.0.1"
$env:OV_LLM_PORT        = "8000"
$env:OV_LLM_DEVICE      = "NPU"                 # CPU | GPU | NPU | AUTO
$env:OV_LLM_MODEL       = "tinyllama-1.1b-chat-fp16" # auto-load on startup (blank = none)
$env:OV_LLM_MODELS_FILE = "models.json"
$env:OV_LLM_MODELS_DIR  = "models\openvino"
$env:OV_LLM_API_KEY     = ""                    # set => /v1/* requires Authorization: Bearer <key>
$env:OV_LLM_MOCK        = ""                     # 1 => force the mock engine
$env:HF_TOKEN           = "hf_..."              # only for converting gated models (e.g. Llama)
```

CLI flags override environment values. Paths resolve against the repo root regardless of
your working directory.

---

## Model catalog

`models.json` describes local OpenVINO IR directories. The repo ships with fifteen NPU-focused FP16 entries:

| id | model | weights | recommended device |
|---|---|---|---|
| `qwen2.5-0.5b-fp16` | Qwen2.5 0.5B Instruct | fp16 | NPU |
| `smollm2-135m-fp16` | SmolLM2 135M Instruct | fp16 | NPU |
| `smollm2-360m-fp16` | SmolLM2 360M Instruct | fp16 | NPU |
| `tinyllama-1.1b-chat-fp16` | TinyLlama 1.1B Chat | fp16 | NPU |
| `qwen2.5-1.5b-fp16` | Qwen2.5 1.5B Instruct | fp16 | NPU |
| `deepseek-r1-distill-qwen-1.5b-fp16` | DeepSeek-R1 Distill Qwen 1.5B | fp16 | NPU |
| `llama-3.2-1b-fp16` | Llama 3.2 1B Instruct (gated) | fp16 | NPU |
| `smollm2-1.7b-fp16` | SmolLM2 1.7B Instruct | fp16 | NPU |
| `gemma-2-2b-fp16` | Gemma 2 2B Instruct (gated) | fp16 | NPU |
| `qwen2.5-3b-fp16` | Qwen2.5 3B Instruct | fp16 | NPU |
| `phi-3.5-mini-fp16` | Phi-3.5 Mini Instruct | fp16 | NPU |
| `llama-3.2-3b-fp16` | Llama 3.2 3B Instruct (gated) | fp16 | NPU |
| `phi-4-mini-fp16` | Phi-4 Mini Instruct | fp16 | NPU |
| `qwen2.5-7b-fp16` | Qwen2.5 7B Instruct | fp16 | NPU |
| `llama-3.1-8b-fp16` | Llama 3.1 8B Instruct (gated) | fp16 | NPU |

A catalog entry:

```json
{
  "tinyllama-1.1b-chat-fp16": {
    "name": "TinyLlama 1.1B Chat FP16",
    "description": "Small NPU validation model for OpenVINO GenAI.",
    "backend": "openvino-genai",
    "model_path": "models/openvino/tinyllama-1.1b-chat-fp16",
    "source_model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "weight_format": "fp16",
    "recommended_device": "NPU",
    "max_context_len": 2048,
    "max_output_tokens": 512
  }
}
```

A model shows in `/v1/models` and the UI once its `model_path` directory exists locally;
`source_model` lets the converter fetch and export it by id.

---

## Project structure

```text
app/
  server.py          FastAPI app: OpenAI routes, lifecycle, CLI
  openai_api.py      Request/response models
  model_manager.py   Load/unload/delete, background loading, per-model locks
  model_registry.py  models.json loading + catalog entries
  chat_format.py     ChatML / chat-template rendering + token-budget trimming
  tools.py           Function/tool-call prompt shim + parsing + retry
  telemetry.py       CPU / RAM / disk telemetry
  errors.py          User-facing error formatting
  config.py          Env-var settings

runtime/
  openvino_engine.py OpenVINO GenAI LLMPipeline wrapper + MockEngine
  model_converter.py optimum-intel export helper (HF -> OpenVINO IR)
  device_check.py    OpenVINO device discovery + validation

web/index.html       Built-in chat UI (streaming, model picker, device selector, telemetry)
setup/*.ps1          Windows setup, hardware check, dep install, convert wrapper
models.json          Model catalog
tests/               69 tests, run against the mock engine (no OpenVINO needed)
```

---

## Development & testing

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest          # 69 tests, all on the mock engine — no Intel hardware required
ruff check .
```

The mock engine means the whole stack (API contract, streaming, tool parsing, UI) is
testable on macOS/Linux/CI. Real CPU/GPU/NPU inference is exercised manually on Windows.

---

## Troubleshooting

### Hugging Face TLS / enterprise certificates

On managed Windows networks, HF downloads can fail because Python doesn't trust the
enterprise root CA:

```powershell
pip install python-certifi-win32
# or point at the corporate root cert:
$env:REQUESTS_CA_BUNDLE = "C:\path\to\company-root-ca.pem"
$env:SSL_CERT_FILE       = "C:\path\to\company-root-ca.pem"
```

### Gated models (Llama, etc.)

1. Accept the model license on Hugging Face
2. Create a token at https://huggingface.co/settings/tokens
3. `setx HF_TOKEN hf_your_token_here` (or set it in `.env`) before converting

### Device errors

If a device fails, the server reports whether OpenVINO sees it and suggests a fallback.
Check what your machine exposes:

```powershell
.\start_server.bat --check-devices
```

If `NPU` doesn't work, retry with `--device CPU` while you sort out drivers.

### First-run conversion is slow

Conversion downloads and exports the model — much slower than server startup. It's a
separate explicit step on purpose; don't expect it to happen during boot.

---

## Security

Binds to `127.0.0.1:8000` by default. To reach it from another machine:

```powershell
.\start_server.bat --host 0.0.0.0 --port 8000
```

If you bind to the LAN: use a trusted private network, add firewall rules intentionally,
**never expose it directly to the internet**, and set `OV_LLM_API_KEY` to require
`Authorization: Bearer <key>` on every `/v1/*` request.

---

## Roadmap

**Done** — FastAPI server, `/health`, device discovery, `models.json` + registry,
`LLMPipeline` wrapper + mock engine, `/v1/models`, streaming + non-streaming
`/v1/chat/completions`, `/v1/responses`, model load/unload/delete, system status,
tool-call shim, optional API-key auth, built-in chat UI, conversion helper, Windows
setup scripts, 69 passing tests.

**Next**

- [ ] Auto-download + convert a catalog model on first load (drop the manual step)
- [ ] CPU / GPU / NPU benchmark numbers on real Intel hardware
- [ ] Documented model ↔ device compatibility matrix and known driver issues
- [ ] Open WebUI and n8n validation write-ups
- [ ] Support/diagnostics bundle command

---

## Relationship to `npu-windows`

| Area | `npu-windows` | `openvino-windows-llm` |
|---|---|---|
| Primary backend | IPEX-LLM / BigDL | OpenVINO GenAI |
| Setup style | Conda + IPEX pins | venv + OpenVINO packages |
| Model format | IPEX low-bit cache | OpenVINO IR directory |
| Runtime API | Torch-style `model.generate()` | `openvino_genai.LLMPipeline` |
| Default target | Intel NPU via IPEX | Intel CPU/GPU/NPU via OpenVINO |
| Direction | Legacy/reference | Successor project |

No legacy IPEX env vars (`IPEX_LLM_NPU_MTL`, `NPU_CONDA_ENV`) and no Torch/Transformers/
neural-compressor pin juggling for normal inference.

---

## References

- OpenVINO GenAI install: https://docs.openvino.ai/2025/get-started/install-openvino/install-openvino-genai.html
- OpenVINO GenAI inference: https://docs.openvino.ai/2025/openvino-workflow-generative/inference-with-genai.html
- Generative model preparation: https://docs.openvino.ai/2025/openvino-workflow-generative/genai-model-preparation.html
- System requirements: https://docs.openvino.ai/2025/about-openvino/release-notes-openvino/system-requirements.html
- Optimum Intel: https://github.com/huggingface/optimum-intel
- OpenVINO GenAI repo: https://github.com/openvinotoolkit/openvino.genai
- Legacy repo: https://github.com/Quazmoz/npu-windows

---

## License

MIT — see [LICENSE](LICENSE).
