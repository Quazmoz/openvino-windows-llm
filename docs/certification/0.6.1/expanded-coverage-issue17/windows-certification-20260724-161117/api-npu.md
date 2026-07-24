# OpenVINO Windows LLM API Validation

- Generated: `2026-07-24T16:11:43.418901+00:00`
- Profile: `full`
- Model: `tinyllama-1.1b-chat-int4`
- Device: `NPU`

**Result:** 3 passed, 0 warnings, 2 skipped, 9 failed.

| Check | Status | Duration | Detail |
|---|---:|---:|---|
| Health and probes | **PASS** | 31.2 ms | version=0.6.0 mock=False |
| API-key enforcement | **SKIP** | 0.0 ms | No API key supplied |
| Device discovery | **PASS** | 16.1 ms | available=CPU,GPU,NPU |
| Model catalog | **PASS** | 32.2 ms | catalog=21 |
| Model load | **FAIL** | 5745.7 ms | [WinError 10054] An existing connection was forcibly closed by the remote host |
| Open WebUI chat | **FAIL** | 2073.2 ms | Cannot reach http://127.0.0.1:8765/v1/chat/completions: [WinError 10061] No connection could be made because the target machine actively refused it |
| Open WebUI streaming | **FAIL** | 2026.5 ms | <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it> |
| Stream cancellation recovery | **FAIL** | 2056.7 ms | <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it> |
| Tool and structured-output requests | **FAIL** | 2052.1 ms | Cannot reach http://127.0.0.1:8765/v1/chat/completions: [WinError 10061] No connection could be made because the target machine actively refused it |
| Request metrics | **FAIL** | 2037.6 ms | Cannot reach http://127.0.0.1:8765/v1/system/status: [WinError 10061] No connection could be made because the target machine actively refused it |
| n8n Responses API | **FAIL** | 2056.9 ms | Cannot reach http://127.0.0.1:8765/v1/responses: [WinError 10061] No connection could be made because the target machine actively refused it |
| Embeddings | **SKIP** | 0.0 ms | Not requested |
| Benchmark | **FAIL** | 2039.0 ms | Cannot reach http://127.0.0.1:8765/v1/models/unload: [WinError 10061] No connection could be made because the target machine actively refused it |
| Model lifecycle | **FAIL** | 2051.5 ms | Cannot reach http://127.0.0.1:8765/v1/models/unload: [WinError 10061] No connection could be made because the target machine actively refused it |

> Reports exclude API keys, prompts, generated text, hostnames, usernames, and full local paths.
