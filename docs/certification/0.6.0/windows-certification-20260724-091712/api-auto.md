# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:19:27.981961+00:00`
- Profile: `full`
- Model: `tinyllama-1.1b-chat-fp16`
- Device: `AUTO`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 31.0 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 2.8 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 54.6 ms | catalog=20 |
| Model load | **PASS** | 7793.8 ms | loaded on AUTO |
| Open WebUI chat | **PASS** | 1699.0 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 1563.1 ms | events=44 |
| Stream cancellation recovery | **PASS** | 3005.1 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 3944.6 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 80.6 ms | requests=5 |
| n8n Responses API | **PASS** | 3245.4 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 5310.6 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1266.9 ms | loaded on AUTO |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
