# 0.6.0 public certification evidence

This directory contains the sanitized hardware-certification reports that back the
`0.6.0` rows in [`../../COMPATIBILITY_MATRIX.md`](../../COMPATIBILITY_MATRIX.md). Every
file here is copied verbatim from a locally retained certification session; nothing has
been added, and the only files omitted are raw server logs (see *Sanitization* below).

Use [`SHA256SUMS.txt`](SHA256SUMS.txt) to confirm each report is unmodified:

```powershell
Get-FileHash .\api-cpu.json -Algorithm SHA256   # compare against SHA256SUMS.txt
```

## What was tested

All evidence was produced by `scripts/validate_windows.ps1` with mock mode disabled, on a
**single physical machine**, on **2026-07-24**. The certification harness recorded the
requested device and the actual runtime device independently.

| Session | Model | Precision | Devices | Extra |
|---|---|---|---|---|
| [`windows-certification-20260724-091712/`](windows-certification-20260724-091712/) | `tinyllama-1.1b-chat-fp16` | FP16 | CPU, GPU, NPU, AUTO | `bge-small-en-v1.5` embeddings on CPU (384-dim) |
| [`windows-certification-20260724-092800/`](windows-certification-20260724-092800/) | `smollm2-135m-fp16` | FP16 | CPU, GPU, NPU, AUTO | tool/structured-output recorded as a model-dependent WARN |
| [`windows-certification-20260724-092853/`](windows-certification-20260724-092853/) | `qwen2.5-1.5b-fp16` | FP16 | CPU, GPU, NPU, AUTO | — |

Each session contains one `windows-certification.{json,md}` summary plus one
`api-<device>.{json,md}` report for each device that was exercised.

## Machine and driver scope

The reports were captured on exactly one laptop. These results apply to this
configuration only; other Intel models, drivers, and OpenVINO versions are unverified.

- **OS:** Windows 11 Home, build 26200 (x64)
- **Processor:** Intel Core Ultra 9 185H
- **Memory:** ~31.7 GB
- **GPU:** Intel Arc Graphics (iGPU), adapter driver `32.0.101.8425` — recorded in every session JSON
- **NPU:** Intel AI Boost — the device is recorded as `Intel(R) AI Boost`, but **the harness did not capture the NPU driver version**, so no NPU driver version is asserted here
- **Python:** 3.13.11
- **OpenVINO:** `2026.2.1` · **OpenVINO GenAI:** `2026.2.1.0` · **Optimum Intel:** `2.0.0` · **NNCF:** `3.2.0`

## Application version recorded in the reports

The reports record server `version=0.5.0`. This is expected and honest: the certification
sessions ran at roughly 09:17–09:32 UTC on 2026-07-24, immediately **before** the release
commit that bumped `app/version.py` to `0.6.0` (committed 09:53 UTC the same day). The
qualified OpenVINO `2026.2.1` runtime stack and all exercised code paths are identical
between that pre-bump tree and the `0.6.0` release; the version bump added only the two
reliability fixes, the Ruff pin, release notes, and the version string. The version strings
in these reports have been left unaltered.

## Requested vs. actual device

A requested device is not proof of execution. The harness records both the requested device
and the device OpenVINO actually ran on. A row is only a direct `CPU`, `GPU`, or `NPU`
result when the requested and actual devices match.

## Why AUTO is not a direct GPU or NPU certification

`AUTO` lets OpenVINO choose a device at runtime. An `AUTO` PASS validates the routing and
fallback path, but it does **not** prove the model ran on any specific accelerator, so
`AUTO` results are reported separately and are never entered as a direct `CPU`, `GPU`, or
`NPU` claim.

## Result meanings

- **PASS** — the check completed and met its contract on this machine.
- **WARN** — the request was accepted and did not fail, but an optional, model-dependent
  behavior was not fully demonstrated (for example, a small model that does not reliably
  emit both a tool call and strict JSON). A WARN is not a failure.
- **SKIP** — the check was intentionally not run (for example, API-key enforcement when no
  key was supplied, or embeddings when embeddings were not requested).
- **FAIL** — the check ran and did not meet its contract. There are no FAIL results in this
  bundle.

## Benchmark results are not performance guarantees

The `Benchmark` check verifies that the benchmark endpoint runs and returns successfully on
this hardware (`benchmark succeeded`). It is a functional check. This bundle intentionally
does **not** publish tokens-per-second figures: throughput depends on the exact CPU, GPU,
NPU, driver, thermal state, model, precision, and prompt, and a number measured on this one
laptop is not a general speed guarantee. Any benchmark you run locally reflects only your
own machine.

## Sanitization

The `windows-certification` harness already excludes API keys, prompts, generated text,
hostnames, usernames, serial numbers, and full local paths from its `.json` and `.md`
reports. Before publishing, every file in this directory was re-scanned for usernames,
hostnames, email addresses, user-home paths (such as `%USERPROFILE%`), Hugging Face
tokens, API keys, and bearer-style authorization values, including a final pass with the
repository's own release scanner (`scripts/release_tools.py scan`). Raw server
stdout/stderr logs are **not** published because they contain local filesystem paths;
only the sanitized contract reports are included here.
