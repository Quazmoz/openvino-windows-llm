# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:30:13.383087+00:00`
- Profile: `full`
- Model: `qwen2.5-1.5b-fp16`
- Device: `GPU`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 32.2 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 2.3 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 52.4 ms | catalog=20 |
| Model load | **PASS** | 20822.0 ms | loaded on GPU |
| Open WebUI chat | **PASS** | 2949.0 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 560.9 ms | events=9 |
| Stream cancellation recovery | **PASS** | 3756.6 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 2082.6 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 128.7 ms | requests=5 |
| n8n Responses API | **PASS** | 1980.9 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 6347.6 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 2344.7 ms | loaded on GPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
