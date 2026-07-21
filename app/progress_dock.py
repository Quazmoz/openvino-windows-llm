"""Persistent compact model-preparation progress dock for the browser client."""

from __future__ import annotations

from app import ui_extension

_EXTENSION_ID = "ovllm-model-progress-dock-extension"

PROGRESS_DOCK_JS = r"""
(() => {
    'use strict';
    if (window.__ovllmProgressDockInstalled) return;
    window.__ovllmProgressDockInstalled = true;

    const style = document.createElement('style');
    style.textContent = `
        #ov-progress-dock { display:none; flex:0 0 auto; margin:10px 14px 0; padding:10px 12px;
            border:1px solid color-mix(in srgb, var(--primary) 32%, var(--border)); border-radius:11px;
            background:color-mix(in srgb, var(--surface-1) 88%, transparent); box-shadow:var(--shadow);
            backdrop-filter:blur(12px); }
        #ov-progress-dock.visible { display:grid; grid-template-columns:auto minmax(0,1fr) auto;
            gap:7px 10px; align-items:center; }
        .ov-dock-spinner { width:15px; height:15px; border:2px solid var(--surface-3); border-top-color:var(--primary);
            border-radius:50%; animation:spin .8s linear infinite; }
        .ov-dock-copy { min-width:0; }
        .ov-dock-title { font-size:11.5px; font-weight:700; color:var(--text-1); white-space:nowrap;
            overflow:hidden; text-overflow:ellipsis; }
        .ov-dock-message { margin-top:2px; font-size:10.5px; color:var(--text-3); white-space:nowrap;
            overflow:hidden; text-overflow:ellipsis; }
        .ov-dock-percent { font-size:11.5px; font-weight:700; color:var(--primary); font-variant-numeric:tabular-nums; }
        .ov-dock-track { grid-column:2 / 4; position:relative; height:6px; overflow:hidden; border-radius:999px;
            background:var(--surface-3); box-shadow:inset 0 0 0 1px var(--border); }
        .ov-dock-fill { position:absolute; inset:0 auto 0 0; width:0; border-radius:inherit; background:var(--accent-grad);
            transition:width .3s ease; }
        .ov-dock-track.indeterminate .ov-dock-fill { width:32% !important; animation:ov-dock-scan 1.2s ease-in-out infinite; }
        @keyframes ov-dock-scan { 0% { transform:translateX(-110%); } 100% { transform:translateX(410%); } }
        @media (max-width:640px) { #ov-progress-dock { margin:8px 10px 0; } .ov-dock-message { display:none; } }
        @media (prefers-reduced-motion:reduce) { .ov-dock-spinner { animation:none; } .ov-dock-track.indeterminate .ov-dock-fill { animation:none; width:45% !important; } }
    `;
    document.head.appendChild(style);

    const chatColumn = document.querySelector('.chat-column');
    const chatArea = document.getElementById('chat-area');
    if (!chatColumn || !chatArea) return;

    const dock = document.createElement('section');
    dock.id = 'ov-progress-dock';
    dock.setAttribute('role', 'status');
    dock.setAttribute('aria-live', 'polite');

    const spinner = document.createElement('div');
    spinner.className = 'ov-dock-spinner';
    spinner.setAttribute('aria-hidden', 'true');
    const copy = document.createElement('div');
    copy.className = 'ov-dock-copy';
    const title = document.createElement('div');
    title.className = 'ov-dock-title';
    const message = document.createElement('div');
    message.className = 'ov-dock-message';
    copy.append(title, message);
    const percent = document.createElement('div');
    percent.className = 'ov-dock-percent';
    const track = document.createElement('div');
    track.className = 'ov-dock-track';
    track.setAttribute('role', 'progressbar');
    track.setAttribute('aria-valuemin', '0');
    track.setAttribute('aria-valuemax', '100');
    const fill = document.createElement('div');
    fill.className = 'ov-dock-fill';
    track.appendChild(fill);
    dock.append(spinner, copy, percent, track);
    chatColumn.insertBefore(dock, chatArea);

    const phaseLabels = {
        queued: 'Queued', resolving: 'Resolving', downloading: 'Downloading',
        converting: 'Converting', finalizing: 'Finalizing', loading: 'Loading',
    };

    function finitePercent(value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : null;
    }

    function baseName(model) {
        return String(model?.name || model?.id || 'Model').split(' — ')[0];
    }

    function render(data) {
        const models = data?.models?.available;
        if (!Array.isArray(models)) return;
        const selectedId = document.getElementById('model-select')?.value;
        const model = models.find(item => item.id === selectedId && item.is_loading)
            || models.find(item => item.is_loading);
        if (!model) {
            dock.classList.remove('visible');
            return;
        }

        const progress = model.progress || {};
        const phase = String(progress.phase || model.status || 'queued').toLowerCase();
        const stagePercent = finitePercent(progress.percent);
        title.textContent = `${phaseLabels[phase] || 'Preparing'} ${baseName(model)}`;
        message.textContent = String(progress.message || model.status_label || 'Preparing model…');
        percent.textContent = stagePercent === null ? 'Working…' : `${Math.round(stagePercent)}%`;
        fill.style.width = `${stagePercent || 0}%`;
        track.classList.toggle('indeterminate', stagePercent === null);
        if (stagePercent === null) track.removeAttribute('aria-valuenow');
        else track.setAttribute('aria-valuenow', String(Math.round(stagePercent)));
        track.setAttribute('aria-label', `${phaseLabels[phase] || 'Model preparation'} progress`);
        dock.classList.add('visible');
    }

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
    window.fetch = async function dockAwareFetch(input, init = {}) {
        const response = await previousFetch(input, init);
        const target = endpoint(input);
        if (target.sameOrigin && target.path === '/v1/system/status' && response.ok) {
            response.clone().json().then(render).catch(() => {});
        }
        return response;
    };

    async function initialStatus() {
        const key = localStorage.getItem('ovllm.apikey.v1') || '';
        const headers = key ? { Authorization: `Bearer ${key}` } : {};
        try {
            const response = await previousFetch('/v1/system/status', { headers });
            if (response.ok) render(await response.json());
        } catch { /* base UI handles connectivity */ }
    }
    void initialStatus();
})();
"""


def install_progress_dock_extension() -> None:
    """Compose the dock injector after the existing browser extensions."""

    if getattr(ui_extension, "_MODEL_PROGRESS_DOCK_INSTALLED", False):
        return
    previous_inject = ui_extension.inject_multimodal_ui

    def inject_with_progress_dock(html: str) -> str:
        html = previous_inject(html)
        if f'id="{_EXTENSION_ID}"' in html:
            return html
        script = f'\n<script id="{_EXTENSION_ID}">\n{PROGRESS_DOCK_JS}\n</script>\n'
        if "</body>" in html:
            return html.replace("</body>", f"{script}</body>", 1)
        return html + script

    ui_extension.inject_multimodal_ui = inject_with_progress_dock
    ui_extension._MODEL_PROGRESS_DOCK_INSTALLED = True
