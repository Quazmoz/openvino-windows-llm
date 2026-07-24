# Compatibility matrix

Only rows backed by retained certification reports belong here. Empty coverage means unverified, not failed.

All rows below were produced by `scripts/validate_windows.ps1` with mock mode disabled on a single physical machine. Requested and actual devices were recorded independently; `AUTO` results are reported separately and are never used to infer a direct `GPU` or `NPU` claim. The sanitized reports are published under [`certification/0.6.0/`](certification/0.6.0/); raw reports, including server logs, remain local under the ignored `certification/results/` path. Verify any report against [`certification/0.6.0/SHA256SUMS.txt`](certification/0.6.0/SHA256SUMS.txt), and see [`certification/0.6.0/README.md`](certification/0.6.0/README.md) for full scope, meanings, and limitations.

Machine: Windows 11 Home build 26200, x64, Intel Core Ultra 9 185H, Intel Arc iGPU (adapter driver 32.0.101.8425), Intel AI Boost NPU (driver version not captured in the retained reports), 31.7 GB RAM.

The reports record server `version=0.5.0`: the certification sessions ran on 2026-07-24 at ~09:17–09:32 UTC, immediately before the commit that bumped `app/version.py` to `0.6.0` (~09:53 UTC the same day). The qualified OpenVINO `2026.2.1` runtime and all exercised code paths are identical between that pre-bump tree and the `0.6.0` release.

| App version | Windows | Arch | Processor | OpenVINO | GenAI | Device | Driver | Model | Precision | Requested | Actual | Load | Benchmark | Report | Date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | CPU | (integrated, no discrete driver) | tinyllama-1.1b-chat-fp16 | FP16 | CPU | CPU | PASS | PASS | [api-cpu.md](certification/0.6.0/windows-certification-20260724-091712/api-cpu.md) | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | GPU (Arc iGPU) | 32.0.101.8425 | tinyllama-1.1b-chat-fp16 | FP16 | GPU | GPU | PASS | PASS | [api-gpu.md](certification/0.6.0/windows-certification-20260724-091712/api-gpu.md) | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | NPU (AI Boost) | not captured in report | tinyllama-1.1b-chat-fp16 | FP16 | NPU | NPU | PASS | PASS | [api-npu.md](certification/0.6.0/windows-certification-20260724-091712/api-npu.md) | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | CPU | (integrated, no discrete driver) | smollm2-135m-fp16 | FP16 | CPU | CPU | PASS | PASS | [api-cpu.md](certification/0.6.0/windows-certification-20260724-092800/api-cpu.md) | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | GPU (Arc iGPU) | 32.0.101.8425 | smollm2-135m-fp16 | FP16 | GPU | GPU | PASS | PASS | [api-gpu.md](certification/0.6.0/windows-certification-20260724-092800/api-gpu.md) | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | NPU (AI Boost) | not captured in report | smollm2-135m-fp16 | FP16 | NPU | NPU | PASS | PASS | [api-npu.md](certification/0.6.0/windows-certification-20260724-092800/api-npu.md) | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | CPU | (integrated, no discrete driver) | qwen2.5-1.5b-fp16 | FP16 | CPU | CPU | PASS | PASS | [api-cpu.md](certification/0.6.0/windows-certification-20260724-092853/api-cpu.md) | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | GPU (Arc iGPU) | 32.0.101.8425 | qwen2.5-1.5b-fp16 | FP16 | GPU | GPU | PASS | PASS | [api-gpu.md](certification/0.6.0/windows-certification-20260724-092853/api-gpu.md) | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | NPU (AI Boost) | not captured in report | qwen2.5-1.5b-fp16 | FP16 | NPU | NPU | PASS | PASS | [api-npu.md](certification/0.6.0/windows-certification-20260724-092853/api-npu.md) | 2026-07-24 |
| 0.6.0 | 11 build 26200 | x64 | Ultra 9 185H | 2026.2.1 | 2026.2.1.0 | CPU | (integrated, no discrete driver) | bge-small-en-v1.5 (embeddings) | FP16 | CPU | CPU | PASS | n/a (384-dim) | [api-cpu.md](certification/0.6.0/windows-certification-20260724-091712/api-cpu.md) | 2026-07-24 |

`AUTO` was also certified PASS for `tinyllama-1.1b-chat-fp16` ([api-auto.md](certification/0.6.0/windows-certification-20260724-091712/api-auto.md)), `smollm2-135m-fp16` ([api-auto.md](certification/0.6.0/windows-certification-20260724-092800/api-auto.md)), and `qwen2.5-1.5b-fp16` ([api-auto.md](certification/0.6.0/windows-certification-20260724-092853/api-auto.md)) in the same sessions. `AUTO` selects an OpenVINO device at runtime; those results validate the routing path and are intentionally not entered as direct `CPU`/`GPU`/`NPU` claims.

The `smollm2-135m-fp16` rows record a model-dependent WARN on the tool/structured-output check (the request was accepted but the small model did not demonstrate both optional outputs). A WARN is not a failure. The `tinyllama` and `qwen2.5-1.5b` rows have no warnings.

The `Benchmark` column records whether the benchmark endpoint ran successfully on this machine; it is a functional check, not a throughput measurement, and is not a general speed guarantee. Only FP16 was certified; INT4/INT8 and contexts longer than the short validation prompts remain unverified.

## Report integrity (SHA-256)

Each report below is a clickable repository-relative link with its SHA-256. The complete list, including the JSON reports and this bundle's README, is in [`certification/0.6.0/SHA256SUMS.txt`](certification/0.6.0/SHA256SUMS.txt).

| Report | SHA-256 |
|---|---|
| [091712/windows-certification.md](certification/0.6.0/windows-certification-20260724-091712/windows-certification.md) | `08efcc998478c50d47ea662ee3b5f6041a4a4491c48114c395cafe7420290f4b` |
| [091712/api-cpu.md](certification/0.6.0/windows-certification-20260724-091712/api-cpu.md) | `d2f83524b9ed6c9477291dcdcad6cb0f574a3e73d583cb0709c4fa4007fd07cc` |
| [091712/api-gpu.md](certification/0.6.0/windows-certification-20260724-091712/api-gpu.md) | `933793bc68d4139c6b335eed9f79db86333a8b7f5ceb75440aee80e3cede4e03` |
| [091712/api-npu.md](certification/0.6.0/windows-certification-20260724-091712/api-npu.md) | `f2721fadd6096a0e8b5bd2f613cb1e7ac7aae42cf78a757abf1ef1f6fa680035` |
| [091712/api-auto.md](certification/0.6.0/windows-certification-20260724-091712/api-auto.md) | `95cb6b75f093bbb1cb1b525b13dd8e5a5560f3a97e0098b7bef7df7fd5dd3675` |
| [092800/windows-certification.md](certification/0.6.0/windows-certification-20260724-092800/windows-certification.md) | `8324bdea0ec7ed2624a1df2de1b03616f637bc41e30bf2676bbfe71f0e5d4822` |
| [092800/api-cpu.md](certification/0.6.0/windows-certification-20260724-092800/api-cpu.md) | `7e611efbbed739494e8890125e54ecf395336d332b5bffbef8c9e73c8abae7bf` |
| [092800/api-gpu.md](certification/0.6.0/windows-certification-20260724-092800/api-gpu.md) | `6e7132d8d8a49d8e63656067ee13e2f1028a627979ad2142a3d0c5ad97169ae0` |
| [092800/api-npu.md](certification/0.6.0/windows-certification-20260724-092800/api-npu.md) | `e1cc6cd3547ea3b68e7903420909095a171075900cfb82400cad76210ef0d3d9` |
| [092800/api-auto.md](certification/0.6.0/windows-certification-20260724-092800/api-auto.md) | `74eeb0936c1668dd9df0b7efdcaf41994d0cfce22b29bfbbf03c924c32578155` |
| [092853/windows-certification.md](certification/0.6.0/windows-certification-20260724-092853/windows-certification.md) | `6c13c0d389d5a6e9f27a3c231a77ce30a24907bcf607acf30bd4fa7983d2f25b` |
| [092853/api-cpu.md](certification/0.6.0/windows-certification-20260724-092853/api-cpu.md) | `097269e633d2a93298f74f64df59417c9e5842c0637a552aa665e5ffa5711b5f` |
| [092853/api-gpu.md](certification/0.6.0/windows-certification-20260724-092853/api-gpu.md) | `63bf0939d62b52c4bfde7aeffa9c835487fd0ef3bb8572bc62573b60eaecafe7` |
| [092853/api-npu.md](certification/0.6.0/windows-certification-20260724-092853/api-npu.md) | `9faebd995378e02dd6d9368f638cd471be58ea9683c88bd7722d20a40ee69766` |
| [092853/api-auto.md](certification/0.6.0/windows-certification-20260724-092853/api-auto.md) | `881cf7842735b41e5333bd074e4a29c955f66b1d0b5c020a0fec547395fcb3d8` |

Mock contract results must not be entered as hardware certification. Add a row only after the Windows certification harness records the requested device, actual device, versions, driver, model, load result, benchmark result, report reference, and validation date.
