// ============================================================
// translation-worker.js — Translation, spellcheck, SSE, merge
// ============================================================

const TranslationWorker = {
    _evtSource: null,
    _activeJobId: null,
    _lastViewedJobId: null,
    _taskStateByJob: new Map(),

    // Nhánh "Dịch lại từ đầu" của modal resume. Gửi trực tiếp force_retranslate:true.
    // KHÔNG dùng checkbox #force-retranslate / #pm-force-retranslate (không tồn tại trong DOM)
    // và KHÔNG .click() vào #btn-translate-single (không tồn tại) — xem B14.
    _forceTranslate(slug, files, btn = null, isBatch = false) {
        return ApiClient.translateFiles(slug, files, { force_retranslate: true })
            .then(data => {
                if (data.status === 'started') {
                    ApiClient.loadTasks();
                    TranslationWorker.connectToProgress(btn, isBatch, data.job_id, data.files_count || files.length);
                } else {
                    UiHelpers.showToast(data.error || 'Không thể dịch lại từ đầu', 'error');
                    TranslationWorker.resetButton(btn, isBatch);
                }
            })
            .catch(e => {
                UiHelpers.showToast('Lỗi dịch lại: ' + e.message, 'error');
                TranslationWorker.resetButton(btn, isBatch);
            });
    },

    stopTranslation(jobId = null) {
        // Ưu tiên: 1. Tham số tường minh -> 2. Job ID modal đang xem -> 3. _activeJobId toàn cục
        const targetJobId = jobId || TranslationWorker._lastViewedJobId || TranslationWorker._activeJobId;
        const endpoint = targetJobId ? `/api/tasks/${targetJobId}/cancel` : '/api/translate/cancel';
        fetch(endpoint, { method: 'POST' })
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(() => {
                UiHelpers.addLog('Đã gửi yêu cầu dừng tác vụ...', 'info');
                UiHelpers.showToast('Đã gửi yêu cầu dừng', 'info');
                ApiClient.loadTasks();
            })
            .catch(e => {
                UiHelpers.addLog('Lỗi gửi yêu cầu dừng: ' + e.message, 'error');
                UiHelpers.showToast('Lỗi dừng task: ' + e.message, 'error');
            });
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
            ApiClient.translateFiles(window.currentProject.slug, [window.currentProjectFile.name], {})
            .then(data => {
                clearTimeout(guardTimer);
                if (data.error) { UiHelpers.addLog(data.error, 'error'); TranslationWorker.resetButton(btn); }
                else if (data.status === 'resume_required') {
                    TranslationWorker.showResumeActionModal(data.checkpoints, (action) => {
                        if (action === 'continue') {
                            fetch(`/api/projects/${window.currentProject.slug}/translate/confirm-resume`, {
                                method: 'POST', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ files: [window.currentProjectFile.name] })
                            }).then(r => r.json()).then(resumeData => {
                                if (resumeData.status === 'started') {
                                    ApiClient.loadTasks();
                                    TranslationWorker.connectToProgress(btn, false, resumeData.job_id, resumeData.files_count || 1);
                                } else {
                                    UiHelpers.showToast(resumeData.error || 'Lỗi resume', 'error');
                                    TranslationWorker.resetButton(btn);
                                }
                            }).catch(e => { UiHelpers.showToast('Lỗi resume: ' + e.message, 'error'); TranslationWorker.resetButton(btn); });
                        } else if (action === 'restart') {
                            TranslationWorker._forceTranslate(window.currentProject.slug, [window.currentProjectFile.name], btn, false);
                        } else if (action === 'close_partial') {
                            TranslationWorker.handleClosePartialByCheckpoints(data.checkpoints, window.currentProject.slug);
                            TranslationWorker.resetButton(btn);
                        } else {
                            TranslationWorker.resetButton(btn);
                        }
                    });
                }
                else if (data.status === 'started') {
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
        ApiClient.translateFiles(window.currentProject.slug, [filename], {})
            .then(data => {
                if (data.status === 'started') {
                    ApiClient.loadTasks();
                    TranslationWorker.connectToProgress(null, false, data.job_id, data.files_count || 1);
                } else if (data.status === 'resume_required') {
                    TranslationWorker.showResumeActionModal(data.checkpoints, (action) => {
                        if (action === 'continue') {
                            fetch(`/api/projects/${window.currentProject.slug}/translate/confirm-resume`, {
                                method: 'POST', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ files: [filename] })
                            }).then(r => r.json()).then(resumeData => {
                                if (resumeData.status === 'started') {
                                    ApiClient.loadTasks();
                                    TranslationWorker.connectToProgress(null, false, resumeData.job_id, resumeData.files_count || 1);
                                } else UiHelpers.showToast(resumeData.error || 'Lỗi resume', 'error');
                            }).catch(e => UiHelpers.showToast('Lỗi resume: ' + e.message, 'error'));
                        } else if (action === 'restart') {
                            TranslationWorker._forceTranslate(window.currentProject.slug, [filename], null, false);
                        } else if (action === 'close_partial') {
                            TranslationWorker.handleClosePartialByCheckpoints(data.checkpoints, window.currentProject.slug);
                        }
                    });
                } else UiHelpers.showToast(data.error || 'Lỗi', 'error');
            })
            .catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
    },

    translateSelectedInProject() {
        if (!window.currentProject || window.selectedFiles.size === 0) { UiHelpers.showToast('Chưa chọn file!', 'error'); return; }
        const files = Array.from(window.selectedFiles);
        const selBtn = document.getElementById('pm-btn-translate-selected');
        ApiClient.translateFiles(window.currentProject.slug, files, {})
            .then(data => {
                if (data.status === 'started') {
                    ApiClient.loadTasks();
                    TranslationWorker.connectToProgress(selBtn, true, data.job_id, data.files_count || files.length);
                } else if (data.status === 'resume_required') {
                    TranslationWorker.showResumeActionModal(data.checkpoints, (action) => {
                        const names = Object.keys(data.checkpoints || {});
                        if (action === 'continue') {
                            fetch(`/api/projects/${window.currentProject.slug}/translate/confirm-resume`, {
                                method: 'POST', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ files: names })
                            }).then(r => r.json()).then(resumeData => {
                                if (resumeData.status === 'started') {
                                    ApiClient.loadTasks();
                                    TranslationWorker.connectToProgress(selBtn, true, resumeData.job_id, resumeData.files_count || names.length);
                                } else {
                                    UiHelpers.showToast(resumeData.error || 'Lỗi resume', 'error');
                                    TranslationWorker.resetButton(selBtn, true);
                                }
                            }).catch(e => { UiHelpers.showToast('Lỗi resume: ' + e.message, 'error'); TranslationWorker.resetButton(selBtn, true); });
                        } else if (action === 'restart') {
                            // Dịch lại từ đầu CHỈ những file có checkpoint (names), không phải
                            // toàn bộ `files` — các file khác đã được server nhận ở lần POST đầu.
                            TranslationWorker._forceTranslate(window.currentProject.slug, names, selBtn, true);
                        } else if (action === 'close_partial') {
                            TranslationWorker.handleClosePartialByCheckpoints(data.checkpoints, window.currentProject.slug);
                            TranslationWorker.resetButton(selBtn, true);
                        } else {
                            TranslationWorker.resetButton(selBtn, true);
                        }
                    });
                } else UiHelpers.showToast(data.error || 'Lỗi', 'error');
            })
            .catch(e => {
                UiHelpers.showToast('Lỗi: ' + e.message, 'error');
                TranslationWorker.resetButton(selBtn, true);
            });
    },

    showResumeActionModal(checkpoints, onAction) {
        const preview = document.getElementById('resume-action-files-preview');
        if (!preview) return;
        const names = Object.keys(checkpoints || {});

        preview.innerHTML = names.map(n => {
            const ck = checkpoints[n] || {};
            const projName = ck.project_name || ck.project_slug || '';
            const projBadge = projName ? `<span class="f8 bg-light-gray gray ph2 pv1 br2 mr2">📁 ${escapeHtml(projName)}</span>` : '';
            return `
            <div class="mb2 bb b--black-05 pb2 flex items-center justify-between">
                <div>
                    <div class="flex items-center gap-1 mb1">
                        ${projBadge}
                        <strong class="dark-gray">${escapeHtml(n)}</strong>
                    </div>
                    <div class="f7 gray">
                        Đã dịch: <span class="blue fw6">${ck.completed_chunks || 0}</span> / <span>${ck.total_chunks || '?'}</span> chunk
                    </div>
                </div>
                <span class="f8 pv1 ph2 br-pill bg-washed-blue blue fw6">Checkpoint sẵn sàng</span>
            </div>`;
        }).join('');

        const closePartialBtn = document.getElementById('btn-resume-action-close-partial');
        const continueBtn = document.getElementById('btn-resume-action-continue');
        const restartBtn = document.getElementById('btn-resume-action-restart');
        if (!closePartialBtn || !continueBtn || !restartBtn) return;

        const newClosePartial = closePartialBtn.cloneNode(true);
        const newContinue = continueBtn.cloneNode(true);
        const newRestart = restartBtn.cloneNode(true);

        closePartialBtn.parentNode.replaceChild(newClosePartial, closePartialBtn);
        continueBtn.parentNode.replaceChild(newContinue, continueBtn);
        restartBtn.parentNode.replaceChild(newRestart, restartBtn);

        let locked = false;
        const fire = (action) => {
            if (locked) return;
            locked = true;
            ModalManager.hide('resume-action-modal');
            onAction(action);
        };
        newClosePartial.addEventListener('click', () => fire('close_partial'));
        newContinue.addEventListener('click', () => fire('continue'));
        newRestart.addEventListener('click', () => fire('restart'));

        ModalManager.show('resume-action-modal');
    },

    async resolveTaskForFile(filename, checkpointKey) {
        try {
            const res = await fetch('/api/tasks');
            if (!res.ok) return null;
            const data = await res.json();
            const tasks = data.tasks || [];
            let task = tasks.find(t => t.filename === filename);
            if (task) return task;
            if (checkpointKey) {
                const norm = String(checkpointKey).replace(/\.db$/, '');
                task = tasks.find(t => (t.checkpoint_key || '').replace(/\.db$/, '') === norm);
                if (task) return task;
                const r = await fetch(`/api/tasks/by-checkpoint/${encodeURIComponent(checkpointKey)}`);
                if (r.ok) {
                    const body = await r.json();
                    if (body.task_id) {
                        return tasks.find(t => t.task_id === body.task_id) ||
                               { task_id: body.task_id, job_id: body.job_id, status: body.status };
                    }
                }
            }
            return null;
        } catch (e) {
            console.error('resolveTaskForFile failed', e);
            return null;
        }
    },

    async handleClosePartialByCheckpoints(checkpoints, projectSlug) {
        let successCount = 0;
        let failCount = 0;
        let pendingCount = 0;
        for (const [name, ck] of Object.entries(checkpoints)) {
            try {
                const task = await TranslationWorker.resolveTaskForFile(name, ck.checkpoint_key);
                if (!task || !task.task_id) { failCount++; continue; }
                const res = await fetch(`/api/tasks/${task.task_id}/close-as-partial`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ confirm: true, export_partial: true })
                });
                if (res.status === 202) { pendingCount++; continue; }
                if (res.ok) { successCount++; }
                else { failCount++; }
            } catch (e) {
                console.error(e);
                failCount++;
            }
        }
        let msg = `Đã chia tách ${successCount} file thành công.`;
        if (pendingCount > 0) msg += ` ${pendingCount} file đang chờ worker dừng.`;
        if (failCount > 0) msg += ` Lỗi: ${failCount} file.`;
        UiHelpers.showToast(msg, successCount > 0 ? 'success' : (pendingCount > 0 ? 'info' : 'error'));
        if (typeof ProjectManager !== 'undefined' && ProjectManager.loadFiles) {
            ProjectManager.loadFiles(projectSlug);
        }
        ApiClient.loadTasks();
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

        if (TranslationWorker._evtSource) {
            TranslationWorker._evtSource.close();
            TranslationWorker._evtSource = null;
        }

        const url = job_id ? `/api/tasks/${job_id}/events` : '/api/progress';
        const evtSource = new EventSource(url);
        TranslationWorker._evtSource = evtSource;

        const logEl = document.getElementById('log-container');
        if (logEl) logEl.innerHTML = '';

        const taskState = TranslationWorker._taskStateByJob.get(job_id) || {
            jobId: job_id,
            taskId: job_id,
            status: 'started',
            percent: 0,
            message: 'Đang chuẩn bị...',
            logs: [],
            completedFiles: 0,
            totalFiles: totalFiles || 0
        };
        taskState.status = 'started';
        taskState.taskId = taskState.taskId || job_id;
        TranslationWorker._updateResumeButton('started');
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
        const btnResume = document.getElementById('btn-progress-resume');
        if (btnResume) {
            btnResume.classList.add('dn');
            btnResume.disabled = false;
            btnResume.textContent = 'Tiếp tục';
        }
        const recoveryInfo = document.getElementById('recovery-info');
        if (recoveryInfo) recoveryInfo.classList.add('dn');

        if (window._autoReturnTimer) {
            clearInterval(window._autoReturnTimer);
            window._autoReturnTimer = null;
        }

        if (window._liveProgressTimer) {
            clearInterval(window._liveProgressTimer);
            window._liveProgressTimer = null;
        }
        window._liveProgressTimer = setInterval(() => {
            if (ModalManager.isOpen('translation-progress-modal') && taskState.status === 'running') {
                UiHelpers.renderProgressModal(taskState);
            } else if (!ModalManager.isOpen('translation-progress-modal')) {
                clearInterval(window._liveProgressTimer);
                window._liveProgressTimer = null;
            }
        }, 1000);

        evtSource.onmessage = function (event) {
            const data = JSON.parse(event.data);
            if (data.type === 'stream_end') {
                evtSource.close();
                TranslationWorker._evtSource = null;
                // Nếu bị end stream đột ngột (task đã resumable/interrupted từ trước)
                fetch(`/api/tasks/${job_id}`)
                    .then(r => r.ok ? r.json() : null)
                    .then(snapshot => {
                        if (snapshot) {
                            taskState.status = snapshot.status;
                            taskState.taskId = snapshot.task_id || taskState.taskId;
                            taskState.completedChunks = snapshot.completed_chunks || taskState.completedChunks || 0;
                            taskState.totalChunks = snapshot.total_chunks || taskState.totalChunks || 0;
                            if (snapshot.total_chunks > 0) {
                                taskState.percent = Math.round((snapshot.completed_chunks / snapshot.total_chunks) * 100);
                            }
                            taskState.message = snapshot.last_error || (snapshot.status === 'resumable' ? 'Đã tạm dừng' : 'Đã kết thúc');
                            TranslationWorker.updateProgress(taskState.percent, taskState.message);
                            if (ModalManager.isOpen('translation-progress-modal')) {
                                UiHelpers.renderProgressModal(taskState);
                            }
                            TranslationWorker._updateResumeButton(snapshot.status);

                            if (snapshot.status === 'failed') {
                                taskState.recoveryAvailable = snapshot.recovery_available !== false;
                                TranslationWorker._showRecoveryActions(taskState);
                            }
                        }
                    })
                    .catch(() => {
                        TranslationWorker.updateProgress(taskState.percent, 'Đã kết thúc stream');
                    });
                return;
            }
            if (data.type === 'progress') {
                taskState.percent = data.percent;
                taskState.message = data.message;
                if (data.current !== undefined) taskState.completedChunks = data.current;
                if (data.total !== undefined) taskState.totalChunks = data.total

                TranslationWorker._updateResumeButton(taskState.status);
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
                TranslationWorker._updateResumeButton('completed');
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
                TranslationWorker._updateResumeButton('failed');
                taskState.message = 'Lỗi: ' + data.message;
                TranslationWorker._lastViewedJobId = job_id;
                TranslationWorker._activeJobId = null;
                UiHelpers.addLog(data.message, 'error');
                TranslationWorker.resetButton(btn, isBatch);
                TranslationWorker.updateProgress(0, 'Lỗi: ' + data.message);
                if (btnStop) btnStop.classList.add('dn');
                ApiClient.loadTasks();
            }
            else if (data.type === 'task_failed') {
                evtSource.close();
                TranslationWorker._evtSource = null;
                taskState.status = 'failed';
                taskState.errorClass = data.error_context?.status || 'unknown';
                taskState.httpStatus = data.error_context?.http_status || null;
                taskState.retryable = data.error_context?.retryable || false;
                taskState.recoveryAvailable = true;
                TranslationWorker._updateResumeButton('failed');
                taskState.message = data.error_context?.message || 'Lỗi: dịch thất bại';
                TranslationWorker._lastViewedJobId = job_id;
                TranslationWorker._activeJobId = null;
                UiHelpers.addLog(taskState.message, 'error');
                TranslationWorker.resetButton(btn, isBatch);
                TranslationWorker.updateProgress(0, taskState.message);
                if (btnStop) btnStop.classList.add('dn');
                ApiClient.loadTasks();
                // The persistent task is the source of truth for recovery
                // metadata; refresh it before enabling recovery actions.
                fetch(`/api/tasks/${taskState.taskId}`)
                    .then(r => r.ok ? r.json() : null)
                    .then(snapshot => {
                        if (snapshot) {
                            taskState.completedChunks = snapshot.completed_chunks || taskState.completedChunks || 0;
                            taskState.totalChunks = snapshot.total_chunks || taskState.totalChunks || 0;
                            taskState.recoveryAvailable = snapshot.recovery_available !== false;
                        }
                        TranslationWorker._updateResumeButton('failed');
                        TranslationWorker._showRecoveryActions(taskState);
                    })
                    .catch(() => {
                        TranslationWorker._updateResumeButton('failed');
                        TranslationWorker._showRecoveryActions(taskState);
                    });
            }
            else if (data.type === 'cancelled') {
                evtSource.close();
                TranslationWorker._evtSource = null;
                taskState.status = 'cancelled';
                TranslationWorker._updateResumeButton('cancelled');
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

            // Lấy state từ DB vì stream bị ngắt kết nối
            fetch(`/api/tasks/${job_id}`)
                .then(r => r.ok ? r.json() : null)
                .then(snapshot => {
                    if (snapshot) {
                        taskState.status = snapshot.status;
                        taskState.taskId = snapshot.task_id || taskState.taskId;
                        taskState.completedChunks = snapshot.completed_chunks || taskState.completedChunks || 0;
                        taskState.totalChunks = snapshot.total_chunks || taskState.totalChunks || 0;
                        if (snapshot.total_chunks > 0) {
                            taskState.percent = Math.round((snapshot.completed_chunks / snapshot.total_chunks) * 100);
                        }
                        taskState.message = snapshot.last_error || (snapshot.status === 'running' ? 'Đang kết nối lại tiến trình...' : (snapshot.status === 'resumable' ? 'Đã tạm dừng' : 'Đã kết thúc'));
                        TranslationWorker.updateProgress(taskState.percent, taskState.message);
                        if (ModalManager.isOpen('translation-progress-modal')) {
                            UiHelpers.renderProgressModal(taskState);
                        }
                        TranslationWorker._updateResumeButton(snapshot.status);

                        if (snapshot.status === 'running') {
                            // Tự động reconnect stream sau 2s nếu task vẫn đang chạy thực tế
                            setTimeout(() => {
                                if (ModalManager.isOpen('translation-progress-modal') && !TranslationWorker._evtSource) {
                                    TranslationWorker.connectToProgress(job_id, btn, isBatch, onComplete, totalFiles);
                                }
                            }, 2000);
                            return;
                        }

                        TranslationWorker.resetButton(btn, isBatch);
                        if (btnStop) btnStop.classList.add('dn');

                        if (snapshot.status === 'failed') {
                            taskState.recoveryAvailable = snapshot.recovery_available !== false;
                            TranslationWorker._showRecoveryActions(taskState);
                        }
                    } else {
                        TranslationWorker.resetButton(btn, isBatch);
                        if (btnStop) btnStop.classList.add('dn');
                        TranslationWorker.updateProgress(taskState.percent, 'Không thể kết nối đến máy chủ.');
                        TranslationWorker._updateResumeButton('interrupted');
                    }
                })
                .catch(() => {
                    TranslationWorker.resetButton(btn, isBatch);
                    if (btnStop) btnStop.classList.add('dn');
                    TranslationWorker.updateProgress(taskState.percent, 'Không thể kết nối đến máy chủ.');
                    TranslationWorker._updateResumeButton('interrupted');
                });
        };

        if (btnResume) {
            btnResume.onclick = function () {
                if (!job_id) return;
                btnResume.disabled = true;
                btnResume.textContent = 'Đang khôi phục...';
                // Lấy taskId thực sự từ state nếu có
                const state = TranslationWorker._taskStateByJob.get(job_id);
                const targetTaskId = state ? state.taskId : job_id

                fetch(`/api/tasks/${targetTaskId}/resume`, { method: 'POST' })
                    .then(r => r.json())
                    .then(data => {
                        if (data.job_id) {
                            if (TranslationWorker._evtSource) TranslationWorker._evtSource.close();
                            TranslationWorker._taskStateByJob.delete(job_id);
                            TranslationWorker.connectToProgress(null, false, data.job_id);
                        } else {
                            btnResume.disabled = false;
                            btnResume.textContent = 'Tiếp tục';
                        }
                    })
                    .catch(e => {
                        btnResume.disabled = false;
                        btnResume.textContent = 'Tiếp tục';
                    });
            };
        }

        // Recovery buttons
        const btnRecovery = document.getElementById('btn-progress-recovery');
        const btnExportPartial = document.getElementById('btn-export-partial');
        if (btnRecovery) {
            btnRecovery.onclick = function () {
                const taskState = TranslationWorker._taskStateByJob.get(job_id);
                if (taskState) TranslationWorker._startRecovery(taskState);
            };
        }
        if (btnExportPartial) {
            btnExportPartial.onclick = function () {
                const taskState = TranslationWorker._taskStateByJob.get(job_id);
                if (taskState) TranslationWorker._exportPartial(taskState);
            };
        }
        const btnClosePartial = document.getElementById('btn-progress-close-partial');
        if (btnClosePartial) {
            btnClosePartial.onclick = function () {
                const taskState = TranslationWorker._taskStateByJob.get(job_id);
                if (taskState) TranslationWorker._closeAsPartial(taskState);
            };
        }
    },

    _updateResumeButton(status) {
        const btnResume = document.getElementById('btn-progress-resume');
        const btnStop = document.getElementById('btn-progress-stop');
        const btnRecovery = document.getElementById('btn-progress-recovery');
        const btnExportPartial = document.getElementById('btn-export-partial');
        const btnClosePartial = document.getElementById('btn-progress-close-partial')

        if (!btnResume) return

        const taskState = TranslationWorker._taskStateByJob.get(TranslationWorker._activeJobId || TranslationWorker._lastViewedJobId)
        const hasChunks = taskState && taskState.completedChunks > 0

        if (['paused', 'failed', 'interrupted', 'resumable'].includes(status)) {
            btnResume.classList.remove('dn')
            btnResume.disabled = false
            btnResume.textContent = 'Tiếp tục'
            if (btnStop) btnStop.classList.add('dn')
        } else if (status === 'running' || status === 'started') {
            btnResume.classList.add('dn')
            if (btnStop) btnStop.classList.remove('dn')
        } else if (status === 'completed' || status === 'cancelled' || status === 'closed_partial') {
            btnResume.classList.add('dn')
            if (btnStop) btnStop.classList.add('dn')
        }

        if (btnRecovery) {
            btnRecovery.classList.toggle('dn', status !== 'failed');
        }
        if (btnExportPartial) {
            btnExportPartial.classList.toggle('dn', status !== 'failed');
        }
        if (btnClosePartial) {
            const canClosePartial = hasChunks && ['running', 'started', 'resumable', 'paused', 'failed', 'interrupted'].includes(status);
            btnClosePartial.classList.toggle('dn', !canClosePartial);
        }
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
        // Tải snapshot trước khi quyết định connect SSE
        fetch(`/api/tasks/${jobId}`)
            .then(r => r.ok ? r.json() : null)
            .then(snapshot => {
                if (snapshot) {
                    let state = TranslationWorker._taskStateByJob.get(jobId);
                    if (!state) {
                        state = {
                            jobId: jobId,
                            taskId: snapshot.task_id || jobId,
                            status: snapshot.status || 'resumable',
                            projectSlug: snapshot.project_slug || '',
                            filename: snapshot.filename || '',
                            percent: snapshot.total_chunks ? Math.round((snapshot.completed_chunks / snapshot.total_chunks) * 100) : 0,
                            message: snapshot.last_error || (snapshot.status === 'resumable' ? 'Đã tạm dừng' : ''),
                            logs: [],
                            completedChunks: snapshot.completed_chunks || 0,
                            totalChunks: snapshot.total_chunks || 0,
                            recoveryAvailable: snapshot.recovery_available !== false,
                            httpStatus: null,
                            retryable: false
                        };
                        TranslationWorker._taskStateByJob.set(jobId, state);
                    } else {
                        state.status = snapshot.status;
                        state.taskId = snapshot.task_id || state.taskId;
                        state.projectSlug = snapshot.project_slug || state.projectSlug || '';
                        state.filename = snapshot.filename || state.filename || '';
                        state.completedChunks = snapshot.completed_chunks || state.completedChunks || 0;
                        state.totalChunks = snapshot.total_chunks || state.totalChunks || 0;
                        if (snapshot.total_chunks > 0) {
                            state.percent = Math.round((snapshot.completed_chunks / snapshot.total_chunks) * 100);
                        }
                    }

                    TranslationWorker._activeJobId = (state.status === 'running' || state.status === 'started') ? jobId : null;
                    TranslationWorker._lastViewedJobId = jobId;

                    // Wire các nút điều khiển với explicit jobId
                    const btnDiscard = document.getElementById('btn-progress-discard');
                    if (btnDiscard) btnDiscard.onclick = () => TranslationWorker._discardTask(state);

                    const btnStop = document.getElementById('btn-progress-stop');
                    if (btnStop) btnStop.onclick = () => TranslationWorker.stopTranslation(state.jobId);

                    if (state.status === 'running' || state.status === 'started') {
                        TranslationWorker.connectToProgress(null, false, jobId);
                    } else {
                        // Trạng thái đã dừng, chỉ hiển thị snapshot, KHÔNG connect SSE
                        UiHelpers.resetProgressModal();
                        UiHelpers.renderProgressModal(state);
                        TranslationWorker.updateProgress(state.percent, state.message);
                        TranslationWorker._updateResumeButton(state.status);

                        if (state.status === 'failed' && state.recoveryAvailable) {
                            TranslationWorker._showRecoveryActions(state);
                        }
                        ModalManager.show('translation-progress-modal');
                    }
                } else {
                    TranslationWorker.connectToProgress(null, false, jobId);
                }
            })
            .catch(() => TranslationWorker.connectToProgress(null, false, jobId));
    },

    async _discardTask(taskState) {
        if (!taskState || !taskState.jobId) return;

        const fileLabel = taskState.filename || 'tác vụ này';
        const chunkInfo = taskState.completedChunks
            ? `\n\nTiến độ hiện tại: ${taskState.completedChunks}/${taskState.totalChunks || '?'} chunk đã dịch.`
            : '';

        const confirmed = await showConfirm(
            `Bạn có chắc chắn muốn bỏ dở “${fileLabel}” không?${chunkInfo}\n\n` +
            `Task sẽ bị xóa khỏi danh sách đang xử lý và checkpoint sẽ được lưu trữ.`,
            { title: 'Xác nhận bỏ task', confirmText: 'Bỏ task', cancelText: 'Quay lại', danger: true }
        );
        if (!confirmed) return;

        try {
            const res = await fetch(`/api/tasks/${taskState.jobId}/discard`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ delete_checkpoint: false })
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || `HTTP ${res.status}`);
            }
            UiHelpers.showToast('Đã hủy bỏ task thành công', 'success');
            if (TranslationWorker._evtSource) {
                TranslationWorker._evtSource.close();
                TranslationWorker._evtSource = null;
            }
            TranslationWorker._taskStateByJob.delete(taskState.jobId);
            TranslationWorker._activeJobId = null;
            TranslationWorker._lastViewedJobId = null;
            ModalManager.hide('translation-progress-modal');
            ApiClient.loadTasks();
        } catch (e) {
            UiHelpers.showToast('Lỗi: ' + e.message, 'error');
            UiHelpers.addLog('Lỗi khi bỏ task: ' + e.message, 'error');
        }
    },

    openLatestTaskProgress() {
        fetch('/api/tasks')
            .then(r => r.ok ? r.json() : { tasks: [] })
            .then(data => {
                const tasks = (data.tasks || []).filter(t => !['completed', 'archived'].includes(t.status));

                if (tasks.length === 0) {
                    // Không có task nào: thông báo
                    UiHelpers.showToast('Không có tác vụ nào đang chạy hoặc chờ resume.', 'info');
                    return;
                }

                if (tasks.length === 1) {
                    // Chỉ có 1 task: Mở thẳng chi tiết tiến trình
                    TranslationWorker.openTaskProgress(tasks[0].job_id);
                    return;
                }

                // Nhiều hơn 1 task: Mở Task Manager Modal để người dùng chọn
                TranslationWorker.openTaskManagerModal(tasks);
            })
            .catch(e => console.error('Failed to load tasks', e));
    },

    openTaskManagerModal(tasks = null) {
        TranslationWorker._initTaskManagerDelegation();
        if (tasks) {
            TranslationWorker.renderTaskManagerList(tasks);
            ModalManager.show('task-manager-modal');
        } else {
            TranslationWorker.refreshTaskManager();
        }
    },

    refreshTaskManager() {
        TranslationWorker._initTaskManagerDelegation();
        fetch('/api/tasks')
            .then(r => r.json())
            .then(data => {
                const tasks = (data.tasks || []).filter(t => !['completed', 'archived'].includes(t.status));
                TranslationWorker.renderTaskManagerList(tasks);
                const totalEl = document.getElementById('tm-total-count');
                if (totalEl) totalEl.textContent = tasks.length;
                ModalManager.show('task-manager-modal');
            })
            .catch(e => UiHelpers.showToast('Lỗi tải danh sách: ' + e.message, 'error'));
    },

    _taskManagerDelegationInitialized: false,
    _initTaskManagerDelegation() {
        if (TranslationWorker._taskManagerDelegationInitialized) return;
        const listEl = document.getElementById('task-manager-list');
        if (!listEl) return;

        listEl.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-action]');
            if (!btn) return;

            const action = btn.dataset.action;
            const jobId = btn.dataset.jobId;
            const taskId = btn.dataset.taskId || jobId;
            const filename = btn.dataset.filename || '';
            const completedChunks = parseInt(btn.dataset.completedChunks || '0', 10);
            const projectSlug = btn.dataset.projectSlug || '';

            if (action === 'view') {
                ModalManager.hide('task-manager-modal');
                TranslationWorker.openTaskProgress(jobId);
            } else if (action === 'resume') {
                TranslationWorker.resumeTaskFromList(taskId);
            } else if (action === 'close-partial') {
                TranslationWorker.closePartialFromList(taskId, filename, completedChunks);
            } else if (action === 'discard') {
                TranslationWorker.discardTaskFromList(jobId, filename);
            } else if (action === 'project-resume') {
                TranslationWorker.resumeProjectTasks(projectSlug);
            } else if (action === 'project-discard') {
                TranslationWorker.discardProjectTasks(projectSlug);
            }
        });

        TranslationWorker._taskManagerDelegationInitialized = true;
    },

    renderTaskManagerList(tasks) {
        const listEl = document.getElementById('task-manager-list');
        const totalEl = document.getElementById('tm-total-count');

        if (!listEl) return;
        if (totalEl) totalEl.textContent = tasks.length;

        if (tasks.length === 0) {
            listEl.innerHTML = '<div class="tc pv4 gray f6 i">Không có tác vụ nào đang hoạt động.</div>';
            return;
        }

        // Nhóm tasks theo project_slug
        const groups = {};
        tasks.forEach(t => {
            const slug = t.project_slug || 'uncategorized';
            if (!groups[slug]) groups[slug] = [];
            groups[slug].push(t);
        });

        let html = '';
        for (const [slug, groupTasks] of Object.entries(groups)) {
            const escSlug = escapeHtml(slug);
            const projectResumableCount = groupTasks.filter(t => ['resumable', 'interrupted', 'paused'].includes(t.status)).length;
            const projectDiscardableCount = groupTasks.filter(t => !['running', 'started', 'completed', 'archived'].includes(t.status)).length;

            html += `
            <div class="ba b--black-10 br3 overflow-hidden bg-white shadow-sm flex-shrink-0">
                <div class="pa2 ph3 bg-near-white bb b--black-05 flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="fw6 dark-gray f6">📁 Dự án: ${escSlug}</span>
                        <span class="f8 bg-light-gray gray ph2 pv1 br-pill">${groupTasks.length} file</span>
                    </div>
                    <!-- Nút thao tác hàng loạt cho riêng từng dự án -->
                    <div class="flex items-center gap-2">
                        ${projectResumableCount > 0 ? `
                            <button type="button" class="nt-btn nt-btn-outline pv1 ph2 f8 blue b--blue"
                                data-action="project-resume"
                                data-project-slug="${escSlug}"
                                title="Tiếp tục tất cả tác vụ của dự án ${escSlug}">
                                ▶ Tiếp tục (${projectResumableCount})
                            </button>
                        ` : ''}
                        ${projectDiscardableCount > 0 ? `
                            <button type="button" class="nt-btn nt-btn-danger pv1 ph2 f8"
                                data-action="project-discard"
                                data-project-slug="${escSlug}"
                                title="Bỏ tất cả tác vụ dở của dự án ${escSlug}">
                                ✕ Bỏ (${projectDiscardableCount})
                            </button>
                        ` : ''}
                    </div>
                </div>
                <div class="flex flex-column divide-y">`;

            groupTasks.forEach(task => {
                const rawFilename = task.filename || '';
                const escFilename = escapeHtml(rawFilename);
                const escJobId = escapeHtml(task.job_id || '');
                const escTaskId = escapeHtml(task.task_id || task.job_id || '');
                const pct = task.total_chunks ? Math.round((task.completed_chunks / task.total_chunks) * 100) : 0;

                const statusBadge = task.status === 'running'
                    ? '<span class="f8 bg-washed-green green ph2 pv1 br2 fw6">Đang chạy</span>'
                    : task.status === 'resumable'
                    ? '<span class="f8 bg-washed-blue blue ph2 pv1 br2 fw6">Có thể Resume</span>'
                    : `<span class="f8 bg-washed-red red ph2 pv1 br2 fw6">${escapeHtml(task.status)}</span>`;

                html += `
                <div class="pa3 flex items-center justify-between hover-bg-near-white bb b--black-05">
                    <div class="flex-auto pr3">
                        <div class="flex items-center gap-2 mb1">
                            <span class="fw6 dark-gray f6">📄 ${escFilename}</span>
                            ${statusBadge}
                        </div>
                        <div class="flex items-center gap-3 f7 gray">
                            <span>Tiến độ: <strong>${task.completed_chunks || 0}/${task.total_chunks || '?'}</strong> chunk (${pct}%)</span>
                            <div class="w4 bg-black-10 br-pill overflow-hidden" style="height:4px">
                                <div class="bg-blue h-100" style="width:${pct}%"></div>
                            </div>
                        </div>
                        ${task.last_error ? `<div class="f8 red mt1 truncate mw6">${escapeHtml(task.last_error)}</div>` : ''}
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        <button type="button" class="nt-btn nt-btn-outline pv1 ph2 f7"
                            data-action="view"
                            data-job-id="${escJobId}"
                            title="Xem chi tiết">
                            🔍 Chi tiết
                        </button>
                        ${task.status === 'resumable' || task.status === 'interrupted' ? `
                            <button type="button" class="nt-btn nt-btn-primary pv1 ph2 f7"
                                data-action="resume"
                                data-task-id="${escTaskId}"
                                data-job-id="${escJobId}">
                                ▶ Tiếp tục
                            </button>
                        ` : ''}
                        ${task.completed_chunks > 0 ? `
                            <button type="button" class="nt-btn nt-btn-outline pv1 ph2 f7 purple b--purple"
                                data-action="close-partial"
                                data-task-id="${escTaskId}"
                                data-filename="${escFilename}"
                                data-completed-chunks="${task.completed_chunks}"
                                title="Chia tách phần đã dịch">
                                ✂ Chia tách
                            </button>
                        ` : ''}
                        <button type="button" class="nt-btn nt-btn-danger pv1 ph2 f7"
                            data-action="discard"
                            data-job-id="${escJobId}"
                            data-filename="${escFilename}"
                            title="Hủy bỏ task này">
                            ✕ Bỏ
                        </button>
                    </div>
                </div>`;
            });

            html += `
                </div>
            </div>`;
        }

        listEl.innerHTML = html;
    },

    async resumeProjectTasks(projectSlug) {
        if (!projectSlug) return;
        try {
            const res = await fetch('/api/tasks');
            if (!res.ok) return;
            const data = await res.json();
            const projectTasks = (data.tasks || []).filter(t =>
                (t.project_slug || 'uncategorized') === projectSlug && ['resumable', 'interrupted', 'paused', 'failed'].includes(t.status)
            );

            if (projectTasks.length === 0) {
                UiHelpers.showToast('Không có tác vụ nào cần resume trong dự án này.', 'info');
                return;
            }

            const confirmed = await showConfirm(
                `Tiếp tục dịch ${projectTasks.length} tác vụ dang dở của dự án "${projectSlug}"?`,
                { title: 'Tiếp tục dự án', confirmText: `Tiếp tục (${projectTasks.length})`, cancelText: 'Hủy' }
            );
            if (!confirmed) return;

            ModalManager.hide('task-manager-modal');
            UiHelpers.showToast(`Đang khôi phục ${projectTasks.length} tác vụ cho dự án ${projectSlug}...`, 'info');

            let lastJobId = null;
            for (const task of projectTasks) {
                const targetId = task.task_id || task.job_id;
                try {
                    const resResume = await fetch(`/api/tasks/${encodeURIComponent(targetId)}/resume`, { method: 'POST' });
                    const resData = await resResume.json();
                    if (resData.job_id) lastJobId = resData.job_id;
                } catch (e) {
                    console.error('Lỗi resume task', targetId, e);
                }
            }

            TranslationWorker.refreshTaskManager();
            ApiClient.loadTasks();
            if (lastJobId) {
                TranslationWorker.connectToProgress(null, false, lastJobId);
            }
        } catch (e) {
            UiHelpers.showToast('Lỗi: ' + e.message, 'error');
        }
    },

    async discardProjectTasks(projectSlug) {
        if (!projectSlug) return;
        const confirmed = await showConfirm(
            `Bạn có chắc chắn muốn bỏ TẤT CẢ các tác vụ dang dở của dự án "${projectSlug}"?\n\nDữ liệu checkpoint sẽ được lưu trữ.`,
            {
                title: 'Bỏ tác vụ dự án',
                confirmText: `Bỏ tác vụ "${projectSlug}"`,
                cancelText: 'Hủy bỏ',
                danger: true
            }
        );
        if (!confirmed) return;

        try {
            const res = await fetch('/api/tasks/bulk-discard', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_slug: projectSlug })
            });
            const result = await res.json();
            if (res.ok) {
                UiHelpers.showToast(result.message || `Đã bỏ thành công các tác vụ của dự án ${projectSlug}`, 'success');
                TranslationWorker.refreshTaskManager();
                ApiClient.loadTasks();
            } else {
                throw new Error(result.error || 'Không thể bỏ tác vụ');
            }
        } catch (e) {
            UiHelpers.showToast('Lỗi: ' + e.message, 'error');
        }
    },

    async resumeTaskFromList(taskId) {
        ModalManager.hide('task-manager-modal');
        try {
            const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/resume`, { method: 'POST' });
            const data = await res.json();
            if (data.job_id) {
                ApiClient.loadTasks();
                TranslationWorker.connectToProgress(null, false, data.job_id);
            } else {
                UiHelpers.showToast('Không thể resume: ' + (data.error || 'Lỗi không xác định'), 'error');
            }
        } catch (e) {
            UiHelpers.showToast('Lỗi: ' + e.message, 'error');
        }
    },

    async closePartialFromList(taskId, filename, completedChunks) {
        const confirmed = await showConfirm(`Chia tách ${completedChunks} chunk đã dịch của “${filename}” thành file riêng?`);
        if (!confirmed) return;
        try {
            const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/close-as-partial`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ confirm: true, export_partial: true })
            });
            if (res.ok) {
                UiHelpers.showToast('Đã chia tách file thành công', 'success');
                TranslationWorker.refreshTaskManager();
                ApiClient.loadTasks();
            } else {
                const err = await res.json();
                UiHelpers.showToast('Lỗi: ' + (err.error || 'Không thể chia tách'), 'error');
            }
        } catch (e) {
            UiHelpers.showToast('Lỗi: ' + e.message, 'error');
        }
    },

    async discardTaskFromList(jobId, filename) {
        const confirmed = await showConfirm(
            `Bỏ task “${filename}”? Dữ liệu chưa lưu vào file chính sẽ bị hủy.`,
            { danger: true }
        );
        if (!confirmed) return;
        try {
            const res = await fetch(`/api/tasks/${encodeURIComponent(jobId)}/discard`, { method: 'POST' });
            if (res.ok) {
                UiHelpers.showToast('Đã bỏ task thành công', 'success');
                TranslationWorker.refreshTaskManager();
                ApiClient.loadTasks();
            } else {
                const err = await res.json();
                UiHelpers.showToast('Lỗi: ' + (err.error || 'Không thể bỏ task'), 'error');
            }
        } catch (e) {
            UiHelpers.showToast('Lỗi: ' + e.message, 'error');
        }
    },

    _showRecoveryActions(taskState) {
        const recoverySection = document.getElementById('recovery-actions');
        const sourceStatus = document.getElementById('source-task-status');
        const recoveryStatus = document.getElementById('recovery-task-status');
        const recoveryInfo = document.getElementById('recovery-info');
        if (recoverySection) recoverySection.classList.remove('dn');
        if (recoveryInfo) recoveryInfo.classList.remove('dn');
        if (sourceStatus) sourceStatus.textContent = `failed / provider blocked (${taskState.httpStatus || '451'})`;
        if (recoveryStatus) recoveryStatus.textContent = 'chờ tạo task mới';
    },

    async _startRecovery(taskState) {
        const confirmed = await showConfirm(
            `Giữ ${taskState.completedChunks || 0} chunk đã dịch và tạo task mới để dịch tiếp phần còn lại?\n\n` +
            `Task cũ: ${taskState.taskId}\n` +
            `Provider/model sẽ được giữ nguyên hoặc chọn mới trong modal.`
        );
        if (!confirmed) return;

        const btnRecovery = document.getElementById('btn-progress-recovery');
        if (btnRecovery) {
            btnRecovery.disabled = true;
            btnRecovery.textContent = 'Đang tạo recovery...';
        }

        try {
            const response = await fetch(`/api/tasks/${taskState.taskId}/recover-from-checkpoint`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    provider_id: document.getElementById('provider-select')?.value || '',
                    model: document.getElementById('model')?.value || '',
                    export_partial: true,
                }),
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Không thể tạo recovery');
            }

            const result = await response.json();

            if (TranslationWorker._evtSource) {
                TranslationWorker._evtSource.close();
                TranslationWorker._evtSource = null;
            }
            TranslationWorker._taskStateByJob.delete(taskState.taskId);

            const newState = {
                ...taskState,
                jobId: result.job_id,
                status: 'running',
                recoveryOf: taskState.taskId,
                partialOutput: result.partial_output,
                completedChunks: result.checkpoint?.completed_chunks || 0,
                totalChunks: result.checkpoint?.total_chunks || 0,
            };
            TranslationWorker._taskStateByJob.set(result.job_id, newState);
            TranslationWorker._activeJobId = result.job_id;
            TranslationWorker._lastViewedJobId = result.job_id;

            const recoveryStatus = document.getElementById('recovery-task-status');
            if (recoveryStatus) recoveryStatus.textContent = 'running';

            UiHelpers.addLog(`Đã tạo recovery task: ${result.job_id}`, 'success');
            TranslationWorker.connectToProgress(null, false, result.job_id);

        } catch (err) {
            UiHelpers.showToast('Lỗi: ' + err.message, 'error');
            if (btnRecovery) {
                btnRecovery.disabled = false;
                btnRecovery.textContent = 'Giữ phần đã dịch + tạo task mới';
            }
        }
    },

    async _exportPartial(taskState) {
        try {
            const response = await fetch(`/api/tasks/${taskState.taskId}/export-partial`, { method: 'POST' });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Không thể xuất partial');
            }
            const result = await response.json();
            UiHelpers.showToast(`Đã xuất partial: ${result.partial_output}`, 'success');
            UiHelpers.addLog(`Partial file: ${result.partial_output} (${result.done_chunks} chunk đã dịch)`, 'info');
        } catch (err) {
            UiHelpers.showToast('Lỗi: ' + err.message, 'error');
        }
    },

    async _closeAsPartial(taskState) {
        const confirmed = await showConfirm(
            `Bạn có chắc muốn chia tách phần đã dịch và kết thúc task này?\n\n` +
            `Một file .partial.md sẽ được tạo ra với ${taskState.completedChunks} chunk đã dịch.`
        );
        if (!confirmed) return;

        try {
            const response = await fetch(`/api/tasks/${taskState.taskId}/close-as-partial`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ confirm: true, export_partial: true })
            });
            if (response.status === 202) {
                // close_pending: worker chưa dừng trong timeout. KHÔNG assemble, KHÔNG cancel thêm.
                await response.json();
                UiHelpers.showToast('Task đang chạy, chờ worker dừng hẳn rồi thử lại...', 'info');
                setTimeout(() => TranslationWorker.openTaskProgress(taskState.jobId), 3000);
                return;
            }
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Không thể chốt task');
            }
            const result = await response.json();
            UiHelpers.showToast(`Đã chốt file: ${result.partial_output}`, 'success');

            if (TranslationWorker._evtSource) {
                TranslationWorker._evtSource.close();
                TranslationWorker._evtSource = null;
            }
            TranslationWorker._taskStateByJob.delete(taskState.jobId);
            // KHÔNG gọi /cancel ở đây — xem B15. Route đã cancel scoped và đã chờ worker dừng.
            ApiClient.loadTasks();
        } catch (err) {
            UiHelpers.showToast('Lỗi: ' + err.message, 'error');
        }
    },

    _setRecoveryInProgress(inProgress) {
        const btnRecovery = document.getElementById('btn-progress-recovery');
        const btnExportPartial = document.getElementById('btn-export-partial');
        if (btnRecovery) {
            btnRecovery.disabled = inProgress;
            btnRecovery.textContent = inProgress ? 'Đang tạo recovery...' : 'Giữ phần đã dịch + tạo task mới';
        }
        if (btnExportPartial) {
            btnExportPartial.disabled = inProgress;
        }
    },
};

window.TranslationWorker = TranslationWorker;
