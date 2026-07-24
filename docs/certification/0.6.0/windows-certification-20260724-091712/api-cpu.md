# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T09:17:40.165914+00:00`
- Profile: `full`
- Model: `tinyllama-1.1b-chat-fp16`
- Device: `CPU`

**Result:** 13 passed, 0 warnings, 1 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 24.4 ms | version=0.5.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 10.9 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 9.7 ms | catalog=20 |
| Model load | **PASS** | 62.0 ms | loaded on CPU |
| Open WebUI chat | **PASS** | 2606.1 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 1998.9 ms | events=44 |
| Stream cancellation recovery | **PASS** | 2602.2 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 5444.4 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 74.9 ms | requests=5 |
| n8n Responses API | **PASS** | 4155.6 ms | streaming and non-streaming passed |
| Embeddings | **PASS** | 1840.6 ms | dimensions=384 |
| Benchmark | **PASS** | 3417.5 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1240.1 ms | loaded on CPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
