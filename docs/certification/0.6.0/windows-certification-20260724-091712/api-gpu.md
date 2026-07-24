# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:18:08.228117+00:00`
- Profile: `full`
- Model: `tinyllama-1.1b-chat-fp16`
- Device: `GPU`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 2.6 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 1.8 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 44.8 ms | catalog=20 |
| Model load | **PASS** | 6599.9 ms | loaded on GPU |
| Open WebUI chat | **PASS** | 1835.4 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 1752.1 ms | events=44 |
| Stream cancellation recovery | **PASS** | 2165.7 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 5147.3 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 105.7 ms | requests=5 |
| n8n Responses API | **PASS** | 3578.8 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 2845.2 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 2317.3 ms | loaded on GPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
