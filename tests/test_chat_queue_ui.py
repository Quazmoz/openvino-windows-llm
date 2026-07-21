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


def test_chat_queue_disables_legacy_single_slot_state():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "queuedPrompt = null" in rendered
    assert "queuedChat = null" in rendered
    assert "activeLoaderBubble = null" in rendered
    assert "startQueuedLoad = function perChatQueuedLoad" in rendered


def test_chat_queue_resumes_and_serializes_when_models_are_ready():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "if (model.is_loaded)" in rendered
    assert "runPending(job)" in rendered
    assert "executeGeneration(job.bubble, job.chat)" in rendered
    assert "requestModelLoad(model.id, true)" in rendered
    assert "requestModelConvert(model.id, true)" in rendered


def test_chat_queue_cleans_deleted_or_failed_jobs():
    rendered = inject_multimodal_ui('<html><body></body></html>')

    assert "chatStillExists(job.chat)" in rendered
    assert "showPreparationError(job" in rendered
    assert "pendingChats.delete(job.chat.id)" in rendered
    assert "queuedChatAwareDelete" in rendered
