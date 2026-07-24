# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T16:10:05.507230+00:00`
- Profile: `full`
- Model: `tinyllama-1.1b-chat-int4`
- Device: `CPU`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 13.8 ms | version=0.6.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 16.9 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 38.5 ms | catalog=21 |
| Model load | **PASS** | 3345.7 ms | loaded on CPU |
| Open WebUI chat | **PASS** | 2108.4 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 857.6 ms | events=49 |
| Stream cancellation recovery | **PASS** | 1353.3 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 3098.7 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 109.3 ms | requests=5 |
| n8n Responses API | **PASS** | 1818.8 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 3252.7 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1258.6 ms | loaded on CPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
