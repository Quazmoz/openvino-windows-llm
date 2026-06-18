# Experimental Ubuntu Support

Linux support is experimental and currently targets Ubuntu only.

This repository remains Windows-first. Ubuntu support is intended as a basic, early path for developers who want to try the Python/FastAPI/OpenVINO stack on Ubuntu while keeping CPU inference as the first validation target.

## Expected Baseline

- Ubuntu 22.04 or 24.04 is expected.
- Python 3.11, 3.12, or 3.13 is expected.
- CPU inference is the recommended first path.
- GPU/NPU can work only when the system has compatible Intel hardware and Linux drivers.
- Ubuntu GPU/NPU support is experimental and hardware/driver-dependent.

## Install

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

git clone https://github.com/Quazmoz/openvino-windows-llm.git
cd openvino-windows-llm
chmod +x setup.sh start_server.sh setup/*.sh
./setup.sh --minimal
```

If Ubuntu 22.04 only provides Python 3.10 from `python3`, install a supported Python 3.11-3.13 interpreter and pass it explicitly:

```bash
./setup.sh --minimal --python python3.11
```

## Device Check

```bash
./start_server.sh --check-devices
```

Device visibility is determined by OpenVINO. If OpenVINO does not list a device, the app cannot use it.

## Model Conversion

Install conversion dependencies and convert a catalog model:

```bash
./setup.sh
./setup/convert_model.sh --id tinyllama-1.1b-chat-fp16
```

Gated Hugging Face models require accepting the model terms and configuring `HF_TOKEN` in `.env` or your shell.

## Start The Server

```bash
./start_server.sh --model tinyllama-1.1b-chat-fp16 --device CPU
./start_server.sh --check-devices
./start_server.sh --mock
```

Open the built-in UI at http://localhost:8000.

## Open WebUI

```text
API Base URL: http://localhost:8000/v1
API Key:      sk-dummy unless OV_LLM_API_KEY is set
```

## Driver Caveats

- CPU should work once the Python/OpenVINO packages install.
- GPU requires Intel's Linux GPU runtime/driver stack and render-device permissions.
- NPU requires Intel's NPU Linux driver, supported hardware, and a compatible kernel.
- Do not assume NPU availability on every Ubuntu machine, even when `lspci` shows an AI/NPU-like device.
- GPU/NPU validation should start with `./start_server.sh --check-devices`.

## Troubleshooting

- Permission denied on scripts: run `chmod +x setup.sh start_server.sh setup/*.sh`.
- Missing venv: run `./setup.sh --minimal`.
- OpenVINO sees only CPU: install or verify Intel GPU/NPU drivers, then rerun `./start_server.sh --check-devices`.
- Import errors: remove and recreate `.venv`, then rerun setup.
- Hugging Face gated models: set `HF_TOKEN=hf_...` in `.env` after accepting the model license.
- Corporate TLS/proxy: set `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, and/or `HTTPS_PROXY` before installing dependencies or converting models.
