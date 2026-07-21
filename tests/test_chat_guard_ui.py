from app.config import Settings  # noqa: F401 - installs composed UI extensions
from app.ui_extension import inject_multimodal_ui


def test_chat_guard_extension_is_injected_once_and_last():
    html = '<html><body></body></html>'

    rendered = inject_multimodal_ui(html)
    rendered_twice = inject_multimodal_ui(rendered)

    assert rendered.count('id="ovllm-chat-guard-extension"') == 1
    assert rendered_twice.count('id="ovllm-chat-guard-extension"') == 1
    assert rendered.index('id="ovllm-chat-queue-extension"') < rendered.index(
        'id="ovllm-chat-guard-extension"'
    )


def test_chat_guard_assigns_attachments_to_the_selecting_chat():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "let ownerChatId = null" in rendered
    assert "function markOwner()" in rendered
    assert "ownerChatId = chatId" in rendered
    assert "hasPendingForChat" in rendered
    assert "window.__ovllmVisionGuard" in rendered


def test_chat_guard_handles_files_without_browser_mime_metadata():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "function isSupportedImageFile(file)" in rendered
    assert "type.startsWith('image/')" in rendered
    assert "jpe?g|png|webp" in rendered


def test_chat_guard_clears_images_on_chat_or_model_changes():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "attachmentAwareSwitchChat" in rendered
    assert "attachmentAwareNewChat" in rendered
    assert "attachmentAwareDeleteChat" in rendered
    assert "selected model changed" in rendered
    assert "clearAttachmentDom()" in rendered
    assert "cancelledUntil" in rendered


def test_chat_guard_blocks_cross_chat_attachment_requests():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "window.__ovllmRequestChatId" in rendered
    assert "ownerChatId !== requestChatId" in rendered
    assert "Blocked image attachments from crossing into another chat" in rendered
    assert "status: 409" in rendered
    assert "url.origin === window.location.origin" in rendered
