"""Per-chat browser context isolation for the bundled multi-conversation UI."""

from __future__ import annotations

from app import ui_extension

_EXTENSION_ID = "ovllm-chat-context-extension"

CHAT_CONTEXT_JS = r"""
(() => {
    'use strict';
    if (window.__ovllmChatContextInstalled) return;
    window.__ovllmChatContextInstalled = true;

    if (
        typeof makeChat !== 'function' || typeof activeChat !== 'function' ||
        typeof executeGeneration !== 'function' || typeof saveChats !== 'function'
    ) return;

    const CONTEXT_VERSION = 1;
    const MAX_SYSTEM_PROMPT_CHARS = 32768;
    const MAX_DRAFT_CHARS = 100000;
    let saveTimer = null;
    let generationTail = Promise.resolve();

    function boundedText(value, limit) {
        return String(value ?? '').slice(0, limit);
    }

    function ensureChatContext(chat, useCurrentDefaults = false) {
        if (!chat || typeof chat !== 'object') return null;
        if (!Array.isArray(chat.messages)) chat.messages = [];
        if (!Object.prototype.hasOwnProperty.call(chat, 'modelId')) {
            chat.modelId = useCurrentDefaults ? (modelSelect.value || null) : null;
        }
        if (!Object.prototype.hasOwnProperty.call(chat, 'systemPrompt')) {
            chat.systemPrompt = useCurrentDefaults
                ? boundedText(settingsSystemPrompt.value, MAX_SYSTEM_PROMPT_CHARS)
                : boundedText(localStorage.getItem('ovllm.system_prompt.v1') || '', MAX_SYSTEM_PROMPT_CHARS);
        }
        if (!Object.prototype.hasOwnProperty.call(chat, 'draft')) chat.draft = '';
        chat.systemPrompt = boundedText(chat.systemPrompt, MAX_SYSTEM_PROMPT_CHARS);
        chat.draft = boundedText(chat.draft, MAX_DRAFT_CHARS);
        chat.contextVersion = CONTEXT_VERSION;
        return chat;
    }

    function scheduleSave() {
        clearTimeout(saveTimer);
        saveTimer = window.setTimeout(() => saveChats(), 120);
    }

    function captureVisibleContext(chat = activeChat(), includeDraft = true) {
        chat = ensureChatContext(chat, true);
        if (!chat) return null;
        if (modelSelect.value) chat.modelId = modelSelect.value;
        chat.systemPrompt = boundedText(settingsSystemPrompt.value, MAX_SYSTEM_PROMPT_CHARS);
        if (includeDraft) chat.draft = boundedText(userInput.value, MAX_DRAFT_CHARS);
        return chat;
    }

    function applyChatContext(chat, { restoreDraft = true } = {}) {
        chat = ensureChatContext(chat, true);
        if (!chat) return;
        if (chat.modelId && availableModels.has(chat.modelId)) {
            modelSelect.value = chat.modelId;
        } else if (!chat.modelId && modelSelect.value) {
            chat.modelId = modelSelect.value;
        }
        settingsSystemPrompt.value = chat.systemPrompt;
        if (restoreDraft) {
            userInput.value = chat.draft;
            autoResize();
        }
        updateModelUi();
        updateSendButtonState();
    }

    // Migrate existing browser data without combining or cloning message arrays.
    chats.forEach(chat => ensureChatContext(chat, chat.id === activeChatId));
    conversation = activeChat()?.messages || [];
    applyChatContext(activeChat());
    saveChats();

    const originalMakeChat = makeChat;
    makeChat = function contextAwareMakeChat(messages = []) {
        const chat = originalMakeChat(messages);
        chat.modelId = modelSelect.value || null;
        chat.systemPrompt = boundedText(settingsSystemPrompt.value, MAX_SYSTEM_PROMPT_CHARS);
        chat.draft = '';
        chat.contextVersion = CONTEXT_VERSION;
        return chat;
    };

    const originalSwitchChat = switchChat;
    switchChat = function contextAwareSwitchChat(id) {
        captureVisibleContext(activeChat());
        const result = originalSwitchChat(id);
        applyChatContext(activeChat());
        saveChats();
        return result;
    };

    const originalNewChat = newChat;
    newChat = function contextAwareNewChat() {
        captureVisibleContext(activeChat());
        const result = originalNewChat();
        applyChatContext(activeChat());
        saveChats();
        return result;
    };

    const originalDeleteChat = deleteChat;
    deleteChat = function contextAwareDeleteChat(id) {
        captureVisibleContext(activeChat());
        if (queuedChat?.id === id) {
            queuedPrompt = null;
            queuedChat = null;
            activeLoaderBubble = null;
        }
        const result = originalDeleteChat(id);
        applyChatContext(activeChat());
        saveChats();
        return result;
    };

    const originalRenderModelOptions = renderModelOptions;
    renderModelOptions = function contextAwareRenderModelOptions(models) {
        const result = originalRenderModelOptions(models);
        const chat = ensureChatContext(activeChat(), true);
        if (chat?.modelId && availableModels.has(chat.modelId)) modelSelect.value = chat.modelId;
        return result;
    };

    const originalStartQueuedLoad = startQueuedLoad;
    startQueuedLoad = function contextAwareQueuedLoad(text, selectedModel) {
        const chat = ensureChatContext(activeChat(), true);
        if (chat) {
            chat.modelId = selectedModel?.id || modelSelect.value || chat.modelId;
            chat.systemPrompt = boundedText(settingsSystemPrompt.value, MAX_SYSTEM_PROMPT_CHARS);
            chat.draft = '';
            saveChats();
        }
        return originalStartQueuedLoad(text, selectedModel);
    };

    const originalSendMessage = sendMessage;
    sendMessage = function contextAwareSendMessage(...args) {
        const chat = captureVisibleContext(activeChat());
        const promise = originalSendMessage(...args);
        if (chat && userInput.value === '') {
            chat.draft = '';
            saveChats();
        }
        return promise;
    };

    function patchAssistantMetadata(chat, modelId) {
        if (!chat || !Array.isArray(chat.messages)) return;
        for (let index = chat.messages.length - 1; index >= 0; index -= 1) {
            const message = chat.messages[index];
            if (message?.role !== 'assistant') continue;
            if (message.meta) message.meta = { ...message.meta, model: modelId };
            break;
        }
    }

    const originalExecuteGeneration = executeGeneration;
    executeGeneration = function contextAwareExecuteGeneration(aiBubble, genChat = activeChat()) {
        const targetChat = ensureChatContext(genChat || activeChat(), true);
        if (!targetChat) return originalExecuteGeneration(aiBubble, genChat);

        const context = {
            chatId: targetChat.id,
            modelId: targetChat.modelId || modelSelect.value,
            systemPrompt: boundedText(targetChat.systemPrompt, MAX_SYSTEM_PROMPT_CHARS),
        };
        targetChat.modelId = context.modelId;
        targetChat.systemPrompt = context.systemPrompt;
        saveChats();

        const run = async () => {
            const visibleChat = activeChat();
            if (context.modelId && availableModels.has(context.modelId)) modelSelect.value = context.modelId;
            settingsSystemPrompt.value = context.systemPrompt;

            let generationPromise;
            try {
                // The base function builds its request body synchronously before its
                // first await. Restore the visible chat immediately afterward so a
                // background queued chat cannot change the controls of another chat.
                generationPromise = originalExecuteGeneration(aiBubble, targetChat);
            } catch (error) {
                applyChatContext(activeChat());
                throw error;
            }
            if (visibleChat?.id !== targetChat.id) applyChatContext(visibleChat);

            try {
                return await generationPromise;
            } finally {
                targetChat.modelId = context.modelId;
                targetChat.systemPrompt = context.systemPrompt;
                patchAssistantMetadata(targetChat, context.modelId);
                saveChats();
                applyChatContext(activeChat());
            }
        };

        // Model-load completion can enqueue a response while another chat is still
        // generating. Serialize those jobs so global AbortController/UI state cannot
        // cross wires between conversations.
        const queued = generationTail.then(run, run);
        generationTail = queued.catch(() => undefined);
        return queued;
    };

    modelSelect.addEventListener('change', () => {
        const chat = ensureChatContext(activeChat(), true);
        if (!chat) return;
        chat.modelId = modelSelect.value || null;
        scheduleSave();
    });

    settingsSystemPrompt.addEventListener('input', () => {
        const chat = ensureChatContext(activeChat(), true);
        if (!chat) return;
        chat.systemPrompt = boundedText(settingsSystemPrompt.value, MAX_SYSTEM_PROMPT_CHARS);
        scheduleSave();
    });

    userInput.addEventListener('input', () => {
        const chat = ensureChatContext(activeChat(), true);
        if (!chat) return;
        chat.draft = boundedText(userInput.value, MAX_DRAFT_CHARS);
        scheduleSave();
    });

    window.addEventListener('beforeunload', () => {
        captureVisibleContext(activeChat());
        saveChats();
    });

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
    window.fetch = async function chatContextFetch(input, init = {}) {
        const target = endpoint(input);
        let registeredModelId = null;
        if (target.sameOrigin && target.path === '/v1/models/download-custom') {
            try { registeredModelId = JSON.parse(String(init.body || '')).model_id || null; }
            catch { registeredModelId = null; }
        }

        const response = await previousFetch(input, init);
        if (registeredModelId && response.ok) {
            const chat = ensureChatContext(activeChat(), true);
            if (chat) {
                chat.modelId = registeredModelId;
                saveChats();
            }
        }
        if (target.sameOrigin && target.path === '/v1/system/status' && response.ok) {
            // Base status rendering may rebuild the select and prefer a model loading
            // for another chat. Reassert the active chat's selection after that task.
            window.setTimeout(() => applyChatContext(activeChat(), { restoreDraft: false }), 80);
        }
        return response;
    };
})();
"""


def install_chat_context_extension() -> None:
    """Compose per-chat context isolation after existing browser extensions."""

    if getattr(ui_extension, "_CHAT_CONTEXT_EXTENSION_INSTALLED", False):
        return
    previous_inject = ui_extension.inject_multimodal_ui

    def inject_with_chat_context(html: str) -> str:
        html = previous_inject(html)
        if f'id="{_EXTENSION_ID}"' in html:
            return html
        script = f'\n<script id="{_EXTENSION_ID}">\n{CHAT_CONTEXT_JS}\n</script>\n'
        if "</body>" in html:
            return html.replace("</body>", f"{script}</body>", 1)
        return html + script

    ui_extension.inject_multimodal_ui = inject_with_chat_context
    ui_extension._CHAT_CONTEXT_EXTENSION_INSTALLED = True
