# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T16:05:30.538623+00:00`
- Profile: `full`
- Model: `qwen2.5-3b-fp16`
- Device: `NPU`

**Result:** 11 passed, 0 warnings, 2 skipped, 1 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 40.2 ms | version=0.6.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 15.1 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 42.6 ms | catalog=21 |
| Model load | **PASS** | 7884.7 ms | loaded on NPU |
| Open WebUI chat | **PASS** | 9865.9 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 4599.7 ms | events=14 |
| Stream cancellation recovery | **FAIL** | 3427.2 ms | POST /v1/chat/completions returned HTTP 500: b'Internal Server Error' |
| Tool and structured-output requests | **PASS** | 8839.0 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 77.7 ms | requests=4 |
| n8n Responses API | **PASS** | 14269.5 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 22083.5 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 8621.2 ms | loaded on NPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
