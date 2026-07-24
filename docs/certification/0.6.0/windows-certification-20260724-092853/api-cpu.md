# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:29:30.641359+00:00`
- Profile: `full`
- Model: `qwen2.5-1.5b-fp16`
- Device: `CPU`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 2.7 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 2.2 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 46.7 ms | catalog=20 |
| Model load | **PASS** | 9848.7 ms | loaded on CPU |
| Open WebUI chat | **PASS** | 3916.8 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 1085.1 ms | events=12 |
| Stream cancellation recovery | **PASS** | 3935.9 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 4569.8 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 107.3 ms | requests=5 |
| n8n Responses API | **PASS** | 2852.3 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 5494.0 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1325.1 ms | loaded on CPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
