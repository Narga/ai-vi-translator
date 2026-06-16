// ============================================================
// ui-helpers.js — Toast, Modal, Focus Mode, Provider, Logs, Plugins
// ============================================================

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return text.toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

const ModalManager = {
    show(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) { console.warn('Modal not found:', modalId); return; }
        modal.classList.remove('dn');
        modal.classList.add('flex');
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    },

    hide(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.add('dn');
        modal.classList.remove('flex');
        modal.style.display = '';
        document.body.style.overflow = '';
    },

    hideAll() {
        document.querySelectorAll('[id$="-modal"]').forEach(function(modal) {
            if (modal.classList.contains('flex') || modal.style.display === 'flex') {
                ModalManager.hide(modal.id);
            }
        });
    },

    isOpen(modalId) {
        var modal = document.getElementById(modalId);
        return modal && (modal.classList.contains('flex') || modal.style.display === 'flex');
    }
};
window.ModalManager = ModalManager;

function showConfirm(message, options) {
    options = options || {};
    var title = options.title || 'Xác nhận';
    var confirmText = options.confirmText || 'Đồng ý';
    var cancelText = options.cancelText || 'Hủy';
    var danger = options.danger || false;

    return new Promise(function(resolve) {
        var overlay = document.createElement('div');
        overlay.className = 'fixed absolute--fill bg-black-50 z-max items-center justify-center';
        overlay.style.cssText = 'display:flex; z-index:99999;';
        overlay.innerHTML = 
            '<div class="bg-white br3 shadow-5 w-100 mw6 pa4 animate-pop">' +
                '<h3 class="f5 mt0 mb3 fw6 dark-gray pb2 bb b--black-10">' + escapeHtml(title) + '</h3>' +
                '<p class="f6 gray mb4">' + escapeHtml(message) + '</p>' +
                '<div class="flex justify-end gap-3 pt3 bt b--black-10">' +
                    '<button class="nt-btn nt-btn-outline" data-action="cancel">' + escapeHtml(cancelText) + '</button>' +
                    '<button class="nt-btn ' + (danger ? 'nt-btn-danger' : 'nt-btn-primary') + '" data-action="confirm">' + escapeHtml(confirmText) + '</button>' +
                '</div>' +
            '</div>';
        
        document.body.appendChild(overlay);

        overlay.addEventListener('click', function(e) {
            var action = e.target.getAttribute('data-action');
            if (action === 'confirm') { resolve(true); overlay.remove(); }
            else if (action === 'cancel' || e.target === overlay) { resolve(false); overlay.remove(); }
        });
    });
}
window.showConfirm = showConfirm;

function showPrompt(message, defaultValue) {
    defaultValue = defaultValue || '';

    return new Promise(function(resolve) {
        var overlay = document.createElement('div');
        overlay.className = 'fixed absolute--fill bg-black-50 z-max items-center justify-center';
        overlay.style.cssText = 'display:flex; z-index:99999;';
        overlay.innerHTML = 
            '<div class="bg-white br3 shadow-5 w-100 mw6 pa4 animate-pop">' +
                '<h3 class="f5 mt0 mb3 fw6 dark-gray pb2 bb b--black-10">Nhập thông tin</h3>' +
                '<label class="db f6 gray mb2">' + escapeHtml(message) + '</label>' +
                '<input type="text" class="nt-input w-100 mb4" value="' + escapeHtml(defaultValue) + '" id="custom-prompt-input">' +
                '<div class="flex justify-end gap-3 pt3 bt b--black-10">' +
                    '<button class="nt-btn nt-btn-outline" data-action="cancel">Hủy</button>' +
                    '<button class="nt-btn nt-btn-primary" data-action="confirm">OK</button>' +
                '</div>' +
            '</div>';
        
        document.body.appendChild(overlay);

        var input = overlay.querySelector('#custom-prompt-input');
        setTimeout(function() { input.focus(); input.select(); }, 50);

        overlay.addEventListener('click', function(e) {
            var action = e.target.getAttribute('data-action');
            if (action === 'confirm') { resolve(input.value); overlay.remove(); }
            else if (action === 'cancel' || e.target === overlay) { resolve(null); overlay.remove(); }
        });

        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') { resolve(input.value); overlay.remove(); }
            if (e.key === 'Escape') { resolve(null); overlay.remove(); }
        });
    });
}
window.showPrompt = showPrompt;

// Auto-wire: close modal khi click vào overlay
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('bg-black-70') || e.target.classList.contains('bg-black-50')) {
        var modal = e.target.closest('[id$="-modal"]');
        if (modal) ModalManager.hide(modal.id);
    }
});

// Auto-wire: close modal khi nhấn Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        ModalManager.hideAll();
    }
});

const UiHelpers = {
    showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        if (type === 'error') icon = '❌';

        toast.innerHTML = `<span>${icon}</span><span class="ml2">${message}</span>`;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    },

    addLog(message, type) {
        const el = document.getElementById('log-container');
        if (!el) return;
        const entry = document.createElement('div');
        const typeClass = type === 'error' ? 'red fw6' : (type === 'success' ? 'green' : 'blue');
        entry.className = 'nt-log-entry mb1 ' + typeClass;
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        el.appendChild(entry);
        el.scrollTop = el.scrollHeight;
    },

    showProgressModal() {
        ModalManager.show('translation-progress-modal');
        // Reset progress bar
        const progressBar = document.getElementById('progress-bar');
        const progressPercent = document.getElementById('progress-percent');
        const progressText = document.getElementById('progress-text');
        if (progressBar) progressBar.style.width = '0%';
        if (progressPercent) progressPercent.textContent = '0%';
        if (progressText) progressText.textContent = 'Đang chuẩn bị...';
        // Clear log
        const logEl = document.getElementById('log-container');
        if (logEl) logEl.innerHTML = '';
        // Hide done button
        const btnDone = document.getElementById('btn-progress-done');
        if (btnDone) btnDone.classList.add('dn');
    },

    // Provider Management
    switchProvider(provider) {
        document.querySelectorAll('.nt-provider-col').forEach(col => {
            const isActive = col.dataset.provider === provider;
            if (isActive) {
                col.classList.add('b--blue', 'o-100');
                col.classList.remove('b--light-gray', 'o-60');
                const radio = col.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;
            } else {
                col.classList.add('b--black-10', 'o-60');
                col.classList.remove('b--blue', 'o-100');
                const radio = col.querySelector('input[type="radio"]');
                if (radio) radio.checked = false;
            }
        });

        // Tìm provider id phù hợp từ danh sách providers
        ApiClient.fetchJson('/api/providers')
            .then(data => {
                const providers = data.providers || [];
                const match = providers.find(p => p.type === provider);
                if (!match) {
                    UiHelpers.showToast(`Không tìm thấy provider loại ${provider}`, 'error');
                    return;
                }
                return ApiClient.fetchJson('/api/providers/select', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ active_id: match.id })
                });
            })
            .then(data => {
                if (data && data.success) {
                    UiHelpers.showToast(`Đã chuyển sang ${provider === 'gemini' ? 'Google Gemini' : 'OpenAI Compatible'}`, 'success');
                    ApiClient.loadModels();
                    const nameEl = document.getElementById('current-provider-name');
                    if (nameEl) nameEl.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';
                }
            })
            .catch(e => UiHelpers.showToast(e.message, 'error'));
    },

    saveOpenAIConfig() {
        const data = {
            api_key: document.getElementById('openai-api-key').value,
            base_url: document.getElementById('openai-base-url').value,
            model: document.getElementById('model').value,
        };

        fetch('/api/openai/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    UiHelpers.showToast('Đã lưu cấu hình OpenAI', 'success');
                    // Reload models với cấu hình mới
                    ApiClient.loadModels();
                } else {
                    UiHelpers.showToast(res.error || 'Lỗi lưu config', 'error');
                }
            })
            .catch(e => UiHelpers.showToast(e.message, 'error'));
    },

    initProvider() {
        ApiClient.fetchJson('/api/providers')
            .then(data => {
                const activeId = data.active_id || '';
                const providers = data.providers || [];
                const active = providers.find(p => p.id === activeId);
                const provider = active ? active.type : 'gemini';

                const radio = document.querySelector(`input[name="active_provider"][value="${provider}"]`);
                if (radio) radio.checked = true;

                document.querySelectorAll('.nt-provider-col').forEach(col => {
                    col.classList.toggle('nt-provider-active', col.dataset.provider === provider);
                });

                const badge = document.getElementById('provider-active-badge');
                if (badge) {
                    badge.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';
                    badge.className = 'f7 fw6 ph2 pv1 br2 ' +
                        (provider === 'gemini' ? 'bg-light-green dark-green' : 'bg-lightest-blue dark-blue');
                }
                const nameEl = document.getElementById('current-provider-name');
                if (nameEl) nameEl.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';

                // Load OpenAI providers dropdown (new in v7.3.0)
                if (typeof OpenAIProvider !== 'undefined') {
                    OpenAIProvider.loadProviders();
                }
            })
            .catch(e => console.error('Failed to load provider info:', e));
    },

    // Logs
    currentLogFile: '',
    selectedLogFiles: new Set(),

    updateSelectedLogsUI() {
        const btn = document.getElementById('btn-delete-selected-logs');
        if (!btn) return;
        if (UiHelpers.selectedLogFiles.size > 0) {
            btn.classList.remove('dn');
            btn.textContent = `🗑️ Xóa đã chọn (${UiHelpers.selectedLogFiles.size})`;
        } else {
            btn.classList.add('dn');
            btn.textContent = '🗑️ Xóa đã chọn';
        }
    },

    toggleLogFile(filename, checked) {
        if (checked) UiHelpers.selectedLogFiles.add(filename);
        else UiHelpers.selectedLogFiles.delete(filename);
        UiHelpers.updateSelectedLogsUI();
    },

    selectAllLogs(checked) {
        const boxes = document.querySelectorAll('.sys-log-checkbox');
        boxes.forEach(box => {
            box.checked = checked;
            UiHelpers.toggleLogFile(box.value, checked);
        });
    },

    async deleteSelectedLogs() {
        if (UiHelpers.selectedLogFiles.size === 0) return;
        const files = Array.from(UiHelpers.selectedLogFiles);
        if (!await showConfirm('Xóa vĩnh viễn ' + files.length + ' file log đã chọn?', { danger: true })) return;

        Promise.all(files.map(filename =>
            fetch(`/api/logs/${encodeURIComponent(filename)}`, { method: 'DELETE' }).then(r => r.json())
        ))
            .then(results => {
                const failed = results.filter(r => !r.success);
                if (failed.length > 0) {
                    UiHelpers.showToast(`Xóa thất bại ${failed.length} file log`, 'error');
                } else {
                    UiHelpers.showToast(`Đã xóa ${files.length} file log`, 'success');
                }
                UiHelpers.currentLogFile = '';
                document.getElementById('current-log-title').textContent = 'Chọn file để xem';
                document.getElementById('sys-log-viewer').innerHTML = '<div class="tc silver mt5 i">Chưa chọn file log.</div>';
                document.getElementById('btn-delete-log').classList.add('dn');
                ApiClient.loadLogList();
            })
            .catch(e => UiHelpers.showToast('Lỗi xóa logs: ' + e.message, 'error'));
    },

    viewLogFile(filename) {
        UiHelpers.currentLogFile = filename;
        document.getElementById('current-log-title').textContent = filename;
        document.getElementById('btn-delete-log').classList.remove('dn');
        document.getElementById('sys-log-viewer').innerHTML = '<div class="tc silver mt5 i">Đang tải nội dung...</div>';

        fetch(`/api/logs/${encodeURIComponent(filename)}`)
            .then(r => r.json())
            .then(data => {
                if (data.error) throw new Error(data.error);
                
                const lines = data.content.split('\n');
                let parsedHtml = '';
                
                lines.forEach(line => {
                    if (!line.trim()) return;
                    
                    let lineClass = "db mb1 pb1 bb b--white-05";
                    let textClass = "near-white";
                    
                    if (line.includes(' - INFO - ')) {
                        line = line.replace(' - INFO - ', ' <span class="blue b">[INFO]</span> ');
                    } else if (line.includes(' - ERROR - ') || line.includes('❌') || line.includes('Error') || line.includes('error')) {
                        line = line.replace(' - ERROR - ', ' <span class="red b">[ERROR]</span> ');
                        textClass = "light-red";
                    } else if (line.includes(' - WARNING - ') || line.includes('⚠️')) {
                        line = line.replace(' - WARNING - ', ' <span class="yellow b">[WARN]</span> ');
                        textClass = "washed-yellow";
                    } else if (line.includes('✅')) {
                        textClass = "light-green";
                    }
                    
                    line = line.replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    line = line.replace(/&lt;span class="([^"]+)"&gt;/g, '<span class="$1">').replace(/&lt;\/span&gt;/g, '</span>');

                    parsedHtml += `<div class="${lineClass} ${textClass}">${line}</div>`;
                });
                
                document.getElementById('sys-log-viewer').innerHTML = parsedHtml;
                const container = document.getElementById('sys-log-viewer').parentElement;
                container.scrollTop = container.scrollHeight;
            })
            .catch(e => UiHelpers.showToast('Lỗi đọc file: ' + e.message, 'error'));
    },

    async deleteCurrentLog() {
        if (!UiHelpers.currentLogFile) return;
        if (!await showConfirm('Xóa vĩnh viễn file log "' + UiHelpers.currentLogFile + '"?', { danger: true })) return;
        
        fetch(`/api/logs/${encodeURIComponent(UiHelpers.currentLogFile)}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    UiHelpers.showToast('Đã xóa log', 'success');
                    UiHelpers.currentLogFile = '';
                    document.getElementById('current-log-title').textContent = 'Chọn file để xem';
                    document.getElementById('sys-log-viewer').innerHTML = '<div class="tc silver mt5 i">Chưa chọn file log.</div>';
                    document.getElementById('btn-delete-log').classList.add('dn');
                    ApiClient.loadLogList();
                } else {
                    UiHelpers.showToast(data.error || 'Lỗi', 'error');
                }
            });
    },

    // Plugins
    getCurrentProjectSlug() {
        if (!window.currentProject) return null;
        return typeof window.currentProject === 'string' ? window.currentProject : window.currentProject.slug;
    },

    runEpubToText() {
        const slug = UiHelpers.getCurrentProjectSlug();
        if (!slug) {
            UiHelpers.showToast('Vui lòng mở một dự án trước khi chạy eBook Kit', 'error');
            return;
        }
        const logEl = document.getElementById('epub-log');
        logEl.innerHTML = '';
        logEl.classList.remove('dn');

        const btn = document.getElementById('btn-run-epub2text');
        btn.disabled = true;
        btn.textContent = '⏳ Đang chạy...';

        let payload = { direction: 'epub_to_text' };
        payload.epub_path = document.getElementById('epub-path').value.trim();
        payload.out_dir = document.getElementById('epub-out-dir').value.trim();
        payload.mode = document.getElementById('epub-mode').value;
        payload.ext = document.getElementById('epub-ext').value;
        payload.underline = document.getElementById('epub-underline').checked;
        payload.include_nonspine = document.getElementById('epub-nonspine').checked;

        if (!payload.epub_path) {
            UiHelpers.pluginLog('epub-log', '❌ Vui lòng nhập đường dẫn file EPUB!', 'error');
            btn.disabled = false;
            btn.textContent = 'Chạy EPUB → Text';
            return;
        }

        UiHelpers.pluginLog('epub-log', '🔄 Đang gửi yêu cầu...', 'info');

        fetch(`/api/projects/${encodeURIComponent(slug)}/plugins/epub-converter`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(r => r.json()).then(data => {
            if (data.plugin_id) {
                UiHelpers.pollPluginProgress(data.plugin_id, 'epub-log', btn, 'Chạy EPUB → Text');
            } else {
                UiHelpers.pluginLog('epub-log', '❌ ' + (data.error || 'Lỗi không xác định'), 'error');
                btn.disabled = false;
                btn.textContent = 'Chạy EPUB → Text';
            }
        }).catch(e => {
            UiHelpers.pluginLog('epub-log', '❌ Lỗi kết nối: ' + e.message, 'error');
            btn.disabled = false;
            btn.textContent = 'Chạy EPUB → Text';
        });
    },

    runTextToEpub() {
        const slug = UiHelpers.getCurrentProjectSlug();
        if (!slug) {
            UiHelpers.showToast('Vui lòng mở một dự án trước khi chạy eBook Kit', 'error');
            return;
        }
        const logEl = document.getElementById('epub-log');
        logEl.innerHTML = '';
        logEl.classList.remove('dn');

        const btn = document.getElementById('btn-run-text2epub');
        btn.disabled = true;
        btn.textContent = '⏳ Đang chạy...';

        let payload = { direction: 'text_to_epub' };
        payload.directory = document.getElementById('epub-book-dir').value.trim();
        payload.use_markdown = document.getElementById('epub-use-md').checked;
        payload.split_chapters = document.getElementById('epub-split-chapters').checked;

        UiHelpers.pluginLog('epub-log', '🔄 Đang gửi yêu cầu...', 'info');

        fetch(`/api/projects/${encodeURIComponent(slug)}/plugins/epub-converter`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(r => r.json()).then(data => {
            if (data.plugin_id) {
                UiHelpers.pollPluginProgress(data.plugin_id, 'epub-log', btn, 'Chạy Text → EPUB');
            } else {
                UiHelpers.pluginLog('epub-log', '❌ ' + (data.error || 'Lỗi không xác định'), 'error');
                btn.disabled = false;
                btn.textContent = 'Chạy Text → EPUB';
            }
        }).catch(e => {
            UiHelpers.pluginLog('epub-log', '❌ Lỗi kết nối: ' + e.message, 'error');
            btn.disabled = false;
            btn.textContent = 'Chạy Text → EPUB';
        });
    },

    runProjectOcr() {
        const slug = UiHelpers.getCurrentProjectSlug();
        if (!slug) {
            UiHelpers.showToast('Vui lòng mở một dự án trước khi chạy OCR Toolbox', 'error');
            return;
        }
        const logEl = document.getElementById('ocr-log');
        logEl.innerHTML = '';
        logEl.classList.remove('dn');

        const btn = document.getElementById('btn-run-ocr');
        btn.disabled = true;
        btn.textContent = '⏳ Đang chạy...';

        const input_path = document.getElementById('ocr-input').value.trim();
        if (!input_path) {
            UiHelpers.pluginLog('ocr-log', '❌ Vui lòng nhập đường dẫn file PDF/Ảnh!', 'error');
            btn.disabled = false;
            btn.textContent = '🚀 Chạy OCR Toolbox';
            return;
        }

        const skip_steps = {};
        if (document.getElementById('ocr-skip-cleanup').checked) skip_steps.cleanup = true;
        if (document.getElementById('ocr-skip-spell').checked) skip_steps.spell_check = true;

        const pagesRaw = document.getElementById('ocr-pages').value.trim();

        const payload = {
            input_path,
            output_path: document.getElementById('ocr-output').value.trim(),
            process_mode: document.getElementById('ocr-mode').value,
            skip_steps: Object.keys(skip_steps).length ? skip_steps : null,
            pages: pagesRaw || null
        };

        UiHelpers.pluginLog('ocr-log', '🔄 Đang gửi yêu cầu OCR...', 'info');

        fetch(`/api/projects/${encodeURIComponent(slug)}/plugins/ocr`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(r => r.json()).then(data => {
            if (data.plugin_id) {
                UiHelpers.pollPluginProgress(data.plugin_id, 'ocr-log', btn, '🚀 Chạy OCR Toolbox');
            } else {
                UiHelpers.pluginLog('ocr-log', '❌ ' + (data.error || 'Lỗi không xác định'), 'error');
                btn.disabled = false;
                btn.textContent = '🚀 Chạy OCR Toolbox';
            }
        }).catch(e => {
            UiHelpers.pluginLog('ocr-log', '❌ Lỗi kết nối: ' + e.message, 'error');
            btn.disabled = false;
            btn.textContent = '🚀 Chạy OCR Toolbox';
        });
    },

    pollPluginProgress(pluginId, logId, btn, btnLabel) {
        let lastCount = 0;

        const interval = setInterval(() => {
            fetch('/api/plugins/progress/' + pluginId)
                .then(r => r.json())
                .then(data => {
                    const msgs = data.messages || [];
                    for (let i = lastCount; i < msgs.length; i++) {
                        const isError = msgs[i].includes('❌') || msgs[i].includes('Lỗi');
                        const isSuccess = msgs[i].includes('✅') || msgs[i].includes('thành công');
                        UiHelpers.pluginLog(logId, msgs[i], isError ? 'error' : (isSuccess ? 'success' : 'info'));
                    }
                    lastCount = msgs.length;

                    if (data.status === 'done' || data.status === 'error') {
                        clearInterval(interval);
                        btn.disabled = false;
                        btn.textContent = btnLabel;

                        if (data.status === 'done' && data.result) {
                            if (data.result.output_dir) UiHelpers.pluginLog(logId, `📂 Output: ${data.result.output_dir}`, 'success');
                            if (data.result.output_path) UiHelpers.pluginLog(logId, `📄 File: ${data.result.output_path}`, 'success');
                            if (data.result.char_count) UiHelpers.pluginLog(logId, `🔤 ${data.result.char_count.toLocaleString()} ký tự`, 'success');
                        }

                        ApiClient.loadStats();
                    }
                })
                .catch(() => {
                    clearInterval(interval);
                    btn.disabled = false;
                    btn.textContent = btnLabel;
                });
        }, 1000);
    },

    // Init dialogs
    initDialogs() {
        document.getElementById('btn-new-genre').addEventListener('click', () => {
            ModalManager.show('new-genre-modal');
        });

        document.getElementById('btn-cancel-genre').addEventListener('click', () => {
            ModalManager.hide('new-genre-modal');
        });

        document.getElementById('btn-confirm-new-genre').addEventListener('click', (e) => {
            PromptManager.createGenre(e);
            ModalManager.hide('new-genre-modal');
        });

        document.getElementById('new-genre-name').addEventListener('input', function () {
            const slug = this.value.toLowerCase()
                .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
                .replace(/đ/g, 'd').replace(/Đ/g, 'D')
                .replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
            document.getElementById('new-genre-slug').value = slug;
        });
    },

    // Restore app state
    restoreAppState() {
        const savedMainTab = localStorage.getItem('nt_active_main_tab');
        if (savedMainTab) {
            const tabLink = document.querySelector(`.nav-link[data-tab="${savedMainTab}"]`);
            if (tabLink) tabLink.click();
        }

        const savedInfoTab = localStorage.getItem('nt_active_info_tab');
        if (savedInfoTab) {
            const infoRadio = document.getElementById(savedInfoTab);
            if (infoRadio) infoRadio.checked = true;
        }
    },
    
    showPluginSettings(pluginId) {
        UiHelpers.showToast(`Tính năng cài đặt cho plugin ${pluginId} đang được phát triển`, 'info');
    }
};

window.UiHelpers = UiHelpers;
