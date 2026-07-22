"""Single-instance Windows launcher for the packaged desktop application."""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

_APP_TITLE = "OpenVINO Windows LLM"
_STARTUP_TIMEOUT_SECONDS = 90
_POLL_INTERVAL_SECONDS = 0.35


@dataclass(frozen=True)
class InstanceMetadata:
    pid: int
    port: int
    nonce: str
    executable: str
    started_at: str

    @classmethod
    def from_json(cls, raw: object) -> InstanceMetadata | None:
        if not isinstance(raw, dict):
            return None
        try:
            pid = int(raw["pid"])
            port = int(raw["port"])
            nonce = str(raw["nonce"])
            executable = str(raw["executable"])
            started_at = str(raw["started_at"])
        except (KeyError, TypeError, ValueError):
            return None
        if pid < 1 or not 1 <= port <= 65535 or not nonce:
            return None
        return cls(pid, port, nonce, executable, started_at)


def choose_available_port(preferred: int = 8000) -> int:
    for candidate in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            try:
                sock.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            return int(sock.getsockname()[1])
    raise RuntimeError("No local TCP port is available for the application server.")


def _http_json(url: str, *, timeout: float = 1.5) -> dict | None:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - localhost only
            if response.status != 200:
                return None
            payload = json.loads(response.read(128 * 1024).decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def verify_instance(metadata: InstanceMetadata) -> bool:
    payload = _http_json(f"http://127.0.0.1:{metadata.port}/desktop/instance")
    return bool(payload and payload.get("instance_nonce") == metadata.nonce)


def wait_for_readiness(metadata: InstanceMetadata, timeout: float = _STARTUP_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    live_seen = False
    while time.monotonic() < deadline:
        instance = _http_json(f"http://127.0.0.1:{metadata.port}/desktop/instance")
        if instance and instance.get("instance_nonce") == metadata.nonce:
            live = _http_json(f"http://127.0.0.1:{metadata.port}/health/live")
            live_seen = live_seen or bool(live and live.get("status") == "ok")
            ready = _http_json(f"http://127.0.0.1:{metadata.port}/health/ready")
            if live_seen and ready and ready.get("status") == "ready":
                return True
        time.sleep(_POLL_INTERVAL_SECONDS)
    return False


def _write_metadata(path: Path, metadata: InstanceMetadata) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(metadata.__dict__, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def _read_metadata(path: Path) -> InstanceMetadata | None:
    try:
        return InstanceMetadata.from_json(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


class InstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: BinaryIO | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")  # noqa: SIM115 - retained for lock lifetime
        handle.seek(0)
        if handle.read(1) == b"":
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.handle = handle
        return True

    def release(self) -> None:
        handle = self.handle
        self.handle = None
        if handle is None:
            return
        with contextlib.suppress(OSError):
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

    def __enter__(self) -> InstanceLock:
        if not self.acquire():
            raise RuntimeError("The application instance lock is already held.")
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()


def _show_dialog(title: str, message: str, *, error: bool = False) -> None:
    if os.name == "nt":
        try:
            import ctypes

            flags = 0x10 if error else 0x40
            ctypes.windll.user32.MessageBoxW(None, message, title, flags)
            return
        except Exception:
            pass
    print(f"{title}: {message}", file=sys.stderr if error else sys.stdout)


def _configure_logging(logs_dir: Path) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / "launcher.log"
    logging.basicConfig(
        filename=path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )
    return path


def _child_command(args: argparse.Namespace, metadata: InstanceMetadata) -> list[str]:
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--server-child"]
    else:
        command = [sys.executable, "-m", "app.desktop_launcher", "--server-child"]
    command.extend(["--port", str(metadata.port), "--instance-nonce", metadata.nonce])
    if args.portable:
        command.append("--portable")
    if args.data_dir:
        command.extend(["--data-dir", args.data_dir])
    if args.mock:
        command.append("--mock")
    return command


def _spawn_server(args: argparse.Namespace, metadata: InstanceMetadata, log_path: Path) -> subprocess.Popen:
    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    stream = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 - child owns inherited handle
    try:
        return subprocess.Popen(
            _child_command(args, metadata),
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            cwd=str(Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()),
            creationflags=creationflags,
            startupinfo=startupinfo,
            close_fds=os.name != "nt",
        )
    finally:
        stream.close()


def _open_browser(port: int) -> bool:
    return bool(webbrowser.open(f"http://127.0.0.1:{port}", new=1, autoraise=True))


def _portable_default() -> bool:
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    return (base / "portable.flag").exists()


def _diagnostic_report(paths, output: Path) -> Path:
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "packaged": bool(getattr(sys, "frozen", False)),
        "python": sys.version.split()[0],
        "executable": str(Path(sys.executable).resolve()),
        "resource_root": str(paths.resource_root),
        "data_root": str(paths.data_root),
        "portable": paths.portable,
        "data_root_exists": paths.data_root.exists(),
        "models_file_exists": paths.models_file.exists(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return output


def _server_child(args: argparse.Namespace) -> int:
    from app.desktop_server import run_server

    return run_server(
        port=args.port,
        instance_nonce=args.instance_nonce,
        portable=args.portable,
        data_dir=args.data_dir,
        mock=args.mock,
    )


def _run_packaged_converter(arguments: list[str]) -> int:
    """Run the converter and Optimum CLI inside the frozen helper process."""

    from runtime import model_converter

    if getattr(sys, "frozen", False):
        original_which = model_converter.shutil.which

        def packaged_which(command: str):
            if command == "optimum-cli":
                return sys.executable
            return original_which(command)

        def run_optimum(command: list[str]) -> None:
            from optimum.commands.optimum_cli import main as optimum_main

            previous = sys.argv
            sys.argv = list(command)
            try:
                result = optimum_main()
            except SystemExit as exc:
                code = int(exc.code or 0)
                if code:
                    raise subprocess.CalledProcessError(code, command) from exc
            finally:
                sys.argv = previous
            if isinstance(result, int) and result:
                raise subprocess.CalledProcessError(result, command)

        model_converter.shutil.which = packaged_which
        model_converter._run_streaming_command = run_optimum
    return model_converter.main(arguments)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:2] == ["-m", "runtime.model_converter"]:
        return _run_packaged_converter(arguments[2:])

    parser = argparse.ArgumentParser(description="OpenVINO Windows LLM desktop launcher")
    parser.add_argument("--server-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--convert-model", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--instance-nonce", default="")
    parser.add_argument("--portable", action="store_true", default=_portable_default())
    parser.add_argument("--data-dir")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--no-browser", action="store_true", help=argparse.SUPPRESS)
    args, remaining = parser.parse_known_args(arguments)
    if args.convert_model:
        return _run_packaged_converter(remaining)
    if remaining:
        parser.error(f"unrecognized arguments: {' '.join(remaining)}")
    if args.port < 1 or args.port > 65535:
        parser.error("--port must be between 1 and 65535")
    if args.server_child:
        if not args.instance_nonce:
            parser.error("--server-child requires --instance-nonce")
        return _server_child(args)

    from app.desktop_server import prepare_desktop_environment
    from app.paths import ensure_data_root_writable, resolve_runtime_paths

    prepare_desktop_environment(
        portable=args.portable,
        data_dir=args.data_dir,
        mock=args.mock,
    )
    paths = resolve_runtime_paths(portable=args.portable, desktop=True)
    try:
        ensure_data_root_writable(paths)
    except RuntimeError as exc:
        _show_dialog(_APP_TITLE, str(exc), error=True)
        return 2
    log_path = _configure_logging(paths.logs_dir)

    if args.diagnostic:
        report = _diagnostic_report(paths, paths.diagnostics_dir / "launcher-diagnostic.json")
        _show_dialog(_APP_TITLE, f"Diagnostic report written to:\n{report}")
        return 0

    lock = InstanceLock(paths.launcher_lock_file)
    if not lock.acquire():
        existing = _read_metadata(paths.launcher_metadata_file)
        if existing and verify_instance(existing):
            if not args.no_browser and not _open_browser(existing.port):
                _show_dialog(
                    _APP_TITLE,
                    f"The application is already running. Open http://127.0.0.1:{existing.port}",
                )
            return 0
        _show_dialog(
            _APP_TITLE,
            "Another launcher instance is active, but its local server did not respond. "
            "Close the existing process or restart Windows, then try again.",
            error=True,
        )
        return 3

    child: subprocess.Popen | None = None
    try:
        stale = _read_metadata(paths.launcher_metadata_file)
        if stale and verify_instance(stale):
            if not args.no_browser:
                _open_browser(stale.port)
            return 0

        port = choose_available_port(args.port)
        metadata = InstanceMetadata(
            pid=os.getpid(),
            port=port,
            nonce=secrets.token_urlsafe(24),
            executable=str(Path(sys.executable).resolve()),
            started_at=datetime.now(UTC).isoformat(),
        )
        logging.info("Starting local desktop server on 127.0.0.1:%d", port)
        child = _spawn_server(args, metadata, log_path)
        metadata = InstanceMetadata(
            pid=child.pid,
            port=metadata.port,
            nonce=metadata.nonce,
            executable=str(Path(sys.executable).resolve()),
            started_at=metadata.started_at,
        )
        _write_metadata(paths.launcher_metadata_file, metadata)
        if not wait_for_readiness(metadata):
            exit_code = child.poll()
            if exit_code is None:
                child.terminate()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    child.wait(timeout=10)
            _show_dialog(
                _APP_TITLE,
                "The local server did not become ready. Review the launcher and desktop logs in "
                f"{paths.logs_dir}",
                error=True,
            )
            return exit_code if isinstance(exit_code, int) and exit_code != 0 else 4

        if not args.no_browser and not _open_browser(port):
            _show_dialog(
                _APP_TITLE,
                f"The server is ready, but the browser could not be opened. Visit http://127.0.0.1:{port}",
            )
        exit_code = child.wait()
        if exit_code != 0:
            _show_dialog(
                _APP_TITLE,
                f"The local server stopped unexpectedly with exit code {exit_code}. Review {log_path}",
                error=True,
            )
        return int(exit_code)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - launcher process boundary
        logging.exception("Desktop launcher failed")
        _show_dialog(
            _APP_TITLE,
            f"The application could not start. Review {log_path}.\n\n{str(exc)[:300]}",
            error=True,
        )
        return 5
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                child.wait(timeout=10)
            if child.poll() is None:
                child.kill()
        with contextlib.suppress(OSError):
            paths.launcher_metadata_file.unlink()
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
