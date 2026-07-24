# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T16:08:44.463237+00:00`
- Profile: `full`
- Model: `qwen2.5-3b-fp16`
- Device: `AUTO`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 13.7 ms | version=0.6.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 14.2 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 34.1 ms | catalog=21 |
| Model load | **PASS** | 87327.7 ms | loaded on AUTO |
| Open WebUI chat | **PASS** | 5516.8 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 4130.6 ms | events=41 |
| Stream cancellation recovery | **PASS** | 7404.3 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 4415.7 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 113.1 ms | requests=5 |
| n8n Responses API | **PASS** | 6276.4 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 38065.6 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 17983.4 ms | loaded on AUTO |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
