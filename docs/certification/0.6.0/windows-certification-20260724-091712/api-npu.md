# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:18:57.110744+00:00`
- Profile: `full`
- Model: `tinyllama-1.1b-chat-fp16`
- Device: `NPU`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 22.9 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 14.4 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 42.6 ms | catalog=20 |
| Model load | **PASS** | 4438.1 ms | loaded on NPU |
| Open WebUI chat | **PASS** | 4128.3 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 6094.8 ms | events=44 |
| Stream cancellation recovery | **PASS** | 5588.6 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 8017.5 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 97.8 ms | requests=5 |
| n8n Responses API | **PASS** | 7881.0 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 7541.4 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 2814.8 ms | loaded on NPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
