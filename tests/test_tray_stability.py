"""Regression coverage for tray menu stability while the menu is on screen.

The Windows notification-area menu is a native handle that pystray destroys and
rebuilds on ``update_menu``. The status poller runs on a separate thread, so a
rebuild can land while the user has the menu open and is hovering over items,
corrupting the handle Windows is actively drawing. These tests lock in the two
defences: deferring rebuilds while the menu is displayed, and skipping refreshes
that would not change anything visible.
"""

from __future__ import annotations

import threading
import types

from app.tray_polling import TrayPollingMixin
from app.tray_state import TrayPhase, TraySnapshot
from app.tray_support import guarded_tray_icon


class _FakeBaseIcon:
    """Minimal stand-in for ``pystray.Icon`` recording native rebuilds."""

    def __init__(self, *args, **kwargs):
        # Records ``_menu_on_screen`` at the moment each native rebuild runs, so
        # a rebuild that happened while the menu was displayed is detectable.
        self.rebuilds: list[bool] = []
        self.during_show = None

    def update_menu(self):  # mirrors pystray._base.Icon.update_menu
        self._update_menu()

    def _update_menu(self):  # the native DestroyMenu + rebuild
        self.rebuilds.append(getattr(self, "_menu_on_screen", False))

    def _on_notify(self, wparam, lparam):
        # Stand in for the blocking TrackPopupMenuEx: the menu is on screen for
        # the duration of this call. Simulate the poller poking update_menu.
        if self.during_show is not None:
            self.during_show()


def _guarded_icon():
    fake_module = types.SimpleNamespace(Icon=_FakeBaseIcon)
    return guarded_tray_icon(fake_module)()


def test_rebuild_is_deferred_while_menu_is_on_screen() -> None:
    icon = _guarded_icon()
    # The status poller calls update_menu once while the menu is displayed.
    icon.during_show = icon.update_menu

    icon._on_notify(0, 0)

    # Exactly one native rebuild happened, and it ran only after the menu closed
    # (recorded _menu_on_screen == False). Nothing rebuilt while it was shown.
    assert icon.rebuilds == [False]


def test_repeated_pokes_while_shown_collapse_to_one_rebuild() -> None:
    icon = _guarded_icon()

    def poke_several_times():
        for _ in range(5):
            icon.update_menu()

    icon.during_show = poke_several_times
    icon._on_notify(0, 0)

    assert icon.rebuilds == [False]


def test_rebuild_runs_immediately_when_menu_is_not_shown() -> None:
    icon = _guarded_icon()
    icon.update_menu()
    assert icon.rebuilds == [False]


class _RecordingIcon:
    def __init__(self):
        self.menu_updates = 0
        self.title = None
        self.icon = None

    def update_menu(self):
        self.menu_updates += 1


class _RefreshStub(TrayPollingMixin):
    """Exercises ``_refresh_icon`` coalescing without a real tray backend."""

    def __init__(self, snapshot: TraySnapshot) -> None:
        self.render_lock = threading.Lock()
        self.last_render_signature = None
        self.icon = _RecordingIcon()
        self._snap = snapshot
        self._startup = False

    def _snapshot(self) -> TraySnapshot:
        return self._snap

    def _startup_enabled(self) -> bool:
        return self._startup


def test_refresh_skips_when_nothing_visible_changed(monkeypatch) -> None:
    monkeypatch.setattr("app.tray_polling.tray_icon", lambda phase: object())
    stub = _RefreshStub(TraySnapshot(phase=TrayPhase.READY, server_status="Ready"))

    stub._refresh_icon()
    stub._refresh_icon()  # identical snapshot -> no second native rebuild

    assert stub.icon.menu_updates == 1


def test_refresh_rebuilds_when_snapshot_changes(monkeypatch) -> None:
    monkeypatch.setattr("app.tray_polling.tray_icon", lambda phase: object())
    stub = _RefreshStub(TraySnapshot(phase=TrayPhase.READY, server_status="Ready"))

    stub._refresh_icon()
    stub._snap = TraySnapshot(phase=TrayPhase.STOPPED, server_status="Stopped")
    stub._refresh_icon()

    assert stub.icon.menu_updates == 2


def test_refresh_rebuilds_when_only_startup_state_changes(monkeypatch) -> None:
    monkeypatch.setattr("app.tray_polling.tray_icon", lambda phase: object())
    stub = _RefreshStub(TraySnapshot(phase=TrayPhase.READY, server_status="Ready"))

    stub._refresh_icon()
    stub._startup = True  # e.g. the user toggled "Start with Windows"
    stub._refresh_icon()

    assert stub.icon.menu_updates == 2
