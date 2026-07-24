# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:28:53.493060+00:00`
- Profile: `full`
- Model: `smollm2-135m-fp16`
- Device: `AUTO`

**Result:** 11 passed, 1 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 24.1 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 2.5 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 38.5 ms | catalog=20 |
| Model load | **PASS** | 1205.4 ms | loaded on AUTO |
| Open WebUI chat | **PASS** | 494.7 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 269.6 ms | events=16 |
| Stream cancellation recovery | **PASS** | 634.6 ms | follow-up request succeeded |
| Tool and structured-output requests | **WARN** | 375.6 ms | Requests were accepted; model/runtime did not demonstrate both optional outputs |
| Request metrics | **PASS** | 96.5 ms | requests=5 |
| n8n Responses API | **PASS** | 732.2 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 3541.3 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1322.7 ms | loaded on AUTO |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
