# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T16:12:39.169035+00:00`
- Profile: `full`
- Model: `tinyllama-1.1b-chat-int4`
- Device: `AUTO`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 29.8 ms | version=0.6.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 2.6 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 51.9 ms | catalog=21 |
| Model load | **PASS** | 24230.3 ms | loaded on AUTO |
| Open WebUI chat | **PASS** | 721.2 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 680.8 ms | events=49 |
| Stream cancellation recovery | **PASS** | 1275.5 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 2104.2 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 109.8 ms | requests=5 |
| n8n Responses API | **PASS** | 1383.8 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 2832.1 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1561.8 ms | loaded on AUTO |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
