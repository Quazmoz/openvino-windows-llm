# OpenVINO 0.6 hardware qualification

## Goal

Qualify a modern OpenVINO GenAI dependency stack and prove the packaged Windows product on a physical Intel Core Ultra 7 185H laptop before publishing broader CPU, GPU, or NPU compatibility claims.

This is a release-qualification exercise, not a feature expansion. Preserve the Windows-first, local-first, OpenVINO-based architecture and the existing OpenAI-compatible contracts.

## Candidate stacks

Use separate clean virtual environments and record the complete resolved dependency inventory for every candidate.

1. **Baseline:** the versions currently pinned in `requirements/release.txt`, including `openvino-genai==2025.1.0`.
2. **Primary candidate:** `openvino-genai==2026.2.1.0`, which was the latest PyPI release when this plan was written on 2026-07-24.
3. **Fallback candidate:** `openvino-genai==2025.4.1.0` when the primary candidate has an unresolved regression.

Re-check the official OpenVINO GenAI release before starting. Do not combine arbitrary OpenVINO, OpenVINO GenAI, Optimum Intel, NNCF, Transformers, or Hugging Face Hub versions. Select and pin one tested set.

## Non-negotiable rules

- Work from a clean checkout of `main`.
- Keep mock mode disabled for hardware evidence.
- Do not log or commit API keys, Hugging Face tokens, prompts, generated text, usernames, hostnames, serial numbers, or complete private paths.
- Do not commit model weights, caches, raw server logs, build output, or `certification/results/`.
- A requested device is not proof of execution. Record the actual runtime device.
- Never infer NPU or GPU support from CPU, mock, or `AUTO` results.
- Do not change the inference runtime away from OpenVINO.
- Do not publish a 0.6.0 release or compatibility claim until the evidence below is complete.

## Phase 1: Capture the machine and baseline

Before changing dependencies, record:

- Git commit SHA and clean-tree state
- Windows edition, version, and build
- CPU model and total memory
- display adapters and driver versions
- BIOS and Intel NPU driver versions when available
- Python version and architecture
- exact `pip list` and `pip freeze`
- OpenVINO-visible devices
- free disk space in the model, cache, temporary, and installation locations

Run the current source validation:

```powershell
ruff check .
ruff format --check .
pytest
```

Run the external mock contract validator, then run the physical baseline with mock mode disabled:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_windows.ps1 `
  -Model tinyllama-1.1b-chat-fp16 `
  -Devices CPU,GPU,NPU,AUTO `
  -IncludeEmbeddings `
  -ContinueOnFailure
```

Direct devices not exposed by OpenVINO may be recorded as skipped. An exposed device that fails load, inference, lifecycle, or benchmark validation is a failure requiring investigation.

## Phase 2: Qualify the dependency candidate

Create a fresh isolated environment for each candidate. Update dependency files only after the candidate can be installed reproducibly.

Inspect and test compatibility around:

- removed or renamed OpenVINO Python namespaces
- OpenVINO GenAI streaming callback status behavior
- `GenerationConfig` fields for stop strings, seed, sampling, and structured output
- `LLMPipeline`, `VLMPipeline`, and `TextEmbeddingPipeline` constructor behavior
- NPU plugin properties such as `MAX_PROMPT_LEN` and compiled-cache configuration
- model conversion APIs and generated artifact layout
- Optimum Intel and NNCF version compatibility
- PyInstaller hidden imports, native DLL collection, and packaged startup

Make the smallest compatibility changes required. Add regression tests for every repository-side defect found. Do not hide a runtime incompatibility by silently falling back to mock mode or another device.

After each candidate change, run:

```powershell
ruff check .
ruff format --check .
pytest
```

Then run the complete external mock API contract validator before moving to physical hardware.

## Phase 3: Certify the maintained model set

Certify these lanes separately:

| Lane | Model | Purpose |
|---|---|---|
| Setup validation | `smollm2-135m-fp16` | Minimal download, conversion, load, and chat path |
| Device validation | `tinyllama-1.1b-chat-fp16` | Repeatable CPU, GPU, NPU, and AUTO contract validation |
| Balanced | `qwen2.5-1.5b-fp16` | Useful default local chat candidate |
| Quality | `qwen2.5-3b-fp16` | Higher-quality candidate for systems passing preflight |
| Embeddings | `bge-small-en-v1.5` | `/v1/embeddings` and lifecycle validation on CPU |

For every supported model and direct device combination, validate:

1. Clean download and conversion.
2. Cancellation during conversion and a successful retry.
3. Converted-model validation and registration.
4. Initial compilation and load.
5. Restart and compiled-cache reuse.
6. Chat Completions, streaming and non-streaming.
7. Responses API, streaming and non-streaming.
8. Early stream cancellation followed by another successful request.
9. Stop sequences, deterministic seed handling, token limits, and context trimming.
10. Tool-call request compatibility and sanitized model-dependent warnings.
11. Structured-output request compatibility.
12. Unload protection, unload, reload, and deletion guards.
13. Short benchmark persistence with requested and actual device identity.
14. Safe failure and an actionable UI message when a device cannot load the model.

Repeat the selected starter-model run with `-SkipConversion` to prove existing converted artifacts are reusable.

## Phase 4: Desktop and package acceptance

Build the complete unsigned validation distribution using the canonical source version. Do not use `-SkipTests`.

Validate both installer and portable modes:

- fresh per-user install
- first-run hardware scan and recommendation
- model preparation progress by real stage
- successful transition to chat
- correct loopback URL and actual selected port
- portable paths containing spaces
- Start Menu and optional desktop shortcuts
- Start with Windows enablement, disablement, and duplicate prevention
- single-instance activation
- tray icon, tooltip, menu states, clipboard, browser opening, and folder actions
- browser survival across tray-owned server restart
- server crash recovery
- exact-process cleanup without terminating unrelated processes
- uninstall preserving mutable data by default
- upgrade from the published 0.5.0 installer while preserving models, settings, onboarding state, and benchmarks
- downgrade warning and documented rollback behavior
- generated diagnostics ZIP manually inspected for privacy leaks

Run checksum generation and verification. Authenticode remains unverified unless signing and `signtool verify /pa /all` are actually completed in a secure signing environment.

## Phase 5: Evidence and repository updates

Review every generated report before using it publicly. Raw reports remain under ignored local paths unless a deliberately sanitized report is approved for publication.

For each passing direct-device result:

- add a precise row to `docs/COMPATIBILITY_MATRIX.md`
- update the corresponding certification array and `max_tested_context` in `model_library_manifest.json`
- include Windows build, processor, adapter or NPU driver, OpenVINO versions, model, precision, requested device, actual device, load result, benchmark result, report reference, and date

For reproducible failures:

- fix repository defects and add regression tests when possible
- otherwise add a scoped entry to `docs/KNOWN_ISSUES.md` with evidence and workaround
- do not convert an unresolved failure into a broad unsupported-hardware statement

Only after the selected dependency stack, source suite, mock contract suite, required physical-device paths, installer, and portable acceptance pass:

1. update `app/version.py` to `0.6.0`
2. add `docs/releases/0.6.0.md`
3. update pinned release dependencies
4. rebuild and repeat final package validation
5. commit directly to `main` and push

Do not publish the GitHub release unless explicitly requested.

## Required final report

Report:

- root causes found
- selected dependency stack and rejected candidates
- files changed
- behavior changed
- exact commands run
- source, mock, package, CPU, GPU, NPU, and AUTO results separately
- requested and actual devices
- models and precisions tested
- installer, upgrade, rollback, tray, startup, and diagnostics results
- commit SHA pushed to `main`
- anything still unverified and why
