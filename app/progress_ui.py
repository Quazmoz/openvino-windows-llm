"""Enhanced model download and conversion progress for the bundled browser UI.

This extension is layered on top of :mod:`app.ui_extension` so the large, static
``web/index.html`` file remains untouched. It observes the existing system-status
polls and renders a phase-aware progress component for download, conversion, and
model loading.
"""

from __future__ import annotations

from app import ui_extension

_EXTENSION_ID = "ovllm-model-progress-extension"
_ORIGINAL_INJECT = ui_extension.inject_multimodal_ui

PROGRESS_EXTENSION_JS = r"""
(() => {
    'use strict';
    if (window.__ovllmProgressInstalled) return;
    window.__ovllmProgressInstalled = true;

    const phaseOrder = { idle: -1, queued: 0, resolving: 0, downloading: 1, converting: 2, finalizing: 2, loading: 3, ready: 4, error: 5 };
    const phaseLabels = {
        queued: 'Queued', resolving: 'Resolving files', downloading: 'Downloading',
        converting: 'Converting', finalizing: 'Finalizing', loading: 'Loading',
        ready: 'Ready', error: 'Failed', idle: 'Waiting',
    };
    const phaseRanges = {
        queued: [0, 3], resolving: [1, 5], downloading: [5, 60],
        converting: [60, 90], finalizing: [90, 94], loading: [94, 99], ready: [100, 100],
    };
    const progressState = new Map();
    let latestStatus = null;
    let renderTimer = null;

    const style = document.createElement('style');
    style.textContent = `
        .ov-progress-panel { width:100%; display:flex; flex-direction:column; gap:10px; padding:14px;
            border:1px solid color-mix(in srgb, var(--primary) 34%, var(--border)); border-radius:12px;
            background:color-mix(in srgb, var(--surface-1) 62%, transparent); text-align:left; }
        .ov-progress-panel.error { border-color:color-mix(in srgb, var(--red) 45%, var(--border)); }
        .ov-progress-head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
        .ov-progress-title { min-width:0; font-size:12px; font-weight:700; color:var(--text-1); }
        .ov-progress-percent { flex:0 0 auto; font-size:12px; font-weight:700; color:var(--primary);
            font-variant-numeric:tabular-nums; }
        .ov-progress-panel.error .ov-progress-percent { color:var(--red); }
        .ov-progress-track { position:relative; width:100%; height:9px; overflow:hidden; border-radius:999px;
            background:var(--surface-3); box-shadow:inset 0 0 0 1px var(--border); }
        .ov-progress-fill { position:absolute; inset:0 auto 0 0; width:0; border-radius:inherit;
            background:var(--accent-grad); transition:width .35s ease; }
        .ov-progress-track.indeterminate .ov-progress-fill { width:34% !important; animation:ov-progress-scan 1.25s ease-in-out infinite; }
        .ov-progress-panel.error .ov-progress-fill { background:var(--red); }
        @keyframes ov-progress-scan { 0% { transform:translateX(-105%); } 50% { transform:translateX(195%); } 100% { transform:translateX(395%); } }
        .ov-progress-steps { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; }
        .ov-progress-step { display:flex; align-items:center; gap:6px; min-width:0; padding:6px 8px;
            border:1px solid var(--border); border-radius:8px; color:var(--text-3); font-size:10.5px; }
        .ov-progress-step::before { content:''; width:7px; height:7px; flex:0 0 7px; border-radius:50%; background:var(--text-3); }
        .ov-progress-step.active { color:var(--text-1); border-color:color-mix(in srgb, var(--primary) 38%, var(--border)); }
        .ov-progress-step.active::before { background:var(--primary); box-shadow:0 0 8px var(--primary-glow); animation:dot-pulse 1.3s ease infinite; }
        .ov-progress-step.done { color:var(--green); }
        .ov-progress-step.done::before { background:var(--green); box-shadow:0 0 6px var(--green-glow); }
        .ov-progress-message { font-size:12px; line-height:1.45; color:var(--text-2); overflow-wrap:anywhere; }
        .ov-progress-meta { display:flex; flex-wrap:wrap; gap:5px 12px; font-size:10.5px; line-height:1.4;
            color:var(--text-3); font-variant-numeric:tabular-nums; }
        .ov-progress-meta span { white-space:nowrap; }
        .ov-progress-log { border-top:1px solid var(--border); padding-top:8px; }
        .ov-progress-log summary { cursor:pointer; color:var(--text-3); font-size:10.5px; user-select:none; }
        .ov-progress-log pre { max-height:105px; overflow:auto; margin-top:7px; padding:8px; border-radius:8px;
            background:var(--code-bg); color:var(--code-text); font:10px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace;
            white-space:pre-wrap; overflow-wrap:anywhere; }
        .ov-inline-progress { flex:1 0 100%; width:100%; display:grid; grid-template-columns:minmax(0,1fr) auto;
            gap:5px 10px; align-items:center; margin-top:6px; color:var(--text-2); }
        .ov-inline-progress .ov-progress-track { grid-column:1/-1; height:7px; }
        .ov-inline-label { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11px; }
        .ov-inline-percent { font-size:11px; font-weight:700; color:var(--primary); font-variant-numeric:tabular-nums; }
        @media (max-width:640px) { .ov-progress-panel { padding:12px; } .ov-progress-steps { grid-template-columns:1fr; }
            .ov-progress-step { padding:5px 7px; } }
        @media (prefers-reduced-motion:reduce) { .ov-progress-track.indeterminate .ov-progress-fill { animation:none; width:45% !important; } }
    `;
    document.head.appendChild(style);

    function finitePercent(value) {
        const number = Number(value);
        return Number.isFinite(number) ? Math.max(0, Math.min(100, number)) : null;
    }

    function baseName(model) {
        return String(model?.name || model?.id || 'Model').split(' — ')[0];
    }

    function displayProgress(model) {
        const progress = model?.progress || {};
        const phase = String(progress.phase || model?.status || 'idle').toLowerCase();
        const raw = finitePercent(progress.percent);
        const previous = progressState.get(model.id) || { value: 0, rank: -1 };
        const rank = phaseOrder[phase] ?? 0;
        let value = previous.value;
        let determinate = raw !== null;

        if (phase === 'ready') {
            value = 100;
            determinate = true;
        } else if (phase === 'error') {
            value = previous.value;
            determinate = previous.value > 0;
        } else if (raw !== null) {
            const [start, end] = phaseRanges[phase] || [0, 99];
            const candidate = start + ((end - start) * raw / 100);
            value = rank >= previous.rank ? Math.max(previous.value, candidate) : candidate;
        } else if (rank > previous.rank) {
            value = Math.max(previous.value, (phaseRanges[phase] || [previous.value])[0]);
        }

        value = Math.max(0, Math.min(100, value));
        progressState.set(model.id, { value, rank: Math.max(previous.rank, rank) });
        return { phase, raw, value, determinate, progress };
    }

    function formatDuration(seconds) {
        const total = Math.max(0, Math.floor(seconds || 0));
        if (total < 60) return `${total}s`;
        const minutes = Math.floor(total / 60);
        const remainder = total % 60;
        if (minutes < 60) return `${minutes}m ${String(remainder).padStart(2, '0')}s`;
        return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
    }

    function transferDetails(logs) {
        const lines = Array.isArray(logs) ? logs : [];
        const result = {};
        for (let index = lines.length - 1; index >= 0; index -= 1) {
            const line = String(lines[index] || '');
            if (!result.file) {
                const match = line.match(/^([^:\r\n]{1,140}\.(?:safetensors|bin|json|model|spm|py|txt|tiktoken))\s*:/i);
                if (match) result.file = match[1].trim();
            }
            if (!result.bytes) {
                const match = line.match(/([\d.]+\s*[KMGTPE]?i?B)\s*\/\s*([\d.]+\s*[KMGTPE]?i?B)/i);
                if (match) result.bytes = `${match[1]} / ${match[2]}`;
            }
            if (!result.rate) {
                const match = line.match(/([\d.]+\s*[KMGTPE]?i?B\/s)/i);
                if (match) result.rate = match[1];
            }
            if (!result.eta) {
                const match = line.match(/\[[^\]<]*<([^,\]]+)/);
                if (match) result.eta = match[1].trim();
            }
            if (!result.files) {
                const match = line.match(/(?:fetching|download(?:ing)?)\s+(\d+)\s*files?.*?(\d+)\s*\/\s*(\d+)/i)
                    || line.match(/(\d+)\s*\/\s*(\d+)\s*files?/i);
                if (match) {
                    const current = match.length === 4 ? match[2] : match[1];
                    const total = match.length === 4 ? match[3] : match[2];
                    result.files = `${current} / ${total} files`;
                }
            }
        }
        return result;
    }

    function createTrack(info, compact = false) {
        const track = document.createElement('div');
        track.className = `ov-progress-track${info.determinate ? '' : ' indeterminate'}`;
        track.setAttribute('role', 'progressbar');
        track.setAttribute('aria-label', compact ? 'Model preparation progress' : `${phaseLabels[info.phase] || 'Model preparation'} progress`);
        track.setAttribute('aria-valuemin', '0');
        track.setAttribute('aria-valuemax', '100');
        if (info.determinate) track.setAttribute('aria-valuenow', String(Math.round(info.value)));
        const fill = document.createElement('div');
        fill.className = 'ov-progress-fill';
        fill.style.width = `${info.value}%`;
        track.appendChild(fill);
        return track;
    }

    function step(label, index, activeIndex, failed) {
        const element = document.createElement('div');
        element.className = 'ov-progress-step';
        if (!failed && index < activeIndex) element.classList.add('done');
        if (!failed && index === activeIndex) element.classList.add('active');
        element.textContent = label;
        return element;
    }

    function buildPanel(model) {
        const info = displayProgress(model);
        const panel = document.createElement('section');
        panel.id = 'ov-model-progress';
        panel.className = `ov-progress-panel${info.phase === 'error' ? ' error' : ''}`;
        panel.setAttribute('role', 'status');
        panel.setAttribute('aria-live', 'polite');

        const head = document.createElement('div');
        head.className = 'ov-progress-head';
        const title = document.createElement('div');
        title.className = 'ov-progress-title';
        title.textContent = `${phaseLabels[info.phase] || 'Preparing'} ${baseName(model)}`;
        const percent = document.createElement('div');
        percent.className = 'ov-progress-percent';
        percent.textContent = info.phase === 'error' ? 'Failed' : (info.determinate ? `${Math.round(info.value)}%` : 'Working…');
        head.append(title, percent);
        panel.append(head, createTrack(info));

        const activeIndex = info.phase === 'loading' ? 2 : (info.phase === 'converting' || info.phase === 'finalizing' ? 1 : 0);
        const steps = document.createElement('div');
        steps.className = 'ov-progress-steps';
        steps.append(step('1. Download', 0, activeIndex, info.phase === 'error'));
        steps.append(step('2. Convert', 1, activeIndex, info.phase === 'error'));
        steps.append(step('3. Load', 2, activeIndex, info.phase === 'error'));
        panel.appendChild(steps);

        const message = document.createElement('div');
        message.className = 'ov-progress-message';
        message.textContent = String(info.progress.message || model.status_label || 'Preparing model…');
        panel.appendChild(message);

        const details = transferDetails(info.progress.log_tail);
        const meta = document.createElement('div');
        meta.className = 'ov-progress-meta';
        const now = Math.floor(Date.now() / 1000);
        if (info.progress.started_at) {
            const elapsed = document.createElement('span');
            elapsed.textContent = `Elapsed ${formatDuration(now - Number(info.progress.started_at))}`;
            meta.appendChild(elapsed);
        }
        if (details.file) {
            const file = document.createElement('span');
            file.textContent = details.file;
            file.title = details.file;
            meta.appendChild(file);
        }
        [details.bytes, details.files, details.rate, details.eta && `ETA ${details.eta}`].filter(Boolean).forEach(value => {
            const item = document.createElement('span');
            item.textContent = value;
            meta.appendChild(item);
        });
        if (info.progress.updated_at) {
            const updated = document.createElement('span');
            updated.textContent = `Updated ${formatDuration(now - Number(info.progress.updated_at))} ago`;
            meta.appendChild(updated);
        }
        if (meta.childNodes.length) panel.appendChild(meta);

        const logs = Array.isArray(info.progress.log_tail) ? info.progress.log_tail.filter(Boolean).slice(-5) : [];
        if (logs.length) {
            const disclosure = document.createElement('details');
            disclosure.className = 'ov-progress-log';
            const summary = document.createElement('summary');
            summary.textContent = 'Recent preparation activity';
            const output = document.createElement('pre');
            output.textContent = logs.join('\n');
            disclosure.append(summary, output);
            panel.appendChild(disclosure);
        }
        return panel;
    }

    function renderActionCard(model) {
        const card = document.getElementById('model-action-card');
        if (!card) return;
        card.querySelector('#ov-model-progress')?.remove();
        if (!model || (!model.is_loading && model.status !== 'error')) return;
        card.appendChild(buildPanel(model));
    }

    function renderInline(model) {
        document.querySelectorAll('.ov-inline-progress').forEach(element => element.remove());
        if (!model?.is_loading) return;
        const host = document.querySelector('.model-loader-status');
        if (!host) return;
        host.style.flexWrap = 'wrap';
        const info = displayProgress(model);
        const wrapper = document.createElement('div');
        wrapper.className = 'ov-inline-progress';
        const label = document.createElement('div');
        label.className = 'ov-inline-label';
        label.textContent = String(info.progress.message || model.status_label || `${phaseLabels[info.phase] || 'Preparing'} model…`);
        const percent = document.createElement('div');
        percent.className = 'ov-inline-percent';
        percent.textContent = info.determinate ? `${Math.round(info.value)}%` : 'Working…';
        wrapper.append(label, percent, createTrack(info, true));
        host.appendChild(wrapper);
    }

    function renderStatus(data) {
        const models = data?.models?.available;
        if (!Array.isArray(models)) return;
        latestStatus = data;
        const selectedId = document.getElementById('model-select')?.value;
        const selected = models.find(model => model.id === selectedId) || null;
        const active = selected?.is_loading ? selected : models.find(model => model.is_loading) || null;
        renderActionCard(selected);
        renderInline(active);
        const activeIds = new Set(models.filter(model => model.is_loading).map(model => model.id));
        for (const modelId of progressState.keys()) {
            if (!activeIds.has(modelId) && models.find(model => model.id === modelId)?.status !== 'error') {
                progressState.delete(modelId);
            }
        }
    }

    function scheduleRender(data) {
        latestStatus = data;
        clearTimeout(renderTimer);
        renderTimer = window.setTimeout(() => renderStatus(data), 20);
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
    window.fetch = async function progressAwareFetch(input, init = {}) {
        const response = await previousFetch(input, init);
        const target = endpoint(input);
        if (target.sameOrigin && target.path === '/v1/system/status' && response.ok) {
            response.clone().json().then(scheduleRender).catch(() => {});
        }
        return response;
    };

    document.getElementById('model-select')?.addEventListener('change', () => {
        if (latestStatus) window.setTimeout(() => renderStatus(latestStatus), 0);
    });

    async function initialStatus() {
        const key = localStorage.getItem('ovllm.apikey.v1') || '';
        const headers = key ? { Authorization: `Bearer ${key}` } : {};
        try {
            const response = await previousFetch('/v1/system/status', { headers });
            if (response.ok) scheduleRender(await response.json());
        } catch { /* the base application owns connectivity errors */ }
    }
    void initialStatus();
})();
"""


def inject_progress_ui(html: str) -> str:
    """Inject the existing multimodal extension and the progress extension once."""

    html = _ORIGINAL_INJECT(html)
    if f'id="{_EXTENSION_ID}"' in html:
        return html
    script = f'\n<script id="{_EXTENSION_ID}">\n{PROGRESS_EXTENSION_JS}\n</script>\n'
    if "</body>" in html:
        return html.replace("</body>", f"{script}</body>", 1)
    return html + script


def install_progress_ui_extension() -> None:
    """Install the composed UI injector before :mod:`app.server` imports it."""

    if getattr(ui_extension, "_MODEL_PROGRESS_EXTENSION_INSTALLED", False):
        return
    ui_extension.inject_multimodal_ui = inject_progress_ui
    ui_extension._MODEL_PROGRESS_EXTENSION_INSTALLED = True
