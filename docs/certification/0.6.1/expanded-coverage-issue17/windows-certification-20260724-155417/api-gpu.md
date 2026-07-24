# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T15:55:27.146866+00:00`
- Profile: `full`
- Model: `qwen2.5-3b-fp16`
- Device: `GPU`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 29.8 ms | version=0.6.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 2.8 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 33.9 ms | catalog=21 |
| Model load | **PASS** | 29808.4 ms | loaded on GPU |
| Open WebUI chat | **PASS** | 5526.8 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 1446.8 ms | events=14 |
| Stream cancellation recovery | **PASS** | 5765.8 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 3848.6 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 107.4 ms | requests=5 |
| n8n Responses API | **PASS** | 6522.0 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 8405.4 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 3500.0 ms | loaded on GPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
