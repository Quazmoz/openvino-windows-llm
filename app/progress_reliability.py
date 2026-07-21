"""Reliable, persistent model-preparation progress for the browser client.

One controller owns optimistic request feedback and server reconciliation for model
loads, conversions, and custom-model downloads. It intentionally avoids additional
fetch wrappers competing for the same DOM surfaces.
"""

from __future__ import annotations

from app import ui_extension

_EXTENSION_ID = "ovllm-model-progress-extension"

PROGRESS_RELIABILITY_JS = r"""
(() => {
    'use strict';
    if (window.__ovllmReliableProgressInstalled) return;
    window.__ovllmReliableProgressInstalled = true;

    const PREPARATION_PATHS = new Set([
        '/v1/models/load',
        '/v1/models/convert',
        '/v1/models/download-custom',
    ]);
    const PHASES = {
        idle: ['Waiting', -1, 0, 0],
        queued: ['Queued', 0, 0, 3],
        resolving: ['Resolving files', 0, 1, 5],
        downloading: ['Downloading', 0, 5, 60],
        converting: ['Converting', 1, 60, 90],
        finalizing: ['Finalizing', 1, 90, 94],
        loading: ['Loading runtime', 2, 94, 99],
        ready: ['Ready', 3, 100, 100],
        error: ['Failed', -1, 0, 100],
    };

    const modelState = new Map();
    const optimistic = new Map();
    let latestStatus = null;
    let expanded = false;
    let renderTimer = null;

    const style = document.createElement('style');
    style.textContent = `
        #ov-reliable-progress{display:none;flex:0 0 auto;margin:10px 14px 0;border:1px solid color-mix(in srgb,var(--primary) 36%,var(--border));border-radius:12px;background:color-mix(in srgb,var(--surface-1) 92%,transparent);box-shadow:var(--shadow-md);backdrop-filter:blur(14px);overflow:hidden}
        #ov-reliable-progress.visible{display:block}#ov-reliable-progress.error{border-color:color-mix(in srgb,var(--red) 48%,var(--border))}
        .ovrp-main{width:100%;display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:7px 10px;align-items:center;padding:11px 12px;border:0;background:transparent;color:inherit;text-align:left;cursor:pointer;font:inherit}
        .ovrp-main:focus-visible{outline:2px solid var(--primary);outline-offset:-2px}.ovrp-spinner{width:16px;height:16px;border:2px solid var(--surface-3);border-top-color:var(--primary);border-radius:50%;animation:spin .8s linear infinite}
        .error .ovrp-spinner{border-color:color-mix(in srgb,var(--red) 28%,var(--surface-3));border-top-color:var(--red);animation:none}.ovrp-copy{min-width:0}
        .ovrp-title{display:block;font-size:11.5px;font-weight:750;color:var(--text-1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ovrp-message{display:block;margin-top:2px;font-size:10.5px;color:var(--text-3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .ovrp-value{font-size:11.5px;font-weight:750;color:var(--primary);font-variant-numeric:tabular-nums;white-space:nowrap}.error .ovrp-value{color:var(--red)}
        .ovrp-track{grid-column:2/4;position:relative;height:7px;overflow:hidden;border-radius:999px;background:var(--surface-3);box-shadow:inset 0 0 0 1px var(--border)}
        .ovrp-fill{position:absolute;inset:0 auto 0 0;width:0;border-radius:inherit;background:var(--accent-grad);transition:width .35s ease}.error .ovrp-fill{background:var(--red)}
        .ovrp-scan{display:none;position:absolute;top:0;bottom:0;width:18%;border-radius:inherit;background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--primary) 75%,white),transparent);opacity:.72;animation:ovrp-scan 1.35s ease-in-out infinite}
        .ovrp-track.indeterminate .ovrp-scan{display:block}@keyframes ovrp-scan{from{transform:translateX(-120%)}to{transform:translateX(650%)}}
        .ovrp-detail{display:none;padding:0 12px 12px 38px;border-top:1px solid color-mix(in srgb,var(--border) 75%,transparent)}.expanded .ovrp-detail{display:block}
        .ovrp-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:10px}.ovrp-step{display:flex;align-items:center;gap:6px;min-width:0;padding:6px 8px;border:1px solid var(--border);border-radius:8px;color:var(--text-3);font-size:10.5px}
        .ovrp-step:before{content:'';width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:var(--text-3)}.ovrp-step.active{color:var(--text-1);border-color:color-mix(in srgb,var(--primary) 40%,var(--border))}
        .ovrp-step.active:before{background:var(--primary);box-shadow:0 0 8px var(--primary-glow);animation:dot-pulse 1.3s ease infinite}.ovrp-step.done{color:var(--green)}.ovrp-step.done:before{background:var(--green);box-shadow:0 0 6px var(--green-glow)}
        .ovrp-meta{display:flex;flex-wrap:wrap;gap:5px 12px;margin-top:9px;color:var(--text-3);font-size:10.5px;font-variant-numeric:tabular-nums}.ovrp-meta .warning{color:var(--amber)}
        .ovrp-log{margin-top:9px}.ovrp-log summary{cursor:pointer;color:var(--text-3);font-size:10.5px;user-select:none}.ovrp-log pre{max-height:130px;overflow:auto;margin:7px 0 0;padding:8px;border-radius:8px;background:var(--code-bg);color:var(--code-text);font:10px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
        .ovrp-inline{flex:1 0 100%;width:100%;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px 10px;align-items:center;margin-top:7px}.ovrp-inline .ovrp-track{grid-column:1/-1;height:7px}
        .ovrp-inline-label{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;color:var(--text-2)}.ovrp-inline-value{font-size:11px;font-weight:750;color:var(--primary);font-variant-numeric:tabular-nums;white-space:nowrap}
        @media(max-width:640px){#ov-reliable-progress{margin:8px 10px 0}.ovrp-detail{padding-left:12px}.ovrp-steps{grid-template-columns:1fr}.ovrp-message{display:none}}
        @media(prefers-reduced-motion:reduce){.ovrp-spinner,.ovrp-step.active:before,.ovrp-scan{animation:none}.ovrp-track.indeterminate .ovrp-scan{left:72%;display:block}}
    `;
    document.head.appendChild(style);

    const chatColumn = document.querySelector('.chat-column');
    const chatArea = document.getElementById('chat-area');
    const dock = document.createElement('section');
    dock.id = 'ov-reliable-progress';
    dock.setAttribute('role', 'status');
    dock.setAttribute('aria-live', 'polite');
    dock.innerHTML = `
        <button type="button" class="ovrp-main" aria-expanded="false" aria-label="Show model preparation details">
            <span class="ovrp-spinner" aria-hidden="true"></span>
            <span class="ovrp-copy"><span class="ovrp-title"></span><span class="ovrp-message"></span></span>
            <span class="ovrp-value"></span>
            <span class="ovrp-track" role="progressbar" aria-valuemin="0" aria-valuemax="100">
                <span class="ovrp-fill"></span><span class="ovrp-scan"></span>
            </span>
        </button>
        <div class="ovrp-detail"></div>`;
    if (chatColumn && chatArea) chatColumn.insertBefore(dock, chatArea);

    const main = dock.querySelector('.ovrp-main');
    main?.addEventListener('click', () => {
        expanded = !expanded;
        dock.classList.toggle('expanded', expanded);
        main.setAttribute('aria-expanded', String(expanded));
        main.setAttribute(
            'aria-label',
            expanded ? 'Hide model preparation details' : 'Show model preparation details'
        );
    });

    function strictPercent(value) {
        if (value === null || value === undefined || value === '') return null;
        const parsed = Number(value);
        return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : null;
    }

    function baseName(model) {
        return String(model?.name || model?.id || 'Model').split(' — ')[0];
    }

    function phaseInfo(phase) {
        const [label, stage, start, end] = PHASES[phase] || ['Preparing', 0, 0, 99];
        return { label, stage, start, end };
    }

    function aggregateDownloadPercent(progress) {
        const lines = Array.isArray(progress?.log_tail) ? progress.log_tail : [];
        for (let index = lines.length - 1; index >= 0; index -= 1) {
            const match = String(lines[index] || '').match(
                /(?:fetching|downloading)\s+\d+\s+files?.*?(100(?:\.0+)?|[1-9]?\d(?:\.\d+)?)\s*%/i
            );
            if (match) return strictPercent(match[1]);
        }
        return null;
    }

    function progressInfo(model) {
        const progress = model?.progress || {};
        const phase = String(progress.phase || model?.status || 'idle').toLowerCase();
        const meta = phaseInfo(phase);
        const raw = phase === 'downloading'
            ? aggregateDownloadPercent(progress) ?? strictPercent(progress.percent)
            : strictPercent(progress.percent);
        const reportedStart = Number(progress.started_at) || 0;
        const previous = modelState.get(model.id);
        const newOperation = !previous
            || (reportedStart > 0 && previous.startedAt > 0 && reportedStart !== previous.startedAt)
            || (previous.terminal && !['ready', 'error'].includes(phase));
        const prior = newOperation ? {
            overall: 0,
            rank: -1,
            startedAt: reportedStart || Math.floor(Date.now() / 1000),
            targetDevice: null,
            terminal: false,
        } : previous;

        let overall = prior.overall;
        let determinate = raw !== null;
        if (phase === 'ready') {
            overall = 100;
            determinate = true;
        } else if (phase === 'error') {
            determinate = prior.overall > 0;
        } else if (raw !== null) {
            const candidate = meta.start + ((meta.end - meta.start) * raw / 100);
            overall = meta.stage >= prior.rank ? Math.max(prior.overall, candidate) : candidate;
        } else {
            overall = Math.max(prior.overall, meta.start);
        }

        overall = Math.max(0, Math.min(100, overall));
        const now = Math.floor(Date.now() / 1000);
        const startedAt = reportedStart || prior.startedAt || now;
        const updatedAt = Number(progress.updated_at) || now;
        const targetDevice = model.device
            || prior.targetDevice
            || document.getElementById('device-select')?.value
            || null;
        modelState.set(model.id, {
            overall,
            rank: Math.max(prior.rank, meta.stage),
            startedAt,
            targetDevice,
            terminal: ['ready', 'error'].includes(phase),
        });

        return {
            model,
            progress,
            phase,
            meta,
            raw,
            overall,
            determinate,
            targetDevice,
            elapsed: Math.max(0, now - startedAt),
            staleFor: Math.max(0, now - updatedAt),
        };
    }

    function duration(seconds) {
        const total = Math.max(0, Math.floor(seconds || 0));
        if (total < 60) return `${total}s`;
        const minutes = Math.floor(total / 60);
        if (minutes < 60) return `${minutes}m ${String(total % 60).padStart(2, '0')}s`;
        return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
    }

    function valueLabel(info) {
        if (info.phase === 'error') return 'Failed';
        if (info.phase === 'ready') return '100%';
        if (info.raw !== null) return `${Math.round(info.overall)}%`;
        return info.meta.stage >= 0 && info.meta.stage < 3
            ? `Stage ${info.meta.stage + 1} of 3`
            : 'Working…';
    }

    function stageLabel(info) {
        return info.raw === null
            ? info.meta.label
            : `${info.meta.label} ${Math.round(info.raw)}%`;
    }

    function updateTrack(track, info) {
        if (!track) return;
        const fill = track.querySelector('.ovrp-fill');
        if (fill) fill.style.width = `${info.overall}%`;
        track.classList.toggle('indeterminate', !info.determinate && info.phase !== 'error');
        if (info.determinate) track.setAttribute('aria-valuenow', String(Math.round(info.overall)));
        else track.removeAttribute('aria-valuenow');
        track.setAttribute('aria-label', `${info.meta.label} model preparation progress`);
    }

    function buildDetail(info) {
        const detail = document.createDocumentFragment();
        const steps = document.createElement('div');
        steps.className = 'ovrp-steps';
        ['1. Download', '2. Convert', '3. Load'].forEach((label, index) => {
            const step = document.createElement('div');
            step.className = 'ovrp-step';
            if (info.phase === 'ready' || index < info.meta.stage) step.classList.add('done');
            if (info.phase !== 'error' && index === info.meta.stage) step.classList.add('active');
            step.textContent = label;
            steps.appendChild(step);
        });
        detail.appendChild(steps);

        const status = document.createElement('div');
        status.className = 'ovrp-meta';
        const values = [
            `Elapsed ${duration(info.elapsed)}`,
            info.raw === null
                ? stageLabel(info)
                : `${stageLabel(info)} · overall ${Math.round(info.overall)}%`,
            info.targetDevice ? `Device ${info.targetDevice}` : null,
        ].filter(Boolean);
        values.forEach(text => {
            const span = document.createElement('span');
            span.textContent = text;
            status.appendChild(span);
        });
        if (info.staleFor >= 15 && !['error', 'ready'].includes(info.phase)) {
            const stale = document.createElement('span');
            stale.className = 'warning';
            stale.textContent = `No new console output for ${duration(info.staleFor)} · still working`;
            status.appendChild(stale);
        } else if (info.progress.updated_at) {
            const updated = document.createElement('span');
            updated.textContent = `Updated ${duration(info.staleFor)} ago`;
            status.appendChild(updated);
        }
        detail.appendChild(status);

        const logs = Array.isArray(info.progress.log_tail)
            ? info.progress.log_tail.filter(Boolean).slice(-8)
            : [];
        if (logs.length) {
            const disclosure = document.createElement('details');
            disclosure.className = 'ovrp-log';
            const summary = document.createElement('summary');
            summary.textContent = `Recent preparation activity (${logs.length})`;
            const output = document.createElement('pre');
            output.textContent = logs.join('\n');
            disclosure.append(summary, output);
            detail.appendChild(disclosure);
        }
        return detail;
    }

    function renderDock(model) {
        if (!model || (!model.is_loading && model.status !== 'error')) {
            dock.classList.remove('visible', 'error');
            return null;
        }
        const info = progressInfo(model);
        dock.classList.add('visible');
        dock.classList.toggle('error', info.phase === 'error');
        dock.querySelector('.ovrp-title').textContent = `${info.meta.label} ${baseName(model)}`;
        dock.querySelector('.ovrp-message').textContent = String(
            info.progress.message || model.status_label || `${info.meta.label} model…`
        );
        dock.querySelector('.ovrp-value').textContent = valueLabel(info);
        updateTrack(dock.querySelector('.ovrp-track'), info);
        dock.querySelector('.ovrp-detail').replaceChildren(buildDetail(info));
        return info;
    }

    function renderInline(model, info) {
        document.querySelectorAll('.ovrp-inline').forEach(element => element.remove());
        if (!model?.is_loading || !info) return;
        const host = document.querySelector('.model-loader-status');
        if (!host) return;
        host.style.flexWrap = 'wrap';
        const inline = document.createElement('div');
        inline.className = 'ovrp-inline';
        const label = document.createElement('div');
        label.className = 'ovrp-inline-label';
        label.textContent = String(
            info.progress.message || model.status_label || `${info.meta.label} model…`
        );
        const value = document.createElement('div');
        value.className = 'ovrp-inline-value';
        value.textContent = valueLabel(info);
        const track = document.createElement('div');
        track.className = 'ovrp-track';
        track.innerHTML = '<span class="ovrp-fill"></span><span class="ovrp-scan"></span>';
        updateTrack(track, info);
        inline.append(label, value, track);
        host.appendChild(inline);
    }

    function renderFooter(model, info) {
        if (!model || !info) return;
        const footer = document.getElementById('model-status');
        if (!footer) return;
        const detail = info.raw === null
            ? `${stageLabel(info)} · elapsed ${duration(info.elapsed)}`
            : `${stageLabel(info)} · overall ${Math.round(info.overall)}%`;
        footer.textContent = `${baseName(model)}: ${detail}`;
        footer.className = info.phase === 'error' ? 'error' : 'loading';
        footer.title = String(info.progress.message || model.status_label || footer.textContent);
    }

    function mergeOptimistic(source) {
        const now = Date.now();
        const models = source.map(model => {
            const pending = optimistic.get(model.id);
            if (!pending) return model;
            if (model.is_loading || model.is_loaded || model.status === 'error') {
                optimistic.delete(model.id);
                return model;
            }
            if (now - pending.createdAt > 15000) {
                optimistic.delete(model.id);
                return model;
            }
            return pending.model;
        });

        const known = new Set(models.map(model => model.id));
        for (const [modelId, pending] of optimistic.entries()) {
            if (known.has(modelId)) continue;
            if (now - pending.createdAt > 15000) {
                optimistic.delete(modelId);
                continue;
            }
            models.push(pending.model);
        }
        return models;
    }

    function renderStatus(data) {
        const source = data?.models?.available;
        if (!Array.isArray(source)) return;
        latestStatus = data;
        const models = mergeOptimistic(source);
        const selectedId = document.getElementById('model-select')?.value;
        const selected = models.find(model => model.id === selectedId) || null;
        const active = selected?.is_loading
            ? selected
            : models.find(model => model.is_loading)
                || (selected?.status === 'error' ? selected : null);
        const info = renderDock(active);
        renderInline(active, info);
        renderFooter(active, info);

        const retained = new Set(
            models.filter(model => model.is_loading || model.status === 'error').map(model => model.id)
        );
        for (const modelId of modelState.keys()) {
            if (!retained.has(modelId)) modelState.delete(modelId);
        }
    }

    function scheduleRender(data) {
        latestStatus = data;
        clearTimeout(renderTimer);
        renderTimer = window.setTimeout(() => renderStatus(data), 0);
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

    function requestMethod(input, init) {
        return String(init?.method || input?.method || 'GET').toUpperCase();
    }

    async function requestBody(input, init) {
        if (typeof init?.body === 'string') {
            try {
                return JSON.parse(init.body);
            } catch {
                return {};
            }
        }
        if (input instanceof Request) {
            try {
                return await input.clone().json();
            } catch {
                return {};
            }
        }
        return {};
    }

    function optimisticIdentity(path, body) {
        const modelId = String(body.model || body.model_id || '').trim();
        if (!modelId) return null;
        return {
            modelId,
            device: body.device || body.recommended_device || null,
            converting: path !== '/v1/models/load',
        };
    }

    function renderOptimistic(path, body) {
        const identity = optimisticIdentity(path, body);
        if (!identity) return null;
        const { modelId, device, converting } = identity;
        modelState.delete(modelId);

        const catalog = latestStatus?.models?.available || [];
        const base = catalog.find(model => model.id === modelId) || {
            id: modelId,
            name: body.name || modelId,
            status_label: 'Preparing model…',
        };
        const now = Math.floor(Date.now() / 1000);
        const message = converting
            ? `Queued ${baseName(base)} for download and conversion…`
            : `Queued ${baseName(base)} to load on ${device || 'the selected device'}…`;
        const model = {
            ...base,
            device: device || base.device || null,
            is_loaded: false,
            is_loading: true,
            status: converting ? 'converting' : 'queued',
            status_label: message,
            progress: {
                phase: 'queued',
                message,
                percent: null,
                started_at: now,
                updated_at: now,
                log_tail: [],
            },
        };
        optimistic.set(modelId, { model, createdAt: Date.now() });
        const info = renderDock(model);
        renderInline(model, info);
        renderFooter(model, info);
        return modelId;
    }

    function clearOptimistic(modelId) {
        if (!modelId) return;
        optimistic.delete(modelId);
        modelState.delete(modelId);
        if (latestStatus) scheduleRender(latestStatus);
        else {
            renderDock(null);
            renderInline(null, null);
        }
    }

    function mergeReturnedModel(payload) {
        if (!payload?.model) return;
        const current = latestStatus || { models: { available: [] } };
        const models = Array.isArray(current.models?.available)
            ? [...current.models.available]
            : [];
        const index = models.findIndex(model => model.id === payload.model.id);
        if (index >= 0) models[index] = payload.model;
        else models.push(payload.model);
        scheduleRender({
            ...current,
            models: { ...(current.models || {}), available: models },
        });
    }

    const previousFetch = window.fetch.bind(window);
    window.fetch = async function reliableProgressFetch(input, init = {}) {
        const target = endpoint(input);
        const method = requestMethod(input, init);
        const isPreparation = target.sameOrigin
            && method === 'POST'
            && PREPARATION_PATHS.has(target.path);
        let optimisticModelId = null;

        if (isPreparation) {
            const body = await requestBody(input, init);
            optimisticModelId = renderOptimistic(target.path, body);
        }

        let response;
        try {
            response = await previousFetch(input, init);
        } catch (error) {
            clearOptimistic(optimisticModelId);
            throw error;
        }

        if (target.sameOrigin && target.path === '/v1/system/status' && response.ok) {
            response.clone().json().then(scheduleRender).catch(() => {});
        } else if (isPreparation) {
            if (!response.ok) {
                clearOptimistic(optimisticModelId);
            } else {
                response.clone().json().then(payload => {
                    optimistic.delete(optimisticModelId);
                    mergeReturnedModel(payload);
                }).catch(() => {
                    clearOptimistic(optimisticModelId);
                });
            }
        }
        return response;
    };

    document.getElementById('model-select')?.addEventListener('change', () => {
        if (latestStatus) scheduleRender(latestStatus);
    });
    window.setInterval(() => {
        if (latestStatus) renderStatus(latestStatus);
    }, 1000);

    async function initialStatus() {
        const key = localStorage.getItem('ovllm.apikey.v1') || '';
        const headers = key ? { Authorization: `Bearer ${key}` } : {};
        try {
            const response = await previousFetch('/v1/system/status', { headers });
            if (response.ok) scheduleRender(await response.json());
        } catch {
            // The base UI owns connectivity errors.
        }
    }
    void initialStatus();
})();
"""


def install_progress_ui_extension() -> None:
    """Install the progress controller after all other browser extensions."""

    if getattr(ui_extension, "_MODEL_PROGRESS_EXTENSION_INSTALLED", False):
        return
    previous_inject = ui_extension.inject_multimodal_ui

    def inject_with_reliable_progress(html: str) -> str:
        html = previous_inject(html)
        if f'id="{_EXTENSION_ID}"' in html:
            return html
        script = f'\n<script id="{_EXTENSION_ID}">\n{PROGRESS_RELIABILITY_JS}\n</script>\n'
        if "</body>" in html:
            return html.replace("</body>", f"{script}</body>", 1)
        return html + script

    ui_extension.inject_multimodal_ui = inject_with_reliable_progress
    ui_extension._MODEL_PROGRESS_EXTENSION_INSTALLED = True
