# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:31:22.763433+00:00`
- Profile: `full`
- Model: `qwen2.5-1.5b-fp16`
- Device: `NPU`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 3.5 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 13.4 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 46.6 ms | catalog=20 |
| Model load | **PASS** | 18886.1 ms | loaded on NPU |
| Open WebUI chat | **PASS** | 6302.6 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 2932.7 ms | events=12 |
| Stream cancellation recovery | **PASS** | 8725.3 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 6047.3 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 72.7 ms | requests=5 |
| n8n Responses API | **PASS** | 7284.8 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 11893.8 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 4325.5 ms | loaded on NPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
