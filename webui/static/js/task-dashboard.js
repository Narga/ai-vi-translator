// ============================================================
// task-dashboard.js — Dedicated Task Management Dashboard (Phase C)
// ============================================================

const TaskDashboard = {
    _activeTab: 'all',
    _searchQuery: '',
    _selectedJobIds: new Set(),
    _tasksCache: [],
    _refreshTimer: null,
    _initialized: false,

    open() {
        TaskDashboard._selectedJobIds.clear();
        TaskDashboard.bindEvents();
        TaskDashboard.refresh();
        ModalManager.show('task-dashboard-modal');

        if (!TaskDashboard._refreshTimer) {
            TaskDashboard._refreshTimer = setInterval(() => {
                if (ModalManager.isOpen('task-dashboard-modal')) {
                    TaskDashboard.refresh(true);
                } else {
                    TaskDashboard.stopTimer();
                }
            }, 5000);
        }
    },

    close() {
        TaskDashboard.stopTimer();
        ModalManager.hide('task-dashboard-modal');
    },

    stopTimer() {
        if (TaskDashboard._refreshTimer) {
            clearInterval(TaskDashboard._refreshTimer);
            TaskDashboard._refreshTimer = null;
        }
    },

    bindEvents() {
        if (TaskDashboard._initialized) return;

        // 1. Tab buttons filter
        document.querySelectorAll('#td-status-tabs button[data-tab]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('#td-status-tabs button[data-tab]').forEach(b => {
                    b.classList.remove('nt-btn-primary');
                    b.classList.add('nt-btn-outline');
                });
                btn.classList.add('nt-btn-primary');
                btn.classList.remove('nt-btn-outline');
                TaskDashboard._activeTab = btn.dataset.tab;
                TaskDashboard.render();
            });
        });

        // 2. Search input filter
        const searchInput = document.getElementById('td-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                TaskDashboard._searchQuery = (e.target.value || '').toLowerCase().trim();
                TaskDashboard.render();
            });
        }

        // 3. Delegated Events on Task Container (XSS/Quote-safe)
        const container = document.getElementById('td-task-container');
        if (container) {
            // Checkbox selection
            container.addEventListener('change', (e) => {
                const cb = e.target.closest('input[data-select-job]');
                if (!cb) return;
                const jobId = cb.dataset.selectJob;
                if (cb.checked) TaskDashboard._selectedJobIds.add(jobId);
                else TaskDashboard._selectedJobIds.delete(jobId);
                TaskDashboard._updateBulkButton();
            });

            // Action buttons click
            container.addEventListener('click', (e) => {
                const btn = e.target.closest('button[data-action]');
                if (!btn) return;

                const action = btn.dataset.action;
                const jobId = btn.dataset.jobId;
                const taskId = btn.dataset.taskId || jobId;
                const filename = btn.dataset.filename || '';
                const completedChunks = parseInt(btn.dataset.completedChunks || '0', 10);
                const projectSlug = btn.dataset.projectSlug || '';

                if (action === 'view') {
                    TaskDashboard.close();
                    TranslationWorker.openTaskProgress(jobId);
                } else if (action === 'resume') {
                    TranslationWorker.resumeTaskFromList(taskId);
                } else if (action === 'close-partial') {
                    TranslationWorker.closePartialFromList(taskId, filename, completedChunks);
                } else if (action === 'discard') {
                    TranslationWorker.discardTaskFromList(jobId, filename);
                } else if (action === 'project-resume') {
                    TaskDashboard.resumeProjectTasks(projectSlug);
                } else if (action === 'project-discard') {
                    TaskDashboard.discardProjectTasks(projectSlug);
                }
            });
        }

        TaskDashboard._initialized = true;
    },

    async refresh(isBackground = false) {
        try {
            const res = await fetch('/api/tasks');
            if (!res.ok) return;
            const data = await res.json();
            TaskDashboard._tasksCache = (data.tasks || []).filter(t => !['archived'].includes(t.status));
            TaskDashboard.updateCounters();
            TaskDashboard.render();
        } catch (e) {
            if (!isBackground) {
                console.error('Lỗi tải danh sách task dashboard', e);
            }
        }
    },

    updateCounters() {
        const all = TaskDashboard._tasksCache.length;
        const running = TaskDashboard._tasksCache.filter(t => ['running', 'started'].includes(t.status)).length;
        const resumable = TaskDashboard._tasksCache.filter(t => ['resumable', 'interrupted', 'paused'].includes(t.status)).length;
        const failed = TaskDashboard._tasksCache.filter(t => t.status === 'failed').length;

        const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        setVal('td-count-all', all);
        setVal('td-count-running', running);
        setVal('td-count-resumable', resumable);
        setVal('td-count-failed', failed);
    },

    _updateBulkButton() {
        const btnBulk = document.getElementById('td-btn-bulk-discard');
        const countEl = document.getElementById('td-selected-count');
        const count = TaskDashboard._selectedJobIds.size;
        if (btnBulk) btnBulk.classList.toggle('dn', count === 0);
        if (countEl) countEl.textContent = count;
    },

    render() {
        const container = document.getElementById('td-task-container');
        if (!container) return;

        let filtered = TaskDashboard._tasksCache;
        if (TaskDashboard._activeTab === 'running') {
            filtered = filtered.filter(t => ['running', 'started'].includes(t.status));
        } else if (TaskDashboard._activeTab === 'resumable') {
            filtered = filtered.filter(t => ['resumable', 'interrupted', 'paused'].includes(t.status));
        } else if (TaskDashboard._activeTab === 'failed') {
            filtered = filtered.filter(t => t.status === 'failed');
        }

        if (TaskDashboard._searchQuery) {
            filtered = filtered.filter(t =>
                (t.filename || '').toLowerCase().includes(TaskDashboard._searchQuery) ||
                (t.project_slug || '').toLowerCase().includes(TaskDashboard._searchQuery)
            );
        }

        if (filtered.length === 0) {
            container.innerHTML = '<div class="tc pv5 gray f6 i bg-white br3 shadow-sm">Không tìm thấy tác vụ nào phù hợp với bộ lọc.</div>';
            return;
        }

        // Gom nhóm theo project_slug
        const groups = {};
        filtered.forEach(t => {
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
                <!-- Project Group Header -->
                <div class="pa2 ph3 bg-near-white bb b--black-05 flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="fw6 dark-gray f6">📁 Dự án: ${escSlug}</span>
                        <span class="f8 bg-light-gray gray ph2 pv1 br-pill">${groupTasks.length} tác vụ</span>
                    </div>
                    <!-- Nút thao tác hàng loạt cho riêng dự án này -->
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
                <!-- Files List inside Project -->
                <div class="flex flex-column divide-y">`;

            groupTasks.forEach(task => {
                const rawFilename = task.filename || '';
                const escFilename = escapeHtml(rawFilename);
                const escJobId = escapeHtml(task.job_id || '');
                const escTaskId = escapeHtml(task.task_id || task.job_id || '');
                const isChecked = TaskDashboard._selectedJobIds.has(task.job_id);
                const pct = task.total_chunks ? Math.round((task.completed_chunks / task.total_chunks) * 100) : 0;

                const statusBadge = task.status === 'running'
                    ? '<span class="f8 bg-washed-green green ph2 pv1 br2 fw6">Đang chạy</span>'
                    : task.status === 'resumable'
                    ? '<span class="f8 bg-washed-blue blue ph2 pv1 br2 fw6">Có thể Resume</span>'
                    : `<span class="f8 bg-washed-red red ph2 pv1 br2 fw6">${escapeHtml(task.status)}</span>`;

                html += `
                <div class="pa3 flex items-center justify-between hover-bg-near-white bb b--black-05">
                    <div class="flex items-center gap-3 flex-auto pr3">
                        <input type="checkbox" data-select-job="${escJobId}" ${isChecked ? 'checked' : ''} class="pointer">
                        <div>
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
                    </div>
                    <!-- Actions -->
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

        container.innerHTML = html;
    },

    async resumeProjectTasks(projectSlug) {
        if (!projectSlug) return;
        const projectTasks = TaskDashboard._tasksCache.filter(t =>
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

        UiHelpers.showToast(`Đang khôi phục ${projectTasks.length} tác vụ cho dự án ${projectSlug}...`, 'info');
        let lastJobId = null;
        for (const task of projectTasks) {
            const targetId = task.task_id || task.job_id;
            try {
                const res = await fetch(`/api/tasks/${encodeURIComponent(targetId)}/resume`, { method: 'POST' });
                const resData = await res.json();
                if (resData.job_id) lastJobId = resData.job_id;
            } catch (e) {
                console.error('Lỗi khi resume task', targetId, e);
            }
        }

        TaskDashboard.refresh();
        ApiClient.loadTasks();
        if (lastJobId) {
            TaskDashboard.close();
            TranslationWorker.connectToProgress(null, false, lastJobId);
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
                TaskDashboard.refresh();
                ApiClient.loadTasks();
            } else {
                throw new Error(result.error || 'Không thể bỏ tác vụ');
            }
        } catch (e) {
            UiHelpers.showToast('Lỗi: ' + e.message, 'error');
        }
    },

    async executeBulkDiscard() {
        const count = TaskDashboard._selectedJobIds.size;
        if (count === 0) return;

        const confirmed = await showConfirm(
            `Bạn có chắc chắn muốn bỏ ${count} tác vụ đã chọn?`,
            {
                title: 'Xác nhận bỏ các tác vụ đã chọn',
                confirmText: `Bỏ ${count} tác vụ`,
                cancelText: 'Hủy bỏ',
                danger: true
            }
        );
        if (!confirmed) return;

        try {
            const res = await fetch('/api/tasks/bulk-discard', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ job_ids: Array.from(TaskDashboard._selectedJobIds) })
            });
            const result = await res.json();
            if (res.ok) {
                UiHelpers.showToast(result.message || `Đã bỏ thành công ${result.count} tác vụ`, 'success');
                TaskDashboard._selectedJobIds.clear();
                TaskDashboard._updateBulkButton();
                TaskDashboard.refresh();
                ApiClient.loadTasks();
            } else {
                throw new Error(result.error || 'Lỗi khi bỏ tác vụ');
            }
        } catch (e) {
            UiHelpers.showToast('Lỗi: ' + e.message, 'error');
        }
    },

    async cleanupStale() {
        try {
            const res = await fetch('/api/tasks/cleanup-stale', { method: 'POST' });
            const data = await res.json();
            UiHelpers.showToast(`Đã dọn dẹp ${data.cleaned_count} task mồ côi`, 'info');
            TaskDashboard.refresh();
            ApiClient.loadTasks();
        } catch (e) {
            UiHelpers.showToast('Lỗi dọn dẹp: ' + e.message, 'error');
        }
    }
};

window.TaskDashboard = TaskDashboard;
