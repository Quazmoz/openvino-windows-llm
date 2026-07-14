"""Apply a focused usability and accessibility pass to the built-in browser UI.

This is a one-shot repository maintenance script. The companion workflow removes it
from the final tree after the patch and regression test are committed.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "web" / "index.html"
TEST_PATH = ROOT / "tests" / "test_web_ui_ux.py"
MARKER = "/* UX_HARDENING_V1 */"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def replace_section(text: str, start: str, end: str, replacement: str, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"Missing {label} start marker")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"Missing {label} end marker")
    return text[:start_index] + replacement + text[end_index:]


UX_CSS = r'''

        /* UX_HARDENING_V1 */
        /* Accessibility, touch ergonomics, and narrow-screen layout hardening. */
        :root {
            --text-3: #71839a;
        }

        [data-theme="light"] {
            --text-3: #65758b;
        }

        #app {
            height: 100vh;
            height: 100dvh;
        }

        button,
        select,
        textarea,
        input {
            touch-action: manipulation;
        }

        .icon-btn {
            width: 36px;
            height: 36px;
        }

        .chats-header .icon-btn {
            width: 32px;
            height: 32px;
        }

        .close-btn {
            min-width: 36px;
            min-height: 36px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: var(--radius-sm);
        }

        #model-select,
        #device-select {
            min-height: 36px;
        }

        #settings-sidebar {
            opacity: 1;
            transition: margin-right 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                border-color 0.3s, opacity 0.2s;
        }

        #settings-sidebar.closed {
            margin-right: -280px;
            border-left-color: transparent;
            opacity: 0;
            pointer-events: none;
        }

        .bubble {
            overflow-wrap: anywhere;
        }

        .bubble table {
            display: block;
            max-width: 100%;
            overflow-x: auto;
        }

        .chat-item {
            display: grid;
            grid-template-columns: minmax(0, 1fr) 34px;
            align-items: center;
            gap: 2px;
            padding: 0;
            cursor: default;
        }

        .chat-item-main {
            min-width: 0;
            width: 100%;
            padding: 9px 8px 9px 11px;
            border: 0;
            border-radius: inherit;
            background: transparent;
            color: inherit;
            font: inherit;
            text-align: left;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .chat-item-main:focus-visible {
            outline: 2px solid var(--primary);
            outline-offset: -2px;
        }

        .chat-item-delete {
            position: static;
            transform: none;
            width: 30px;
            height: 30px;
            opacity: 0;
        }

        .chat-item:hover .chat-item-delete,
        .chat-item:focus-within .chat-item-delete {
            opacity: 1;
        }

        .modal-card {
            overscroll-behavior: contain;
        }

        .modal-tab-btn[aria-selected="true"] {
            color: var(--primary);
            border-bottom-color: var(--primary);
        }

        @media (hover: none), (pointer: coarse) {
            .icon-btn,
            .close-btn {
                min-width: 44px;
                min-height: 44px;
            }

            .chip,
            .action-btn,
            .benchmark-run-btn,
            .btn-cancel,
            .btn-submit,
            .search-result-select-btn,
            .search-row button {
                min-height: 44px;
            }

            .meta-btn {
                width: 36px;
                height: 36px;
                opacity: 1;
            }

            .code-copy,
            .chat-item-delete {
                opacity: 1;
            }

            .chat-item-delete {
                width: 44px;
                height: 44px;
            }
        }

        @media (max-width: 950px) {
            .header-right {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
            }

            .model-select-wrap {
                flex: 1 0 100%;
            }

            .device-select-wrap {
                flex: 1 1 180px;
            }

            #device-chip {
                flex: 0 1 auto;
            }

            .btn-group {
                display: inline-flex;
            }

            #chats-sidebar,
            #settings-sidebar {
                width: min(340px, 92vw);
            }

            #chats-sidebar.collapsed {
                margin-left: min(-340px, -92vw);
            }

            #settings-sidebar.closed {
                margin-right: min(-340px, -92vw);
            }
        }

        @media (max-width: 700px) {
            header {
                padding: 10px 12px;
                gap: 10px;
            }

            .header-left {
                justify-content: space-between;
            }

            .header-right {
                display: flex;
                gap: 8px;
            }

            .model-select-wrap {
                flex: 1 0 100%;
                order: 0;
            }

            .device-select-wrap {
                flex: 1 1 170px;
                order: 1;
            }

            #device-chip {
                min-height: 44px;
                order: 2;
            }

            .btn-group {
                order: 3;
            }

            #new-chat-btn,
            #add-model-btn,
            #export-chat-btn,
            #theme-toggle-btn,
            #settings-toggle-btn {
                order: 4;
            }

            #model-select,
            #device-select,
            #device-select.has-advanced-value {
                min-height: 44px;
                width: 100%;
                max-width: none;
                font-size: 13px;
            }

            #input-area {
                padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
            }

            #user-input {
                min-height: 48px;
                font-size: 16px;
            }

            #send-btn {
                width: 48px;
                height: 48px;
            }

            .footer-meta > span:first-child {
                display: none;
            }

            .footer-meta {
                margin-top: 6px;
            }

            .footer-right {
                width: 100%;
            }

            .msg-row.ai {
                align-items: stretch;
            }

            .msg-row.ai .msg-col {
                width: 100%;
                max-width: 100%;
            }

            .msg-row.user {
                align-items: flex-end;
            }

            .msg-row.user .msg-col {
                width: auto;
                max-width: 92%;
                align-items: flex-end;
            }

            .empty-state h2 {
                font-size: 21px;
            }

            .empty-state p {
                font-size: 13px;
            }

            #toast {
                bottom: calc(96px + env(safe-area-inset-bottom));
            }
        }
'''


TEST_CONTENT = '''"""Regression checks for the built-in UI usability hardening."""

from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(
    encoding="utf-8"
)


def test_mobile_and_touch_ergonomics_are_preserved() -> None:
    assert "/* UX_HARDENING_V1 */" in HTML
    assert "height: 100dvh" in HTML
    assert "@media (hover: none), (pointer: coarse)" in HTML
    assert "min-width: 44px" in HTML
    assert "env(safe-area-inset-bottom)" in HTML


def test_chat_list_has_no_nested_interactive_delete_control() -> None:
    assert "item.className = `chat-item" in HTML
    assert "selectButton.className = 'chat-item-main'" in HTML
    assert "const del = document.createElement('button');" in HTML
    assert "del.setAttribute('role', 'button')" not in HTML


def test_panels_and_modal_expose_accessible_state() -> None:
    assert 'aria-controls="chats-sidebar"' in HTML
    assert 'aria-controls="settings-sidebar"' in HTML
    assert 'role="dialog" aria-modal="true"' in HTML
    assert 'role="status" aria-live="polite"' in HTML
    assert "setSettingsSidebarOpen" in HTML
    assert "settingsSidebar.inert = !open" in HTML


def test_icon_only_actions_have_programmatic_names() -> None:
    assert "copyBtn.setAttribute('aria-label', 'Copy message');" in HTML
    assert "regenBtn.setAttribute('aria-label', 'Regenerate response');" in HTML
    assert "btn.setAttribute('aria-label', 'Copy code block');" in HTML
    assert "sendBtn.setAttribute('aria-label'" in HTML
'''


def main() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    if MARKER in html:
        raise RuntimeError("UX hardening marker already exists; refusing to apply twice")

    html = replace_once(html, "    </style>", UX_CSS + "\n    </style>", "style close")

    html = replace_once(
        html,
        '                <button class="icon-btn" id="chats-toggle-btn" title="Toggle conversations (Ctrl+B)"\n'
        '                    aria-label="Toggle conversation list">',
        '                <button class="icon-btn" id="chats-toggle-btn" title="Toggle conversations (Ctrl+B)"\n'
        '                    aria-label="Toggle conversation list" aria-controls="chats-sidebar" aria-expanded="true">',
        "chat toggle",
    )
    html = replace_once(
        html,
        '<aside id="chats-sidebar" aria-label="Conversations">',
        '<aside id="chats-sidebar" aria-label="Conversations" aria-hidden="false">',
        "chat sidebar",
    )
    html = replace_once(
        html,
        '<button class="icon-btn" id="settings-toggle-btn" title="Toggle Settings" aria-label="Toggle Settings">',
        '<button class="icon-btn" id="settings-toggle-btn" title="Toggle settings" aria-label="Toggle settings" '
        'aria-controls="settings-sidebar" aria-expanded="false">',
        "settings toggle",
    )
    html = replace_once(
        html,
        '                        <textarea id="user-input" placeholder="Message the model… (Enter to send, Shift+Enter for newline)"\n'
        '                            rows="1" autocomplete="off"></textarea>',
        '                        <textarea id="user-input" placeholder="Message the model… (Enter to send, Shift+Enter for newline)"\n'
        '                            rows="1" autocomplete="off" aria-label="Message the selected model"></textarea>',
        "message input",
    )
    html = replace_once(
        html,
        '<button type="submit" id="send-btn" title="Send (Enter)">',
        '<button type="submit" id="send-btn" title="Send (Enter)" aria-label="Send message">',
        "send button",
    )
    html = replace_once(
        html,
        '<span id="model-status">Loading model catalog…</span>',
        '<span id="model-status" role="status" aria-live="polite">Loading model catalog…</span>',
        "model status",
    )
    html = replace_once(
        html,
        '<div id="settings-sidebar" class="hidden">',
        '<aside id="settings-sidebar" class="closed" aria-label="Generation settings" aria-hidden="true">',
        "settings sidebar open",
    )
    html = replace_once(
        html,
        '            </div>\n        </div>\n    </div>\n\n    <div id="toast"></div>',
        '            </aside>\n        </div>\n    </div>\n\n    <div id="toast" role="status" aria-live="polite" aria-atomic="true"></div>',
        "settings sidebar close and toast",
    )
    html = replace_once(
        html,
        '<div id="custom-model-modal" class="modal-overlay hidden">\n        <div class="modal-card">',
        '<div id="custom-model-modal" class="modal-overlay hidden" aria-hidden="true">\n'
        '        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="custom-model-title">',
        "custom model dialog",
    )
    html = replace_once(
        html,
        '<h3>Add Custom Model</h3>\n                <button id="close-modal-btn" class="close-btn" title="Close modal">&times;</button>',
        '<h3 id="custom-model-title">Add Custom Model</h3>\n'
        '                <button id="close-modal-btn" class="close-btn" title="Close modal" '
        'aria-label="Close add custom model dialog">&times;</button>',
        "custom model heading",
    )
    html = replace_once(
        html,
        '            <div class="modal-tabs">\n'
        '                <button type="button" class="modal-tab-btn active" id="tab-btn-search">Search HF Hub</button>\n'
        '                <button type="button" class="modal-tab-btn" id="tab-btn-manual">Manual Add</button>\n'
        '            </div>',
        '            <div class="modal-tabs" role="tablist" aria-label="Custom model source">\n'
        '                <button type="button" class="modal-tab-btn active" id="tab-btn-search" role="tab" '
        'aria-selected="true" aria-controls="modal-panel-search">Search HF Hub</button>\n'
        '                <button type="button" class="modal-tab-btn" id="tab-btn-manual" role="tab" '
        'aria-selected="false" aria-controls="modal-panel-manual">Manual Add</button>\n'
        '            </div>',
        "modal tabs",
    )
    html = replace_once(
        html,
        '<div id="modal-panel-search" class="modal-panel">',
        '<div id="modal-panel-search" class="modal-panel" role="tabpanel" aria-labelledby="tab-btn-search">',
        "search panel",
    )
    html = replace_once(
        html,
        '<input type="text" id="hf-search-input" placeholder="Search HF Hub, e.g. Qwen2.5-0.5B or bge-small">',
        '<input type="text" id="hf-search-input" aria-label="Search Hugging Face Hub" '
        'placeholder="Search HF Hub, e.g. Qwen2.5-0.5B or bge-small">',
        "HF search input",
    )
    html = replace_once(
        html,
        '<div id="modal-panel-manual" class="modal-panel hidden">',
        '<div id="modal-panel-manual" class="modal-panel hidden" role="tabpanel" '
        'aria-labelledby="tab-btn-manual">',
        "manual panel",
    )

    html = replace_once(
        html,
        """        function applyTheme(theme) {
            if (theme === 'light') document.documentElement.dataset.theme = 'light';
            else delete document.documentElement.dataset.theme;
            themeToggleBtn.innerHTML = theme === 'light' ? MOON_ICON : SUN_ICON;
            themeToggleBtn.title = theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme';
        }
""",
        """        function applyTheme(theme) {
            if (theme === 'light') document.documentElement.dataset.theme = 'light';
            else delete document.documentElement.dataset.theme;
            themeToggleBtn.innerHTML = theme === 'light' ? MOON_ICON : SUN_ICON;
            const label = theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme';
            themeToggleBtn.title = label;
            themeToggleBtn.setAttribute('aria-label', label);
        }
""",
        "theme function",
    )
    html = replace_once(
        html,
        "                btn.type = 'button';\n                btn.textContent = 'Copy';",
        "                btn.type = 'button';\n                btn.setAttribute('aria-label', 'Copy code block');\n"
        "                btn.textContent = 'Copy';",
        "code copy label",
    )

    render_chat_list = """        function renderChatList() {
            const sorted = [...chats].sort((a, b) => (b.updated || 0) - (a.updated || 0));
            chatsList.innerHTML = '';
            sorted.forEach(chat => {
                const item = document.createElement('div');
                item.className = `chat-item${chat.id === activeChatId ? ' active' : ''}`;
                item.dataset.chatId = chat.id;

                const selectButton = document.createElement('button');
                selectButton.type = 'button';
                selectButton.className = 'chat-item-main';
                selectButton.setAttribute('aria-current', chat.id === activeChatId ? 'true' : 'false');

                const title = document.createElement('span');
                title.className = 'chat-item-title';
                title.textContent = chat.title || 'New chat';
                const sub = document.createElement('span');
                sub.className = 'chat-item-sub';
                sub.textContent = chatSubtitle(chat);

                selectButton.appendChild(title);
                selectButton.appendChild(sub);
                selectButton.addEventListener('click', () => switchChat(chat.id));

                const del = document.createElement('button');
                del.type = 'button';
                del.className = 'chat-item-delete';
                del.title = 'Delete chat';
                del.setAttribute('aria-label', `Delete chat: ${chat.title || 'New chat'}`);
                del.innerHTML = TRASH_ICON;
                del.addEventListener('click', () => deleteChat(chat.id));

                item.appendChild(selectButton);
                item.appendChild(del);
                chatsList.appendChild(item);
            });
            chatsFooter.textContent = `${chats.length} chat${chats.length === 1 ? '' : 's'} · stored in this browser`;
        }

"""
    html = replace_section(
        html,
        "        function renderChatList() {",
        "        function updateChatListTimes() {",
        render_chat_list,
        "chat list renderer",
    )

    html = replace_once(
        html,
        """        function setChatsSidebarCollapsed(collapsed) {
            chatsSidebar.classList.toggle('collapsed', collapsed);
            chatsToggleBtn.classList.toggle('active', !collapsed);
            try { localStorage.setItem(CHATLIST_KEY, collapsed ? 'closed' : 'open'); } catch { }
        }
""",
        """        function setChatsSidebarCollapsed(collapsed) {
            chatsSidebar.classList.toggle('collapsed', collapsed);
            chatsToggleBtn.classList.toggle('active', !collapsed);
            chatsToggleBtn.setAttribute('aria-expanded', String(!collapsed));
            chatsSidebar.setAttribute('aria-hidden', String(collapsed));
            chatsSidebar.inert = collapsed;
            if (!collapsed && window.innerWidth <= 950) setSettingsSidebarOpen(false);
            try { localStorage.setItem(CHATLIST_KEY, collapsed ? 'closed' : 'open'); } catch { }
        }
""",
        "chat sidebar state",
    )
    html = replace_once(
        html,
        """        chatsToggleBtn.addEventListener('click', () => {
            setChatsSidebarCollapsed(!chatsSidebar.classList.contains('collapsed'));
        });

        newChatBtn.addEventListener('click', newChat);
""",
        """        chatsToggleBtn.addEventListener('click', () => {
            setChatsSidebarCollapsed(!chatsSidebar.classList.contains('collapsed'));
        });

        function closeMobilePanelsFromContent() {
            if (window.innerWidth > 950) return;
            setChatsSidebarCollapsed(true);
            setSettingsSidebarOpen(false);
        }
        chatArea.addEventListener('pointerdown', closeMobilePanelsFromContent);
        document.getElementById('input-area').addEventListener('pointerdown', closeMobilePanelsFromContent);

        newChatBtn.addEventListener('click', newChat);
""",
        "mobile panel dismissal",
    )
    html = replace_once(
        html,
        "            avatar.className = `avatar ${role}`;",
        "            avatar.className = `avatar ${role}`;\n            avatar.setAttribute('aria-hidden', 'true');",
        "decorative avatar",
    )
    html = replace_once(
        html,
        "            copyBtn.title = 'Copy message';\n            copyBtn.innerHTML = COPY_ICON;",
        "            copyBtn.title = 'Copy message';\n            copyBtn.setAttribute('aria-label', 'Copy message');\n"
        "            copyBtn.innerHTML = COPY_ICON;",
        "message copy label",
    )
    html = replace_once(
        html,
        "                regenBtn.title = 'Regenerate response';\n                regenBtn.innerHTML = REGEN_ICON;",
        "                regenBtn.title = 'Regenerate response';\n"
        "                regenBtn.setAttribute('aria-label', 'Regenerate response');\n"
        "                regenBtn.innerHTML = REGEN_ICON;",
        "regenerate label",
    )
    html = replace_once(
        html,
        """        function setSendButtonMode(mode) {
            const stop = mode === 'stop';
            sendBtn.innerHTML = stop ? STOP_ICON : SEND_ICON;
            sendBtn.classList.toggle('stop', stop);
            sendBtn.title = stop ? 'Stop generating' : 'Send (Enter)';
        }
""",
        """        function setSendButtonMode(mode) {
            const stop = mode === 'stop';
            sendBtn.innerHTML = stop ? STOP_ICON : SEND_ICON;
            sendBtn.classList.toggle('stop', stop);
            sendBtn.title = stop ? 'Stop generating' : 'Send (Enter)';
            sendBtn.setAttribute('aria-label', stop ? 'Stop generating' : 'Send message');
        }
""",
        "send button mode",
    )

    tabs_replacement = """        // Tab Switching
        function selectCustomModelTab(tab) {
            const searchSelected = tab === 'search';
            tabBtnSearch.classList.toggle('active', searchSelected);
            tabBtnManual.classList.toggle('active', !searchSelected);
            tabBtnSearch.setAttribute('aria-selected', String(searchSelected));
            tabBtnManual.setAttribute('aria-selected', String(!searchSelected));
            modalPanelSearch.classList.toggle('hidden', !searchSelected);
            modalPanelManual.classList.toggle('hidden', searchSelected);
        }
        tabBtnSearch.addEventListener('click', () => selectCustomModelTab('search'));
        tabBtnManual.addEventListener('click', () => selectCustomModelTab('manual'));

"""
    html = replace_section(
        html,
        "        // Tab Switching\n",
        "        // Toggle INT4 options\n",
        tabs_replacement,
        "modal tab handlers",
    )

    html = replace_once(
        html,
        """        addModelBtn.addEventListener('click', () => {
            customModelModal.classList.remove('hidden');
            tabBtnSearch.click();
            hfSearchInput.value = '';
            hfSearchResults.innerHTML = '<div class="search-empty">Type a query and click Search to browse models on Hugging Face.</div>';
            hfSearchInput.focus();
        });
        closeModalBtn.addEventListener('click', () => customModelModal.classList.add('hidden'));
        cancelModalBtn.addEventListener('click', () => customModelModal.classList.add('hidden'));
        customModelModal.addEventListener('click', e => {
            if (e.target === customModelModal) customModelModal.classList.add('hidden');
        });
""",
        """        let modalReturnFocus = null;
        function setCustomModelModalOpen(open) {
            customModelModal.classList.toggle('hidden', !open);
            customModelModal.setAttribute('aria-hidden', String(!open));
            if (open) {
                modalReturnFocus = document.activeElement;
                selectCustomModelTab('search');
                hfSearchInput.value = '';
                hfSearchResults.innerHTML = '<div class="search-empty">Type a query and click Search to browse models on Hugging Face.</div>';
                hfSearchInput.focus();
            } else if (modalReturnFocus instanceof HTMLElement) {
                modalReturnFocus.focus();
                modalReturnFocus = null;
            }
        }
        addModelBtn.addEventListener('click', () => setCustomModelModalOpen(true));
        closeModalBtn.addEventListener('click', () => setCustomModelModalOpen(false));
        cancelModalBtn.addEventListener('click', () => setCustomModelModalOpen(false));
        customModelModal.addEventListener('click', e => {
            if (e.target === customModelModal) setCustomModelModalOpen(false);
        });
""",
        "modal open and close handlers",
    )
    html = replace_once(
        html,
        "                customModelModal.classList.add('hidden');\n                customModelForm.reset();",
        "                setCustomModelModalOpen(false);\n                customModelForm.reset();",
        "modal submit close",
    )
    html = replace_once(
        html,
        """            if (e.key === 'Escape') {
                if (!customModelModal.classList.contains('hidden')) {
                    e.preventDefault();
                    customModelModal.classList.add('hidden');
                } else if (isGenerating) {
                    e.preventDefault();
                    stopGeneration();
                }
            }
""",
        """            if (e.key === 'Escape') {
                if (!customModelModal.classList.contains('hidden')) {
                    e.preventDefault();
                    setCustomModelModalOpen(false);
                } else if (!settingsSidebar.classList.contains('closed')) {
                    e.preventDefault();
                    setSettingsSidebarOpen(false, true);
                } else if (window.innerWidth <= 950 && !chatsSidebar.classList.contains('collapsed')) {
                    e.preventDefault();
                    setChatsSidebarCollapsed(true);
                    chatsToggleBtn.focus();
                } else if (isGenerating) {
                    e.preventDefault();
                    stopGeneration();
                }
            }
""",
        "escape handling",
    )
    html = replace_once(
        html,
        """                settingsSidebar.classList.remove('hidden');
                settingsToggleBtn.classList.add('active');
                settingsApiKey.focus();
""",
        """                setSettingsSidebarOpen(true);
                settingsApiKey.focus();
""",
        "auth settings open",
    )

    html = replace_once(
        html,
        """        // Toggle sidebar
        settingsToggleBtn.addEventListener('click', () => {
            settingsSidebar.classList.toggle('hidden');
            settingsToggleBtn.classList.toggle('active');
        });
        closeSidebarBtn.addEventListener('click', () => {
            settingsSidebar.classList.add('hidden');
            settingsToggleBtn.classList.remove('active');
        });
""",
        """        // Toggle sidebar while keeping visual, focus, and accessibility state aligned.
        function setSettingsSidebarOpen(open, restoreFocus = false) {
            settingsSidebar.classList.toggle('closed', !open);
            settingsToggleBtn.classList.toggle('active', open);
            settingsToggleBtn.setAttribute('aria-expanded', String(open));
            settingsSidebar.setAttribute('aria-hidden', String(!open));
            settingsSidebar.inert = !open;
            if (open && window.innerWidth <= 950) setChatsSidebarCollapsed(true);
            if (restoreFocus) settingsToggleBtn.focus();
        }
        settingsToggleBtn.addEventListener('click', () => {
            setSettingsSidebarOpen(settingsSidebar.classList.contains('closed'));
        });
        closeSidebarBtn.addEventListener('click', () => setSettingsSidebarOpen(false, true));
        setSettingsSidebarOpen(false);
""",
        "settings handlers",
    )

    HTML_PATH.write_text(html, encoding="utf-8")
    TEST_PATH.write_text(TEST_CONTENT, encoding="utf-8")


if __name__ == "__main__":
    main()
