import socket

from app import desktop_launcher
from app.desktop_launcher import InstanceLock


def test_port_selection_falls_back_when_preferred_is_busy():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        selected = desktop_launcher.choose_available_port(port)
    assert selected != port
    assert 1 <= selected <= 65535


def test_instance_verification_requires_matching_nonce(monkeypatch):
    metadata = desktop_launcher.InstanceMetadata(1, 8123, "expected", "app.exe", "now")
    monkeypatch.setattr(
        desktop_launcher,
        "_http_json",
        lambda url, timeout=1.5: (
            {"instance_nonce": "other"} if url.endswith("/desktop/instance") else {"status": "ok"}
        ),
    )
    assert desktop_launcher.verify_instance(metadata) is False


def test_stale_metadata_is_rejected(monkeypatch):
    metadata = desktop_launcher.InstanceMetadata(999999, 8123, "expected", "app.exe", "now")
    monkeypatch.setattr(desktop_launcher, "_http_json", lambda *args, **kwargs: None)
    assert desktop_launcher.verify_instance(metadata) is False


def test_second_lock_acquire_returns_false_without_raising(tmp_path):
    """A second launch while the first holds the lock must fail cleanly.

    On Windows the msvcrt byte-range lock held by the first instance makes the
    lock file's first byte unreadable from a second handle. Acquiring the lock
    a second time must report contention by returning False, not crash the
    launcher with an unhandled PermissionError.
    """
    lock_path = tmp_path / "launcher.lock"
    first = InstanceLock(lock_path)
    second = InstanceLock(lock_path)
    assert first.acquire() is True
    try:
        assert second.acquire() is False
    finally:
        second.release()
        first.release()
    # Once the first instance releases, a fresh acquire must succeed again.
    third = InstanceLock(lock_path)
    assert third.acquire() is True
    third.release()
