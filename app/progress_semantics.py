"""Final browser-side normalization for model preparation percentages.

Hugging Face downloads may report both an aggregate file-set percentage and
individual shard percentages. The UI should prefer the aggregate value and must
not coerce an API ``null`` percentage to zero.
"""

from __future__ import annotations

from app import ui_extension

_EXTENSION_ID = "ovllm-model-progress-semantics-extension"

PROGRESS_SEMANTICS_JS = r"""
(() => {
    'use strict';
    if (window.__ovllmProgressSemanticsInstalled) return;
    window.__ovllmProgressSemanticsInstalled = true;

    const phaseRanges = {
        queued: [0, 3], resolving: [1, 5], downloading: [5, 60],
        converting: [60, 90], finalizing: [90, 94], loading: [94, 99], ready: [100, 100],
    };
    const phaseRank = {
        idle: -1, queued: 0, resolving: 0, downloading: 1,
        converting: 2, finalizing: 2, loading: 3, ready: 4, error: 5,
    };
    const overallState = new Map();
    let latestStatus = null;
    let patchTimer = null;

    function strictPercent(value) {
        if (value === null || value === undefined || value === '') return null;
        const parsed = Number(value);
        return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : null;
    }

    function setText(element, value) {
        if (element && element.textContent !== value) element.textContent = value;
    }

    function aggregateDownloadPercent(progress) {
        const lines = Array.isArray(progress?.log_tail) ? progress.log_tail : [];
        for (let index = lines.length - 1; index >= 0; index -= 1) {
            const line = String(lines[index] || '');
            const match = line.match(/(?:fetching|downloading)\s+\d+\s+files?.*?(100(?:\.0+)?|[1-9]?\d(?:\.\d+)?)\s*%/i);
            if (match) return strictPercent(match[1]);
        }
        return null;
    }

    function stagePercent(model) {
        const progress = model?.progress || {};
        const phase = String(progress.phase || model?.status || 'idle').toLowerCase();
        if (phase === 'downloading') {
            const aggregate = aggregateDownloadPercent(progress);
            if (aggregate !== null) return aggregate;
        }
        return strictPercent(progress.percent);
    }

    function overallPercent(model) {
        const progress = model?.progress || {};
        const phase = String(progress.phase || model?.status || 'idle').toLowerCase();
        if (phase === 'ready') return 100;
        if (phase === 'error') return overallState.get(model.id)?.value ?? null;

        const raw = stagePercent(model);
        if (raw === null) return null;
        const [start, end] = phaseRanges[phase] || [0, 99];
        const candidate = start + ((end - start) * raw / 100);
        const previous = overallState.get(model.id) || { value: 0, rank: -1 };
        const rank = phaseRank[phase] ?? 0;
        const value = rank >= previous.rank ? Math.max(previous.value, candidate) : candidate;
        const normalized = Math.max(0, Math.min(100, value));
        overallState.set(model.id, { value: normalized, rank: Math.max(previous.rank, rank) });
        return normalized;
    }

    function updateTrack(track, value) {
        if (!track) return;
        const fill = track.querySelector('.ov-progress-fill, .ov-dock-fill');
        const determinate = value !== null;
        track.classList.toggle('indeterminate', !determinate);
        if (determinate) {
            const rounded = String(Math.round(value));
            if (track.getAttribute('aria-valuenow') !== rounded) track.setAttribute('aria-valuenow', rounded);
            const width = `${value}%`;
            if (fill && fill.style.width !== width) fill.style.width = width;
        } else {
            if (track.hasAttribute('aria-valuenow')) track.removeAttribute('aria-valuenow');
            if (fill && fill.style.width !== '0%') fill.style.width = '0%';
        }
    }

    function patchDetailedPanel(model) {
        const panel = document.getElementById('ov-model-progress');
        if (!panel || !model) return;
        const value = overallPercent(model);
        const phase = String(model.progress?.phase || model.status || '').toLowerCase();
        const label = panel.querySelector('.ov-progress-percent');
        if (phase !== 'error') setText(label, value === null ? 'Working…' : `${Math.round(value)}%`);
        updateTrack(panel.querySelector('.ov-progress-track'), value);
    }

    function patchInline(model) {
        const wrapper = document.querySelector('.ov-inline-progress');
        if (!wrapper || !model) return;
        const value = overallPercent(model);
        setText(wrapper.querySelector('.ov-inline-percent'), value === null ? 'Working…' : `${Math.round(value)}%`);
        updateTrack(wrapper.querySelector('.ov-progress-track'), value);
    }

    function patchDock(model) {
        const dock = document.getElementById('ov-progress-dock');
        if (!dock || !model) return;
        const value = stagePercent(model);
        setText(dock.querySelector('.ov-dock-percent'), value === null ? 'Working…' : `${Math.round(value)}%`);
        updateTrack(dock.querySelector('.ov-dock-track'), value);
    }

    function patch(data) {
        const models = data?.models?.available;
        if (!Array.isArray(models)) return;
        latestStatus = data;
        const selectedId = document.getElementById('model-select')?.value;
        const selected = models.find(model => model.id === selectedId) || null;
        const active = selected?.is_loading ? selected : models.find(model => model.is_loading) || null;
        patchDetailedPanel(selected);
        patchInline(active);
        patchDock(active);

        const retained = new Set(models.filter(model => model.is_loading || model.status === 'error').map(model => model.id));
        for (const modelId of overallState.keys()) {
            if (!retained.has(modelId)) overallState.delete(modelId);
        }
    }

    function schedulePatch(data) {
        latestStatus = data;
        clearTimeout(patchTimer);
        patchTimer = window.setTimeout(() => patch(data), 60);
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
    window.fetch = async function progressSemanticsFetch(input, init = {}) {
        const response = await previousFetch(input, init);
        const target = endpoint(input);
        if (target.sameOrigin && target.path === '/v1/system/status' && response.ok) {
            response.clone().json().then(schedulePatch).catch(() => {});
        }
        return response;
    };

    const root = document.querySelector('.chat-column');
    if (root) {
        new MutationObserver(() => {
            if (latestStatus) schedulePatch(latestStatus);
        }).observe(root, { childList: true, subtree: true });
    }

    document.getElementById('model-select')?.addEventListener('change', () => {
        if (latestStatus) schedulePatch(latestStatus);
    });

    async function initialStatus() {
        const key = localStorage.getItem('ovllm.apikey.v1') || '';
        const headers = key ? { Authorization: `Bearer ${key}` } : {};
        try {
            const response = await previousFetch('/v1/system/status', { headers });
            if (response.ok) schedulePatch(await response.json());
        } catch { /* base UI owns connection errors */ }
    }
    void initialStatus();
})();
"""


def install_progress_semantics_extension() -> None:
    """Compose percentage normalization after all progress renderers."""

    if getattr(ui_extension, "_MODEL_PROGRESS_SEMANTICS_INSTALLED", False):
        return
    previous_inject = ui_extension.inject_multimodal_ui

    def inject_with_progress_semantics(html: str) -> str:
        html = previous_inject(html)
        if f'id="{_EXTENSION_ID}"' in html:
            return html
        script = f'\n<script id="{_EXTENSION_ID}">\n{PROGRESS_SEMANTICS_JS}\n</script>\n'
        if "</body>" in html:
            return html.replace("</body>", f"{script}</body>", 1)
        return html + script

    ui_extension.inject_multimodal_ui = inject_with_progress_semantics
    ui_extension._MODEL_PROGRESS_SEMANTICS_INSTALLED = True
