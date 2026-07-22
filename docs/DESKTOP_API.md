# Desktop onboarding API

The packaged desktop server extends the existing FastAPI application. It does not duplicate model recommendation, conversion, load, or benchmark logic in JavaScript.

All request and response bodies use Pydantic models from `app.onboarding_models`.

## Read routes

| Route | Purpose |
|---|---|
| `GET /v1/onboarding/status` | Versioned completion state and optional rescan recommendation |
| `GET /v1/onboarding/system-scan?refresh=true` | Existing hardware-advisor snapshot presented with ready, warning, unavailable, or unknown statuses |
| `GET /v1/onboarding/npu-readiness?refresh=true` | Explicit NPU readiness classification and safe fallback |
| `GET /v1/onboarding/recommendation?refresh=true` | Conservative compatible starting model and estimates |
| `GET /v1/onboarding/preparation/{job_id}` | Current stage, determinate or indeterminate progress, sanitized details, and benchmark result |
| `GET /v1/onboarding/connection` | Actual-port connection configuration after successful setup |

## State-changing routes

| Route | Purpose |
|---|---|
| `POST /v1/onboarding/prepare` | Validate model, device, path, confirmations, and start one serialized preparation job |
| `POST /v1/onboarding/preparation/{job_id}/cancel` | Request cancellation only during safe stages |
| `POST /v1/onboarding/complete` | Return connection details for a successfully verified job |
| `POST /v1/onboarding/restart` | Restart setup without deleting models or benchmarks |

When `OV_LLM_API_KEY` is configured, state-changing routes require the same bearer-key policy as the existing protected API.

## Desktop process routes

`GET /desktop/instance` returns the local instance nonce and selected port for launcher identity verification.

`POST /desktop/shutdown` requires the exact nonce in `X-Instance-Nonce`. It requests a graceful Uvicorn shutdown for the matching local desktop process. The launcher never terminates unrelated processes.

## Preparation contract

Normal stage order:

```text
preparing
downloading
converting
validating
compiling
loading
benchmarking
ready
```

The response includes whether progress is determinate. A percentage is omitted when the backend cannot measure it reliably. User-visible logs are bounded and sanitized.

Onboarding completion is persisted only after successful measured or explicitly marked mock generation. The benchmark reports requested and actual devices separately.
