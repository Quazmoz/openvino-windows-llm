import asyncio
from types import SimpleNamespace

from app import model_manager_core


class Process:
    def __init__(self, *, returncode=None, wait_result=0):
        self.returncode = returncode
        self.wait_result = wait_result
        self.pid = 123
        self.killed = False

    async def wait(self):
        return self.wait_result

    def kill(self):
        self.killed = True


def test_windows_taskkill_success(monkeypatch):
    proc = Process()
    killer = Process(wait_result=0)
    monkeypatch.setattr(model_manager_core.os, "name", "nt")
    monkeypatch.setattr(
        model_manager_core.asyncio,
        "create_subprocess_exec",
        lambda *_a, **_k: asyncio.sleep(0, result=killer),
    )
    asyncio.run(
        model_manager_core.ModelManager._terminate_conversion_process(SimpleNamespace(), proc)
    )
    assert not proc.killed


def test_windows_taskkill_failure_falls_back(monkeypatch):
    proc = Process()
    killer = Process(wait_result=1)
    monkeypatch.setattr(model_manager_core.os, "name", "nt")
    monkeypatch.setattr(
        model_manager_core.asyncio,
        "create_subprocess_exec",
        lambda *_a, **_k: asyncio.sleep(0, result=killer),
    )
    asyncio.run(
        model_manager_core.ModelManager._terminate_conversion_process(SimpleNamespace(), proc)
    )
    assert proc.killed


def test_non_windows_kills_converter(monkeypatch):
    proc = Process()
    monkeypatch.setattr(model_manager_core.os, "name", "posix")
    asyncio.run(
        model_manager_core.ModelManager._terminate_conversion_process(SimpleNamespace(), proc)
    )
    assert proc.killed
