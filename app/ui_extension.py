"""Inject the multimodal UI extension into the existing single-file browser client.

Keeping the extension here avoids a risky rewrite of the large, intentionally standalone
``web/index.html`` file.  The patch is limited to that one response and leaves every
other ``FileResponse`` untouched.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse

_EXTENSION_ID = "ovllm-vision-extension"
_ORIGINAL_FILE_RESPONSE_CALL = FileResponse.__call__
_INSTALLED = False

VISION_EXTENSION_JS = r"""
(() => {
    'use strict';
    if (window.__ovllmVisionInstalled) return;
    window.__ovllmVisionInstalled = true;

    const MAX_IMAGES = 4;
    const MAX_BYTES = 10 * 1024 * 1024;
    const MAX_PIXELS = 25000000;
    const SUPPORTED = new Set(['image/jpeg', 'image/png', 'image/webp']);
    const modelCapabilities = new Map();
    let pendingImages = [];

    const form = document.getElementById('chat-form');
    const inputArea = document.getElementById('input-area');
    const userInput = document.getElementById('user-input');
    const modelSelect = document.getElementById('model-select');
    if (!form || !inputArea || !userInput || !modelSelect) return;

    const style = document.createElement('style');
    style.textContent = `
        #vision-attach-btn {
            width: 42px; height: 42px; flex: 0 0 42px; border-radius: 11px;
            border: 1px solid var(--border); background: var(--surface-2);
            color: var(--text-2); cursor: pointer; display: grid; place-items: center;
            transition: border-color .2s, color .2s, background .2s, opacity .2s;
        }
        #vision-attach-btn:hover:not(:disabled) { border-color: var(--primary); color: var(--text-1); background: var(--surface-3); }
        #vision-attach-btn:disabled { opacity: .42; cursor: not-allowed; }
        #vision-attach-btn.has-images { color: var(--primary); border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }
        #vision-preview-tray { display: none; gap: 8px; align-items: center; overflow-x: auto; padding: 0 2px 8px; }
        #vision-preview-tray.visible { display: flex; }
        .vision-preview { position: relative; flex: 0 0 auto; width: 58px; height: 58px; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; background: var(--surface-2); }
        .vision-preview img { width: 100%; height: 100%; object-fit: cover; display: block; }
        .vision-preview button { position: absolute; top: 3px; right: 3px; width: 20px; height: 20px; border: 0; border-radius: 50%; background: rgba(5,8,15,.82); color: white; cursor: pointer; font-size: 14px; line-height: 20px; }
        .vision-preview-count { flex: 0 0 auto; font-size: 11px; color: var(--text-3); line-height: 1.35; max-width: 190px; }
        #input-area.vision-drag-active { outline: 2px dashed var(--primary); outline-offset: -7px; border-radius: 16px; }
        @media (max-width: 640px) { #vision-attach-btn { width: 40px; height: 40px; flex-basis: 40px; } }
    `;
    document.head.appendChild(style);

    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/jpeg,image/png,image/webp';
    fileInput.multiple = true;
    fileInput.hidden = true;
    fileInput.id = 'vision-file-input';

    const attachButton = document.createElement('button');
    attachButton.type = 'button';
    attachButton.id = 'vision-attach-btn';
    attachButton.setAttribute('aria-label', 'Attach images');
    attachButton.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>';

    const previewTray = document.createElement('div');
    previewTray.id = 'vision-preview-tray';
    previewTray.setAttribute('aria-live', 'polite');

    form.insertBefore(attachButton, userInput);
    form.appendChild(fileInput);
    inputArea.insertBefore(previewTray, form);

    const customBackend = document.getElementById('custom-backend');
    if (customBackend && !customBackend.querySelector('option[value="openvino-vlm"]')) {
        const option = document.createElement('option');
        option.value = 'openvino-vlm';
        option.textContent = 'Vision + Text (openvino-vlm)';
        customBackend.appendChild(option);
    }
    const hfTask = document.getElementById('hf-search-task');
    if (hfTask && !hfTask.querySelector('option[value="image-text-to-text"]')) {
        const option = document.createElement('option');
        option.value = 'image-text-to-text';
        option.textContent = 'Vision Language Models (VLMs)';
        hfTask.appendChild(option);
    }

    function toast(message) {
        const element = document.getElementById('toast');
        if (!element) return;
        element.textContent = message;
        element.classList.add('show');
        window.setTimeout(() => element.classList.remove('show'), 2600);
    }

    function selectedSupportsVision() {
        return modelCapabilities.get(modelSelect.value)?.supports_vision === true;
    }

    function updateAttachState() {
        const known = modelCapabilities.has(modelSelect.value);
        const capable = selectedSupportsVision();
        attachButton.disabled = !known || !capable;
        attachButton.classList.toggle('has-images', pendingImages.length > 0);
        attachButton.title = !known
            ? 'Checking whether this model supports images…'
            : capable
                ? 'Attach up to four JPEG, PNG, or WebP images'
                : 'Select a vision-capable model to attach images';
        if (known && !capable && pendingImages.length) {
            pendingImages = [];
            renderPreviews();
            toast('Image attachments cleared because the selected model is text-only.');
        }
    }

    function renderPreviews() {
        previewTray.replaceChildren();
        previewTray.classList.toggle('visible', pendingImages.length > 0);
        pendingImages.forEach((item, index) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'vision-preview';
            wrapper.title = `${item.name} · ${item.width}×${item.height}`;
            const image = document.createElement('img');
            image.src = item.dataUrl;
            image.alt = '';
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.setAttribute('aria-label', `Remove ${item.name}`);
            remove.textContent = '×';
            remove.addEventListener('click', () => {
                pendingImages.splice(index, 1);
                renderPreviews();
            });
            wrapper.append(image, remove);
            previewTray.appendChild(wrapper);
        });
        if (pendingImages.length) {
            const note = document.createElement('div');
            note.className = 'vision-preview-count';
            note.textContent = `${pendingImages.length}/${MAX_IMAGES} attached · sent with the next request only`;
            previewTray.appendChild(note);
        }
        attachButton.classList.toggle('has-images', pendingImages.length > 0);
    }

    function readAsDataUrl(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
            reader.onload = () => resolve(String(reader.result || ''));
            reader.readAsDataURL(file);
        });
    }

    function imageDimensions(dataUrl) {
        return new Promise((resolve, reject) => {
            const image = new Image();
            image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
            image.onerror = () => reject(new Error('Image could not be decoded'));
            image.src = dataUrl;
        });
    }

    async function addFiles(fileList) {
        if (!selectedSupportsVision()) {
            toast('Select a loaded vision-capable model before attaching an image.');
            return;
        }
        for (const file of Array.from(fileList || [])) {
            if (pendingImages.length >= MAX_IMAGES) {
                toast(`A maximum of ${MAX_IMAGES} images can be attached.`);
                break;
            }
            if (!SUPPORTED.has(file.type)) {
                toast(`${file.name}: use JPEG, PNG, or WebP.`);
                continue;
            }
            if (file.size > MAX_BYTES) {
                toast(`${file.name}: images must be 10 MiB or smaller.`);
                continue;
            }
            try {
                const dataUrl = await readAsDataUrl(file);
                const dimensions = await imageDimensions(dataUrl);
                if (!dimensions.width || !dimensions.height || dimensions.width * dimensions.height > MAX_PIXELS) {
                    throw new Error('image exceeds the 25,000,000-pixel safety limit');
                }
                pendingImages.push({
                    name: file.name || `image-${pendingImages.length + 1}`,
                    type: file.type,
                    size: file.size,
                    dataUrl,
                    width: dimensions.width,
                    height: dimensions.height,
                });
            } catch (error) {
                toast(`${file.name}: ${error.message}`);
            }
        }
        fileInput.value = '';
        renderPreviews();
    }

    attachButton.addEventListener('click', () => {
        if (selectedSupportsVision()) fileInput.click();
        else toast('Select a vision-capable model first.');
    });
    fileInput.addEventListener('change', () => addFiles(fileInput.files));

    inputArea.addEventListener('dragover', event => {
        if (!event.dataTransfer?.types?.includes('Files')) return;
        event.preventDefault();
        if (selectedSupportsVision()) inputArea.classList.add('vision-drag-active');
    });
    inputArea.addEventListener('dragleave', () => inputArea.classList.remove('vision-drag-active'));
    inputArea.addEventListener('drop', event => {
        if (!event.dataTransfer?.files?.length) return;
        event.preventDefault();
        inputArea.classList.remove('vision-drag-active');
        addFiles(event.dataTransfer.files);
    });
    userInput.addEventListener('paste', event => {
        const files = Array.from(event.clipboardData?.files || []).filter(file => file.type.startsWith('image/'));
        if (files.length) addFiles(files);
    });

    modelSelect.addEventListener('change', updateAttachState);
    ['new-chat-btn', 'new-chat-side-btn'].forEach(id => {
        document.getElementById(id)?.addEventListener('click', () => {
            pendingImages = [];
            renderPreviews();
        });
    });

    function recordCapabilities(data) {
        const models = data?.models?.available;
        if (!Array.isArray(models)) return;
        modelCapabilities.clear();
        models.forEach(model => modelCapabilities.set(model.id, model));
        updateAttachState();
    }

    function responseWithJson(data, source) {
        const headers = new Headers(source.headers);
        headers.delete('content-length');
        headers.delete('content-encoding');
        headers.set('content-type', 'application/json');
        return new Response(JSON.stringify(data), {
            status: source.status,
            statusText: source.statusText,
            headers,
        });
    }

    const originalFetch = window.fetch.bind(window);
    window.fetch = async function visionAwareFetch(input, init = {}) {
        const url = typeof input === 'string' ? input : input?.url || '';
        const method = String(init?.method || (typeof input !== 'string' && input?.method) || 'GET').toUpperCase();

        if (url.includes('/v1/chat/completions') && method === 'POST' && pendingImages.length) {
            let body;
            try { body = JSON.parse(String(init.body || '')); }
            catch { return originalFetch(input, init); }

            const capabilities = modelCapabilities.get(body.model);
            if (!capabilities?.supports_vision) {
                toast('The selected model cannot process images. Choose a vision-capable model.');
                return responseWithJson({ detail: 'Selected model is not vision-capable.' }, new Response('', { status: 400 }));
            }

            const messages = Array.isArray(body.messages) ? body.messages : [];
            let userMessage = null;
            for (let index = messages.length - 1; index >= 0; index -= 1) {
                if (messages[index]?.role === 'user') { userMessage = messages[index]; break; }
            }
            if (userMessage) {
                const content = Array.isArray(userMessage.content)
                    ? [...userMessage.content]
                    : [{ type: 'text', text: String(userMessage.content || '') }];
                pendingImages.forEach(item => content.push({
                    type: 'image_url',
                    image_url: { url: item.dataUrl, detail: 'auto' },
                }));
                userMessage.content = content;
                body.messages = messages;
                init = { ...init, body: JSON.stringify(body) };
                pendingImages = [];
                renderPreviews();
            }
        }

        const response = await originalFetch(input, init);

        if (url.includes('/v1/system/status') && response.ok) {
            response.clone().json().then(recordCapabilities).catch(() => {});
        }

        if (url.includes('/v1/models/search-hf') && url.includes('task=image-text-to-text') && response.ok) {
            try {
                const data = await response.clone().json();
                if (Array.isArray(data)) data.forEach(item => { item.backend = 'openvino-vlm'; });
                return responseWithJson(data, response);
            } catch { /* preserve the original response */ }
        }
        return response;
    };

    async function refreshCapabilities() {
        const key = localStorage.getItem('ovllm.apikey.v1') || '';
        const headers = key ? { Authorization: `Bearer ${key}` } : {};
        try {
            const response = await originalFetch('/v1/system/status', { headers });
            if (response.ok) recordCapabilities(await response.json());
        } catch { /* the existing application will continue polling */ }
    }

    updateAttachState();
    refreshCapabilities();
})();
"""


def inject_multimodal_ui(html: str) -> str:
    """Return *html* with the extension inserted once before ``</body>``."""

    if f'id="{_EXTENSION_ID}"' in html:
        return html
    script = f'\n<script id="{_EXTENSION_ID}">\n{VISION_EXTENSION_JS}\n</script>\n'
    if "</body>" in html:
        return html.replace("</body>", f"{script}</body>", 1)
    return html + script


def install_ui_extension() -> None:
    """Patch ``FileResponse`` narrowly for the bundled ``web/index.html`` page."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    async def patched_call(self: FileResponse, scope, receive, send) -> None:
        path = Path(self.path)
        if path.name == "index.html" and path.parent.name == "web" and path.is_file():
            html = inject_multimodal_ui(path.read_text(encoding="utf-8"))
            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in {"content-length", "content-type", "etag", "last-modified"}
            }
            response = HTMLResponse(
                html,
                status_code=self.status_code,
                headers=headers,
                background=self.background,
            )
            await response(scope, receive, send)
            return
        await _ORIGINAL_FILE_RESPONSE_CALL(self, scope, receive, send)

    FileResponse.__call__ = patched_call
