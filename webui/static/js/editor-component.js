// ============================================================
// editor-component.js — Editor, token estimation, diff view, file loading
// ============================================================

const EditorComponent = {
    syncScrollEnabled: true,

    // Helper: derive tên file log _info từ tên file nội dung
    // Quy tắc giống backend: stem + '_info.txt' (filename.rsplit('.', 1)[0] + '_info.txt')
    getSpellcheckInfoFilename(filename) {
        const slash = filename.lastIndexOf('/');
        const dir = slash >= 0 ? filename.slice(0, slash + 1) : '';
        const base = slash >= 0 ? filename.slice(slash + 1) : filename;
        const dot = base.lastIndexOf('.');
        const stem = dot > 0 ? base.slice(0, dot) : base;
        return `${dir}${stem}_info.txt`;
    },

    // Generic file loader — prefix = '' hoặc 'pm-'
    async _loadFilePair(prefix, filename, section) {
        if (!window.currentProject) return;
        if (DirtyState.isDirty() && !await showConfirm('Bạn có thay đổi chưa lưu. Tiếp tục?')) {
            return;
        }
        DirtyState.clean(prefix + 'source-text');
        DirtyState.clean(prefix + 'result-text');
        DirtyState.clean(prefix + 'spell-source-text');
        DirtyState.clean(prefix + 'spell-result-text');
        const slug = window.currentProject.slug;

        const statusEl = document.getElementById(prefix + 'opened-file-status');
        if (statusEl) {
            statusEl.innerHTML = `<strong>Tập tin:</strong> <em>${filename}</em> | `;
        }

        if (section === 'sources') {
            fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(data => {
                document.getElementById(prefix + 'source-text').value = data.content || '';
                window.currentProjectFile = { name: filename, section };
                if (!prefix) document.getElementById('token-estimate-mini')?.classList.remove('dn');
                EditorComponent.updateTokenEstimate();
                fetch(`/api/projects/${slug}/file/translated/${filename}`).then(r => r.json()).then(tData => {
                    document.getElementById(prefix + 'result-text').value = tData.content || '';
                    DirtyState.clean(prefix + 'result-text');
                }).catch(() => {
                    document.getElementById(prefix + 'result-text').value = '';
                    DirtyState.clean(prefix + 'result-text');
                });
            });
        } else if (section === 'translated') {
            fetch(`/api/projects/${slug}/file/translated/${filename}`).then(r => r.json()).then(data => {
                document.getElementById(prefix + 'result-text').value = data.content || '';
                window.currentProjectFile = { name: filename, section };
                DirtyState.clean(prefix + 'result-text');
                if (!prefix) document.getElementById('token-estimate-mini')?.classList.remove('dn');
                fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(sData => {
                    document.getElementById(prefix + 'source-text').value = sData.content || '';
                    EditorComponent.updateTokenEstimate();
                }).catch(() => {
                    document.getElementById(prefix + 'source-text').value = '(Không tìm thấy bản gốc tương ứng)';
                });
            });
        }
    },

    // Generic spellcheck file loader — prefix = '' hoặc 'pm-'
    _loadSpellcheckFile(prefix, filename) {
        if (!window.currentProject) return;
        const slug = window.currentProject.slug;
        const infoName = EditorComponent.getSpellcheckInfoFilename(filename);

        const statusEl = document.getElementById(prefix + 'spell-opened-file-status');
        if (statusEl) {
            statusEl.innerHTML = `<strong>Tập tin:</strong> <em>${filename}</em> | `;
        }

        fetch(`/api/projects/${slug}/file/spelling/${filename}`).then(r => r.json()).then(data => {
            document.getElementById(prefix + 'spell-result-text').value = data.content || '';
            window.currentProjectFile = { name: filename, section: 'spelling' };
            DirtyState.clean(prefix + 'spell-result-text');
            fetch(`/api/projects/${slug}/file/spelling/${infoName}`).then(r => r.json()).then(infoData => {
                const logEl = document.getElementById(prefix + 'spell-log-content');
                if (logEl) logEl.textContent = infoData.content || 'Không có dữ liệu soát lỗi.';
            }).catch(() => {
                const logEl = document.getElementById(prefix + 'spell-log-content');
                if (logEl) logEl.textContent = 'Không có dữ liệu soát lỗi.';
            });
        }).catch(() => {
            document.getElementById(prefix + 'spell-result-text').value = '';
            const logEl = document.getElementById(prefix + 'spell-log-content');
            if (logEl) logEl.textContent = 'Lỗi tải file.';
        });
        fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(sourceData => {
            document.getElementById(prefix + 'spell-source-text').value = sourceData.content || '';
            DirtyState.clean(prefix + 'spell-source-text');
        }).catch(() => {
            document.getElementById(prefix + 'spell-source-text').value = '';
        });
    },

    // Public API — delegates to generic helpers
    async loadProjectFile(filename, section) { return this._loadFilePair('', filename, section); },
    async loadPmProjectFile(filename, section) { return this._loadFilePair('pm-', filename, section); },
    loadSpellcheckFile(filename) { this._loadSpellcheckFile('', filename); },
    loadPmSpellcheckFile(filename) { this._loadSpellcheckFile('pm-', filename); },

    _tokenEstimateTimer: null,

    updateTokenEstimate() {
        clearTimeout(EditorComponent._tokenEstimateTimer);
        EditorComponent._tokenEstimateTimer = setTimeout(() => EditorComponent._doTokenEstimate(), 300);
    },

    _doTokenEstimate() {
        // Xác định editor nào đang active - ưu tiên editor có nội dung
        const pmSourceEl = document.getElementById('pm-source-text');
        const pmSpellSourceEl = document.getElementById('pm-spell-source-text');
        const oldSourceEl = document.getElementById('source-text');
        
        // Tìm editor có nội dung
        const sourceEl = (pmSourceEl && pmSourceEl.value) ? pmSourceEl 
                       : (pmSpellSourceEl && pmSpellSourceEl.value) ? pmSpellSourceEl 
                       : oldSourceEl;
        if (!sourceEl) return;
        
        const text = sourceEl.value || '';
        const charCount = text.length;
        const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;

        // Cập nhật cho tất cả các vị trí hiển thị token estimate
        const charCountEls = document.querySelectorAll('#token-char-count, #pm-token-char-count, #pm-spell-char-count');
        charCountEls.forEach(el => el.innerHTML = `<strong>${charCount.toLocaleString()}</strong>`);
        
        const wordCountEls = document.querySelectorAll('#token-word-count, #pm-token-word-count, #pm-spell-word-count');
        wordCountEls.forEach(el => el.innerHTML = `<strong>${wordCount.toLocaleString()}</strong>`);

        if (charCount === 0) {
            const estEls = document.querySelectorAll('#token-estimate, #pm-token-estimate');
            estEls.forEach(el => el.innerHTML = '<strong>~0</strong>');
            const fitEls = document.querySelectorAll('#token-model-fit, #pm-token-model-fit');
            fitEls.forEach(el => el.textContent = '');
            return;
        }

        const cjkMatch = text.match(/[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]/g);
        const cjkCount = cjkMatch ? cjkMatch.length : 0;
        const cjkRatio = cjkCount / charCount;

        let tokensPerChar;
        if (cjkRatio > 0.5) tokensPerChar = 1 / 1.5;
        else if (cjkRatio > 0.2) tokensPerChar = 1 / 2.5;
        else tokensPerChar = 1 / 4.0;

        const estimatedTokens = Math.round(charCount * tokensPerChar);
        const promptOverhead = 2000;
        const totalInput = estimatedTokens + promptOverhead;

        const tokenEstEls = document.querySelectorAll('#token-estimate, #pm-token-estimate');
        tokenEstEls.forEach(el => el.innerHTML = '<strong>~' + estimatedTokens.toLocaleString() + '</strong>');

        const fitEls = document.querySelectorAll('#token-model-fit, #pm-token-model-fit');
        if (window.currentModelInfo && window.currentModelInfo.input_token_limit) {
            const limit = window.currentModelInfo.input_token_limit;
            const ratio = totalInput / limit;
            const ratioText = `<strong>${Math.round(ratio * 100)}%</strong>`;
            const fitHtml = ratio > 0.9 
                ? `<span class="red fw6">⚠️ Gần/vượt giới hạn!</span>`
                : ratio > 0.5 
                    ? `<span class="orange">⚡ ${ratioText} giới hạn</span>`
                    : `<span class="green">✅ OK (${ratioText} giới hạn)</span>`;
            fitEls.forEach(el => el.innerHTML = fitHtml);
        } else {
            fitEls.forEach(el => el.textContent = '');
        }

        if (charCount > 200000) {
            fitEls.forEach(el => el.innerHTML = '<span class="orange fw6">⚠️ Văn bản rất lớn (' + (charCount / 1000).toFixed(0) + 'k ký tự). Có thể chậm trên trình duyệt.</span>');
        }
    },

    toggleWordWrap(textareaId) {
        var ta = document.getElementById(textareaId);
        if (!ta) return;
        if (ta.style.whiteSpace === 'pre') {
            ta.style.whiteSpace = 'pre-wrap';
            ta.wrap = 'on';
        } else {
            ta.style.whiteSpace = 'pre';
            ta.wrap = 'off';
        }
    },

    openSearchReplaceModal(textareaId) {
        const el = document.querySelector('[x-data="searchReplace()"]');
        if (el && el._x_dataStack) {
            const component = Alpine.$data(el);
            if (component && component.open) {
                component.open(textareaId);
            }
        }
    },

    saveSourceFile() {
        if (!window.currentProject || !window.currentProjectFile) {
            UiHelpers.showToast('Không xác định dự án/file', 'error');
            return;
        }
        const slug = window.currentProject.slug;
        const filename = window.currentProjectFile.name;
        const content = document.getElementById('pm-source-text').value;
        
        fetch(`/api/projects/${slug}/file/sources/${filename}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                UiHelpers.showToast('Đã lưu file nguồn', 'success');
                DirtyState.clean('pm-source-text');
            } else {
                UiHelpers.showToast('Lỗi: ' + (res.error || 'Unknown'), 'error');
            }
        });
    },

    async findInText(textareaId) {
        var ta = document.getElementById(textareaId);
        if (!ta || !ta.value) return;
        var term = await showPrompt('Tìm kiếm trong văn bản:');
        if (!term) return;
        var idx = ta.value.toLowerCase().indexOf(term.toLowerCase());
        if (idx === -1) {
            UiHelpers.showToast('Không tìm thấy: ' + term, 'warning');
            return;
        }
        ta.focus();
        ta.setSelectionRange(idx, idx + term.length);
        var linesBefore = ta.value.substring(0, idx).split('\n').length;
        ta.scrollTop = Math.max(0, (linesBefore - 5) * 20);
        UiHelpers.showToast('Tìm thấy ở dòng ' + linesBefore, 'success');
    },

    showDiffView(sourceId, targetId) {
        var sourceText = document.getElementById(sourceId).value;
        var targetText = document.getElementById(targetId).value;

        if (!sourceText && !targetText) {
            UiHelpers.showToast('Cần nội dung để so sánh', 'warning');
            return;
        }

        var sourceLines = sourceText.split('\n');
        var targetLines = targetText.split('\n');
        var maxLines = Math.max(sourceLines.length, targetLines.length);

        // Unified diff view
        var unifiedHtml = '<div style="font-family:monospace;font-size:13px;line-height:1.6;white-space:pre-wrap;word-break:break-all;">';
        var changes = 0;

        for (var i = 0; i < maxLines; i++) {
            var sl = i < sourceLines.length ? sourceLines[i] : '';
            var tl = i < targetLines.length ? targetLines[i] : '';

            if (sl === tl) {
                unifiedHtml += '<div style="padding:1px 8px;color:#6b7280;">  ' + escapeHtml(sl) + '</div>';
            } else {
                changes++;
                if (sl) unifiedHtml += '<div style="padding:1px 8px;background:#fee2e2;color:#991b1b;">- ' + escapeHtml(sl) + '</div>';
                if (tl) unifiedHtml += '<div style="padding:1px 8px;background:#d1fae5;color:#065f46;">+ ' + escapeHtml(tl) + '</div>';
            }
        }
        unifiedHtml += '</div>';

        // Side-by-side diff view
        var sideHtml = '<div style="display:flex;gap:0;font-family:monospace;font-size:13px;line-height:1.6;">';
        sideHtml += '<div style="flex:1;border-right:1px solid #e0e0e0;overflow:auto;white-space:pre-wrap;word-break:break-all;">';
        sideHtml += '<div style="padding:4px 8px;background:#fee2e2;font-weight:600;color:#991b1b;border-bottom:1px solid #e0e0e0;">Bản gốc</div>';
        for (var i = 0; i < sourceLines.length; i++) {
            var sl = sourceLines[i];
            var tl = i < targetLines.length ? targetLines[i] : '';
            var bg = sl === tl ? 'transparent' : '#fee2e2';
            sideHtml += '<div style="padding:1px 8px;background:' + bg + ';">' + escapeHtml(sl) + '</div>';
        }
        sideHtml += '</div>';
        sideHtml += '<div style="flex:1;overflow:auto;white-space:pre-wrap;word-break:break-all;">';
        sideHtml += '<div style="padding:4px 8px;background:#d1fae5;font-weight:600;color:#065f46;border-bottom:1px solid #e0e0e0;">Bản dịch</div>';
        for (var i = 0; i < maxLines; i++) {
            var sl = i < sourceLines.length ? sourceLines[i] : '';
            var tl = targetLines[i];
            var bg = sl === tl ? 'transparent' : '#d1fae5';
            sideHtml += '<div style="padding:1px 8px;background:' + bg + ';">' + escapeHtml(tl) + '</div>';
        }
        sideHtml += '</div></div>';

        var overlay = this._createOverlay({
            title: '📊 So sánh thay đổi (' + changes + ' dòng khác)',
            subtitle: 'So sánh dòng thay đổi giữa hai editor',
            bodyHtml:
                '<div id="diff-view-unified" class="pa3" style="background:#fafafa;">' + unifiedHtml + '</div>' +
                '<div id="diff-view-side" class="pa3" style="background:#fafafa;display:none;">' + sideHtml + '</div>',
            wide: false
        });

        // Add tab switching buttons to header
        var headerDiv = overlay.querySelector('.flex.justify-between');
        var btnGroup = document.createElement('div');
        btnGroup.className = 'flex gap-2';
        btnGroup.innerHTML =
            '<button id="btn-diff-unified" class="ph2 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white" onclick="EditorComponent.switchDiffView(\'unified\')">Dọc</button>' +
            '<button id="btn-diff-side" class="ph2 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white" onclick="EditorComponent.switchDiffView(\'side\')">Ngang</button>';
        headerDiv.querySelector('button.modal-close-btn').before(btnGroup);
    },

    switchDiffView(mode) {
        var unifiedEl = document.getElementById('diff-view-unified');
        var sideEl = document.getElementById('diff-view-side');
        var btnUnified = document.getElementById('btn-diff-unified');
        var btnSide = document.getElementById('btn-diff-side');
        
        if (mode === 'unified') {
            if (unifiedEl) unifiedEl.style.display = '';
            if (sideEl) sideEl.style.display = 'none';
            if (btnUnified) btnUnified.classList.add('active');
            if (btnSide) btnSide.classList.remove('active');
        } else {
            if (unifiedEl) unifiedEl.style.display = 'none';
            if (sideEl) sideEl.style.display = '';
            if (btnUnified) btnUnified.classList.remove('active');
            if (btnSide) btnSide.classList.add('active');
        }
    },

    copyResult() {
        navigator.clipboard.writeText(document.getElementById('pm-result-text').value)
            .then(() => UiHelpers.showToast('Đã sao chép vào Clipboard!', 'success'))
            .catch(() => UiHelpers.showToast('Copy thất bại', 'error'));
    },

    downloadResult() {
        const text = document.getElementById('pm-result-text').value;
        if (!text) { UiHelpers.showToast('Chưa có nội dung để tải!', 'error'); return; }
        const fname = window.currentProjectFile ? window.currentProjectFile.name : 'translated.txt';
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
        a.download = fname;
        a.click();
        URL.revokeObjectURL(a.href);
    },

    copySpellcheckResult() {
        navigator.clipboard.writeText(document.getElementById('pm-spell-result-text').value)
            .then(() => UiHelpers.showToast('Đã sao chép vào Clipboard!', 'success'))
            .catch(() => UiHelpers.showToast('Copy thất bại', 'error'));
    },

    downloadSpellCheckResult() {
        if (!window.currentProject || !window.currentProjectFile) { UiHelpers.showToast('Chưa chọn file!', 'error'); return; }
        window.location.href = `/api/projects/${window.currentProject.slug}/file/spelling/${window.currentProjectFile.name}`;
    },

    saveChunkTranslation() {
        if (!window.currentProject || !window.currentProjectFile) {
            UiHelpers.showToast('Không xác định được dự án hoặc file nguồn đang thao tác.', 'error');
            return;
        }

        const slug = window.currentProject.slug;
        const filename = window.currentProjectFile.name;
        const content = document.getElementById('pm-result-text').value;

        if (!content.trim()) {
            UiHelpers.showToast('Nội dung dịch trống, không thể lưu.', 'warning');
            return;
        }

        const btn = document.getElementById('btn-save-translation');
        const originalText = btn.innerHTML;
        btn.innerHTML = '⏳ Đang lưu...';
        btn.disabled = true;

        fetch(`/api/projects/${slug}/file/translated/${filename}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        })
            .then(r => r.json())
            .then(res => {
                btn.innerHTML = originalText;
                btn.disabled = false;
                if (res.success) {
                    UiHelpers.showToast(`Đã lưu bản dịch cho file: ${filename}`, 'success');
                    DirtyState.clean('pm-result-text');
                } else {
                    UiHelpers.showToast('Lỗi lưu file: ' + (res.error || 'Unknown'), 'error');
                }
            })
            .catch(e => {
                btn.innerHTML = originalText;
                btn.disabled = false;
                UiHelpers.showToast('Lỗi mạng: ' + e.message, 'error');
            });
    },

    saveSpellcheckResult() {
        if (!window.currentProject || !window.currentProjectFile) {
            UiHelpers.showToast('Không xác định được dự án hoặc file.', 'error');
            return;
        }
        const slug = window.currentProject.slug;
        const filename = window.currentProjectFile.name;
        const content = document.getElementById('spell-result-text').value;
        if (!content.trim()) {
            UiHelpers.showToast('Nội dung trống.', 'warning');
            return;
        }
        const btn = document.getElementById('btn-save-spellcheck');
        const originalText = btn.innerHTML;
        btn.innerHTML = '⏳...';
        btn.disabled = true;
        fetch(`/api/projects/${slug}/file/spelling/${filename}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        }).then(r => r.json()).then(res => {
            btn.innerHTML = originalText;
            btn.disabled = false;
            if (res.success) {
                UiHelpers.showToast('Đã lưu.', 'success');
                DirtyState.clean('spell-result-text');
            } else {
                UiHelpers.showToast('Lỗi: ' + (res.error || 'Unknown'), 'error');
            }
        }).catch(e => {
            btn.innerHTML = originalText;
            btn.disabled = false;
            UiHelpers.showToast('Lỗi: ' + e.message, 'error');
        });
    },

    // Private helper for creating overlay (used by showDiffView and openPreview)
    _createOverlay({ title, subtitle, bodyHtml, wide }) {
        var overlay = document.createElement('div');
        overlay.className = 'fixed absolute--fill bg-black-70 items-center justify-center z-max';
        overlay.style.cssText = 'display:flex; z-index:99999;';
        var widthClass = wide ? 'mw9' : 'mw8';
        var subtitleHtml = subtitle
            ? '<div class="f7 silver mt1">' + subtitle + '</div>'
            : '';
        overlay.innerHTML =
            '<div class="bg-white br3 shadow-5 w-100 ' + widthClass + ' overflow-hidden animate-pop" style="max-height:85vh;">' +
                '<div class="pa3 bb b--black-10 bg-near-white flex justify-between items-center">' +
                    '<div>' +
                        '<h3 class="f5 ma0 fw6 dark-gray">' + title + '</h3>' +
                        subtitleHtml +
                    '</div>' +
                    '<button class="modal-close-btn" onclick="this.closest(\'.fixed\').remove()">&times;</button>' +
                '</div>' +
                '<div class="overflow-y-auto" style="max-height:75vh;">' + bodyHtml + '</div>' +
            '</div>';
        document.body.appendChild(overlay);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) overlay.remove();
        });
        document.addEventListener('keydown', function onEsc(e) {
            if (e.key === 'Escape') {
                overlay.remove();
                document.removeEventListener('keydown', onEsc);
            }
        });
        return overlay;
    },

    openPreview(textareaId, options) {
        var content = document.getElementById(textareaId).value;
        if (!content.trim()) {
            UiHelpers.showToast('Editor không có nội dung để preview', 'warning');
            return;
        }
        var label = options.label || 'Preview';
        var filename = window.currentProjectFile ? window.currentProjectFile.name : '';
        // Detect format
        var format = 'markdown';
        if (filename) {
            var ext = filename.split('.').pop().toLowerCase();
            if (ext === 'md' || ext === 'markdown') format = 'markdown';
            else if (ext === 'html' || ext === 'htm' || ext === 'xhtml') format = 'html';
        } else {
            // Fallback: heuristic theo nội dung
            if (/<!DOCTYPE html>|<html[\s>]|<body[\s>]/.test(content) ||
                ((content.match(/<(div|p|h[1-6]|section|article|table|ul|ol)[>\s]/gi) || []).length >= 3)) {
                format = 'html';
            }
        }
        // Build subtitle
        var subtitle = (filename ? filename + ' • ' : '') + (format === 'html' ? 'HTML' : 'Markdown');
        // Build bodyHtml
        var bodyHtml;
        if (format === 'markdown') {
            bodyHtml = '<div class="doc-markdown pa3" style="max-width: none;">' + marked.parse(content) + '</div>';
        } else {
            bodyHtml = '<iframe sandbox="" srcdoc="" style="width:100%;height:70vh;border:none;display:block;"></iframe>';
        }
        var overlay = this._createOverlay({
            title: 'Preview — ' + label,
            subtitle: subtitle,
            bodyHtml: bodyHtml,
            wide: false
        });
        // Gán srcdoc sau khi overlay đã vào DOM (tránh timing issue)
        if (format === 'html') {
            var iframe = document.querySelector('.fixed iframe[sandbox]');
            if (iframe) iframe.srcdoc = content;
        }
    },

    setupSyncScroll(sourceEl, resultEl) {
        let isSyncing = false;
        
        sourceEl.addEventListener('scroll', () => {
            if (isSyncing || !EditorComponent.syncScrollEnabled) return;
            if (document.activeElement !== sourceEl) return;
            isSyncing = true;
            const ratio = sourceEl.scrollTop / (sourceEl.scrollHeight - sourceEl.clientHeight || 1);
            resultEl.scrollTop = ratio * (resultEl.scrollHeight - resultEl.clientHeight);
            setTimeout(() => isSyncing = false, 50);
        });
        
        resultEl.addEventListener('scroll', () => {
            if (isSyncing || !EditorComponent.syncScrollEnabled) return;
            if (document.activeElement !== resultEl) return;
            isSyncing = true;
            const ratio = resultEl.scrollTop / (resultEl.scrollHeight - resultEl.clientHeight || 1);
            sourceEl.scrollTop = ratio * (sourceEl.scrollHeight - sourceEl.clientHeight);
            setTimeout(() => isSyncing = false, 50);
        });
    }
};

window.EditorComponent = EditorComponent;
