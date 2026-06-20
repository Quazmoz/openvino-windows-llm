# Quickstart

This is the shortest path to get the server running. Windows remains the primary, stable target. Linux support is experimental and currently supports Ubuntu and Fedora.

## Windows Quickstart

### Requirements

- **OS**: Windows 11
- **Python**: 3.11, 3.12, or 3.13
- **Hardware**: Intel CPU, with Intel GPU/NPU supported when OpenVINO sees the device and drivers are installed

> [!TIP]
> If `python` or `py` opens the Microsoft Store, turn off **App execution aliases** for Python in Windows Settings.

### 1. Install & Setup

```powershell
git clone https://github.com/Quazmoz/openvino-windows-llm.git
cd openvino-windows-llm
.\setup.bat
```

To install only runtime dependencies and skip Hugging Face conversion tools:

```powershell
.\setup.bat -Minimal
```

### 2. Start the Server

Launch the server in mock mode to verify the stack works end-to-end without needing model files:

```powershell
.\start_server.bat --mock
```

Open **http://localhost:8000** in your browser.

### 3. Convert a Catalog Model

```powershell
.\setup\convert_model.ps1 -Id tinyllama-1.1b-chat-fp16
```

> [!IMPORTANT]
> **Converting Gated Models (e.g. Gemma 2, Llama 3.2, Llama 3.1)**:
> 1. Accept the model license on Hugging Face.
> 2. Create a token at https://huggingface.co/settings/tokens.
> 3. Configure it in `.env` as `HF_TOKEN=your_token`.

### 4. Run Local Inference

```powershell
# Run on Intel NPU
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device NPU

# Fallback to CPU if NPU is not available or drivers are outdated
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device CPU
```

## Experimental Linux Quickstart

Linux support is experimental and currently supports Ubuntu and Fedora. CPU inference is the recommended first validation path. Linux GPU/NPU support is hardware/driver-dependent and experimental.

### Requirements

- **OS**: Ubuntu 22.04/24.04 or Fedora 40+ expected
- **Python**: 3.11, 3.12, or 3.13
- **Hardware**: CPU first; Intel GPU/NPU only with compatible Linux drivers

### 1. Install & Setup

Ubuntu:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

Fedora:

```bash
sudo dnf install -y python3 python3-pip python3-devel git
```

Then:

```bash
git clone https://github.com/Quazmoz/openvino-windows-llm.git
cd openvino-windows-llm
chmod +x setup.sh start_server.sh setup/*.sh setup/linux/*.sh
./setup.sh --minimal
```

If your `python3` is not 3.11-3.13, install a supported interpreter and pass it explicitly:

```bash
./setup.sh --minimal --python python3.11
```

### 2. Start the Server

```bash
./start_server.sh --mock
```

### 3. Convert a Catalog Model

Install conversion dependencies, then export TinyLlama:

```bash
./setup.sh
./setup/linux/convert_model.sh --id tinyllama-1.1b-chat-fp16
```

### 4. Run Local Inference

```bash
./start_server.sh --model tinyllama-1.1b-chat-fp16 --device CPU
./start_server.sh --check-devices
```

## Device modes: CPU, GPU, NPU, AUTO, and experimental multi-device routing

Use `CPU`, `GPU`, or `NPU` to run on one target. `AUTO` lets OpenVINO choose an available target, while `AUTO:NPU,GPU,CPU` and `AUTO:GPU,NPU,CPU` set explicit fallback priorities.

```powershell
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device AUTO:NPU,GPU,CPU
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device AUTO:GPU,NPU,CPU
```

Linux uses the same CLI arguments:

```bash
./start_server.sh --model tinyllama-1.1b-chat-fp16 --device CPU
```

`MULTI` and `HETERO` are experimental. They may help some throughput or graph partitioning cases, but they do not guarantee faster single-prompt generation:

```powershell
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device MULTI:NPU,GPU,CPU
```

Benchmark your own hardware before choosing an advanced mode:

```powershell
python scripts\benchmark_devices.py tinyllama-1.1b-chat-fp16 --experimental
```

## Useful Commands

- **List catalog models**: `.\start_server.bat --list` or `./start_server.sh --list`
- **Show detected hardware**: `.\start_server.bat --check-devices` or `./start_server.sh --check-devices`
- **Run tests (mock mode)**:
  ```powershell
  .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
  .venv\Scripts\python.exe -m pytest
  ```
