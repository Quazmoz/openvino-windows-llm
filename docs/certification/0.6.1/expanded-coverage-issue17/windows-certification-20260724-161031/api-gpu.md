# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T16:11:01.217473+00:00`
- Profile: `full`
- Model: `tinyllama-1.1b-chat-int4`
- Device: `GPU`

**Result:** 12 passed, 0 warnings, 2 skipped, 0 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 29.4 ms | version=0.6.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 2.2 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 48.7 ms | catalog=21 |
| Model load | **PASS** | 15426.9 ms | loaded on GPU |
| Open WebUI chat | **PASS** | 1047.6 ms | finish_reason=stop |
| Open WebUI streaming | **PASS** | 907.6 ms | events=49 |
| Stream cancellation recovery | **PASS** | 1205.9 ms | follow-up request succeeded |
| Tool and structured-output requests | **PASS** | 1942.7 ms | tool call and strict JSON demonstrated |
| Request metrics | **PASS** | 99.8 ms | requests=5 |
| n8n Responses API | **PASS** | 1322.9 ms | streaming and non-streaming passed |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **PASS** | 2235.6 ms | benchmark succeeded |
| Model lifecycle | **PASS** | 1266.0 ms | loaded on GPU |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
