window.ConverterToolPlugin = {
    getSelectionFromWorkspace() {
        if (!window.currentProject) {
            return { slug: null, section: 'sources', filenames: [] };
        }

        const sourcesBtn = document.getElementById('pm-tab-sources');
        const translatedBtn = document.getElementById('pm-tab-translated');
        const spellingBtn = document.getElementById('pm-tab-spelling');

        if (translatedBtn && translatedBtn.classList.contains('active')) {
            return {
                slug: window.currentProject.slug,
                section: 'translated',
                filenames: Array.from(window.selectedTranslatedFiles || []),
            };
        }

        if (spellingBtn && spellingBtn.classList.contains('active')) {
            return {
                slug: window.currentProject.slug,
                section: 'spelling',
                filenames: Array.from(window.selectedFiles || []),
            };
        }

        return {
            slug: window.currentProject.slug,
            section: (sourcesBtn && sourcesBtn.classList.contains('active')) ? 'sources' : 'sources',
            filenames: Array.from(window.selectedFiles || []),
        };
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

    runCreateEpub() {
        this.runTask('create_epub', 'btn-create-epub', 'Tạo EPUB 3');
    },

    runTask(task, buttonId, buttonLabel) {
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

        fetch(`/api/projects/${encodeURIComponent(selection.slug)}/plugins/epub-converter`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task,
                section: selection.section,
                filenames: selection.filenames,
            }),
        })
            .then(r => r.json())
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

    pollProgress(slug, pluginId, btn, buttonLabel) {
        let lastCount = 0;
        const interval = setInterval(() => {
            fetch(`/api/plugins/progress/${pluginId}`)
                .then(r => r.json())
                .then(data => {
                    const messages = data.messages || [];
                    for (let i = lastCount; i < messages.length; i++) {
                        const message = messages[i];
                        const type = message.includes('❌') ? 'error' : (message.includes('✅') ? 'success' : 'info');
                        this.appendLog(message, type);
                    }
                    lastCount = messages.length;

                    if (data.status === 'done' || data.status === 'error') {
                        clearInterval(interval);
                        btn.disabled = false;
                        btn.textContent = buttonLabel;

                        if (data.status === 'done') {
                            const outputPath = data.result?.output_path
                                || (data.result?.output_paths && data.result.output_paths[0]);
                            if (outputPath) {
                                const name = outputPath.split('/').pop();
                                const url = `/api/projects/${encodeURIComponent(slug)}/download/${encodeURIComponent(outputPath)}`;
                                this.setSelectionSummaryHtml(
                                    `<span>Đã hoàn tất chuyển đổi thành epub →</span>` +
                                    `<a href="${url}" download class="ml-auto underline">${name}</a>`,
                                    'success');
                            } else {
                                this.setSelectionSummary('Đã hoàn tất chuyển đổi thành epub', 'success');
                            }
                            // Làm mới sidebar tại chỗ: giữ nguyên tab 'ebook-kit',
                            // không gọi openProject (vì openProject ép wsTab='editor').
                            if (ProjectManager.refreshProjectFiles) {
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
};
