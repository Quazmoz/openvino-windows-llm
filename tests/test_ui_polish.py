from app.config import Settings  # noqa: F401 - installs composed UI extensions
from app.ui_extension import inject_multimodal_ui


def test_ui_polish_extension_is_injected_once_and_last():
    html = "<html><head></head><body></body></html>"

    rendered = inject_multimodal_ui(html)
    rendered_twice = inject_multimodal_ui(rendered)

    assert rendered.count('id="ovllm-ui-polish-extension"') == 1
    assert rendered.count('id="ovllm-ui-polish-extension-styles"') == 1
    assert rendered_twice.count('id="ovllm-ui-polish-extension"') == 1
    assert rendered.index('id="ovllm-chat-guard-extension"') < rendered.index(
        'id="ovllm-ui-polish-extension"'
    )


def test_ui_polish_adds_workspace_hierarchy_and_composer_shell():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "workspace-context-bar" in rendered
    assert "workspace-chat-title" in rendered
    assert "workspace-chat-meta" in rendered
    assert "workspace-state" in rendered
    assert "composer-shell" in rendered
    assert "empty-eyebrow" in rendered
    assert "control-field" in rendered


def test_ui_polish_surfaces_per_chat_draft_and_pending_states():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "chat.pendingModelId || hasDraft" in rendered
    assert "chat-item-state" in rendered
    assert "Waiting" in rendered
    assert "Draft" in rendered
    assert "updateWorkspaceHeader" in rendered
    assert "decorateChatList" in rendered


def test_ui_polish_retains_responsive_and_accessibility_behavior():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "@media (max-width: 700px)" in rendered
    assert "prefers-reduced-motion" in rendered
    assert "aria-live" in rendered
    assert "env(safe-area-inset-bottom)" in rendered
    assert "document.title" in rendered


def test_ui_polish_does_not_add_remote_runtime_dependencies():
    rendered = inject_multimodal_ui("<html><body></body></html>")

    assert "fonts.googleapis.com" not in rendered
    assert "cdn.jsdelivr.net" not in rendered
    assert "unpkg.com" not in rendered
