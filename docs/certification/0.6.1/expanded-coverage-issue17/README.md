# Expanded model coverage evidence

This bundle retains sanitized, inspectable evidence for issue #17. Every model/device
combination was run separately with mock mode disabled on Windows 11 build 26200,
Intel Core Ultra 9 185H, Intel Arc iGPU (adapter driver `32.0.101.8425`), Intel AI
Boost NPU (driver version not captured), OpenVINO `2026.2.1`, and OpenVINO GenAI
`2026.2.1.0`.

The API reports record application version `0.6.0` because certification preceded the
`0.6.1` version-only release bump. The certified runtime and exercised implementation are
the same changes shipped by `0.6.1`.

PASS requires the API contract, exact maximum prompt-depth generation, first-depth-beyond-
maximum rejection, requested/actual direct-device agreement, and unchanged compiled-cache
metadata across two restarted helper processes. No elapsed-time or throughput observation
is used as cache evidence or published as a performance claim.

| Model | Requested | Actual | API | Context | Cache | Overall | Retained report |
|---|---|---|---:|---:|---:|---:|---|
| `qwen2.5-3b-fp16` | CPU | CPU | 12 PASS, 2 SKIP | 3,072 prompt tokens + 1 generated; 3,073 rejected | PASS | PASS | [`155829`](windows-certification-20260724-155829/windows-certification.json) |
| `qwen2.5-3b-fp16` | GPU | GPU | 12 PASS, 2 SKIP | 3,072 prompt tokens + 1 generated; 3,073 rejected | PASS | PASS | [`155417`](windows-certification-20260724-155417/windows-certification.json) |
| `qwen2.5-3b-fp16` | NPU | not captured | 11 PASS, 2 SKIP, 1 FAIL | not run | not run | FAIL | [`160406`](windows-certification-20260724-160406/windows-certification.json) |
| `qwen2.5-3b-fp16` | AUTO | unknown | 12 PASS, 2 SKIP | boundary rejected, generation claim rejected because actual device was unknown | FAIL | FAIL | [`160549`](windows-certification-20260724-160549/windows-certification.json) |
| `tinyllama-1.1b-chat-int4` | CPU | CPU | 12 PASS, 2 SKIP | 1,536 prompt tokens + 3 generated; 1,537 rejected | PASS | PASS | [`160943`](windows-certification-20260724-160943/windows-certification.json) |
| `tinyllama-1.1b-chat-int4` | GPU | GPU | 12 PASS, 2 SKIP | 1,536 prompt tokens + 3 generated; 1,537 rejected | PASS | PASS | [`161031`](windows-certification-20260724-161031/windows-certification.json) |
| `tinyllama-1.1b-chat-int4` | NPU | not captured | 3 PASS, 2 SKIP, 9 FAIL | not run | not run | FAIL | [`161117`](windows-certification-20260724-161117/windows-certification.json) |
| `tinyllama-1.1b-chat-int4` | AUTO | unknown | 12 PASS, 2 SKIP | boundary rejected, generation claim rejected because actual device was unknown | FAIL | FAIL | [`161200`](windows-certification-20260724-161200/windows-certification.json) |

The Qwen NPU stream-cancellation recovery check returned HTTP 500 with an
`Infer Request is busy` runtime error. TinyLlama INT4 failed during NPU model load; the
server connection closed and later checks could not connect. AUTO is reported independently
and never supports a direct CPU, GPU, or NPU claim.

[`conversion-lifecycle-tinyllama-int4.json`](conversion-lifecycle-tinyllama-int4.json)
records a real conversion cancellation, task cleanup, retry, and successful INT4 IR output.
The temporary retry output was removed after inspection.

## Footprint

The measured local OpenVINO IR sizes were:

- Qwen 2.5 3B FP16: `6,193,935,620` bytes (5.77 GiB).
- TinyLlama 1.1B INT4: `662,045,180` bytes (0.62 GiB).
- TinyLlama 1.1B FP16 comparison: `2,207,733,357` bytes (2.06 GiB).

The INT4 artifact used 1,545,688,177 fewer bytes than the FP16 comparison, a 70.0%
reduction. Model IR and compiled caches are local runtime data and are excluded from release
packages. Only this documentation/evidence bundle, which is under 0.1 MiB, affects
repository and package size.

## Scope and privacy

Reports contain no prompts, generated text, raw server logs, tokens, usernames, hostnames,
emails, or full local paths. `scripts/release_tools.py scan` and a separate pattern scan were
run over the retained bundle. `SHA256SUMS.txt` covers every retained file except itself.

Unverified: both NPU combinations, AUTO actual-device selection, the Intel NPU driver
version, other hardware/driver/runtime combinations, quality, throughput, and any prompt
depth beyond the configured model boundary.
