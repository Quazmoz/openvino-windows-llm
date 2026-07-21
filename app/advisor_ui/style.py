"""Hardware advisor CSS."""

ADVISOR_STYLE = r"""
        #advisor-open-btn {
            width: 36px; height: 36px; flex: 0 0 36px; display: grid; place-items: center;
            border: 1px solid var(--border); border-radius: 10px; background: var(--surface-2);
            color: var(--text-2); cursor: pointer; transition: .2s ease;
        }
        #advisor-open-btn:hover { color: var(--text-1); border-color: var(--primary); background: var(--surface-3); }
        #advisor-open-btn.has-warning { color: var(--amber); border-color: color-mix(in srgb, var(--amber) 58%, var(--border)); }
        #advisor-open-btn.auto-active { color: var(--green); border-color: color-mix(in srgb, var(--green) 58%, var(--border)); box-shadow: 0 0 0 3px var(--green-glow); }
        #advisor-overlay { position: fixed; inset: 0; z-index: 1200; display: none; align-items: center; justify-content: center; padding: 20px; background: rgba(2,6,14,.72); backdrop-filter: blur(9px); }
        #advisor-overlay.visible { display: flex; }
        #advisor-dialog { width: min(1080px, 100%); max-height: min(880px, calc(100vh - 40px)); overflow: hidden; display: grid; grid-template-rows: auto minmax(0,1fr); background: var(--surface-1); border: 1px solid var(--border); border-radius: 18px; box-shadow: var(--shadow-md); }
        .advisor-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 20px; border-bottom: 1px solid var(--border); }
        .advisor-title { display: flex; align-items: center; gap: 12px; min-width: 0; }
        .advisor-title-icon { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 11px; color: white; background: var(--accent-grad); box-shadow: 0 0 18px var(--primary-glow); }
        .advisor-title h2 { margin: 0; font-size: 17px; letter-spacing: -.3px; }
        .advisor-title p { margin: 3px 0 0; color: var(--text-3); font-size: 11px; }
        #advisor-close-btn { width: 34px; height: 34px; border-radius: 9px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text-2); cursor: pointer; font-size: 20px; }
        #advisor-body { overflow: auto; padding: 18px 20px 24px; }
        .advisor-profile-row { display: flex; gap: 7px; overflow-x: auto; padding-bottom: 4px; margin-bottom: 16px; }
        .advisor-profile-btn { flex: 0 0 auto; border: 1px solid var(--border); border-radius: 999px; background: var(--surface-2); color: var(--text-2); padding: 7px 11px; font-size: 12px; font-weight: 600; cursor: pointer; }
        .advisor-profile-btn.active { color: white; border-color: transparent; background: var(--accent-grad); box-shadow: 0 0 0 3px var(--primary-glow); }
        .advisor-grid { display: grid; grid-template-columns: minmax(0,1.35fr) minmax(280px,.65fr); gap: 14px; }
        .advisor-card { border: 1px solid var(--border); border-radius: 14px; background: var(--surface-2); padding: 15px; min-width: 0; }
        .advisor-card h3 { margin: 0 0 11px; font-size: 12px; color: var(--text-2); text-transform: uppercase; letter-spacing: .08em; }
        .advisor-recommendation { position: relative; overflow: hidden; background: linear-gradient(145deg, color-mix(in srgb, var(--surface-2) 82%, var(--primary) 18%), var(--surface-2)); }
        .advisor-recommendation::after { content: ''; position: absolute; width: 180px; height: 180px; right: -90px; top: -90px; border-radius: 50%; background: var(--primary-glow); filter: blur(8px); pointer-events: none; }
        .advisor-model-name { position: relative; z-index: 1; font-size: 20px; font-weight: 720; letter-spacing: -.45px; margin-bottom: 5px; }
        .advisor-reason { position: relative; z-index: 1; color: var(--text-2); font-size: 12px; line-height: 1.55; margin-bottom: 13px; }
        .advisor-pills { position: relative; z-index: 1; display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
        .advisor-pill { border: 1px solid var(--border); border-radius: 999px; background: color-mix(in srgb, var(--surface-1) 75%, transparent); padding: 5px 8px; color: var(--text-2); font-size: 11px; font-variant-numeric: tabular-nums; }
        .advisor-actions { position: relative; z-index: 1; display: flex; flex-wrap: wrap; gap: 8px; }
        .advisor-primary, .advisor-secondary { border-radius: 9px; padding: 8px 12px; font-size: 12px; font-weight: 650; cursor: pointer; }
        .advisor-primary { border: 0; color: white; background: var(--accent-grad); }
        .advisor-secondary { border: 1px solid var(--border); color: var(--text-2); background: var(--surface-1); }
        .advisor-primary:disabled, .advisor-secondary:disabled { opacity: .45; cursor: wait; }
        .advisor-hardware-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; }
        .advisor-hw-item { border: 1px solid var(--border); border-radius: 10px; background: var(--surface-1); padding: 10px; min-width: 0; }
        .advisor-hw-label { color: var(--text-3); font-size: 10px; text-transform: uppercase; letter-spacing: .07em; margin-bottom: 4px; }
        .advisor-hw-value { color: var(--text-1); font-size: 12px; font-weight: 650; overflow-wrap: anywhere; }
        .advisor-hw-sub { color: var(--text-3); font-size: 10px; line-height: 1.4; margin-top: 3px; }
        .advisor-notice { margin-top: 13px; border: 1px solid var(--border); border-radius: 10px; padding: 9px 10px; color: var(--text-3); background: var(--surface-1); font-size: 10px; line-height: 1.5; }
        .advisor-models { margin-top: 14px; }
        .advisor-table-wrap { overflow: auto; border: 1px solid var(--border); border-radius: 12px; }
        .advisor-table { width: 100%; border-collapse: collapse; min-width: 760px; font-size: 11px; }
        .advisor-table th { position: sticky; top: 0; z-index: 1; text-align: left; color: var(--text-3); background: var(--surface-2); padding: 9px 10px; border-bottom: 1px solid var(--border); text-transform: uppercase; letter-spacing: .06em; font-size: 9px; }
        .advisor-table td { padding: 9px 10px; border-bottom: 1px solid var(--border); color: var(--text-2); vertical-align: top; }
        .advisor-table tr:last-child td { border-bottom: 0; }
        .advisor-table strong { color: var(--text-1); font-size: 11px; }
        .advisor-status { display: inline-flex; align-items: center; gap: 5px; border-radius: 999px; padding: 3px 7px; font-size: 10px; font-weight: 650; }
        .advisor-status.compatible { color: var(--green); background: var(--green-glow); }
        .advisor-status.caution { color: var(--amber); background: var(--amber-glow); }
        .advisor-status.blocked { color: var(--red); background: rgba(239,68,68,.13); }
        .advisor-warning-list { margin: 5px 0 0; padding-left: 14px; color: var(--text-3); line-height: 1.45; }
        .advisor-warning-list li + li { margin-top: 3px; }
        .advisor-empty { padding: 30px 16px; text-align: center; color: var(--text-3); font-size: 12px; }
        .advisor-spinner { width: 20px; height: 20px; margin: 18px auto; border-radius: 50%; border: 2px solid var(--border); border-top-color: var(--primary); animation: advisor-spin .8s linear infinite; }
        @keyframes advisor-spin { to { transform: rotate(360deg); } }
        @media (max-width: 760px) { #advisor-overlay { padding: 0; align-items: stretch; } #advisor-dialog { max-height: 100vh; border-radius: 0; } .advisor-grid { grid-template-columns: 1fr; } .advisor-hardware-grid { grid-template-columns: 1fr 1fr; } }
        @media (max-width: 460px) { .advisor-hardware-grid { grid-template-columns: 1fr; } .advisor-header, #advisor-body { padding-left: 14px; padding-right: 14px; } }
    """
