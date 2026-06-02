// ============================================================
// editor-component.js — Editor, token estimation, diff view, file loading
// ============================================================

const EditorComponent = {
    syncScrollEnabled: true,

    async loadProjectFile(filename, section) {
        if (!window.currentProject) return;
        if (DirtyState.isDirty() && !await showConfirm('Bạn có thay đổi chưa lưu. Tiếp tục?')) {
            return;
        }
        DirtyState.clean('source-text');
        DirtyState.clean('result-text');
        DirtyState.clean('spell-source-text');
        DirtyState.clean('spell-result-text');
        const slug = window.currentProject.slug;
        
        if (section === 'sources') {
            fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(data => {
                document.getElementById('source-text').value = data.content || '';
                window.currentProjectFile = { name: filename, section };
                document.getElementById('token-estimate-mini').classList.remove('dn');
                EditorComponent.updateTokenEstimate();
                
                fetch(`/api/projects/${slug}/file/translated/${filename}`).then(r => r.json()).then(tData => {
                    document.getElementById('result-text').value = tData.content || '';
                    DirtyState.clean('result-text');
                }).catch(() => {
                    document.getElementById('result-text').value = '';
                    DirtyState.clean('result-text');
                });
            });
        } else if (section === 'translated') {
            fetch(`/api/projects/${slug}/file/translated/${filename}`).then(r => r.json()).then(data => {
                document.getElementById('result-text').value = data.content || '';
                window.currentProjectFile = { name: filename, section };
                DirtyState.clean('result-text');
                document.getElementById('token-estimate-mini').classList.remove('dn');
                
                fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(sData => {
                    document.getElementById('source-text').value = sData.content || '';
                    EditorComponent.updateTokenEstimate();
                }).catch(() => {
                    document.getElementById('source-text').value = '(Không tìm thấy bản gốc tương ứng)';
                });
            });
        }
    },

    loadSpellcheckFile(filename) {
        if (!window.currentProject) return;
        const slug = window.currentProject.slug;
        fetch(`/api/projects/${slug}/file/spelling/${filename}`).then(r => r.json()).then(data => {
            document.getElementById('spell-result-text').value = data.content || '';
            window.currentProjectFile = { name: filename, section: 'spelling' };
            DirtyState.clean('spell-result-text');
            const infoName = filename.replace(/\.(txt|md)$/, '') + '_info.txt';
            fetch(`/api/projects/${slug}/file/spelling/${infoName}`).then(r => r.json()).then(infoData => {
                const logEl = document.getElementById('spell-log-content');
                if (logEl) logEl.textContent = infoData.content || 'Không có dữ liệu soát lỗi.';
            }).catch(() => {
                const logEl = document.getElementById('spell-log-content');
                if (logEl) logEl.textContent = 'Không có dữ liệu soát lỗi.';
            });
        }).catch(() => {
            document.getElementById('spell-result-text').value = '';
            const logEl = document.getElementById('spell-log-content');
            if (logEl) logEl.textContent = 'Lỗi tải file.';
        });
        fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(sourceData => {
            document.getElementById('spell-source-text').value = sourceData.content || '';
            DirtyState.clean('spell-source-text');
        }).catch(() => {
            document.getElementById('spell-source-text').value = '';
        });
    },

    async loadPmProjectFile(filename, section) {
        if (!window.currentProject) return;
        if (DirtyState.isDirty() && !await showConfirm('Bạn có thay đổi chưa lưu. Tiếp tục?')) {
            return;
        }
        DirtyState.clean('pm-source-text');
        DirtyState.clean('pm-result-text');
        DirtyState.clean('pm-spell-source-text');
        DirtyState.clean('pm-spell-result-text');
        const slug = window.currentProject.slug;
        
        if (section === 'sources') {
            fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(data => {
                document.getElementById('pm-source-text').value = data.content || '';
                window.currentProjectFile = { name: filename, section };
                EditorComponent.updateTokenEstimate();
                
                fetch(`/api/projects/${slug}/file/translated/${filename}`).then(r => r.json()).then(tData => {
                    document.getElementById('pm-result-text').value = tData.content || '';
                    DirtyState.clean('pm-result-text');
                }).catch(() => {
                    document.getElementById('pm-result-text').value = '';
                    DirtyState.clean('pm-result-text');
                });
            });
        } else if (section === 'translated') {
            fetch(`/api/projects/${slug}/file/translated/${filename}`).then(r => r.json()).then(data => {
                document.getElementById('pm-result-text').value = data.content || '';
                window.currentProjectFile = { name: filename, section };
                DirtyState.clean('pm-result-text');
                
                fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(sData => {
                    document.getElementById('pm-source-text').value = sData.content || '';
                    EditorComponent.updateTokenEstimate();
                }).catch(() => {
                    document.getElementById('pm-source-text').value = '(Không tìm thấy bản gốc tương ứng)';
                });
            });
        }
    },

    loadPmSpellcheckFile(filename) {
        if (!window.currentProject) return;
        const slug = window.currentProject.slug;
        fetch(`/api/projects/${slug}/file/spelling/${filename}`).then(r => r.json()).then(data => {
            document.getElementById('pm-spell-result-text').value = data.content || '';
            window.currentProjectFile = { name: filename, section: 'spelling' };
            DirtyState.clean('pm-spell-result-text');
        }).catch(() => {
            document.getElementById('pm-spell-result-text').value = '';
        });
        fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(sourceData => {
            document.getElementById('pm-spell-source-text').value = sourceData.content || '';
            DirtyState.clean('pm-spell-source-text');
        }).catch(() => {
            document.getElementById('pm-spell-source-text').value = '';
        });
        // Load spell log
        const infoName = filename.replace(/\.(txt|md)$/, '') + '_info.txt';
        fetch(`/api/projects/${slug}/file/spelling/${infoName}`).then(r => r.json()).then(infoData => {
            const logEl = document.getElementById('pm-spell-log-content');
            if (logEl) logEl.textContent = infoData.content || 'Không có dữ liệu soát lỗi.';
        }).catch(() => {
            const logEl = document.getElementById('pm-spell-log-content');
            if (logEl) logEl.textContent = 'Không có dữ liệu soát lỗi.';
        });
    },

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

        var html = '<div style="font-family:monospace;font-size:13px;line-height:1.6;white-space:pre-wrap;word-break:break-all;">';
        var changes = 0;

        for (var i = 0; i < maxLines; i++) {
            var sl = i < sourceLines.length ? sourceLines[i] : '';
            var tl = i < targetLines.length ? targetLines[i] : '';

            if (sl === tl) {
                html += '<div style="padding:1px 8px;color:#6b7280;">  ' + escapeHtml(sl) + '</div>';
            } else {
                changes++;
                if (sl) html += '<div style="padding:1px 8px;background:#fee2e2;color:#991b1b;">- ' + escapeHtml(sl) + '</div>';
                if (tl) html += '<div style="padding:1px 8px;background:#d1fae5;color:#065f46;">+ ' + escapeHtml(tl) + '</div>';
            }
        }
        html += '</div>';

        var overlay = document.createElement('div');
        overlay.className = 'fixed absolute--fill bg-black-70 items-center justify-center z-max';
        overlay.style.cssText = 'display:flex; z-index:99999;';
        overlay.innerHTML = 
            '<div class="bg-white br3 shadow-5 w-100 mw8 overflow-hidden animate-pop" style="max-height:85vh;">' +
                '<div class="pa3 bb b--black-10 bg-near-white flex justify-between items-center">' +
                    '<h3 class="f5 ma0 fw6 dark-gray">📊 So sánh thay đổi (' + changes + ' dòng khác)</h3>' +
                    '<button class="modal-close-btn" onclick="this.closest(\'.fixed\').remove()">&times;</button>' +
                '</div>' +
                '<div class="pa3 overflow-y-auto" style="max-height:75vh;background:#fafafa;">' + html + '</div>' +
            '</div>';

        document.body.appendChild(overlay);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) overlay.remove();
        });
    },

    copyResult() {
        navigator.clipboard.writeText(document.getElementById('result-text').value)
            .then(() => UiHelpers.showToast('Đã sao chép vào Clipboard!', 'success'))
            .catch(() => UiHelpers.showToast('Copy thất bại', 'error'));
    },

    downloadResult() {
        if (window.currentOutputFile) window.open('/api/download/' + window.currentOutputFile, '_blank');
        else {
            const text = document.getElementById('result-text').value;
            if (!text) { UiHelpers.showToast('Chưa có nội dung để tải!', 'error'); return; }
            const fname = window.currentProjectFile ? window.currentProjectFile.name : 'translated.txt';
            const a = document.createElement('a');
            a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
            a.download = fname; a.click();
        }
    },

    copySpellcheckResult() {
        const el = document.getElementById('spell-result-text');
        el.select();
        document.execCommand('copy');
        UiHelpers.showToast('Đã sao chép.', 'success');
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
        const content = document.getElementById('result-text').value;

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
                    DirtyState.clean('result-text');
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
