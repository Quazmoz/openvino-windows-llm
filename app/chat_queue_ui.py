"""Per-chat pending prompt queue for model download/load workflows."""

from __future__ import annotations

from app import ui_extension

_EXTENSION_ID = "ovllm-chat-queue-extension"

CHAT_QUEUE_JS = r"""
(() => {
    'use strict';
    if (window.__ovllmChatQueueInstalled) return;
    window.__ovllmChatQueueInstalled = true;

    if (typeof startQueuedLoad !== 'function' || typeof executeGeneration !== 'function') return;

    const pendingChats = new Map();

    function chatStillExists(chat) {
        return !!chat && chats.some(candidate => candidate === chat || candidate.id === chat.id);
    }

    function detachedBubble() {
        const bubble = document.createElement('div');
        const content = document.createElement('div');
        bubble.appendChild(content);
        return bubble;
    }

    function loaderBubble(model, loadDevice) {
        const bubble = appendMessage('ai', '', true);
        const action = model.status === 'converting' || model.can_convert
            ? 'Downloading and converting'
            : 'Loading';
        bubble.firstElementChild.innerHTML = `
            <div class="model-loader-status" style="display:flex;align-items:center;gap:10px;padding:4px 0;color:var(--amber);">
                <div class="spinner"></div>
                <span>${escapeHtml(action)} <strong>${escapeHtml(model.name)}</strong> on <strong>${escapeHtml(loadDevice)}</strong>…</span>
            </div>
        `;
        return bubble;
    }

    function rememberPending(chat, modelId, bubble = null) {
        chat.pendingModelId = modelId;
        chat.pendingSince = chat.pendingSince || Date.now();
        const job = {
            chat,
            modelId,
            bubble: bubble || detachedBubble(),
            running: false,
            resumeStarted: false,
        };
        pendingChats.set(chat.id, job);
        saveChats();
        return job;
    }

    function clearPending(job) {
        pendingChats.delete(job.chat.id);
        if (chatStillExists(job.chat)) {
            delete job.chat.pendingModelId;
            delete job.chat.pendingSince;
            saveChats();
        }
    }

    function showPreparationError(job, message) {
        const content = job.bubble?.firstElementChild;
        if (content) {
            content.innerHTML = `<span style="color:var(--red)">⚠ Failed to prepare model: ${escapeHtml(message || 'Unknown error')}</span>`;
        }
        if (activeChatId === job.chat.id) showToast('Model preparation failed');
        clearPending(job);
    }

    function runPending(job) {
        if (job.running || !chatStillExists(job.chat)) {
            if (!chatStillExists(job.chat)) clearPending(job);
            return;
        }
        job.running = true;
        void executeGeneration(job.bubble, job.chat)
            .catch(() => undefined)
            .finally(() => clearPending(job));
    }

    function processStatus(data) {
        const models = data?.models?.available;
        if (!Array.isArray(models)) return;
        const byId = new Map(models.map(model => [model.id, model]));

        pendingChats.forEach(job => {
            if (!chatStillExists(job.chat)) {
                clearPending(job);
                return;
            }
            const model = byId.get(job.modelId);
            if (!model) return;
            if (model.is_loaded) {
                runPending(job);
                return;
            }
            if (model.status === 'error') {
                showPreparationError(job, model.error || model.status_label);
                return;
            }
            if (job.resumeStarted || model.is_loading) return;
            if (model.can_load) {
                job.resumeStarted = true;
                requestModelLoad(model.id, true);
            } else if (model.can_convert) {
                job.resumeStarted = true;
                requestModelConvert(model.id, true);
            }
        });
    }

    // Recover pending chats after a browser refresh. The user message is already
    // persisted in that chat, so only the eventual assistant response is resumed.
    chats.forEach(chat => {
        if (chat?.pendingModelId && Array.isArray(chat.messages) && chat.messages.at(-1)?.role === 'user') {
            rememberPending(chat, chat.pendingModelId);
        } else if (chat && (chat.pendingModelId || chat.pendingSince)) {
            delete chat.pendingModelId;
            delete chat.pendingSince;
        }
    });
    saveChats();

    startQueuedLoad = function perChatQueuedLoad(text, selectedModel) {
        const chat = activeChat();
        if (!chat || !selectedModel) return;
        if (pendingChats.has(chat.id)) {
            showToast('This chat already has a prompt waiting for its model.');
            return;
        }

        chat.modelId = selectedModel.id;
        chat.systemPrompt = String(settingsSystemPrompt.value || '').slice(0, 32768);
        chat.draft = '';
        userInput.value = '';
        autoResize();

        chat.messages.push({ role: 'user', content: text });
        saveConversation(chat);
        appendMessage('user', text);
        scrollToBottom(true);

        const bubble = loaderBubble(selectedModel, modelLoadDevice());
        rememberPending(chat, selectedModel.id, bubble);
        scrollToBottom(true);

        // Disable the legacy single-slot queue. Status processing below owns every
        // pending chat independently, including several chats waiting on one model.
        queuedPrompt = null;
        queuedChat = null;
        activeLoaderBubble = null;
        waitingForModelId = selectedModel.id;

        if (selectedModel.can_convert) requestModelConvert(selectedModel.id, true);
        else if (selectedModel.can_load) requestModelLoad(selectedModel.id, true);
        setStatusPolling(1000);
    };

    const previousDeleteChat = deleteChat;
    deleteChat = function queuedChatAwareDelete(id) {
        const job = pendingChats.get(id);
        if (job) clearPending(job);
        return previousDeleteChat(id);
    };

    function endpoint(input) {
        const value = typeof input === 'string' ? input : input instanceof URL ? input.href : input?.url || '';
        try {
            const url = new URL(value, window.location.href);
            return { path: url.pathname, sameOrigin: url.origin === window.location.origin };
        } catch {
            return { path: '', sameOrigin: false };
        }
    }

    const previousFetch = window.fetch.bind(window);
    window.fetch = async function queuedChatFetch(input, init = {}) {
        const response = await previousFetch(input, init);
        const target = endpoint(input);
        if (target.sameOrigin && target.path === '/v1/system/status' && response.ok) {
            response.clone().json().then(processStatus).catch(() => undefined);
        }
        return response;
    };

    async function initialStatus() {
        const key = localStorage.getItem('ovllm.apikey.v1') || '';
        const headers = key ? { Authorization: `Bearer ${key}` } : {};
        try {
            const response = await previousFetch('/v1/system/status', { headers });
            if (response.ok) processStatus(await response.json());
        } catch { /* base UI owns connectivity errors */ }
    }
    void initialStatus();
})();
"""


def install_chat_queue_extension() -> None:
    """Compose the per-chat pending queue after context isolation."""

    if getattr(ui_extension, "_CHAT_QUEUE_EXTENSION_INSTALLED", False):
        return
    previous_inject = ui_extension.inject_multimodal_ui

    def inject_with_chat_queue(html: str) -> str:
        html = previous_inject(html)
        if f'id="{_EXTENSION_ID}"' in html:
            return html
        script = f'\n<script id="{_EXTENSION_ID}">\n{CHAT_QUEUE_JS}\n</script>\n'
        if "</body>" in html:
            return html.replace("</body>", f"{script}</body>", 1)
        return html + script

    ui_extension.inject_multimodal_ui = inject_with_chat_queue
    ui_extension._CHAT_QUEUE_EXTENSION_INSTALLED = True
