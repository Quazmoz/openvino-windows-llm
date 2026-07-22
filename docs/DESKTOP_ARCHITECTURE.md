# Desktop distribution architecture

The desktop build is intentionally a thin launcher around the existing server and browser UI.

## Components

- `app.desktop_launcher` owns single-instance locking, port selection, child-process identity, startup polling, browser launch, user-visible startup errors, diagnostics, and exact child shutdown.
- `app.desktop_server` prepares writable paths, initializes the user catalog, configures local caches and logs, creates the existing FastAPI application, and registers desktop-only routes.
- `app.onboarding_service` orchestrates the existing hardware advisor, model lifecycle, conversion progress, load locks, and benchmark runner.
- `app.onboarding_ui` injects the accessible wizard into the existing dependency-free browser UI.
- `app.paths` separates packaged resources from installed or portable mutable data.

No Electron runtime, Node frontend, Docker service, cloud inference provider, or second model manager is introduced.

## Single-instance behavior

A per-user file lock remains held by the launcher for the server lifetime. Metadata includes a random nonce, selected port, child PID, executable path, and start time. A stale PID is never trusted by itself. An existing instance is accepted only when the local identity endpoint returns the expected nonce and the liveness endpoint succeeds.

The launcher terminates only the child process handle it created. It never scans for or kills unrelated Python processes.

## Liveness and readiness

`/health/live` confirms that the HTTP process is running. `/health/ready` confirms that startup is complete and no startup load is still pending. The launcher performs bounded polling and reports failure through a Windows dialog and sanitized logs.

## Packaged conversion dispatch

The existing lifecycle starts conversion through `sys.executable -m runtime.model_converter`. A frozen executable detects this invocation and dispatches to the bundled converter. Inside that helper process, the packaged Optimum CLI entry point is invoked in-process, preserving streamed progress without requiring a separately installed Python or `optimum-cli` command.
