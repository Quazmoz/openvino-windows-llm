# Compatibility matrix

Only rows backed by retained certification reports belong here. Empty coverage means unverified, not failed.

All rows below were produced by `scripts/validate_windows.ps1` with mock mode disabled on a single physical machine. Requested and actual devices were recorded independently; `AUTO` results are reported separately and are never used to infer a direct `GPU` or `NPU` claim. Raw reports are retained locally under the ignored `certification/results/` path and are not committed.

Machine: Windows 11 Home build 26200, x64, Intel Core Ultra 9 185H, Intel Arc iGPU (driver 32.0.101.8425), Intel AI Boost NPU (driver 32.0.100.4514), 31.7 GB RAM.

| App version | Windows | Arch | Processor | OpenVINO | GenAI | Device | Driver | Model | Precision | Requested | Actual | Load | Benchmark | tokens/s | Report | Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | CPU | (integrated, no discrete driver) | tinyllama-1.1b-chat-fp16 | FP16 | CPU | CPU | PASS | PASS | 11.5 | windows-certification-20260724-091712 | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | GPU (Arc iGPU) | 32.0.101.8425 | tinyllama-1.1b-chat-fp16 | FP16 | GPU | GPU | PASS | PASS | 27.9 | windows-certification-20260724-091712 | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | NPU (AI Boost) | 32.0.100.4514 | tinyllama-1.1b-chat-fp16 | FP16 | NPU | NPU | PASS | PASS | 8.3 | windows-certification-20260724-091712 | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | CPU | (integrated, no discrete driver) | smollm2-135m-fp16 | FP16 | CPU | CPU | PASS | PASS | 43.2 | windows-certification-20260724-092800 | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | GPU (Arc iGPU) | 32.0.101.8425 | smollm2-135m-fp16 | FP16 | GPU | GPU | PASS | PASS | 60.8 | windows-certification-20260724-092800 | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | NPU (AI Boost) | 32.0.100.4514 | smollm2-135m-fp16 | FP16 | NPU | NPU | PASS | PASS | 25.1 | windows-certification-20260724-092800 | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | CPU | (integrated, no discrete driver) | qwen2.5-1.5b-fp16 | FP16 | CPU | CPU | PASS | PASS | 6.7 | windows-certification-20260724-092853 | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | GPU (Arc iGPU) | 32.0.101.8425 | qwen2.5-1.5b-fp16 | FP16 | GPU | GPU | PASS | PASS | 14.5 | windows-certification-20260724-092853 | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | NPU (AI Boost) | 32.0.100.4514 | qwen2.5-1.5b-fp16 | FP16 | NPU | NPU | PASS | PASS | 4.7 | windows-certification-20260724-092853 | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | CPU | (integrated, no discrete driver) | bge-small-en-v1.5 (embeddings) | FP16 | CPU | CPU | PASS | n/a | n/a (384-dim) | windows-certification-20260724-091712 | 2026-07-24 |

`AUTO` was also certified PASS for `tinyllama-1.1b-chat-fp16`, `smollm2-135m-fp16`, and `qwen2.5-1.5b-fp16` in the same sessions. `AUTO` selects an OpenVINO device at runtime; those results validate the routing path and are intentionally not entered as direct `CPU`/`GPU`/`NPU` claims.

`tokens/s` is a single short-prompt benchmark on this exact machine and is not a general speed guarantee. Only FP16 was certified; INT4/INT8 and contexts longer than the short validation prompts remain unverified.

Mock contract results must not be entered as hardware certification. Add a row only after the Windows certification harness records the requested device, actual device, versions, driver, model, load result, benchmark result, report reference, and validation date.
