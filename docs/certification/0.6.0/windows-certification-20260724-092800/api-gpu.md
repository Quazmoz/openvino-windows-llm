# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:28:26.554090+00:00`
- Profile: `full`
- Model: `smollm2-135m-fp16`
- Device: `GPU`

**Result:** 11 passed, 1 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 14.9 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 14.9 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 37.3 ms | catalog=20 |
| Model load | **PASS** | 3384.9 ms | loaded on GPU |
| Open WebUI chat | **PASS** | 540.2 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 283.9 ms | events=16 |
| Stream cancellation recovery | **PASS** | 718.8 ms | follow-up request succeeded |
| Tool and structured-output requests | **WARN** | 470.7 ms | Requests were accepted; model/runtime did not demonstrate both optional outputs |
| Request metrics | **PASS** | 107.4 ms | requests=5 |
| n8n Responses API | **PASS** | 926.7 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 2803.4 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1227.5 ms | loaded on GPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
