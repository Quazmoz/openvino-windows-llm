from app.config import Settings  # noqa: F401 - installs composed UI extensions
from app.ui_extension import inject_multimodal_ui


def test_chat_context_extension_is_injected_once():
    html = '<html><body><select id="model-select"></select></body></html>'

    rendered = inject_multimodal_ui(html)
    rendered_twice = inject_multimodal_ui(rendered)

    assert rendered.count('id="ovllm-chat-context-extension"') == 1
    assert rendered_twice.count('id="ovllm-chat-context-extension"') == 1


def test_chat_context_extension_persists_each_chat_configuration():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "chat.modelId" in rendered
    assert "chat.systemPrompt" in rendered
    assert "chat.draft" in rendered
    assert "chat.contextVersion" in rendered
    assert "applyChatContext(activeChat())" in rendered
    assert "captureVisibleContext(activeChat())" in rendered


def test_chat_context_extension_pins_and_serializes_generation():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "originalExecuteGeneration(aiBubble, targetChat)" in rendered
    assert "generationTail.then(run, run)" in rendered
    assert "targetChat.modelId = context.modelId" in rendered
    assert "targetChat.systemPrompt = context.systemPrompt" in rendered
    assert "patchAssistantMetadata(targetChat, context.modelId)" in rendered


def test_chat_context_extension_handles_queued_and_deleted_chats():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "originalStartQueuedLoad" in rendered
    assert "queuedChat?.id === id" in rendered
    assert "queuedPrompt = null" in rendered
    assert "activeLoaderBubble = null" in rendered


def test_chat_context_extension_reasserts_active_chat_after_status_poll():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "target.path === '/v1/system/status'" in rendered
    assert "applyChatContext(activeChat(), { restoreDraft: false })" in rendered
    assert "target.path === '/v1/models/download-custom'" in rendered
