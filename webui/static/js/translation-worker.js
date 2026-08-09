// ============================================================
// translation-worker.js — Translation, spellcheck, SSE, merge
// ============================================================

const TranslationWorker = {
    _evtSource: null,
    _activeJobId: null,
    _lastViewedJobId: null,
    _taskStateByJob: new Map(),

    stopTranslation() {
        fetch('/api/translate/cancel', { method: 'POST' })
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(data => {
                UiHelpers.addLog('Đã gửi yêu cầu dừng...', 'info');
            })
            .catch(e => UiHelpers.addLog('Lỗi gửi yêu cầu dừng: ' + e.message, 'error'));
    },

    startTranslation() {
        if (window.currentProject && window.currentProjectFile) {
            // --- Project context ---
            const btn = document.querySelector('#pm-translation-bottom-bar button.bg-blue');

            if (btn) {
                btn.dataset.originalHtml = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '🔄 <span class="nt-btn-spinner dib"></span> Đang dịch...';
            }

            const guardTimer = setTimeout(() => { TranslationWorker.resetButton(btn); }, 3000);

            UiHelpers.addLog('Bắt đầu dịch nội dung...', 'info');
            const forceRetranslateEl = document.getElementById('force-retranslate');
            const forceRetranslate = forceRetranslateEl ? forceRetranslateEl.checked : false;
            fetch(`/api/projects/${window.currentProject.slug}/translate`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: [window.currentProjectFile.name], force_retranslate: forceRetranslate })
            }).then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            }).then(data => {
                clearTimeout(guardTimer);
                if (data.error) { UiHelpers.addLog(data.error, 'error'); TranslationWorker.resetButton(btn); }
                else {
                    ApiClient.loadTasks();
                    TranslationWorker.connectToProgress(btn, false, data.job_id, data.files_count || 1);
                }
            }).catch(e => { clearTimeout(guardTimer); UiHelpers.addLog(e.message, 'error'); TranslationWorker.resetButton(btn); });
        } else {
            // --- Standalone context ---
            const btn = document.getElementById('translate-btn');
            const sourceEl = document.getElementById('source-text');
            const text = sourceEl ? sourceEl.value : '';
            if (!text.trim()) { UiHelpers.showToast('Vui lòng nhập văn bản hoặc chọn file!', 'error'); return; }

            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '🔄 <span class="nt-btn-spinner dib"></span> Đang dịch...';
            }

            const guardTimer = setTimeout(() => {
                if (btn && btn.disabled && btn.innerHTML.includes('Đang dịch')) {
                    TranslationWorker.resetButton(btn);
                }
            }, 3000);

            UiHelpers.addLog('Bắt đầu dịch nội dung...', 'info');
            fetch('/api/translate', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text, model: document.getElementById('model').value,
                    temperature: parseFloat(document.getElementById('temperature').value),
                    chunk_size: parseInt(document.getElementById('chunk-size').value),
                    prompts: window.prompts
                })
            }).then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            }).then(data => {
                clearTimeout(guardTimer);
                if (data.error) { UiHelpers.addLog(data.error, 'error'); TranslationWorker.resetButton(btn); }
                else {
                    ApiClient.loadTasks();
                    TranslationWorker.connectToProgress(btn);
                }
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
        }).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
        }).then(data => {
            if (data.status === 'started') {
                ApiClient.loadTasks();
                TranslationWorker.connectToProgress(null, false, data.job_id, data.files_count || 1);
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
        }).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
        }).then(data => {
            if (data.status === 'started') {
                ApiClient.loadTasks();
                TranslationWorker.connectToProgress(document.getElementById('pm-btn-translate-selected'), true, data.job_id, data.files_count || files.length);
            } else UiHelpers.showToast(data.error || 'Lỗi', 'error');
        });
    },

    spellcheckSelectedInProject() {
        if (!window.currentProject || window.selectedFiles.size === 0) { UiHelpers.showToast('Chưa chọn file!', 'error'); return; }
        const files = Array.from(window.selectedFiles);
        // Xác định folder_type dựa vào mini-tab đang active
        const activeTab = document.querySelector('.sidebar-mini-tab.active');
        const folder_type = activeTab && activeTab.id === 'pm-tab-translated' ? 'translated' : 'sources';
        fetch(`/api/projects/${window.currentProject.slug}/spellcheck`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files, folder_type })
        }).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
        }).then(data => {
            if (data.status === 'started') {
                ApiClient.loadTasks();
                TranslationWorker.connectToProgress(document.getElementById('pm-btn-spellcheck-selected'), true, data.job_id, data.files_count || files.length);
            } else UiHelpers.showToast(data.error || 'Lỗi', 'error');
        });
    },

    spellcheckFileInProject(filename, folder_type = 'sources') {
        if (!window.currentProject) return;
        fetch(`/api/projects/${window.currentProject.slug}/spellcheck`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: [filename], folder_type })
        }).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
        }).then(data => {
            if (data.status === 'started') {
                ApiClient.loadTasks();
                TranslationWorker.connectToProgress(null, false, data.job_id, data.files_count || 1);
            } else UiHelpers.showToast(data.error || 'Lỗi', 'error');
        });
    },

    runSpellcheck() {
        if (!window.currentProject || !window.currentProjectFile) { UiHelpers.showToast('Chưa chọn file!', 'error'); return; }
        window.selectedFiles.clear();
        window.selectedFiles.add(window.currentProjectFile.name);
        TranslationWorker.spellcheckSelectedInProject();
    },

    retranslateActiveFile() {
        if (!window.currentProject || !window.currentProjectFile) {
            UiHelpers.showToast('Chưa chọn file để dịch!', 'error');
            return;
        }
        const filename = window.currentProjectFile.name;
        const btn = document.getElementById('btn-retranslate-file');
        if (btn) { btn.disabled = true; btn.classList.add('spinning'); }
        UiHelpers.addLog(`Bắt đầu dịch lại từ đầu chương: ${filename}...`, 'info');
        fetch(`/api/projects/${window.currentProject.slug}/translate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: [filename], force_retranslate: true })
        }).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
        }).then(data => {
            if (btn) { btn.disabled = false; btn.classList.remove('spinning'); }
            if (data.error) {
                UiHelpers.addLog(data.error, 'error');
            } else {
                ApiClient.loadTasks();
                TranslationWorker.connectToProgress(btn, false, data.job_id, 1);
            }
        }).catch(e => {
            if (btn) { btn.disabled = false; btn.classList.remove('spinning'); }
            UiHelpers.addLog(e.message, 'error');
        });
    },

    connectToProgress(btn = null, isBatch = false, job_id = null, totalFiles = 0, onComplete = null) {
        if (job_id && TranslationWorker._evtSource && TranslationWorker._activeJobId === job_id) {
            const existingState = TranslationWorker._taskStateByJob.get(job_id);
            if (existingState) {
                UiHelpers.renderProgressModal(existingState);
                UiHelpers.showProgressModal();
                return;
            }
        }

        const url = job_id ? `/api/tasks/${job_id}/events` : '/api/progress';
        const evtSource = new EventSource(url);
        TranslationWorker._evtSource = evtSource;

        const logEl = document.getElementById('log-container');
        if (logEl) logEl.innerHTML = '';

        const taskState = TranslationWorker._taskStateByJob.get(job_id) || {
            jobId: job_id,
            status: 'started',
            percent: 0,
            message: 'Đang chuẩn bị...',
            logs: [],
            completedFiles: 0,
            totalFiles: totalFiles || 0
        };
        taskState.status = 'started';
        if (totalFiles > 0) taskState.totalFiles = totalFiles;
        TranslationWorker._taskStateByJob.set(job_id, taskState);
        TranslationWorker._activeJobId = job_id;
        TranslationWorker._lastViewedJobId = job_id;

        UiHelpers.resetProgressModal();
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
            if (data.type === 'stream_end') {
                evtSource.close();
                TranslationWorker._evtSource = null;
                return;
            }
            if (data.type === 'progress') {
                taskState.percent = data.percent;
                taskState.message = data.message;
                TranslationWorker.updateProgress(data.percent, data.message);
                if (ModalManager.isOpen('translation-progress-modal')) {
                    UiHelpers.renderProgressModal(taskState);
                }
            }
            else if (data.type === 'info' || data.type === 'log') {
                const logEntry = { time: new Date().toLocaleTimeString(), message: data.message, type: data.level || 'info' };
                taskState.logs.push(logEntry);
                if (taskState.logs.length > 500) taskState.logs.shift();
                UiHelpers.addLog(data.message, data.level || 'info');
                if (ModalManager.isOpen('translation-progress-modal')) {
                    UiHelpers.renderProgressModal(taskState);
                }
            }
            else if (data.type === 'file_complete') {
                taskState.completedFiles += 1;
                taskState.totalFiles = taskState.totalFiles || taskState.completedFiles;
                taskState.percent = taskState.totalFiles > 0
                    ? Math.round((taskState.completedFiles / taskState.totalFiles) * 100)
                    : taskState.percent;
                taskState.message = data.message || taskState.message;
                const logEntry = { time: new Date().toLocaleTimeString(), message: data.message, type: 'success' };
                taskState.logs.push(logEntry);
                UiHelpers.addLog(data.message, 'success');
                if (ModalManager.isOpen('translation-progress-modal')) {
                    UiHelpers.renderProgressModal(taskState);
                }
                if (window.currentProject) {
                    ProjectManager.openProject(window.currentProject.slug);
                }
            }
            else if (data.type === 'complete') {
                evtSource.close();
                TranslationWorker._evtSource = null;
                taskState.status = 'completed';
                taskState.percent = 100;
                taskState.message = 'Tất cả hoàn tất! 🚀';
                TranslationWorker._lastViewedJobId = job_id;
                TranslationWorker._activeJobId = null;
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
                ApiClient.loadTasks();

                if (onComplete) onComplete(data);

                window._autoCloseTimer = setTimeout(() => {
                    TranslationWorker.closeProgress();
                }, 5000);
            }
            else if (data.type === 'error') {
                evtSource.close();
                TranslationWorker._evtSource = null;
                taskState.status = 'failed';
                taskState.message = 'Lỗi: ' + data.message;
                TranslationWorker._lastViewedJobId = job_id;
                TranslationWorker._activeJobId = null;
                UiHelpers.addLog(data.message, 'error');
                TranslationWorker.resetButton(btn, isBatch);
                TranslationWorker.updateProgress(0, 'Lỗi: ' + data.message);
                if (btnStop) btnStop.classList.add('dn');
                ApiClient.loadTasks();
            }
            else if (data.type === 'cancelled') {
                evtSource.close();
                TranslationWorker._evtSource = null;
                taskState.status = 'cancelled';
                taskState.message = data.message || 'Đã dừng';
                TranslationWorker._lastViewedJobId = job_id;
                TranslationWorker._activeJobId = null;
                UiHelpers.addLog(data.message || 'Đã dừng theo yêu cầu', 'info');
                TranslationWorker.resetButton(btn, isBatch);
                TranslationWorker.updateProgress(0, 'Đã dừng');
                if (btnStop) btnStop.classList.add('dn');
                if (btnDone) {
                    btnDone.classList.remove('dn');
                    btnDone.textContent = '✓ Đóng';
                }
                ApiClient.loadTasks();
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
            // Restore original button HTML with icon (don't replace with text-only)
            if (btn.dataset && btn.dataset.originalHtml) {
                btn.innerHTML = btn.dataset.originalHtml;
                delete btn.dataset.originalHtml;
            } else if (isBatch) {
                if (btn.id === 'pm-btn-translate-selected') {
                    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 8l6 6"/><path d="M4 14l6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="M22 22l-5-10-5 10"/><path d="M14 18h6"/></svg>';
                } else if (btn.id === 'pm-btn-spellcheck-selected') {
                    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 16 6-12 6 12"/><path d="M8 12h8"/><path d="m16 20 2 2 4-4"/></svg>';
                }
            } else if (btn.id === 'translate-btn') {
                btn.innerHTML = 'Dịch';
            }
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
    },

    openTaskProgress(jobId) {
        const state = TranslationWorker._taskStateByJob.get(jobId);
        if (state) {
            TranslationWorker._activeJobId = jobId;
            TranslationWorker._lastViewedJobId = jobId;
            UiHelpers.renderProgressModal(state);
            ModalManager.show('translation-progress-modal');
            return;
        }

        TranslationWorker.connectToProgress(null, false, jobId);
    },

    openLatestTaskProgress() {
        // First try active job
        if (TranslationWorker._activeJobId) {
            TranslationWorker.openTaskProgress(TranslationWorker._activeJobId);
            return;
        }
        // Fallback to last viewed
        if (TranslationWorker._lastViewedJobId) {
            TranslationWorker.openTaskProgress(TranslationWorker._lastViewedJobId);
            return;
        }
        // Last resort: fetch from API
        fetch('/api/tasks')
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(tasks => {
                if (tasks.length > 0) {
                    const active = tasks.find(t => t.status === 'started');
                    if (active) {
                        TranslationWorker.openTaskProgress(active.job_id);
                    }
                }
            })
            .catch(e => console.error('Failed to load tasks', e));
    }
};

window.TranslationWorker = TranslationWorker;
