# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T14:45:12.131569+00:00`
- Profile: `full`
- Model: `tinyllama-1.1b-chat-fp16`
- Device: `CPU`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 15.3 ms | version=0.6.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 14.8 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 11.7 ms | catalog=20 |
| Model load | **PASS** | 71.9 ms | loaded on CPU |
| Open WebUI chat | **PASS** | 2642.3 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 2057.2 ms | events=44 |
| Stream cancellation recovery | **PASS** | 2610.0 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 5345.6 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 70.8 ms | requests=5 |
| n8n Responses API | **PASS** | 4578.6 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 3728.7 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1281.0 ms | loaded on CPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
