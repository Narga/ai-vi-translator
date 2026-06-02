// ============================================================
// translation-worker.js — Translation, spellcheck, SSE, merge
// ============================================================

const TranslationWorker = {
    startTranslation() {
        const btn = document.getElementById('translate-btn');
        const text = document.getElementById('source-text').value;
        if (!text.trim()) { UiHelpers.showToast('Vui lòng nhập văn bản hoặc chọn file!', 'error'); return; }

        btn.disabled = true;
        btn.innerHTML = '🔄 <span class="nt-btn-spinner dib"></span> Đang dịch...';

        UiHelpers.addLog('Bắt đầu dịch nội dung...', 'info');

        if (window.currentProject && window.currentProjectFile) {
            fetch(`/api/projects/${window.currentProject.slug}/translate`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: [window.currentProjectFile.name] })
            }).then(r => r.json()).then(data => {
                if (data.error) { UiHelpers.addLog(data.error, 'error'); TranslationWorker.resetButton(btn); }
                else TranslationWorker.connectToProgress(btn);
            }).catch(e => { UiHelpers.addLog(e.message, 'error'); TranslationWorker.resetButton(btn); });
        } else {
            fetch('/api/translate', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text, model: document.getElementById('model').value,
                    temperature: parseFloat(document.getElementById('temperature').value),
                    chunk_size: parseInt(document.getElementById('chunk-size').value),
                    use_cache: document.getElementById('use-cache').checked,
                    prompts: window.prompts
                })
            }).then(r => r.json()).then(data => {
                if (data.error) { UiHelpers.addLog(data.error, 'error'); TranslationWorker.resetButton(btn); }
                else TranslationWorker.connectToProgress(btn);
            }).catch(e => { UiHelpers.addLog(e.message, 'error'); TranslationWorker.resetButton(btn); });
        }
    },

    translateFileInProject(filename) {
        if (!window.currentProject) return;
        fetch(`/api/projects/${window.currentProject.slug}/translate`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: [filename] })
        }).then(r => r.json()).then(data => {
            if (data.status === 'started') {
                TranslationWorker.connectToProgress();
            } else UiHelpers.showToast(data.error || 'Lỗi', 'error');
        });
    },

    translateSelectedInProject() {
        if (!window.currentProject || window.selectedFiles.size === 0) { UiHelpers.showToast('Chưa chọn file!', 'error'); return; }
        const files = Array.from(window.selectedFiles);
        fetch(`/api/projects/${window.currentProject.slug}/translate`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files })
        }).then(r => r.json()).then(data => {
            if (data.status === 'started') TranslationWorker.connectToProgress(document.getElementById('btn-translate-selected'), true);
            else UiHelpers.showToast(data.error || 'Lỗi', 'error');
        });
    },

    spellcheckSelectedInProject() {
        if (!window.currentProject || window.selectedFiles.size === 0) { UiHelpers.showToast('Chưa chọn file!', 'error'); return; }
        const files = Array.from(window.selectedFiles);
        fetch(`/api/projects/${window.currentProject.slug}/spellcheck`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files })
        }).then(r => r.json()).then(data => {
            if (data.status === 'started') TranslationWorker.connectToProgress(document.getElementById('btn-spellcheck-selected'), true);
            else UiHelpers.showToast(data.error || 'Lỗi', 'error');
        });
    },

    spellcheckFileInProject(filename) {
        if (!window.currentProject) return;
        fetch(`/api/projects/${window.currentProject.slug}/spellcheck`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: [filename] })
        }).then(r => r.json()).then(data => {
            if (data.status === 'started') {
                TranslationWorker.connectToProgress();
            } else UiHelpers.showToast(data.error || 'Lỗi', 'error');
        });
    },

    runSpellcheck() {
        if (!window.currentProject || !window.currentProjectFile) { UiHelpers.showToast('Chưa chọn file!', 'error'); return; }
        window.selectedFiles.clear();
        window.selectedFiles.add(window.currentProjectFile.name);
        TranslationWorker.spellcheckSelectedInProject();
    },

    connectToProgress(btn = null, isBatch = false) {
        const evtSource = new EventSource('/api/progress');
        
        const logEl = document.getElementById('log-container');
        if (logEl) logEl.innerHTML = '';
        
        UiHelpers.showProgressModal();

        const btnDone = document.getElementById('btn-progress-done');
        if (btnDone) btnDone.classList.add('dn');

        if (window._autoReturnTimer) {
            clearInterval(window._autoReturnTimer);
            window._autoReturnTimer = null;
        }

        evtSource.onmessage = function (event) {
            const data = JSON.parse(event.data);
            if (data.type === 'progress') {
                TranslationWorker.updateProgress(data.percent, data.message);
            }
            else if (data.type === 'info' || data.type === 'log') {
                UiHelpers.addLog(data.message, data.level || 'info');
            }
            else if (data.type === 'file_complete') {
                UiHelpers.addLog(data.message, 'success');
                if (window.currentProject) {
                    ProjectManager.selectProject(window.currentProject.slug, true);
                }
            }
            else if (data.type === 'complete') {
                evtSource.close();
                TranslationWorker.updateProgress(100, 'Tất cả hoàn tất! 🚀');

                if (data.translated_text) {
                    const resText = document.getElementById('result-text');
                    if (resText) resText.value = data.translated_text;
                } else if (data.output_file) {
                    window.currentOutputFile = data.output_file;
                    const resText = document.getElementById('result-text');
                    if (resText) resText.value = "Đã dịch xong. Kết quả được lưu tại:\n👉 " + data.output_file;
                }

                TranslationWorker.resetButton(btn, isBatch);
                
                if (btnDone) {
                    btnDone.classList.remove('dn');
                    btnDone.textContent = '✓ Hoàn thành';
                }
                if (window._autoReturnTimer) {
                    clearInterval(window._autoReturnTimer);
                    window._autoReturnTimer = null;
                }
                
                if (window.currentProject) {
                    ProjectManager.selectProject(window.currentProject.slug, isBatch);
                }
                ApiClient.loadStats();
            }
            else if (data.type === 'error') {
                evtSource.close();
                UiHelpers.addLog(data.message, 'error');
                TranslationWorker.resetButton(btn, isBatch);
            }
        };
        evtSource.onerror = function () { evtSource.close(); };
    },

    updateProgress(percent, text) {
        const bar = document.getElementById('progress-bar');
        if (bar) bar.style.width = percent + '%';
        const num = document.getElementById('progress-percent');
        if (num) num.textContent = percent + '%';
        const txt = document.getElementById('progress-text');
        if (txt) txt.textContent = text;
    },

    closeProgress() {
        if (window.selectedFiles) {
            window.selectedFiles.clear();
            ProjectManager.updateSelectAllButton();
        }

        if (window.currentProject) {
            ProjectManager.selectProject(window.currentProject.slug, true);
        }

        if (window._autoReturnTimer) {
            clearInterval(window._autoReturnTimer);
            window._autoReturnTimer = null;
        }

        ModalManager.hide('translation-progress-modal');
    },

    resetButton(btn, isBatch = false) {
        if (btn) {
            btn.disabled = false;
            if (btn.id === 'btn-translate-selected') {
                btn.innerHTML = `🚀 Dịch đã chọn`;
            } else if (btn.id === 'btn-spellcheck-selected') {
                btn.innerHTML = `🔤 Soát được chọn`;
            } else {
                btn.innerHTML = '🚀 Dịch Nội Dung';
            }
        } else if (isBatch) {
            const batchBtn = document.getElementById('btn-translate-selected');
            if (batchBtn) {
                batchBtn.disabled = false;
                batchBtn.innerHTML = `🚀 Dịch đã chọn`;
            }
        } else {
            const singleBtn = document.getElementById('translate-btn');
            if (singleBtn) {
                singleBtn.disabled = false;
                singleBtn.innerHTML = '🚀 Dịch Nội Dung';
            }
        }
    }
};

window.TranslationWorker = TranslationWorker;
