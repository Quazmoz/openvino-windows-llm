"""Make the built-in first-test model start on NPU in the browser UI.

Older installations can retain a browser-local CPU preference or can have the default
model already loading on CPU before the UI opens. The backend can safely retarget an
in-flight or loaded model, but the browser previously never issued that NPU request.
This extension performs a one-time bootstrap for TinyLlama, then permanently returns
control of device selection to the user after NPU readiness has been observed.
"""

from __future__ import annotations

from app import ui_extension

_BOOTSTRAP_ID = "ovllm-first-run-npu-bootstrap"
_EXTENSION_ID = "ovllm-first-run-npu-extension"

FIRST_RUN_NPU_BOOTSTRAP_JS = r"""
(() => {
    'use strict';
    const COMPLETE_KEY = 'ovllm.first-npu-ready.v1';
    const DEVICE_KEY = 'ovllm.device.v1';
    try {
        if (localStorage.getItem(COMPLETE_KEY) !== '1') {
            // This runs in <head>, before the base UI reads its device preference.
            // It also repairs the legacy browser default that selected CPU.
            localStorage.setItem(DEVICE_KEY, 'NPU');
        }
    } catch {
        // Private browsing/storage restrictions must not prevent the UI from loading.
    }
})();
"""

FIRST_RUN_NPU_EXTENSION_JS = r"""
(() => {
    'use strict';
    if (window.__ovllmFirstRunNpuInstalled) return;
    window.__ovllmFirstRunNpuInstalled = true;

    const FIRST_TEST_MODEL_ID = 'tinyllama-1.1b-chat-fp16';
    const COMPLETE_KEY = 'ovllm.first-npu-ready.v1';
    const DEVICE_KEY = 'ovllm.device.v1';
    let attemptedRetarget = false;

    function normalized(value) {
        return String(value || '').trim().toUpperCase();
    }

    function isComplete() {
        try {
            return localStorage.getItem(COMPLETE_KEY) === '1';
        } catch {
            return false;
        }
    }

    function markComplete() {
        try {
            localStorage.setItem(COMPLETE_KEY, '1');
        } catch {
            // The current page still remains correctly targeted at NPU.
        }
    }

    function rememberNpu() {
        try {
            localStorage.setItem(DEVICE_KEY, 'NPU');
        } catch {
            // The base UI already defaults to NPU when storage is unavailable.
        }
    }

    function endpoint(input) {
        const value = typeof input === 'string'
            ? input
            : input instanceof URL
                ? input.href
                : input?.url || '';
        try {
            const url = new URL(value, window.location.href);
            return { path: url.pathname, sameOrigin: url.origin === window.location.origin };
        } catch {
            return { path: '', sameOrigin: false };
        }
    }

    function authHeaders() {
        let key = '';
        try {
            key = localStorage.getItem('ovllm.apikey.v1') || '';
        } catch {
            key = '';
        }
        return key
            ? { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` }
            : { 'Content-Type': 'application/json' };
    }

    function selectFirstTestModel() {
        window.setTimeout(() => {
            const modelSelect = document.getElementById('model-select');
            if (!(modelSelect instanceof HTMLSelectElement)) return;
            if (!modelSelect.querySelector(`option[value="${FIRST_TEST_MODEL_ID}"]`)) return;
            if (modelSelect.value === FIRST_TEST_MODEL_ID) return;
            modelSelect.value = FIRST_TEST_MODEL_ID;
            modelSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }, 0);
    }

    const previousFetch = window.fetch.bind(window);

    async function retargetToNpu() {
        if (attemptedRetarget || isComplete()) return;
        attemptedRetarget = true;
        rememberNpu();
        try {
            const response = await previousFetch('/v1/models/load', {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ model: FIRST_TEST_MODEL_ID, device: 'NPU' }),
            });
            if (!response.ok) {
                console.warn('First-test model could not be retargeted to NPU.', response.status);
            }
        } catch (error) {
            console.warn('First-test NPU retarget request failed.', error);
        }
    }

    function reconcile(data) {
        if (isComplete()) return;
        const devices = Array.isArray(data?.device?.available) ? data.device.available : [];
        const npuAvailable = devices.some(device => /^NPU(?:\.\d+)?$/.test(normalized(device)));
        if (!npuAvailable) return;

        const models = Array.isArray(data?.models?.available) ? data.models.available : [];
        const model = models.find(item => item?.id === FIRST_TEST_MODEL_ID);
        if (!model) return;

        rememberNpu();
        selectFirstTestModel();

        if (model.is_loaded && /^NPU(?:\.\d+)?$/.test(normalized(model.device))) {
            markComplete();
            return;
        }

        // The lifecycle manager safely retargets both an in-flight CPU/GPU build and
        // an already-loaded engine without discarding the working engine first.
        if (model.is_loading || model.is_loaded) {
            void retargetToNpu();
        }
    }

    window.fetch = async function firstRunNpuFetch(input, init = {}) {
        const target = endpoint(input);
        const response = await previousFetch(input, init);
        if (target.sameOrigin && target.path === '/v1/system/status' && response.ok) {
            response.clone().json().then(reconcile).catch(() => {});
        }
        return response;
    };

    async function initialStatus() {
        try {
            const key = localStorage.getItem('ovllm.apikey.v1') || '';
            const headers = key ? { Authorization: `Bearer ${key}` } : {};
            const response = await previousFetch('/v1/system/status', { headers });
            if (response.ok) reconcile(await response.json());
        } catch {
            // The normal UI polling path owns connectivity and authentication errors.
        }
    }

    void initialStatus();
})();
"""


def install_first_run_npu_extension() -> None:
    """Install the one-time first-test NPU bootstrap after other UI extensions."""

    if getattr(ui_extension, "_FIRST_RUN_NPU_EXTENSION_INSTALLED", False):
        return
    previous_inject = ui_extension.inject_multimodal_ui

    def inject_with_first_run_npu(html: str) -> str:
        html = previous_inject(html)
        if f'id="{_EXTENSION_ID}"' in html:
            return html

        bootstrap = f'\n<script id="{_BOOTSTRAP_ID}">\n{FIRST_RUN_NPU_BOOTSTRAP_JS}\n</script>\n'
        extension = f'\n<script id="{_EXTENSION_ID}">\n{FIRST_RUN_NPU_EXTENSION_JS}\n</script>\n'
        if "</head>" in html:
            html = html.replace("</head>", f"{bootstrap}</head>", 1)
        else:
            html = bootstrap + html
        if "</body>" in html:
            return html.replace("</body>", f"{extension}</body>", 1)
        return html + extension

    ui_extension.inject_multimodal_ui = inject_with_first_run_npu
    ui_extension._FIRST_RUN_NPU_EXTENSION_INSTALLED = True
