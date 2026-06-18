# Quickstart

This is the shortest path to get the server up and running on Windows with an OpenVINO model.

## Requirements

- **OS**: Windows 11
- **Python**: 3.11, 3.12, or 3.13
- **Hardware**: Intel CPU (Intel GPU/NPU supported if drivers are installed)

> [!TIP]
> If `python` or `py` opens the Microsoft Store, turn off **App execution aliases** for Python in Windows Settings.

---

## 1. Install & Setup

Clone the repository and run the setup script to install all runtime and model conversion tools:

```powershell
git clone https://github.com/Quazmoz/openvino-windows-llm.git
cd openvino-windows-llm
.\setup.bat
```

*(Note: To install only runtime dependencies and skip Hugging Face conversion tools, run `.\setup.bat -Minimal` instead).*

---

## 2. Start the Server

Launch the server in mock mode to verify the stack works end-to-end without needing any model files:

```powershell
.\start_server.bat --mock
```

Now open **http://localhost:8000** in your browser. You can select the mock model and start chatting instantly!

---

## 3. Convert a Catalog Model

To run real AI inference locally, convert a model from Hugging Face into the local OpenVINO IR format. Let's export TinyLlama:

```powershell
.\setup\convert_model.ps1 -Id tinyllama-1.1b-chat-fp16
```

> [!IMPORTANT]
> **Converting Gated Models (e.g. Gemma 2, Llama 3.2, Llama 3.1)**:
> 1. **Accept License Terms**: Visit the model's repository on [Hugging Face](https://huggingface.co) and accept the license terms.
> 2. **Set Access Token**: Generate a token in [Hugging Face Settings](https://huggingface.co/settings/tokens) and configure it in your `.env` file (`HF_TOKEN=your_token`).
> 
> *Tip: The setup script (`setup.bat`) automatically checks for an active Hugging Face CLI cache token to copy to `.env` or prompts you to enter one interactively.*

---

## 4. Run Local Inference

Run the server with your newly converted model on your choice of device (e.g. NPU, GPU, or CPU):

```powershell
# Run on Intel NPU
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device NPU

# Fallback to CPU if NPU is not available or drivers are outdated
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device CPU
```

Open **http://localhost:8000** to chat!

---

## Useful Commands

- **List catalog models**: `.\start_server.bat --list`
- **Show detected hardware**: `.\start_server.bat --check-devices`
- **Run tests (mock mode)**:
  ```powershell
  .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
  .venv\Scripts\python.exe -m pytest
  ```
