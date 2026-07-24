# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:32:17.625068+00:00`
- Profile: `full`
- Model: `qwen2.5-1.5b-fp16`
- Device: `AUTO`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 3.5 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 2.2 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 59.1 ms | catalog=20 |
| Model load | **PASS** | 26166.9 ms | loaded on AUTO |
| Open WebUI chat | **PASS** | 2987.3 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 595.4 ms | events=9 |
| Stream cancellation recovery | **PASS** | 4585.4 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 2205.9 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 103.0 ms | requests=5 |
| n8n Responses API | **PASS** | 3202.4 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 8676.8 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 2356.9 ms | loaded on AUTO |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
