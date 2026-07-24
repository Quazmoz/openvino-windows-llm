# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T15:59:48.461851+00:00`
- Profile: `full`
- Model: `qwen2.5-3b-fp16`
- Device: `CPU`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 29.8 ms | version=0.6.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 2.5 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 46.6 ms | catalog=21 |
| Model load | **PASS** | 27343.8 ms | loaded on CPU |
| Open WebUI chat | **PASS** | 7311.6 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 6317.4 ms | events=49 |
| Stream cancellation recovery | **PASS** | 7688.4 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 7600.3 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 112.1 ms | requests=5 |
| n8n Responses API | **PASS** | 8556.0 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 8712.6 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1450.7 ms | loaded on CPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
