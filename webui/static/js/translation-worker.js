// ============================================================
// translation-worker.js — Translation, spellcheck, SSE, merge
// ============================================================

const TranslationWorker = {
    _evtSource: null,

    stopTranslation() {
        fetch('/api/translate/cancel', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                UiHelpers.addLog('Đã gửi yêu cầu dừng...', 'info');
            })
            .catch(e => UiHelpers.addLog('Lỗi gửi yêu cầu dừng: ' + e.message, 'error'));
    },

    startTranslation() {
        const btn = document.getElementById('translate-btn');
        const text = document.getElementById('source-text').value;
        if (!text.trim()) { UiHelpers.showToast('Vui lòng nhập văn bản hoặc chọn file!', 'error'); return; }

        btn.disabled = true;
        btn.innerHTML = '🔄 <span class="nt-btn-spinner dib"></span> Đang dịch...';

        // Double-click guard: re-enable sau 3s nếu không có response
        const guardTimer = setTimeout(() => {
            if (btn.disabled && btn.innerHTML.includes('Đang dịch')) {
                TranslationWorker.resetButton(btn);
            }
        }, 3000);

        UiHelpers.addLog('Bắt đầu dịch nội dung...', 'info');

        if (window.currentProject && window.currentProjectFile) {
            const forceRetranslateEl = document.getElementById('force-retranslate');
            const forceRetranslate = forceRetranslateEl ? forceRetranslateEl.checked : false;
            fetch(`/api/projects/${window.currentProject.slug}/translate`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: [window.currentProjectFile.name], force_retranslate: forceRetranslate })
            }).then(r => r.json()).then(data => {
                clearTimeout(guardTimer);
                if (data.error) { UiHelpers.addLog(data.error, 'error'); TranslationWorker.resetButton(btn); }
                else TranslationWorker.connectToProgress(btn);
            }).catch(e => { clearTimeout(guardTimer); UiHelpers.addLog(e.message, 'error'); TranslationWorker.resetButton(btn); });
        } else {
            fetch('/api/translate', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text, model: document.getElementById('model').value,
                    temperature: parseFloat(document.getElementById('temperature').value),
                    chunk_size: parseInt(document.getElementById('chunk-size').value),
                    prompts: window.prompts
                })
            }).then(r => r.json()).then(data => {
                clearTimeout(guardTimer);
                if (data.error) { UiHelpers.addLog(data.error, 'error'); TranslationWorker.resetButton(btn); }
                else TranslationWorker.connectToProgress(btn);
            }).catch(e => { clearTimeout(guardTimer); UiHelpers.addLog(e.message, 'error'); TranslationWorker.resetButton(btn); });
        }
    },

    translateFileInProject(filename) {
        if (!window.currentProject) return;
        const forceRetranslateEl = document.getElementById('force-retranslate');
        const forceRetranslate = forceRetranslateEl ? forceRetranslateEl.checked : false;
        fetch(`/api/projects/${window.currentProject.slug}/translate`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: [filename], force_retranslate: forceRetranslate })
        }).then(r => r.json()).then(data => {
            if (data.status === 'started') {
                TranslationWorker.connectToProgress();
            } else UiHelpers.showToast(data.error || 'Lỗi', 'error');
        });
    },

    translateSelectedInProject() {
        if (!window.currentProject || window.selectedFiles.size === 0) { UiHelpers.showToast('Chưa chọn file!', 'error'); return; }
        const files = Array.from(window.selectedFiles);
        const forceRetranslateEl = document.getElementById('force-retranslate');
        const forceRetranslate = forceRetranslateEl ? forceRetranslateEl.checked : false;
        fetch(`/api/projects/${window.currentProject.slug}/translate`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files, force_retranslate: forceRetranslate })
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
        TranslationWorker._evtSource = evtSource;
        
        const logEl = document.getElementById('log-container');
        if (logEl) logEl.innerHTML = '';
        
        UiHelpers.showProgressModal();

        const btnDone = document.getElementById('btn-progress-done');
        if (btnDone) btnDone.classList.add('dn');
        const btnStop = document.getElementById('btn-progress-stop');
        if (btnStop) btnStop.classList.remove('dn');

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
                    ProjectManager.openProject(window.currentProject.slug);
                }
            }
            else if (data.type === 'complete') {
                evtSource.close();
                TranslationWorker._evtSource = null;
                TranslationWorker.updateProgress(100, 'Tất cả hoàn tất! 🚀');
                if (btnStop) btnStop.classList.add('dn');

                if (data.translated_text) {
                    const resText = document.getElementById('result-text');
                    if (resText) resText.value = data.translated_text;
                } else if (data.output_file) {
                    window.currentOutputFile = data.output_file;
                    const resText = document.getElementById('result-text');
                    if (resText) resText.value = "Đã dịch xong. Kết quả được lưu tại:\n👉 " + data.output_file;
                }

                TranslationWorker.resetButton(btn, isBatch);
                
                // Hiện nút Hoàn thành
                if (btnDone) {
                    btnDone.classList.remove('dn');
                    btnDone.textContent = '✓ Xong';
                    btnDone.onclick = function() {
                        TranslationWorker.closeProgress();
                    };
                }
                
                if (window.currentProject) {
                    ProjectManager.openProject(window.currentProject.slug);
                }
                ApiClient.loadStats();
                
                // Tự động đóng modal sau 5 giây
                window._autoCloseTimer = setTimeout(() => {
                    TranslationWorker.closeProgress();
                }, 5000);
            }
            else if (data.type === 'error') {
                evtSource.close();
                TranslationWorker._evtSource = null;
                UiHelpers.addLog(data.message, 'error');
                TranslationWorker.resetButton(btn, isBatch);
                TranslationWorker.updateProgress(0, 'Lỗi: ' + data.message);
                if (btnStop) btnStop.classList.add('dn');
            }
            else if (data.type === 'cancelled') {
                evtSource.close();
                TranslationWorker._evtSource = null;
                UiHelpers.addLog(data.message || 'Đã dừng theo yêu cầu', 'info');
                TranslationWorker.resetButton(btn, isBatch);
                TranslationWorker.updateProgress(0, 'Đã dừng');
                if (btnStop) btnStop.classList.add('dn');
                if (btnDone) {
                    btnDone.classList.remove('dn');
                    btnDone.textContent = '✓ Đóng';
                }
            }
        };

        evtSource.onerror = function () {
            evtSource.close();
            TranslationWorker._evtSource = null;
            TranslationWorker.resetButton(btn, isBatch);
            if (btnStop) btnStop.classList.add('dn');
        };
    },

    updateProgress(percent, message) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        if (progressBar) {
            progressBar.style.width = percent + '%';
            progressBar.setAttribute('aria-valuenow', percent);
        }
        if (progressText) progressText.textContent = message || '';
    },

    resetButton(btn, isBatch = false) {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = isBatch ? 'Dịch đã chọn' : 'Dịch';
        }
    },

    closeProgress() {
        ModalManager.hide('translation-progress-modal');
        if (window._autoCloseTimer) {
            clearTimeout(window._autoCloseTimer);
            window._autoCloseTimer = null;
        }
        if (window._autoReturnTimer) {
            clearInterval(window._autoReturnTimer);
            window._autoReturnTimer = null;
        }
    }
};

window.TranslationWorker = TranslationWorker;
