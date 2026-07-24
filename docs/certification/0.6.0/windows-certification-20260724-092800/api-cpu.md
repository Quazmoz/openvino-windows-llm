# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:28:13.348254+00:00`
- Profile: `full`
- Model: `smollm2-135m-fp16`
- Device: `CPU`

**Result:** 11 passed, 1 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 19.9 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 15.2 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 39.9 ms | catalog=20 |
| Model load | **PASS** | 2324.2 ms | loaded on CPU |
| Open WebUI chat | **PASS** | 597.2 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 212.0 ms | events=16 |
| Stream cancellation recovery | **PASS** | 574.7 ms | follow-up request succeeded |
| Tool and structured-output requests | **WARN** | 516.9 ms | Requests were accepted; model/runtime did not demonstrate both optional outputs |
| Request metrics | **PASS** | 145.8 ms | requests=5 |
| n8n Responses API | **PASS** | 623.9 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 2327.7 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1239.0 ms | loaded on CPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
