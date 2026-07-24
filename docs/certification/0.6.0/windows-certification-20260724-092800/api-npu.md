# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:28:41.475005+00:00`
- Profile: `full`
- Model: `smollm2-135m-fp16`
- Device: `NPU`

**Result:** 11 passed, 1 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 36.0 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 16.3 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 29.9 ms | catalog=20 |
| Model load | **PASS** | 2247.0 ms | loaded on NPU |
| Open WebUI chat | **PASS** | 724.8 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 571.1 ms | events=16 |
| Stream cancellation recovery | **PASS** | 1222.2 ms | follow-up request succeeded |
| Tool and structured-output requests | **WARN** | 929.4 ms | Requests were accepted; model/runtime did not demonstrate both optional outputs |
| Request metrics | **PASS** | 61.5 ms | requests=5 |
| n8n Responses API | **PASS** | 1576.4 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 2925.8 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1366.7 ms | loaded on NPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
