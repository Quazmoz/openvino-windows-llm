# Windows Hardware Certification

The certification harness verifies the real Windows and Intel execution path. It is
separate from the mock-backed unit suite because CI cannot prove local driver, model,
CPU, GPU, or NPU behavior.

## What it validates

For each requested OpenVINO device target, the harness:

1. Confirms OpenVINO and device discovery from the active Python environment.
2. Starts the server on localhost with mock mode explicitly disabled.
3. Converts the selected catalog model when it is missing, unless conversion is disabled.
4. Loads the model on the requested device and waits for a ready or error state.
5. Runs the Open WebUI-style chat contract in streaming and non-streaming modes.
6. Cancels a stream early and confirms the next generation can acquire the model lock.
7. Exercises stop, seed, tool-call request, and structured-output request fields.
8. Runs the n8n-oriented Responses API in streaming and non-streaming modes.
9. Verifies request metrics, unload protection, unload, and reload behavior.
10. Runs a short benchmark after confirming the serving model was unloaded.
11. Optionally converts, loads, and validates the embedding model on CPU.
12. Produces sanitized JSON and Markdown reports.

The harness does not claim that every model works on every device. A passing report is
specific to the recorded Windows, Python, package, model, driver, and device combination.

## Prerequisites

Run the normal Windows setup first:

```powershell
.\setup.bat
```

The default certification model is TinyLlama FP16. The first run can download and
convert the model, so it requires enough disk space and network access to Hugging Face.
Gated models additionally require `HF_TOKEN` and accepted model terms.

## Run the default certification

```powershell
.\scripts\validate_windows.ps1
```

The defaults request `CPU`, `GPU`, `NPU`, and `AUTO`. Direct devices that OpenVINO does
not expose are recorded as skipped rather than misreported as tested.

A fuller run that also validates the embedding endpoint is:

```powershell
.\scripts\validate_windows.ps1 `
  -Model tinyllama-1.1b-chat-fp16 `
  -Devices CPU,GPU,NPU,AUTO `
  -IncludeEmbeddings
```

To require API-key authentication during certification:

```powershell
$env:OV_LLM_API_KEY = "replace-with-a-local-test-key"
.\scripts\validate_windows.ps1 -Devices CPU,NPU
```

The inherited key is passed to the local server and validator but is never written to
the report or placed in a child-process argument list.

## Useful options

| Option | Purpose |
|---|---|
| `-Model <id>` | Catalog text-generation model to certify. |
| `-Devices <array>` | Device expressions to test. Composite expressions are accepted. |
| `-IncludeEmbeddings` | Validate `/v1/embeddings` with the configured embedding model. |
| `-EmbeddingModel <id>` | Override the default `bge-small-en-v1.5` model. |
| `-SkipConversion` | Require model files to exist instead of downloading/converting. |
| `-ApiKey <key>` | Override `OV_LLM_API_KEY` and verify 401/200 behavior. Prefer the environment variable to avoid shell history. |
| `-ContinueOnFailure` | Continue through remaining devices after a failed profile. |
| `-KeepServerLogs` | Retain raw local server logs for private troubleshooting. |
| `-OutputDirectory <path>` | Change the report root. |

The harness refuses to start if its selected localhost port is already listening, which
prevents an unrelated process from being mistaken for the certification server.

Raw server logs may contain machine-specific paths or generated text. They are deleted
by default and must not be attached publicly without review.

## Report layout

Each run creates a timestamped directory under `certification/results/`:

```text
windows-certification-YYYYMMDD-HHMMSS/
  windows-certification.json
  windows-certification.md
  api-cpu.json
  api-cpu.md
  api-npu.json
  api-npu.md
```

The report includes:

- Windows version and build
- architecture and total memory
- processor and display-adapter names
- display-driver and relevant Python package versions
- OpenVINO-visible devices
- pass, warning, skip, and failure results for each contract check
- benchmark success metadata

It intentionally excludes:

- API keys and Hugging Face tokens
- prompts and generated model text
- usernames and hostnames
- serial numbers
- complete local filesystem paths

## Status meanings

- **PASS**: the required contract completed successfully.
- **WARN**: the server accepted the feature, but the selected model/runtime did not
  demonstrate an optional behavior. Tool emission and strict JSON generation are common
  model-dependent warnings.
- **SKIP**: the check was not requested or the direct device was not exposed by OpenVINO.
- **FAIL**: a required contract, load, inference, lifecycle, or benchmark assertion failed.

Warnings do not make the process exit nonzero. Any failure does.

## Standalone API validation

The cross-platform validator can target an already-running server:

```powershell
python .\scripts\validate_api_contract.py `
  --base-url http://127.0.0.1:8000 `
  --profile full `
  --model tinyllama-1.1b-chat-fp16 `
  --device CPU `
  --expect-real `
  --run-benchmark `
  --exercise-lifecycle
```

Use `--expect-mock` when validating the mock engine in CI or on a non-Intel development
machine.

## Publishing compatibility results

Only add a model/device row to public documentation after attaching or reviewing a
real-hardware report. Record the exact model, weight format, device, OpenVINO packages,
Windows build, and driver context. Do not infer NPU or GPU support from CPU or mock runs.
