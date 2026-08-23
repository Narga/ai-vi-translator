window.ConverterToolPlugin = {
    // Cờ chống ghi đè summary khi refresh file list tự động sau tác vụ (one-shot reset)
    _suppressSyncSummary: false,

    getSelectionFromWorkspace() {
        if (!window.currentProject) {
            return { slug: null, section: 'sources', filenames: [] };
        }

        const sourcesBtn = document.getElementById('pm-tab-sources');
        const translatedBtn = document.getElementById('pm-tab-translated');
        const spellingBtn = document.getElementById('pm-tab-spelling');

        let section = 'sources';
        let selectedSet = window.selectedFiles;

        if (translatedBtn && translatedBtn.classList.contains('active')) {
            section = 'translated';
            selectedSet = window.selectedTranslatedFiles;
        } else if (spellingBtn && spellingBtn.classList.contains('active')) {
            section = 'spelling';
            selectedSet = window.selectedFiles;
        }

        let filenames = Array.from(selectedSet || []);

        // Smart Fallback: Nếu không tick checkbox nào, fallback sang file đang active trong editor/panel
        if (filenames.length === 0 && window.currentProjectFile && window.currentProjectFile.name) {
            if (window.currentProjectFile.section === section) {
                filenames = [window.currentProjectFile.name];
            }
        }

        return {
            slug: window.currentProject.slug,
            section: section,
            filenames: filenames,
        };
    },

    syncSelectionSummary() {
        if (this._suppressSyncSummary) {
            this._suppressSyncSummary = false;
            return;
        }
        const selection = this.getSelectionFromWorkspace();
        if (!selection.slug) return;

        const count = selection.filenames.length;
        if (count === 0) {
            this.setSelectionSummary('Chọn một hoặc nhiều tập tin ở panel bên trái, sau đó bấm nút tác vụ tương ứng.', 'info');
        } else {
            const sectionName = selection.section === 'translated' ? 'Bản dịch' : (selection.section === 'spelling' ? 'Soát lỗi' : 'Bản gốc');
            const displayNames = count <= 2 ? selection.filenames.join(', ') : `${selection.filenames[0]} và ${count - 1} tập tin khác`;
            this.setSelectionSummary(`Đang chọn: ${displayNames} (${count} tập tin từ tab ${sectionName})`, 'info');
        }
    },

    setSelectionSummary(message, type = 'info') {
        const el = document.getElementById('converter-tool-selection-summary');
        if (!el) return;
        el.className = `f7 flex items-center ${type === 'error' ? 'dark-red' : (type === 'success' ? 'dark-green' : 'gray')}`;
        el.textContent = message;
    },

    setSelectionSummaryHtml(html, type = 'info') {
        const el = document.getElementById('converter-tool-selection-summary');
        if (!el) return;
        el.className = `f7 flex items-center ${type === 'error' ? 'dark-red' : (type === 'success' ? 'dark-green' : 'gray')}`;
        el.innerHTML = html;
    },

    clearLog() {
        const logEl = document.getElementById('converter-tool-log');
        if (logEl) logEl.innerHTML = '';
    },

    appendLog(message, type = 'info') {
        const logEl = document.getElementById('converter-tool-log');
        if (!logEl) return;
        const entry = document.createElement('div');
        entry.className = `mb2 ${type === 'error' ? 'light-red' : (type === 'success' ? 'light-green' : 'near-white')}`;
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        logEl.appendChild(entry);
        logEl.scrollTop = logEl.scrollHeight;
    },

    runHtmlToMarkdown() {
        this.runTask('html_to_markdown', 'btn-convert-html-to-md', 'HTML → .MD');
    },

    runMarkdownToHtml() {
        this.runTask('markdown_to_html', 'btn-convert-md-to-html', '.MD → HTML');
    },

    runMarkdownToEpub() {
        this.runTask('markdown_to_epub', 'btn-create-epub-from-md', 'MD → EPUB 3');
    },

    runCreateEpub() {
        this.runTask('create_epub', 'btn-create-epub', 'HTML → EPUB 3');
    },

    runSplitFile() {
        const maxChars = Number(document.getElementById('converter-tool-max-chars')?.value || 100000);
        if (!Number.isInteger(maxChars) || maxChars < 1000) {
            UiHelpers.showToast('Giới hạn chunk phải là số nguyên từ 1000 ký tự trở lên', 'error');
            return;
        }
        this.runTask('split_file', 'btn-split-file', 'Chia tập tin', { max_chars: maxChars });
    },

    runMergeFiles() {
        this.runTask('merge_files', 'btn-merge-files', 'Ghép tập tin');
    },

    runTask(task, buttonId, buttonLabel, options = {}) {
        if (task === 'merge_files' && !this._preflightMergeCheck()) {
            return;
        }

        const selection = this.getSelectionFromWorkspace();
        if (!selection.slug) {
            UiHelpers.showToast('Vui lòng mở một dự án trước khi chạy Công cụ chuyển đổi', 'error');
            return;
        }

        this.setSelectionSummary(
            `Đang dùng ${selection.filenames.length} tập tin từ tab ${selection.section}.`,
            selection.filenames.length ? 'info' : 'error'
        );

        if (!selection.filenames.length) {
            UiHelpers.showToast('Chưa chọn tập tin nào ở panel bên trái', 'error');
            return;
        }

        const btn = document.getElementById(buttonId);
        if (!btn) return;

        btn.disabled = true;
        btn.textContent = '⏳ Đang chạy...';
        this.clearLog();
        this.appendLog(`🔄 Gửi tác vụ ${buttonLabel}...`);

        const deleteSource = !!document.getElementById('converter-tool-delete-source')?.checked;

        const body = {
            task,
            section: selection.section,
            filenames: selection.filenames,
            delete_source: deleteSource,
        };
        if (task === 'split_file') {
            body.max_chars = options.max_chars || 100000;
        }

        fetch(`/api/projects/${encodeURIComponent(selection.slug)}/plugins/epub-converter`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        })
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(data => {
                if (!data.plugin_id) {
                    throw new Error(data.error || 'Plugin không trả về tiến trình');
                }
                this.pollProgress(selection.slug, data.plugin_id, btn, buttonLabel);
            })
            .catch(err => {
                this.appendLog(`❌ ${err.message}`, 'error');
                btn.disabled = false;
                btn.textContent = buttonLabel;
            });
    },

    _preflightMergeCheck() {
        const selection = this.getSelectionFromWorkspace();
        if (!selection.filenames.length) return true;
        const extGroups = new Map();
        selection.filenames.forEach(fn => {
            const ext = (fn.split('.').pop() || '').toLowerCase();
            if (!extGroups.has(ext)) extGroups.set(ext, []);
            extGroups.get(ext).push(fn);
        });
        if (extGroups.size <= 1) return true;

        const groups = Array.from(extGroups.entries()).map(([ext, files]) =>
            `${ext}: ${files.length} tập tin`
        ).join('<br>');

        const modal = document.getElementById('converter-tool-mixed-ext-modal');
        const body = document.getElementById('converter-tool-mixed-ext-body');
        if (modal && body) {
            body.innerHTML = `Các tập tin đã chọn có nhiều định dạng khác nhau:<br><br><code>${groups}</code><br><br>Vui lòng chọn một nhóm định dạng duy nhất trước khi ghép.`;
            ModalManager.show('converter-tool-mixed-ext-modal');
        } else {
            this.setSelectionSummaryHtml(
                `<span class="light-red">⚠️ Mixed extensions: ${groups}</span>`,
                'error'
            );
        }
        return false;
    },

    pollProgress(slug, pluginId, btn, buttonLabel) {
        let lastCount = 0;
        const interval = setInterval(() => {
            fetch(`/api/plugins/progress/${pluginId}`)
                .then(r => {
                    if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                    return r.json();
                })
                .then(data => {
                    const messages = data.messages || [];
                    for (let i = lastCount; i < messages.length; i++) {
                        const message = messages[i];
                        const type = message.includes('❌') ? 'error' : (message.includes('✅') ? 'success' : 'info');
                        this.appendLog(message, type);
                    }
                    lastCount = messages.length;

                    const isTerminal = ['done', 'partial', 'error'].includes(data.status);
                    if (isTerminal) {
                        clearInterval(interval);
                        btn.disabled = false;
                        btn.textContent = buttonLabel;

                        if (data.status === 'done' || data.status === 'partial') {
                            const outputPath = data.result?.output_path
                                || (data.result?.output_paths && data.result.output_paths[0]);
                            const processedCount = data.result?.processed_count || 0;
                            const failedFiles = data.result?.failed_files || [];
                            const failedCount = failedFiles.length;
                            const skippedFiles = data.result?.skipped_files || [];
                            const skippedCount = skippedFiles.length;

                            let summaryLabel = 'Đã hoàn tất chuyển đổi';
                            let summaryType = 'success';

                            if (data.status === 'partial') {
                                summaryLabel = `Hoàn tất một phần: ${processedCount} OK, ${failedCount} lỗi`;
                                summaryType = 'error';
                            } else if (processedCount === 0 && skippedCount > 0) {
                                const skippedReason = skippedFiles[0]?.reason || 'không hợp lệ hoặc quá nhỏ';
                                summaryLabel = `Bỏ qua ${skippedCount} tập tin (${skippedReason})`;
                                summaryType = 'info';
                            }

                            if (outputPath) {
                                const name = outputPath.split('/').pop();
                                const url = `/api/projects/${encodeURIComponent(slug)}/download/${encodeURIComponent(outputPath)}`;
                                this.setSelectionSummaryHtml(
                                    `<span>${summaryLabel} →</span>` +
                                    `<a href="${url}" download class="ml-auto underline">${name}</a>`,
                                    summaryType);
                            } else {
                                this.setSelectionSummary(summaryLabel, summaryType);
                            }

                            // Làm mới sidebar tại chỗ: giữ nguyên tab 'ebook-kit',
                            // sử dụng one-shot suppress để không xóa đè summary vừa render
                            if (ProjectManager.refreshProjectFiles) {
                                this._suppressSyncSummary = true;
                                ProjectManager.refreshProjectFiles();
                            }
                        } else {
                            this.setSelectionSummary('Tác vụ thất bại. Xem nhật ký bên dưới.', 'error');
                        }
                    }
                })
                .catch(() => {
                    clearInterval(interval);
                    btn.disabled = false;
                    btn.textContent = buttonLabel;
                    this.appendLog('❌ Không thể đọc tiến trình plugin', 'error');
                });
        }, 1000);
    },

    initDefaultChunkSize() {
        const input = document.getElementById('converter-tool-max-chars');
        if (!input) return;
        fetch('/api/config')
            .then(r => r.ok ? r.json() : Promise.reject())
            .then(data => {
                const val = data?.default_chunk_size;
                if (typeof val === 'number' && val >= 1000) {
                    input.value = String(val);
                }
            })
            .catch(() => {
                input.value = '100000';
            });
    },
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => ConverterToolPlugin.initDefaultChunkSize());
} else {
    ConverterToolPlugin.initDefaultChunkSize();
}
