"""Regression checks for the built-in UI usability hardening."""

from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(
    encoding="utf-8"
)


def test_mobile_and_touch_ergonomics_are_preserved() -> None:
    assert "/* UX_HARDENING_V1 */" in HTML
    assert "height: 100dvh" in HTML
    assert "@media (hover: none), (pointer: coarse)" in HTML
    assert "min-width: 44px" in HTML
    assert "env(safe-area-inset-bottom)" in HTML


def test_chat_list_has_no_nested_interactive_delete_control() -> None:
    assert "item.className = `chat-item" in HTML
    assert "selectButton.className = 'chat-item-main'" in HTML
    assert "const del = document.createElement('button');" in HTML
    assert "del.setAttribute('role', 'button')" not in HTML


def test_panels_and_modal_expose_accessible_state() -> None:
    assert 'aria-controls="chats-sidebar"' in HTML
    assert 'aria-controls="settings-sidebar"' in HTML
    assert 'role="dialog" aria-modal="true"' in HTML
    assert 'role="status" aria-live="polite"' in HTML
    assert "setSettingsSidebarOpen" in HTML
    assert "settingsSidebar.inert = !open" in HTML


def test_icon_only_actions_have_programmatic_names() -> None:
    assert "copyBtn.setAttribute('aria-label', 'Copy message');" in HTML
    assert "regenBtn.setAttribute('aria-label', 'Regenerate response');" in HTML
    assert "btn.setAttribute('aria-label', 'Copy code block');" in HTML
    assert "sendBtn.setAttribute('aria-label'" in HTML
