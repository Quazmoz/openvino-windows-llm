from app.config import Settings  # noqa: F401 - installs composed UI extensions
from app.ui_extension import inject_multimodal_ui


def test_chat_queue_extension_is_injected_once():
    html = '<html><body></body></html>'

    rendered = inject_multimodal_ui(html)
    rendered_twice = inject_multimodal_ui(rendered)

    assert rendered.count('id="ovllm-chat-queue-extension"') == 1
    assert rendered_twice.count('id="ovllm-chat-queue-extension"') == 1


def test_chat_queue_tracks_pending_work_by_chat_id():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "const pendingChats = new Map()" in rendered
    assert "pendingChats.set(chat.id, job)" in rendered
    assert "pendingChats.has(chat.id)" in rendered
    assert "chat.pendingModelId = modelId" in rendered
    assert "chat.pendingSince" in rendered
    assert "chat.pendingReady" in rendered


def test_chat_queue_disables_legacy_single_slot_state():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "queuedPrompt = null" in rendered
    assert "queuedChat = null" in rendered
    assert "activeLoaderBubble = null" in rendered
    assert "startQueuedLoad = function perChatQueuedLoad" in rendered


def test_chat_queue_resumes_when_models_are_ready():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "if (model.is_loaded)" in rendered
    assert "markReady(job)" in rendered
    assert "runPending(job)" in rendered
    assert "executeGeneration(job.bubble, job.chat)" in rendered
    assert "requestModelLoad(model.id, true)" in rendered
    assert "requestModelConvert(model.id, true)" in rendered
    assert "PREPARATION_RETRY_MS" in rendered


def test_chat_queue_only_generates_inside_its_active_chat():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "if (activeChatId !== job.chat.id)" in rendered
    assert "markReady(job);" in rendered
    assert "if (activeChatId === job.chat.id) runPending(job)" in rendered
    assert "if (job.ready || model.is_loaded) window.setTimeout(() => runPending(job), 0)" in rendered


def test_chat_queue_cleans_deleted_failed_missing_or_expired_jobs():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "chatStillExists(job.chat)" in rendered
    assert "showPreparationError(job" in rendered
    assert "pendingChats.delete(job.chat.id)" in rendered
    assert "queuedChatAwareDelete" in rendered
    assert "MAX_PENDING_AGE_MS" in rendered
    assert "is no longer available" in rendered
    assert "pending request expired" in rendered
    assert "delete job.chat.pendingReady" in rendered


def test_chat_queue_renders_pending_state_after_switch_or_refresh():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "pendingAwareRenderChat" in rendered
    assert "ensureVisibleBubble(job)" in rendered
    assert "renderChat();" in rendered
    assert "Generating response" in rendered
    assert "Ready to generate" in rendered


def test_chat_queue_never_backgrounds_in_memory_image_attachments():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "window.__ovllmVisionGuard?.hasPendingForChat?.(chat.id)" in rendered
    assert "Images and draft were kept" in rendered
    assert "startPreparation(selectedModel)" in rendered


def test_chat_queue_preserves_generation_errors_in_the_visible_chat():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "const initialMessageCount" in rendered
    assert "const completed" in rendered
    assert "Generation did not complete" in rendered
    assert "!job.bubble?.isConnected" in rendered
