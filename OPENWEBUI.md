# Open WebUI compatibility

This project exposes an OpenAI-compatible `/v1` API so Open WebUI can connect to it the same way it connects to the older [`npu-windows`](https://github.com/Quazmoz/npu-windows) server.

## Start the OpenVINO server

Start with at least one converted model loaded. Open WebUI discovers models through `/v1/models`, so a model should be loaded before you expect it to appear in the Open WebUI model selector.

```powershell
# Example: run a converted model on Intel NPU
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device NPU

# CPU fallback while debugging drivers or model conversion
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device CPU

# Mock-mode compatibility smoke test without OpenVINO hardware
.\start_server.bat --mock --model tinyllama-1.1b-chat-fp16
```

If you start the server without `--model`, use the built-in UI or API to convert/load a model first.

## Configure Open WebUI

In Open WebUI:

1. Open **Settings**.
2. Go to **Connections**.
3. Add an **OpenAI-compatible** connection.
4. Use this base URL:

```text
http://localhost:8000/v1
```

For LAN access from an Open WebUI container or another machine, use the Windows host IP:

```text
http://<WINDOWS-PC-IP>:8000/v1
```

Use any dummy API key unless `OV_LLM_API_KEY` is set. If `OV_LLM_API_KEY` is set, the Open WebUI API key must match it.

```text
API Key: sk-dummy
```

## Compatibility endpoints

Open WebUI primarily needs these endpoints:

```text
GET  /v1/models
POST /v1/chat/completions
```

This server supports both streaming and non-streaming chat completions:

```json
{
  "model": "tinyllama-1.1b-chat-fp16",
  "messages": [
    {"role": "user", "content": "What is 2+2?"}
  ],
  "stream": true
}
```

Streaming responses are emitted as OpenAI-style Server-Sent Events:

```text
data: {"id":"chatcmpl-...","object":"chat.completion.chunk",...}

data: [DONE]
```

## Quick smoke test

Run the included PowerShell compatibility check:

```powershell
.\scripts\test_openwebui_compat.ps1 -BaseUrl http://localhost:8000/v1
```

Specify a model explicitly if needed:

```powershell
.\scripts\test_openwebui_compat.ps1 `
  -BaseUrl http://localhost:8000/v1 `
  -Model tinyllama-1.1b-chat-fp16 `
  -ApiKey sk-dummy
```

The test verifies:

- `/v1/models` returns an OpenAI-style model list
- a selected model can answer `/v1/chat/completions`
- streaming responses emit `data:` chunks and end with `data: [DONE]`

## Troubleshooting

### No models show in Open WebUI

Start the server with a loaded model:

```powershell
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device NPU
```

Then refresh the Open WebUI connection/model list.

### Open WebUI can see the model but chat fails

Check the server directly:

```powershell
curl http://localhost:8000/v1/models
```

Then test a chat completion:

```powershell
curl -X POST http://localhost:8000/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"tinyllama-1.1b-chat-fp16","messages":[{"role":"user","content":"What is 2+2?"}],"stream":false}'
```

### Open WebUI is running in Docker

`localhost` from inside the Open WebUI container points to the container, not your Windows host. Use the Windows host IP address or Docker host gateway address instead.

Example:

```text
http://192.168.1.50:8000/v1
```

If binding beyond localhost, start the server with:

```powershell
.\start_server.bat --host 0.0.0.0 --port 8000 --model tinyllama-1.1b-chat-fp16 --device NPU
```

Use a trusted private network only, and set `OV_LLM_API_KEY` if exposing it over LAN.
