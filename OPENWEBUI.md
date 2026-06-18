# Open WebUI compatibility

This project exposes an OpenAI-compatible `/v1` API so Open WebUI can connect to it the same way it connects to the older [`npu-windows`](https://github.com/Quazmoz/npu-windows) server.

## Correct Open WebUI connection type

Use the **OpenAI API / OpenAI-compatible** connection in Open WebUI.

Do **not** point the **Ollama API** connection at this server. This project is not an Ollama server and does not implement Ollama endpoints such as `/api/tags` or `/api/chat`. If the same URL is configured under both OpenAI API and Ollama API, Open WebUI can show confusing model behavior.

Recommended setup:

```text
OpenAI API: enabled
Ollama API: disabled for this URL
Base URL:   http://localhost:8000/v1
API Key:    sk-dummy   # unless OV_LLM_API_KEY is set
```

Depending on your Open WebUI version, this may be under either **Settings > Connections** or **Admin Settings > Connections**.

## Start the OpenVINO server

Open WebUI discovers selectable models through:

```text
GET /v1/models
```

The server must be running, and the model you want to chat with should be loaded before you expect a clean Open WebUI chat experience. The built-in OpenVINO UI can convert/load models, but Open WebUI itself only acts as a chat client; it does not automatically call this project's model conversion or load endpoints.

Start with a converted model loaded:

```powershell
# Example: run a converted model on Intel NPU
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device NPU

# CPU fallback while debugging drivers or model conversion
.\start_server.bat --model tinyllama-1.1b-chat-fp16 --device CPU

# Mock-mode compatibility smoke test without OpenVINO hardware
.\start_server.bat --mock --model tinyllama-1.1b-chat-fp16
```

If you start the server without `--model`, open the built-in UI at `http://localhost:8000` and convert/load a model first, or call the model lifecycle endpoint directly:

```powershell
curl -X POST http://localhost:8000/v1/models/load `
  -H "Content-Type: application/json" `
  -d '{"model":"tinyllama-1.1b-chat-fp16","device":"NPU"}'
```

## Configure Open WebUI

In Open WebUI:

1. Open **Settings** or **Admin Settings**.
2. Go to **Connections**.
3. Add or edit an **OpenAI API** connection.
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

After saving the connection, refresh the model list. If Open WebUI still shows stale models, temporarily disable **Cache Base Model List**, save the connection again, and refresh the page.

## Multiple models in Open WebUI

Open WebUI can only choose between models that it sees from `/v1/models`.

For the legacy `npu-windows` repo, that means starting the backend with multiple models loaded, for example:

```powershell
python .\intel-npu-llm\npu_server.py --models qwen1.5-1.8b,qwen2-1.5b --port 8000
```

For this OpenVINO repo, load each model you want available before refreshing Open WebUI. You can load models from the built-in UI, or by calling `/v1/models/load` for each converted model.

Example:

```powershell
curl -X POST http://localhost:8000/v1/models/load `
  -H "Content-Type: application/json" `
  -d '{"model":"tinyllama-1.1b-chat-fp16","device":"NPU"}'

curl -X POST http://localhost:8000/v1/models/load `
  -H "Content-Type: application/json" `
  -d '{"model":"qwen2.5-0.5b-fp16","device":"NPU"}'
```

Then check what Open WebUI should see:

```powershell
curl http://localhost:8000/v1/models
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

## Kokoro / TTS note

This project and the older `npu-windows` project are LLM text-generation servers. They expose chat/model endpoints, not text-to-speech audio endpoints.

Kokoro voice generation should be configured in Open WebUI as a separate TTS/audio provider if your Open WebUI setup supports that workflow. It will not run through the `npu-windows` or `openvino-windows-llm` chat completion endpoint unless a separate TTS bridge is added, such as an OpenAI-compatible `/v1/audio/speech` service.

In other words:

```text
LLM chat:      Open WebUI -> openvino-windows-llm or npu-windows -> /v1/chat/completions
Voice / TTS:   Open WebUI -> separate Kokoro/TTS service -> audio output
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

### Only one model shows, or Open WebUI will not let you switch models

Confirm that `/v1/models` shows more than one model:

```powershell
curl http://localhost:8000/v1/models
```

If the server returns multiple models but Open WebUI still shows one, refresh the OpenAI connection, turn off **Cache Base Model List** temporarily, save the connection again, and reload Open WebUI.

Also make sure the URL is configured only under the **OpenAI API** connection, not under both OpenAI and Ollama.

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
