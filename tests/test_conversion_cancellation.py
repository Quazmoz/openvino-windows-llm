import asyncio
import contextlib
import logging
from types import SimpleNamespace

import pytest

from app import model_manager_core
from app.config import Settings
from app.model_manager import ModelManager
from app.model_registry import ModelConfig


class Process:
    def __init__(
        self,
        *,
        returncode=None,
        wait_result=0,
        wait_error=None,
        kill_error=None,
        wait_hook=None,
    ):
        self.returncode = returncode
        self.wait_result = wait_result
        self.wait_error = wait_error
        self.kill_error = kill_error
        self.wait_hook = wait_hook
        self.pid = 123
        self.killed = False

    async def wait(self):
        if self.wait_hook:
            self.wait_hook()
        if self.wait_error:
            raise self.wait_error
        return self.wait_result

    def kill(self):
        if self.kill_error:
            raise self.kill_error
        self.killed = True


def _terminate(monkeypatch, proc, *, platform="nt", killer=None, launch_error=None):
    monkeypatch.setattr(model_manager_core.os, "name", platform)

    async def launch(*_args, **_kwargs):
        if launch_error:
            raise launch_error
        return killer

    monkeypatch.setattr(model_manager_core.asyncio, "create_subprocess_exec", launch)
    manager = SimpleNamespace(_safe_kill_process=model_manager_core.ModelManager._safe_kill_process)
    asyncio.run(model_manager_core.ModelManager._terminate_conversion_process(manager, proc))


def test_windows_taskkill_success(monkeypatch):
    proc = Process()
    _terminate(monkeypatch, proc, killer=Process(wait_result=0))
    assert not proc.killed


@pytest.mark.parametrize("exit_code", [1, 5])
def test_windows_taskkill_failure_falls_back(monkeypatch, exit_code):
    proc = Process()
    _terminate(monkeypatch, proc, killer=Process(wait_result=exit_code))
    assert proc.killed


def test_windows_taskkill_timeout_falls_back(monkeypatch):
    proc = Process()
    real_wait_for = asyncio.wait_for
    calls = 0

    async def wait_for(awaitable, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            awaitable.close()
            raise TimeoutError
        return await real_wait_for(awaitable, timeout)

    monkeypatch.setattr(model_manager_core.asyncio, "wait_for", wait_for)
    _terminate(monkeypatch, proc, killer=Process())
    assert proc.killed


def test_windows_taskkill_launch_failure_falls_back(monkeypatch):
    proc = Process()
    _terminate(monkeypatch, proc, launch_error=OSError("unavailable"))
    assert proc.killed


def test_converter_exit_before_fallback_kill(monkeypatch):
    proc = Process()
    killer = Process(wait_result=1, wait_hook=lambda: setattr(proc, "returncode", 0))
    _terminate(monkeypatch, proc, killer=killer)
    assert not proc.killed


@pytest.mark.parametrize("error", [ProcessLookupError(), OSError("gone")])
def test_fallback_kill_process_disappearance_is_suppressed(monkeypatch, error):
    proc = Process(kill_error=error)
    _terminate(monkeypatch, proc, killer=Process(wait_result=1))
    assert not proc.killed


@pytest.mark.parametrize("wait_error", [None, ProcessLookupError(), OSError("gone")])
def test_converter_final_wait_is_bounded_and_expected_errors_are_safe(
    monkeypatch, wait_error, caplog
):
    proc = Process(wait_error=wait_error)
    calls = []
    real_wait_for = asyncio.wait_for

    async def wait_for(awaitable, timeout):
        calls.append(timeout)
        return await real_wait_for(awaitable, timeout)

    monkeypatch.setattr(model_manager_core.asyncio, "wait_for", wait_for)
    with caplog.at_level(logging.WARNING):
        _terminate(monkeypatch, proc, platform="posix")
    assert calls == [model_manager_core.CONVERTER_EXIT_TIMEOUT_SECONDS]
    assert "secret" not in caplog.text


def test_converter_final_wait_timeout_is_bounded_and_sanitized(monkeypatch, caplog):
    proc = Process()

    async def wait_for(awaitable, timeout):
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(model_manager_core.asyncio, "wait_for", wait_for)
    with caplog.at_level(logging.WARNING):
        _terminate(monkeypatch, proc, platform="posix")
    assert "cancellation timeout" in caplog.text
    assert "taskkill" not in caplog.text
    assert "123" not in caplog.text


def test_non_windows_kills_converter(monkeypatch):
    proc = Process()
    _terminate(monkeypatch, proc, platform="posix")
    assert proc.killed


@pytest.mark.parametrize("cleanup_error", [None, RuntimeError("cleanup defect")])
def test_conversion_cancellation_preserves_state_cleanup_and_retry(
    monkeypatch, cleanup_error, caplog
):
    async def scenario():
        cfg = SimpleNamespace(name="Test Model", source_model="example/model")
        manager = SimpleNamespace(
            catalog={"test-model": cfg},
            _convert_lock=asyncio.Lock(),
            convert_tasks={},
            status_overrides={},
            progress={},
        )
        manager._set_status = model_manager_core.ModelManager._set_status.__get__(manager)
        manager._set_progress = model_manager_core.ModelManager._set_progress.__get__(manager)
        manager._sanitize_progress_line = (
            model_manager_core.ModelManager._sanitize_progress_line.__get__(manager)
        )
        proc = Process(wait_error=asyncio.CancelledError())
        proc.stdout = None
        proc.stderr = None

        async def read_stream(*_args):
            return []

        async def terminate(_proc):
            if cleanup_error:
                raise cleanup_error

        manager._read_conversion_stream = read_stream
        manager._terminate_conversion_process = terminate

        async def launch(*_args, **_kwargs):
            return proc

        monkeypatch.setattr(model_manager_core.registry, "is_downloaded", lambda *_a: False)
        monkeypatch.setattr(model_manager_core.asyncio, "create_subprocess_exec", launch)
        task = asyncio.create_task(
            model_manager_core.ModelManager._convert_task(manager, "test-model", "CPU", False)
        )
        manager.convert_tasks["test-model"] = task
        with caplog.at_level(logging.ERROR):
            with pytest.raises(asyncio.CancelledError):
                await task

        assert manager.status_overrides["test-model"]["status"] == "cancelled"
        assert manager.progress["test-model"]["phase"] == "cancelled"
        assert "test-model" not in manager.convert_tasks
        assert "cleanup defect" not in caplog.text

        async def replacement():
            return None

        replacement_task = asyncio.create_task(replacement())
        manager.convert_tasks["test-model"] = replacement_task
        await replacement_task
        assert replacement_task.done()

    asyncio.run(scenario())


def test_cancelled_status_is_serialized_and_retry_requeues(tmp_path, monkeypatch):
    async def scenario():
        models_file = tmp_path / "models.json"
        models_file.write_text("{}\n", encoding="utf-8")
        manager = ModelManager(
            Settings(
                models_file=models_file,
                models_dir=tmp_path / "models",
                cache_dir=tmp_path / "cache",
                benchmark_results_file=tmp_path / "benchmarks.json",
                force_mock=True,
            )
        )
        cfg = ModelConfig(
            id="retry-model",
            name="Retry Model",
            description="",
            backend="openvino-genai",
            model_path=str(tmp_path / "models" / "retry-model"),
            source_model="example/retry",
            weight_format="int4",
            recommended_device="CPU",
            max_context_len=2048,
            max_output_tokens=512,
        )
        manager.catalog[cfg.id] = cfg
        manager._set_status(cfg.id, "cancelled")
        manager._set_progress(cfg.id, "cancelled", "Conversion cancelled.")

        entry = manager.catalog_entry(cfg.id)
        assert entry["status"] == "cancelled"
        assert entry["is_loading"] is False
        assert entry["progress"]["phase"] == "cancelled"
        assert manager.loading_count() == 0

        release = asyncio.Event()

        async def conversion(*_args, **_kwargs):
            try:
                await release.wait()
            finally:
                manager.convert_tasks.pop(cfg.id, None)

        monkeypatch.setattr(manager, "_convert_task", conversion)
        task = manager.schedule_convert(cfg.id, load_after=False)
        assert task is not None
        assert manager.status_overrides[cfg.id]["status"] == "queued_convert"
        assert manager.progress[cfg.id]["phase"] == "queued"

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
