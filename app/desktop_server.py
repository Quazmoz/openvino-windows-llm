"""Packaged desktop server wrapper with onboarding APIs and writable paths."""

from __future__ import annotations

import argparse
import logging
import os
import secrets
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


def prepare_desktop_environment(
    *,
    portable: bool = False,
    data_dir: str | None = None,
    mock: bool = False,
) -> None:
    os.environ["OV_LLM_DESKTOP"] = "1"
    if portable:
        os.environ["OV_LLM_PORTABLE"] = "1"
    if data_dir:
        os.environ["OV_LLM_DATA_DIR"] = str(Path(data_dir).expanduser())
    if mock:
        os.environ["OV_LLM_MOCK"] = "1"


def _configure_file_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    log_path = logs_dir / "desktop.log"
    if any(getattr(handler, "baseFilename", None) == str(log_path) for handler in root.handlers):
        return
    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
    )
    root.addHandler(handler)


def create_desktop_app(
    *,
    port: int,
    instance_nonce: str,
    portable: bool = False,
    data_dir: str | None = None,
    mock: bool = False,
) -> Any:
    prepare_desktop_environment(portable=portable, data_dir=data_dir, mock=mock)

    from app.config import Settings
    from app.desktop_onboarding import DesktopOnboardingService
    from app.onboarding_routes import register_onboarding_routes
    from app.onboarding_state import OnboardingStateStore
    from app.paths import (
        ensure_data_root_writable,
        materialize_user_catalog,
        resolve_runtime_paths,
    )
    from app.server import create_app

    paths = resolve_runtime_paths(portable=portable, desktop=True)
    ensure_data_root_writable(paths)
    materialize_user_catalog(paths)
    os.environ.setdefault("HF_HOME", str(paths.huggingface_cache_dir))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(paths.huggingface_cache_dir / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(paths.huggingface_cache_dir / "transformers"))
    os.environ.setdefault("OV_CACHE_DIR", str(paths.compiled_cache_dir))

    settings = Settings.from_env().replace(host="127.0.0.1", port=port)
    state_store = OnboardingStateStore(paths.onboarding_file)
    state = state_store.load().state
    if state.get("completed") and not state.get("restart_requested"):
        selected_model = state.get("selected_model")
        selected_device = state.get("selected_device")
        settings = settings.replace(
            default_model=selected_model if selected_model else None,
            device=selected_device if selected_device else None,
        )

    app = create_app(settings)
    if app.state.manager.force_mock and not mock:
        raise RuntimeError(
            "OpenVINO GenAI could not be loaded by the packaged application. Run the desktop "
            "diagnostic command and reinstall a complete build. Mock mode is never enabled "
            "silently for a normal desktop launch."
        )
    _configure_file_logging(paths.logs_dir)
    service = DesktopOnboardingService(
        settings=settings,
        manager=app.state.manager,
        paths=paths,
        state_store=state_store,
        endpoint_port=port,
    )
    app.state.desktop_paths = paths
    app.state.onboarding_service = service
    register_onboarding_routes(
        app,
        service=service,
        settings=settings,
        instance_nonce=instance_nonce,
    )
    return app


def run_server(
    *,
    port: int,
    instance_nonce: str,
    portable: bool = False,
    data_dir: str | None = None,
    mock: bool = False,
) -> int:
    import uvicorn

    app = create_desktop_app(
        port=port,
        instance_nonce=instance_nonce,
        portable=portable,
        data_dir=data_dir,
        mock=mock,
    )
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    app.state.shutdown_callback = lambda: setattr(server, "should_exit", True)
    server.run()
    return 0 if server.started else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenVINO Windows LLM desktop server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--data-dir")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--instance-nonce", default="")
    args = parser.parse_args(argv)
    if args.port < 1 or args.port > 65535:
        parser.error("--port must be between 1 and 65535")
    nonce = args.instance_nonce or secrets.token_urlsafe(24)
    try:
        return run_server(
            port=args.port,
            instance_nonce=nonce,
            portable=args.portable,
            data_dir=args.data_dir,
            mock=args.mock,
        )
    except Exception:
        logging.getLogger("ov-llm.desktop").exception("Desktop server startup failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
