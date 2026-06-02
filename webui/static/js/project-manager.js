// ============================================================
// project-manager.js — Project CRUD, file management, rendering
// ============================================================

// ============================================================
// Auto-save Module (CHỈ cho editor Bản dịch - result-text)
// ============================================================
const AutoSave = {
    _timer: null,
    _delay: 10000, // 10 giây
    _isSaving: false,

    init() {
        const editor = document.getElementById('result-text');
        if (!editor) return;

        editor.addEventListener('input', () => {
            this.schedule();
        });

        editor.addEventListener('blur', () => {
            this.save();
        });
    },

    schedule() {
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.save(), this._delay);
    },

    async save() {
        if (this._isSaving) return;
        if (!window.currentProject || !window.currentProjectFile) return;
        if (!DirtyState.isDirty('result-text')) return;

        const editor = document.getElementById('result-text');
        if (!editor) return;

        this._isSaving = true;
        this.showIndicator('Đang lưu...');

        try {
            const slug = window.currentProject.slug;
            const filename = window.currentProjectFile.name;
            const content = editor.value;

            const response = await fetch(`/api/projects/${slug}/file/translated/${filename}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content })
            });

            const data = await response.json();
            if (data.success) {
                DirtyState.clean('result-text');
                this.showIndicator('Đã lưu tự động');
                setTimeout(() => this.hideIndicator(), 2000);
            } else {
                this.showIndicator('Lỗi lưu');
            }
        } catch (err) {
            console.error('Auto-save error:', err);
            this.showIndicator('Lỗi lưu');
        } finally {
            this._isSaving = false;
        }
    },

    showIndicator(text) {
        let el = document.getElementById('auto-save-indicator');
        if (!el) {
            el = document.createElement('span');
            el.id = 'auto-save-indicator';
            el.className = 'f7 gray ml2';
            const header = document.querySelector('#result-text')?.closest('.editor-pane-3col')?.querySelector('.pa2');
            if (header) header.appendChild(el);
        }
        el.textContent = text;
        el.style.display = 'inline';
        if (text.includes('Đã lưu')) {
            el.className = 'f7 green ml2 fw6';
        } else if (text.includes('Lỗi')) {
            el.className = 'f7 red ml2 fw6';
        } else {
            el.className = 'f7 gray ml2';
        }
    },

    hideIndicator() {
        const el = document.getElementById('auto-save-indicator');
        if (el) el.style.display = 'none';
    },

    cancel() {
        clearTimeout(this._timer);
    }
};

window.AutoSave = AutoSave;

// ============================================================
// SVG Icons (simple line style)
// ============================================================
const Icons = {
    upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
    chunk: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="4" x2="6" y2="20"/><line x1="18" y1="4" x2="18" y2="20"/><line x1="6" y1="12" x2="18" y2="12"/></svg>',
    translate: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 8l6 6"/><path d="M4 14l6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="M22 22l-5-10-5 10"/><path d="M14 18h6"/></svg>',
    merge: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/></svg>',
    rename: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>',
    delete: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>',
    spellcheck: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/><path d="m5 12 5 5 10-10"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    wrap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M3 12h15a3 3 0 1 1 0 6h-4"/><path d="M3 18l4-4"/><path d="M3 14l4 4"/></svg>'
};

window.Icons = Icons;

const ProjectManager = {
    loadProjects() {
        fetch('/api/projects').then(r => r.json()).then(projects => {
            const el = document.getElementById('project-list');
            if (!el) return;
            if (!projects.length) { el.innerHTML = '<div class="pa4 tc silver i">Chưa có dự án.</div>'; return; }
            el.innerHTML = projects.map(p => {
                const active = (window.currentProject && window.currentProject.slug === p.slug) ? 'active shadow-1' : '';
                const isDone = p.source_count > 0 && p.translated_count >= p.source_count;
                const doneCheck = isDone ? '<span class="green ml1">🟢</span>' : '';
                return `<div class="sidebar-item ${active} flex flex-column gap-1" onclick="ProjectManager.selectProject('${p.slug}')">
                    <div class="flex justify-between items-center">
                        <span class="fw6 f5 dark-gray truncate">${p.name}${doneCheck}</span>
                    </div>
                    <div class="f7 gray truncate">
                        Nguồn: <span class="fw6">${p.source_count || 0}</span> | Đã dịch: <span class="fw6">${p.translated_count || 0}</span>
                    </div>
                </div>`;
            }).join('');
            
            const savedSlug = localStorage.getItem('nt_active_project_slug');
            if (!window.currentProject && projects.length > 0) {
                const slugToSelect = savedSlug || projects[0].slug;
                ProjectManager.selectProject(slugToSelect, false, true); 
            } else if (window.currentProject) {
                ProjectManager.updateSidebarHighlight(window.currentProject.slug);
            }
        });
    },

    updateSidebarHighlight(slug) {
        document.querySelectorAll('.sidebar-item').forEach(el => {
            const isActive = el.getAttribute('onclick').includes(`'${slug}'`);
            el.classList.toggle('active', isActive);
            el.classList.toggle('shadow-1', isActive);
        });
    },

    selectProject(slug, keepSelection = false) {
        if (!slug) return;
        
        fetch('/api/projects/' + slug)
        .then(r => {
            if (!r.ok) throw new Error('Network response was not ok: ' + r.statusText);
            return r.json();
        })
        .then(data => {
            if (data.error) throw new Error(data.error);
            
            window.currentProject = data;
            localStorage.setItem('nt_active_project_slug', slug);
            ProjectManager.updateSidebarHighlight(slug);

            if (!keepSelection) {
                window.selectedFiles.clear();
                window.selectedTranslatedFiles.clear();
                ProjectManager.updateSelectAllButton();
            }

            const activeContent = document.getElementById('project-active-content');
            if (activeContent) activeContent.classList.remove('dn');
            
            const titleEl = document.getElementById('project-title');
            const descEl = document.getElementById('project-desc');
            if (titleEl) titleEl.textContent = data.name;
            if (descEl) descEl.textContent = data.description || 'Dự án không có mô tả';

            ProjectManager.renderProjectSources(data.sources || []);
            ProjectManager.renderProjectTranslated(data.translated || []);
            
            // Render 3-column file lists
            ProjectManager.renderFileList3Col(data.sources || []);
            ProjectManager.renderSpellcheckFileList3Col(data.sources || []);

            const editorIds = ['source-text', 'result-text', 'spell-source-text', 'spell-result-text'];
            editorIds.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            const tokenMini = document.getElementById('token-estimate-mini');
            if (tokenMini) tokenMini.classList.add('dn');
            window.currentProjectFile = null;
            
            setTimeout(() => {
                const workspaceEl = document.querySelector('[x-data*="activeTab"]');
                let currentTab = 'editor';
                if (workspaceEl && workspaceEl._x_dataStack) {
                    currentTab = Alpine.evaluate(workspaceEl, 'activeTab') || 'editor';
                }
                switchProjectTab(currentTab);
            }, 100);
            
            UiHelpers.showToast('Đã chọn: ' + data.name, 'success');
        })
        .catch(err => {
            console.error('selectProject error:', err);
            UiHelpers.showToast('Lỗi nạp dự án: ' + err.message, 'error');
        });
    },

    resetSelection() {
        window.selectedFiles.clear();
        window.selectedTranslatedFiles.clear();
        ProjectManager.updateSelectAllButton();
        ProjectManager.updateSelectAllTranslatedButton();
    },

    renderProjectSources(sources) {
        const el = document.getElementById('project-source-table-body');
        if (!el) return;
        if (!sources.length) { 
            el.innerHTML = '<tr><td colspan="5" class="pa3 tc silver i">Chưa có file nguồn</td></tr>'; 
            return; 
        }
        
        try {
            el.innerHTML = sources.map(f => {
                const esc = escapeHtml(f.name);
                const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
                const statusHtml = f.has_translation 
                    ? `<span class="f7 bg-washed-green green pa1 br2 fw6">✔️ Xong</span>`
                    : `<span class="f7 bg-washed-yellow gold pa1 br2 fw6">⏳ Chờ</span>`;
                
                return `<tr>
                    <td class="tc"><input type="checkbox" ${checked} onchange="ProjectManager.toggleProjectFile('${esc}',this.checked)"></td>
                    <td>
                        <div class="fw6 blue pointer underline-hover" onclick="EditorComponent.loadProjectFile('${esc}','sources')">${esc}</div>
                    </td>
                    <td class="f7 gray">${f.size_display || ''}</td>
                    <td>${statusHtml}</td>
                    <td class="tr">
                        <div class="flex justify-end gap-1">
                            <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();TranslationWorker.translateFileInProject('${esc}')" title="Dịch">🚀</button>
                            <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();ProjectManager.renameProjectFile('${esc}','sources')" title="Đổi tên">✏️</button>
                            <button class="ph2 pv1 f7 ba b--red red bg-white pointer hover-bg-washed-red br1" onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','sources')" title="Xóa">🗑️</button>
                        </div>
                    </td>
                </tr>`;
            }).join('');
            ProjectManager.updateSelectAllButton();
        } catch (err) {
            console.error('Error rendering sources:', err);
            el.innerHTML = `<tr><td colspan="5" class="pa3 tc red">Lỗi: ${err.message}</td></tr>`;
        }
    },

    renderProjectTranslated(translated) {
        const el = document.getElementById('project-translated-table-body');
        if (!el) return;

        if (!translated.length) {
            el.innerHTML = '<tr><td colspan="5" class="pa3 tc silver i">Chưa có file dịch</td></tr>';
            return;
        }

        el.innerHTML = translated.map(f => {
            const esc = escapeHtml(f.name);
            const checked = window.selectedTranslatedFiles.has(f.name) ? 'checked' : '';
            const status = (window.currentProject.file_status && window.currentProject.file_status[f.name]) || "Chờ";
            const isDone = status === "Xong";
            
            const statusHtml = isDone
                ? `<button class="pointer ph2 pv1 f7 bn white bg-green br2 shadow-1 hover-bg-dark-green fw6" onclick="event.stopPropagation();ProjectManager.updateFileStatus('${esc}', 'Chờ')" title="Đánh dấu chờ">✔️ Xong</button>`
                : `<button class="pointer ph2 pv1 f7 ba b--silver bg-white br2 gray hover-bg-near-white fw6" onclick="event.stopPropagation();ProjectManager.updateFileStatus('${esc}', 'Xong')" title="Đánh dấu xong">⏳ Chờ</button>`;

            return `<tr>
                <td class="tc"><input type="checkbox" ${checked} onchange="ProjectManager.toggleTranslatedFile('${esc}',this.checked)"></td>
                <td>
                    <div class="fw6 blue pointer underline-hover" onclick="EditorComponent.loadProjectFile('${esc}','translated')">${esc}</div>
                </td>
                <td class="f7 gray">${f.size_display || ''}</td>
                <td class="tc">${statusHtml}</td>
                <td class="tr">
                    <div class="flex justify-end gap-1">
                        <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();ProjectManager.renameProjectFile('${esc}','translated')" title="Đổi tên">✏️</button>
                        <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();ProjectManager.moveBackInProject('${esc}')" title="Trả về sources">↩</button>
                        <button class="ph2 pv1 f7 ba b--red red bg-white pointer hover-bg-washed-red br1" onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','translated')" title="Xóa">🗑️</button>
                    </div>
                </td>
            </tr>`;
        }).join('');
        ProjectManager.updateSelectAllTranslatedButton();
    },

    renderProjectSpellcheckSources(sources) {
        const el = document.getElementById('project-spellcheck-table-body');
        if (!el) return;
        if (!sources.length) { 
            el.innerHTML = '<tr><td colspan="5" class="pa3 tc silver i">Chưa có file nguồn</td></tr>'; 
            return; 
        }
        try {
            el.innerHTML = sources.map(f => {
                const esc = escapeHtml(f.name);
                const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
                const statusHtml = f.has_translation 
                    ? `<span class="f7 bg-washed-green green pa1 br2 fw6">✔️ Xong</span>`
                    : `<span class="f7 bg-washed-yellow gold pa1 br2 fw6">⏳ Chờ</span>`;
                return `<tr>
                    <td class="tc"><input type="checkbox" ${checked} onchange="ProjectManager.toggleProjectFile('${esc}',this.checked)"></td>
                    <td><div class="fw6 blue pointer underline-hover" onclick="EditorComponent.loadSpellcheckFile('${esc}')">${esc}</div></td>
                    <td class="f7 gray">${f.size_display || ''}</td>
                    <td>${statusHtml}</td>
                    <td class="tr">
                        <div class="flex justify-end gap-1">
                            <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();TranslationWorker.spellcheckFileInProject('${esc}')" title="Soát lỗi AI">🔤</button>
                            <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();ProjectManager.renameProjectFile('${esc}','sources')" title="Đổi tên">✏️</button>
                            <button class="ph2 pv1 f7 ba b--red red bg-white pointer hover-bg-washed-red br1" onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','sources')" title="Xóa">🗑️</button>
                        </div>
                    </td>
                </tr>`;
            }).join('');
        } catch (err) {
            console.error('Error:', err);
            el.innerHTML = '<tr><td colspan="5" class="pa3 tc red">Lỗi</td></tr>';
        }
        ProjectManager.renderSpellcheckedFiles();
    },

    renderSpellcheckedFiles() {
        const el = document.getElementById('project-spellchecked-table-body');
        if (!el || !window.currentProject) return;
        const slug = window.currentProject.slug;
        fetch(`/api/projects/${slug}/files/spelling`)
            .then(r => r.json())
            .then(files => {
                if (!files.length) {
                    el.innerHTML = '<tr><td colspan="3" class="pa3 tc silver i">Chưa có file đã soát</td></tr>';
                    return;
                }
                el.innerHTML = files.map(f => {
                    const esc = escapeHtml(f.name);
                    return `<tr>
                        <td><div class="fw6 blue pointer underline-hover" onclick="EditorComponent.loadSpellcheckFile('${esc}')">${esc}</div></td>
                        <td class="f7 gray">${f.size_display || ''}</td>
                        <td class="tr">
                            <div class="flex justify-end gap-1">
                                <button class="ph2 pv1 f7 ba b--red red bg-white pointer hover-bg-washed-red br1" onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','spelling')" title="Xóa">🗑️</button>
                            </div>
                        </td>
                    </tr>`;
                }).join('');
            })
            .catch(() => {
                el.innerHTML = '<tr><td colspan="3" class="pa3 tc silver i">Lỗi tải danh sách</td></tr>';
            });
    },

    toggleProjectFile(name, checked) {
        if (checked) window.selectedFiles.add(name); else window.selectedFiles.delete(name);
        ProjectManager.updateSelectAllButton();
    },

    toggleTranslatedFile(filename, checked) {
        if (checked) window.selectedTranslatedFiles.add(filename);
        else window.selectedTranslatedFiles.delete(filename);
        ProjectManager.updateSelectAllTranslatedButton();
    },

    updateSelectAllButton() {
        const chks = document.querySelectorAll('#chk-select-all-sources, #chk-select-all-spellcheck');
        const countSpans = document.querySelectorAll('#selected-files-count, #pm-selected-files-count, #pm-selected-spellcheck-count');
        const infoSpans = document.querySelectorAll('#pm-selected-files-info, #pm-selected-spellcheck-info');

        countSpans.forEach(countSpan => {
            if (window.selectedFiles.size > 0) {
                countSpan.textContent = `Đã chọn ${window.selectedFiles.size} tập tin`;
                countSpan.classList.remove('dn');
            } else {
                countSpan.classList.add('dn');
            }
        });
        
        infoSpans.forEach(infoSpan => {
            if (window.selectedFiles.size > 0) {
                infoSpan.textContent = `Đã chọn ${window.selectedFiles.size} tập tin`;
                infoSpan.classList.remove('dn');
            } else {
                infoSpan.classList.add('dn');
            }
        });

        if (chks.length > 0 && window.currentProject && window.currentProject.sources) {
            const isAllSelected = (window.selectedFiles.size > 0 && window.selectedFiles.size === window.currentProject.sources.length);
            const isIndeterminate = (window.selectedFiles.size > 0 && window.selectedFiles.size < window.currentProject.sources.length);
            chks.forEach(chk => {
                chk.checked = isAllSelected;
                chk.indeterminate = isIndeterminate;
            });
        }
    },

    updateSelectAllTranslatedButton() {
        const chk = document.getElementById('chk-select-all-translated');
        if (!chk || !window.currentProject) return;
        const total = (window.currentProject.translated || []).length;
        chk.checked = total > 0 && window.selectedTranslatedFiles.size === total;
        chk.indeterminate = window.selectedTranslatedFiles.size > 0 && window.selectedTranslatedFiles.size < total;
        const countEls = document.querySelectorAll('#selected-translated-count, #pm-selected-files-count');
        countEls.forEach(countEl => {
            if (window.selectedTranslatedFiles.size > 0) {
                countEl.textContent = `${window.selectedTranslatedFiles.size} đã chọn`;
                countEl.classList.remove('dn');
            } else {
                countEl.classList.add('dn');
            }
        });
    },

    selectAllProjectFiles() {
        if (!window.currentProject) return;
        const allSources = window.currentProject.sources || [];
        if (window.selectedFiles.size === allSources.length && allSources.length > 0) {
            window.selectedFiles.clear();
        } else {
            allSources.forEach(f => window.selectedFiles.add(f.name));
        }
        ProjectManager.updateSelectAllButton();
        ProjectManager.renderProjectSources(allSources);
        ProjectManager.renderProjectSpellcheckSources(allSources);
    },

    selectAllTranslatedFiles() {
        const chk = document.getElementById('chk-select-all-translated');
        const allChecked = chk && chk.checked;
        if (allChecked) {
            (window.currentProject.translated || []).forEach(f => window.selectedTranslatedFiles.add(f.name));
        } else {
            window.selectedTranslatedFiles.clear();
        }
        ProjectManager.renderProjectTranslated(window.currentProject.translated || []);
    },

    updateFileStatus(filename, status) {
        if (!window.currentProject || !window.currentProject.slug) return;
        fetch(`/api/projects/${window.currentProject.slug}/file-status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, status })
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            if (!window.currentProject.file_status) window.currentProject.file_status = {};
            window.currentProject.file_status[filename] = status;
            ProjectManager.renderProjectTranslated(window.currentProject.translated || []);
            ProjectManager.renderProjectSources(window.currentProject.sources || []);
        })
        .catch(err => {
            console.error('Error updating status:', err);
            UiHelpers.showToast('Lỗi cập nhật trạng thái: ' + err.message, 'error');
        });
    },

    uploadProjectFile() {
        if (!window.currentProject) { UiHelpers.showToast('Chưa chọn dự án!', 'error'); return; }
        const fileInput = document.getElementById('upload-source-file');
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        UiHelpers.showToast('📤 Đang tải file lên...', 'info');

        fetch(`/api/projects/${window.currentProject.slug}/upload`, {
            method: 'POST',
            body: formData
        }).then(r => r.json()).then(data => {
            if (data.success) {
                UiHelpers.showToast(`Đã tải lên: ${data.filename} (${data.size_display})`, 'success');
                ProjectManager.selectProject(window.currentProject.slug);
            } else {
                UiHelpers.showToast(data.error || 'Lỗi upload', 'error');
            }
            fileInput.value = '';
        }).catch(e => {
            UiHelpers.showToast(e.message, 'error');
            fileInput.value = '';
        });
    },

    showChunkConfig() {
        ModalManager.show('chunk-config-modal');
    },

    confirmChunking() {
        if (!window.currentProject) return;
        const size = document.getElementById('chunk-size-input').value;
        const type = document.querySelector('input[name="chunk-type"]:checked').value;
        
        if (window.selectedFiles.size === 0) {
            UiHelpers.showToast('Vui lòng chọn ít nhất 1 file để chia chunk!', 'warning');
            return;
        }
        
        UiHelpers.showToast('✂️ Đang chia chunk...', 'info');
        ModalManager.hide('chunk-config-modal');
        
        const files = Array.from(window.selectedFiles);
        
        Promise.all(files.map(filename => 
            fetch(`/api/projects/${window.currentProject.slug}/chunk/${filename}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ max_chars: parseInt(size) })
            }).then(r => r.json())
        )).then(results => {
            const failed = results.filter(r => !r.success);
            if (failed.length > 0) {
                UiHelpers.showToast(`Lỗi chia ${failed.length} file`, 'error');
            } else {
                UiHelpers.showToast(`Đã chia chunk thành công ${files.length} file`, 'success');
            }
            ProjectManager.selectProject(window.currentProject.slug);
        }).catch(e => {
            UiHelpers.showToast('Lỗi chia chunk: ' + e.message, 'error');
        });
    },

    async deleteProjectFile(filename, section) {
        if (!await showConfirm('Xóa vĩnh viễn "' + filename + '"?', { danger: true })) return;
        fetch(`/api/projects/${window.currentProject.slug}/file/${section}/${filename}`, {
            method: 'DELETE', headers: { 'Content-Type': 'application/json' }
        }).then(r => r.json()).then(() => {
            // Reload project trong projects tab workspace hoặc old workspace
            if (document.getElementById('projects-workspace-view') && document.getElementById('projects-workspace-view').style.display !== 'none') {
                ProjectManager.openProject(window.currentProject.slug);
            } else {
                ProjectManager.selectProject(window.currentProject.slug);
            }
        });
    },

    async renameProjectFile(filename, section) {
        if (!window.currentProject) return;
        const newName = await showPrompt('Đổi tên file thành:', filename);
        if (!newName || newName === filename) return;

        fetch(`/api/projects/${window.currentProject.slug}/rename`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_name: filename, new_name: newName, section: section })
        }).then(r => r.json()).then(data => {
            if (data.success) {
                UiHelpers.showToast(`Đã tải lên: ${data.filename} (${data.size_display})`, 'success');
                // Reload project trong projects tab workspace
                if (document.getElementById('projects-workspace-view') && !document.getElementById('projects-workspace-view').classList.contains('dn')) {
                    ProjectManager.openProject(window.currentProject.slug);
                } else {
                    ProjectManager.selectProject(window.currentProject.slug);
                }
            } else {
                UiHelpers.showToast(data.error || 'Lỗi đổi tên', 'error');
            }
        });
    },

    async moveBackInProject(filename) {
        if (!await showConfirm('Trả "' + filename + '" về sources?')) return;
        fetch(`/api/projects/${window.currentProject.slug}/move-back`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        }).then(r => r.json()).then(() => ProjectManager.selectProject(window.currentProject.slug));
    },

    mergeTranslatedFiles() {
        if (!window.currentProject) { UiHelpers.showToast('Chưa chọn dự án!', 'error'); return; }
        const translated = window.currentProject.translated || [];
        if (translated.length === 0) { UiHelpers.showToast('Chưa có file dịch để ghép!', 'warning'); return; }

        const slug = window.currentProject.slug;
        let filesToMerge;
        if (window.selectedTranslatedFiles.size > 0) {
            filesToMerge = Array.from(window.selectedTranslatedFiles);
        } else {
            filesToMerge = translated.map(f => f.name);
        }
        filesToMerge.sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));

        const outName = `${slug}.txt`;
        const btn = document.getElementById('btn-merge-translated');
        const originalText = btn.innerHTML;
        btn.innerHTML = '⏳ Đang ghép nối...';
        btn.disabled = true;

        fetch(`/api/projects/${slug}/merge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: filesToMerge, output_filename: outName })
        })
            .then(r => r.json())
            .then(data => {
                btn.innerHTML = originalText;
                btn.disabled = false;
                if (data.success) {
                    UiHelpers.showToast(`Ghép thành công ${filesToMerge.length} file vào: ${data.file}`, 'success');
                    ProjectManager.selectProject(window.currentProject.slug, true);
                } else {
                    UiHelpers.showToast('Lỗi ghép file: ' + (data.error || 'Unknown'), 'error');
                }
            })
            .catch(e => {
                btn.innerHTML = originalText;
                btn.disabled = false;
                UiHelpers.showToast('Lỗi mạng: ' + e.message, 'error');
            });
    },

    showCreateProjectDialog() {
        const genreSelect = document.getElementById('new-project-genre');
        fetch('/api/prompt-sets')
            .then(r => r.json())
            .then(data => {
                let opts = '<option value="">— Không chọn —</option>';
                if (data.genres) {
                    data.genres.forEach(g => {
                        opts += `<option value="${g.slug}">${g.name}</option>`;
                    });
                }
                genreSelect.innerHTML = opts;
            })
            .catch(() => {});
        document.getElementById('new-project-name').value = '';
        document.getElementById('new-project-desc').value = '';
        ModalManager.show('new-project-modal');
    },

    initProjectDialog() {
        if (!document.getElementById('new-project-modal')) return;

        document.getElementById('btn-cancel-project').addEventListener('click', () => {
            ModalManager.hide('new-project-modal');
        });

        document.getElementById('btn-confirm-new-project').addEventListener('click', () => {
            const name = document.getElementById('new-project-name').value.trim();
            if (!name) { UiHelpers.showToast('Tên dự án không được trống!', 'error'); return; }
            const desc = document.getElementById('new-project-desc').value.trim();
            const genre = document.getElementById('new-project-genre').value;

            fetch('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description: desc, genre })
            })
                .then(r => r.json())
                .then(data => {
                    ModalManager.hide('new-project-modal');
                    if (data.success) {
                        UiHelpers.showToast(`Đã tạo dự án "${name}"`, 'success');
                        ProjectManager.loadProjects();
                        ProjectManager.selectProject(data.slug);
                    } else {
                        UiHelpers.showToast(data.error || 'Lỗi tạo dự án', 'error');
                    }
                })
                .catch(e => UiHelpers.showToast(e.message, 'error'));
        });
    },

    showProjectInfoModal() {
        if (!window.currentProject) return;
        const p = window.currentProject;

        const nameEl = document.getElementById('proj-info-name');
        const descEl = document.getElementById('proj-info-desc');
        const genreEl = document.getElementById('proj-info-genre');
        const srcEl = document.getElementById('proj-info-src-count');
        const trEl = document.getElementById('proj-info-tr-count');
        const createdEl = document.getElementById('proj-info-created');

        if (nameEl) nameEl.value = p.name || '';
        if (descEl) descEl.value = p.description || '';
        if (genreEl) genreEl.value = p.slug || '';
        if (srcEl) srcEl.textContent = p.source_count ?? '—';
        if (trEl) trEl.textContent = p.translated_count ?? '—';
        if (createdEl) {
            const d = p.created_at ? new Date(p.created_at).toLocaleString('vi-VN') : '—';
            createdEl.textContent = d;
        }

        ModalManager.show('project-info-modal');
    },

    hideProjectInfoModal() {
        ModalManager.hide('project-info-modal');
    },

    saveProjectInfo() {
        if (!window.currentProject) return;
        const name = document.getElementById('proj-info-name').value.trim();
        const description = document.getElementById('proj-info-desc').value.trim();

        if (!name) { UiHelpers.showToast('Tên dự án không được trống!', 'error'); return; }

        fetch('/api/projects/' + window.currentProject.slug, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description })
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            window.currentProject.name = name;
            window.currentProject.description = description;
            const titleEl = document.getElementById('project-title');
            const descEl = document.getElementById('project-desc');
            if (titleEl) titleEl.textContent = name;
            if (descEl) descEl.textContent = description || 'Dự án không có mô tả';
            ProjectManager.loadProjects();
            ProjectManager.hideProjectInfoModal();
            UiHelpers.showToast('Đã cập nhật thông tin dự án!', 'success');
        })
        .catch(err => UiHelpers.showToast('Lỗi cập nhật: ' + err.message, 'error'));
    },

    archiveProjectFromModal() {
        ProjectManager.hideProjectInfoModal();
        ProjectManager.archiveProject();
    },

    deleteProjectFromModal() {
        ProjectManager.hideProjectInfoModal();
        ProjectManager.deleteCurrentProject();
    },

    archiveProject() {
        if (!window.currentProject) return;
        
        fetch('/api/projects/' + window.currentProject.slug + '/archive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strategy: 'check' })
        })
        .then(r => r.json())
        .then(async (data) => {
            if (data.error) throw new Error(data.error);
            
            let strategy = 'overwrite';
            if (data.exists) {
                const userChoice = await showConfirm('Bản lưu trữ đã tồn tại. Ghi đè? (Hủy = tạo bản sao)');
                strategy = userChoice ? 'overwrite' : 'copy';
            }
            
            UiHelpers.showToast('Đang tiến hành lưu trữ...', 'info');
            
            return fetch('/api/projects/' + window.currentProject.slug + '/archive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ strategy })
            });
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                UiHelpers.showToast('Lỗi lưu trữ: ' + data.error, 'error');
            } else {
                UiHelpers.showToast(data.message, 'success');
                window.currentProject = null;
                const activeContent = document.getElementById('project-active-content');
                if (activeContent) activeContent.classList.add('dn');
                ProjectManager.loadProjects();
            }
        })
        .catch(err => {
            UiHelpers.showToast('Lỗi: ' + err.message, 'error');
        });
    },

    async deleteCurrentProject() {
        if (!window.currentProject) return;
        if (!await showConfirm('Xóa VĨNH VIỄN dự án "' + window.currentProject.name + '"?', { danger: true })) return;
        fetch('/api/projects/' + window.currentProject.slug, { method: 'DELETE' })
            .then(r => r.json()).then(() => {
                window.currentProject = null;
                const activeContent = document.getElementById('project-active-content');
                if (activeContent) activeContent.classList.add('dn');
                ProjectManager.loadProjects();
            });
    },

    async restoreProject(filename) {
        if (!await showConfirm('Khôi phục dự án từ ' + filename + '?')) return;
        
        UiHelpers.showToast('Đang khôi phục...', 'info');
        fetch('/api/archive/restore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                UiHelpers.showToast('Lỗi khôi phục: ' + data.error, 'error');
            } else {
                UiHelpers.showToast('Khôi phục thành công!', 'success');
                ApiClient.loadArchiveList();
                ProjectManager.loadProjects();
            }
        });
    },

    async deleteArchive(filename) {
        if (!await showConfirm('Xóa VĨNH VIỄN bản lưu trữ ' + filename + '?', { danger: true })) return;
        
        fetch('/api/archive/' + filename, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                UiHelpers.showToast('Đã xóa ' + filename, 'success');
                ApiClient.loadArchiveList();
            } else {
                UiHelpers.showToast(data.error, 'error');
            }
        });
    },

    // ===== PROJECT MANAGEMENT FUNCTIONS =====

    createNewProject() {
        const bookTitle = document.getElementById('new-project-book-title').value.trim();
        const author = document.getElementById('new-project-author').value.trim();
        const genre = document.getElementById('new-project-genre-new').value;
        const description = document.getElementById('new-project-desc-new').value.trim();
        
        if (!bookTitle) {
            UiHelpers.showToast('Tên tác phẩm không được trống!', 'error');
            return;
        }
        
        fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ book_title: bookTitle, author, genre, description })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                UiHelpers.showToast(`Đã tạo dự án "${bookTitle}"`, 'success');
                document.getElementById('new-project-book-title').value = '';
                document.getElementById('new-project-author').value = '';
                document.getElementById('new-project-desc-new').value = '';
                ProjectManager.loadProjectCards();
            } else {
                UiHelpers.showToast(data.error || 'Lỗi tạo dự án', 'error');
            }
        })
        .catch(e => UiHelpers.showToast(e.message, 'error'));
    },

    loadProjectCards() {
        fetch('/api/projects')
        .then(r => r.json())
        .then(projects => {
            const container = document.getElementById('project-cards-container');
            if (!container) return;
            
            if (!projects.length) {
                container.innerHTML = '<div class="pa4 tc silver i">Chưa có dự án nào. Hãy tạo dự án mới!</div>';
                return;
            }
            
            container.innerHTML = projects.map(p => {
                const statusClass = p.status === 'Hoàn thành' ? 'done' : 'pending';
                const statusText = p.status || 'Đang thực hiện';
                const statusIcon = statusClass === 'done' ? '✅' : '⏳';
                const createdDate = p.created_at ? new Date(p.created_at).toLocaleDateString('vi-VN') : '—';
                
                return `
                <div class="project-card">
                    <div class="project-card-header">
                        <div class="flex-auto">
                            <h3 class="project-card-title pointer hover-blue" onclick="ProjectManager.openProject('${p.slug}')" style="cursor: pointer;">
                                ${escapeHtml(p.book_title || p.name)}
                            </h3>
                            ${p.author ? `<p class="project-card-author">${escapeHtml(p.author)}</p>` : ''}
                            ${p.description ? `<p class="project-card-desc">${escapeHtml(p.description)}</p>` : ''}
                        </div>
                        <div class="project-card-actions">
                            <button class="bn white bg-blue hover-bg-dark-blue fw6" onclick="ProjectManager.openProject('${p.slug}')">Mở dự án</button>
                            <button class="ba b--silver bg-white hover-bg-near-white" onclick="ProjectManager.exportProject('${p.slug}')">💾 Lưu trữ</button>
                            <button class="ba b--red red bg-white hover-bg-washed-red" onclick="ProjectManager.deleteProjectCard('${p.slug}')">🗑️ Xóa</button>
                        </div>
                    </div>
                    <div class="project-card-meta">
                        <span class="project-card-meta-item">📁 ${p.source_count || 0} files</span>
                        <span class="project-card-meta-item">✅ ${p.translated_count || 0} đã xong</span>
                        <span class="project-card-meta-item">📅 ${createdDate}</span>
                        ${p.genre ? `<span class="project-card-meta-item">📖 ${escapeHtml(p.genre)}</span>` : ''}
                        <span class="project-card-status ${statusClass}">${statusIcon} ${statusText}</span>
                    </div>
                </div>`;
            }).join('');
        })
        .catch(err => {
            console.error('Error loading project cards:', err);
            const container = document.getElementById('project-cards-container');
            if (container) container.innerHTML = '<div class="pa4 tc red">Lỗi tải danh sách dự án</div>';
        });
    },

    openProject(slug) {
        // Hiển thị workspace view trong tab Quản lý dự án
        const listView = document.getElementById('projects-list-view');
        const workspaceView = document.getElementById('projects-workspace-view');
        if (listView) listView.style.display = 'none';
        if (workspaceView) workspaceView.style.display = 'flex';
        
        // Load project data
        fetch('/api/projects/' + slug)
        .then(r => r.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            
            window.currentProject = data;
            localStorage.setItem('nt_active_project_slug', slug);
            
            // Update header
            const titleEl = document.getElementById('pm-project-title');
            const descEl = document.getElementById('pm-project-desc');
            if (titleEl) titleEl.textContent = data.name;
            if (descEl) descEl.textContent = data.description || 'Dự án không có mô tả';
            
            // Render file lists
            ProjectManager.renderPmFileList(data.sources || []);
            ProjectManager.renderPmSpellcheckFileList(data.sources || []);
            
            // Khôi phục trạng thái ẩn/hiện cột
            ProjectManager.restoreColumnStates();
            
            // Clear editors
            ['pm-source-text', 'pm-result-text', 'pm-spell-source-text', 'pm-spell-result-text'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            window.currentProjectFile = null;
            
            UiHelpers.showToast('Đã mở: ' + data.name, 'success');
        })
        .catch(err => {
            console.error('openProject error:', err);
            UiHelpers.showToast('Lỗi mở dự án: ' + err.message, 'error');
        });
    },
    
    backToList() {
        const listView = document.getElementById('projects-list-view');
        const workspaceView = document.getElementById('projects-workspace-view');
        if (listView) {
            listView.style.display = '';
            listView.classList.remove('dn');
        }
        if (workspaceView) {
            workspaceView.style.display = 'none';
        }
        
        window.currentProject = null;
        window.currentProjectFile = null;
        ProjectManager.loadProjectCards();
    },
    
    switchPmFileTab(tab) {
        const sourcesBtn = document.getElementById('pm-tab-sources');
        const translatedBtn = document.getElementById('pm-tab-translated');
        
        if (tab === 'sources') {
            if (sourcesBtn) sourcesBtn.classList.add('active');
            if (translatedBtn) translatedBtn.classList.remove('active');
            ProjectManager.renderPmFileList(window.currentProject?.sources || []);
        } else {
            if (sourcesBtn) sourcesBtn.classList.remove('active');
            if (translatedBtn) translatedBtn.classList.add('active');
            ProjectManager.renderPmTranslatedList(window.currentProject?.translated || []);
        }
    },
    
    renderPmTranslatedList(translated) {
        const el = document.getElementById('pm-file-list');
        if (!el) return;
        
        if (!translated || !translated.length) {
            el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file dịch</div>';
            return;
        }
        
        el.innerHTML = translated.map(f => {
            const esc = escapeHtml(f.name);
            const isActive = window.currentProjectFile === f.name;
            const checked = window.selectedTranslatedFiles.has(f.name) ? 'checked' : '';
            
            return `
            <div class="file-item-compact ${isActive ? 'active' : ''}" onclick="EditorComponent.loadPmProjectFile('${esc}','translated')">
                <div class="flex items-center gap-2">
                    <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleTranslatedFile('${esc}',this.checked)" class="flex-shrink-0">
                    <div class="flex-auto min-width-0">
                        <span class="file-item-name">${esc}</span>
                    </div>
                </div>
                <div class="file-item-meta">
                    <span>${f.size_display || ''}</span>
                    <div class="file-item-actions">
                        <button onclick="event.stopPropagation();ProjectManager.renameProjectFile('${esc}','translated')" title="Đổi tên">${Icons.rename}</button>
                        <button onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','translated')" title="Xóa" class="red">${Icons.delete}</button>
                    </div>
                </div>
            </div>`;
        }).join('');
    },
    
    switchPmSpellTab(tab) {
        const unspellcheckedBtn = document.getElementById('pm-tab-unspellchecked');
        const spellcheckedBtn = document.getElementById('pm-tab-spellchecked');
        
        if (tab === 'unspellchecked') {
            if (unspellcheckedBtn) unspellcheckedBtn.classList.add('active');
            if (spellcheckedBtn) spellcheckedBtn.classList.remove('active');
            ProjectManager.renderPmSpellcheckFileList(window.currentProject?.sources || []);
        } else {
            if (unspellcheckedBtn) unspellcheckedBtn.classList.remove('active');
            if (spellcheckedBtn) spellcheckedBtn.classList.add('active');
            ProjectManager.renderPmSpellcheckedList();
        }
    },
    
    renderPmSpellcheckedList() {
        const el = document.getElementById('pm-spellcheck-file-list');
        if (!el) return;
        
        if (!window.currentProject) {
            el.innerHTML = '<div class="pa3 tc silver i f7">Chưa chọn dự án</div>';
            return;
        }
        
        const slug = window.currentProject.slug;
        fetch(`/api/projects/${slug}/files/spelling`)
            .then(r => r.json())
            .then(files => {
                if (!files.length) {
                    el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file đã soát</div>';
                    return;
                }
                el.innerHTML = files.map(f => {
                    const esc = escapeHtml(f.name);
                    const isActive = window.currentProjectFile === f.name;
                    const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
                    
                    return `
                    <div class="file-item-compact ${isActive ? 'active' : ''}" onclick="EditorComponent.loadPmSpellcheckFile('${esc}')">
                        <div class="flex items-center gap-2">
                            <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile('${esc}',this.checked)" class="flex-shrink-0">
                            <div class="flex-auto min-width-0">
                                <span class="file-item-name">${esc}</span>
                            </div>
                        </div>
                        <div class="file-item-meta">
                            <span>${f.size_display || ''}</span>
                            <span class="file-done-dot" title="Đã soát xong"></span>
                            <div class="file-item-actions">
                                <button onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','spelling')" title="Xóa" class="red">${Icons.delete}</button>
                            </div>
                        </div>
                    </div>`;
                }).join('');
            })
            .catch(() => {
                el.innerHTML = '<div class="pa3 tc silver i f7">Lỗi tải danh sách</div>';
            });
    },
    
    showPmInfoTab(tabName) {
        const panels = ['style-guide', 'relationship', 'glossary', 'summary'];
        panels.forEach(p => {
            const el = document.getElementById('pm-info-panel-' + p);
            if (el) {
                if (p === tabName) {
                    el.style.display = '';
                    el.classList.remove('dn');
                } else {
                    el.style.display = 'none';
                    el.classList.add('dn');
                }
            }
        });
    },
    
    toggleColumn(colName) {
        // Map column name to element IDs
        const colMap = {
            'file': { sidebar: 'pm-file-sidebar', btn: 'btn-toggle-file-col' },
            'source': { editor: 'pm-source-editor', btn: 'btn-toggle-source-col' },
            'result': { editor: 'pm-result-editor', btn: 'btn-toggle-result-col' },
            'spell-file': { sidebar: 'pm-spell-file-sidebar', btn: 'btn-toggle-spell-file-col' },
            'spell-source': { editor: 'pm-spell-source-editor', btn: 'btn-toggle-spell-source-col' },
            'spell-result': { editor: 'pm-spell-result-editor', btn: 'btn-toggle-spell-result-col' }
        };
        
        const col = colMap[colName];
        if (!col) return;
        
        const el = document.getElementById(col.sidebar || col.editor);
        const btn = document.getElementById(col.btn);
        if (!el) return;
        
        const isHidden = el.style.display === 'none';
        
        // Toggle visibility
        el.style.display = isHidden ? '' : 'none';
        
        // Cập nhật trạng thái nút
        if (btn) {
            btn.classList.toggle('active', isHidden);
        }
        
        // Lưu trạng thái
        localStorage.setItem(`nt_col_${colName}_hidden`, !isHidden);
        
        // Cập nhật layout cho tất cả cột
        ProjectManager.updateColumnLayout();
    },
    
    updateColumnLayout() {
        // Xử lý cả tab Biên tập và Kiểm chính tả
        const containers = [
            { sidebar: 'pm-file-sidebar', name: 'editor' },
            { sidebar: 'pm-spell-file-sidebar', name: 'spellcheck' }
        ];
        
        containers.forEach(({ sidebar: sidebarId }) => {
            const sidebar = document.getElementById(sidebarId);
            if (!sidebar) return;
            
            const editorContainer = sidebar.closest('.workspace-layout-3col');
            if (!editorContainer) return;
            
            const editorsContainer = editorContainer.querySelector('.editors-container-2col');
            const editorPanes = editorContainer.querySelectorAll('.editor-pane-3col');
            
            if (!sidebar || !editorsContainer) return;
            
            // Đếm số cột đang hiện
            const isSidebarVisible = sidebar.style.display !== 'none';
            const visibleEditorPanes = Array.from(editorPanes).filter(p => p.style.display !== 'none');
            const visibleCount = (isSidebarVisible ? 1 : 0) + visibleEditorPanes.length;
            
            if (visibleCount === 0) return;
            
            // Cập nhật width cho sidebar
            if (isSidebarVisible) {
                if (visibleCount === 1) {
                    sidebar.style.width = '100%';
                } else if (visibleCount === 2) {
                    sidebar.style.width = '50%';
                } else {
                    sidebar.style.width = '25%';
                }
            }
            
            // Cập nhật width cho editor panes
            if (visibleEditorPanes.length === 1) {
                visibleEditorPanes[0].style.flex = '1';
            } else if (visibleEditorPanes.length === 2) {
                visibleEditorPanes.forEach(pane => {
                    pane.style.flex = '1';
                });
            }
        });
    },
    
    restoreColumnStates() {
        const columns = ['file', 'source', 'result', 'spell-file', 'spell-source', 'spell-result'];
        columns.forEach(col => {
            const isHidden = localStorage.getItem(`nt_col_${col}_hidden`) === 'true';
            if (isHidden) {
                const colMap = {
                    'file': { sidebar: 'pm-file-sidebar', btn: 'btn-toggle-file-col' },
                    'source': { editor: 'pm-source-editor', btn: 'btn-toggle-source-col' },
                    'result': { editor: 'pm-result-editor', btn: 'btn-toggle-result-col' },
                    'spell-file': { sidebar: 'pm-spell-file-sidebar', btn: 'btn-toggle-spell-file-col' },
                    'spell-source': { editor: 'pm-spell-source-editor', btn: 'btn-toggle-spell-source-col' },
                    'spell-result': { editor: 'pm-spell-result-editor', btn: 'btn-toggle-spell-result-col' }
                };
                const c = colMap[col];
                if (c) {
                    const el = document.getElementById(c.sidebar || c.editor);
                    const btn = document.getElementById(c.btn);
                    if (el) el.style.display = 'none';
                    if (btn) btn.classList.remove('active');
                }
            }
        });
    },
    
    showPmPromptTab(tabName) {
        const panels = ['main', 'summary', 'relationships', 'glossary', 'chinh-ta'];
        panels.forEach(p => {
            const el = document.getElementById('pm-prompt-panel-' + p);
            if (el) {
                if (p === tabName) {
                    el.style.display = '';
                    el.classList.remove('dn');
                } else {
                    el.style.display = 'none';
                    el.classList.add('dn');
                }
            }
        });
    },

    exportProject(slug) {
        UiHelpers.showToast('Đang tạo file sao lưu...', 'info');
        window.location.href = `/api/projects/${slug}/export`;
    },

    importProject() {
        const fileInput = document.getElementById('import-project-file');
        const file = fileInput.files[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append('file', file);
        
        UiHelpers.showToast('Đang nhập dự án...', 'info');
        
        fetch('/api/projects/import', {
            method: 'POST',
            body: formData
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                UiHelpers.showToast(`Đã nhập dự án "${data.slug}"`, 'success');
                ProjectManager.loadProjectCards();
            } else {
                UiHelpers.showToast(data.error || 'Lỗi nhập dự án', 'error');
            }
            fileInput.value = '';
        })
        .catch(e => {
            UiHelpers.showToast(e.message, 'error');
            fileInput.value = '';
        });
    },

    async deleteProjectCard(slug) {
        if (!await showConfirm('Xóa VĨNH VIỄN dự án "' + slug + '"?', { danger: true })) return;
        
        fetch('/api/projects/' + slug, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                UiHelpers.showToast('Đã xóa dự án', 'success');
                
                if (window.currentProject && window.currentProject.slug === slug) {
                    window.currentProject = null;
                    localStorage.removeItem('nt_active_project_slug');
                    const activeContent = document.getElementById('project-active-content');
                    if (activeContent) activeContent.classList.add('dn');
                }
                
                ProjectManager.loadProjectCards();
            } else {
                UiHelpers.showToast(data.error || 'Lỗi xóa dự án', 'error');
            }
        });
    },

    // ===== 3-COLUMN FILE LIST RENDERING =====

    renderFileList3Col(sources) {
        const el = document.getElementById('file-list-3col');
        if (!el) return;
        
        if (!sources || !sources.length) {
            el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file nguồn</div>';
            return;
        }
        
        el.innerHTML = sources.map(f => {
            const esc = escapeHtml(f.name);
            const isActive = window.currentProjectFile === f.name;
            const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
            const doneIcon = f.has_translation ? '<span class="green" title="Đã dịch xong">✔️</span>' : '';
            
            const isDirty = isActive && DirtyState.isDirty('result-text');
            const dirtyIndicator = isDirty ? '<span class="red fw6 ml1" title="Có thay đổi chưa lưu">*</span>' : '';
            
            return `
            <div class="file-item-compact ${isActive ? 'active' : ''}" onclick="EditorComponent.loadProjectFile('${esc}','sources')">
                <div class="flex items-start gap-2">
                    <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile('${esc}',this.checked)" class="mt1">
                    <div class="flex-auto">
                        <div class="file-item-name">
                            ${esc}${dirtyIndicator}
                            ${doneIcon}
                        </div>
                        <div class="file-item-meta">
                            <span>${f.size_display || ''}</span>
                            <div class="file-item-actions">
                                <button onclick="event.stopPropagation();TranslationWorker.translateFileInProject('${esc}')" title="Dịch">🚀</button>
                                <button onclick="event.stopPropagation();ProjectManager.renameProjectFile('${esc}','sources')" title="Đổi tên">✏️</button>
                                <button onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','sources')" title="Xóa" class="red">🗑️</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
        }).join('');
        
        ProjectManager.updateSelectAllButton();
    },

    renderSpellcheckFileList3Col(sources) {
        const el = document.getElementById('spellcheck-file-list-3col');
        if (!el) return;
        
        if (!sources || !sources.length) {
            el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file</div>';
            return;
        }
        
        el.innerHTML = sources.map(f => {
            const esc = escapeHtml(f.name);
            const isActive = window.currentProjectFile === f.name;
            const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
            const status = (window.currentProject.file_status && window.currentProject.file_status[f.name]) || "Chờ";
            const statusIcon = status === "Xong" 
                ? '<span class="status-badge done">✔️ Xong</span>'
                : '<span class="status-badge pending">⏳ Chờ</span>';
            
            return `
            <div class="file-item-compact ${isActive ? 'active' : ''}" onclick="EditorComponent.loadSpellcheckFile('${esc}')">
                <div class="flex items-start gap-2">
                    <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile('${esc}',this.checked)" class="mt1">
                    <div class="flex-auto">
                        <div class="file-item-name">${esc}</div>
                        <div class="file-item-meta">
                            <span>${f.size_display || ''}</span>
                            ${statusIcon}
                            <div class="file-item-actions">
                                <button onclick="event.stopPropagation();TranslationWorker.spellcheckFileInProject('${esc}')" title="Soát lỗi AI">🔤</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
        }).join('');
    },

    // ===== DRAG AND DROP UPLOAD =====

    initDragDrop() {
        const sidebar = document.querySelector('.file-list-sidebar');
        if (!sidebar) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            sidebar.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        sidebar.addEventListener('dragenter', () => {
            sidebar.classList.add('drag-over');
        });

        sidebar.addEventListener('dragleave', (e) => {
            if (!sidebar.contains(e.relatedTarget)) {
                sidebar.classList.remove('drag-over');
            }
        });

        sidebar.addEventListener('drop', (e) => {
            sidebar.classList.remove('drag-over');
            
            if (!window.currentProject) {
                UiHelpers.showToast('Vui lòng chọn dự án trước!', 'warning');
                return;
            }

            const files = e.dataTransfer.files;
            if (!files.length) return;

            Array.from(files).forEach(file => {
                ProjectManager.uploadSingleFile(file);
            });
        });
    },

    async uploadSingleFile(file) {
        if (!window.currentProject) return;

        const formData = new FormData();
        formData.append('file', file);

        UiHelpers.showToast(`📤 Đang tải lên: ${file.name}...`, 'info');

        try {
            const response = await fetch(`/api/projects/${window.currentProject.slug}/upload`, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                UiHelpers.showToast(`Đã tải lên: ${data.filename} (${data.size_display})`, 'success');
                ProjectManager.selectProject(window.currentProject.slug);
            } else {
                UiHelpers.showToast(data.error || 'Lỗi upload', 'error');
            }
        } catch (err) {
            UiHelpers.showToast('Lỗi upload: ' + err.message, 'error');
        }
    },
    
    // ===== PROJECT MANAGEMENT WORKSPACE RENDERING =====
    
    renderPmFileList(sources) {
        const el = document.getElementById('pm-file-list');
        if (!el) return;
        
        if (!sources || !sources.length) {
            el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file nguồn</div>';
            return;
        }
        
        el.innerHTML = sources.map(f => {
            const esc = escapeHtml(f.name);
            const isActive = window.currentProjectFile === f.name;
            const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
            const doneDot = f.has_translation ? '<span class="file-done-dot" title="Đã dịch xong"></span>' : '';
            const isDirty = isActive && DirtyState.isDirty('pm-result-text');
            const dirtyIndicator = isDirty ? '<span class="red fw6 ml1" title="Có thay đổi chưa lưu">*</span>' : '';
            
            return `
            <div class="file-item-compact ${isActive ? 'active' : ''}" onclick="EditorComponent.loadPmProjectFile('${esc}','sources')">
                <div class="flex items-center gap-2">
                    <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile('${esc}',this.checked)" class="flex-shrink-0">
                    <div class="flex-auto min-width-0">
                        <span class="file-item-name">${esc}${dirtyIndicator}</span>
                    </div>
                </div>
                <div class="file-item-meta">
                    <span>${f.size_display || ''}</span>
                    ${doneDot}
                    <div class="file-item-actions">
                        <button onclick="event.stopPropagation();TranslationWorker.translateFileInProject('${esc}')" title="Dịch">${Icons.translate}</button>
                        <button onclick="event.stopPropagation();ProjectManager.renameProjectFile('${esc}','sources')" title="Đổi tên">${Icons.rename}</button>
                        <button onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','sources')" title="Xóa" class="red">${Icons.delete}</button>
                    </div>
                </div>
            </div>`;
        }).join('');
    },
    
    renderPmSpellcheckFileList(sources) {
        const el = document.getElementById('pm-spellcheck-file-list');
        if (!el) return;
        
        if (!sources || !sources.length) {
            el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file</div>';
            return;
        }
        
        el.innerHTML = sources.map(f => {
            const esc = escapeHtml(f.name);
            const isActive = window.currentProjectFile === f.name;
            const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
            const status = (window.currentProject.file_status && window.currentProject.file_status[f.name]) || "Chờ";
            const doneDot = status === "Xong" ? '<span class="file-done-dot" title="Đã soát xong"></span>' : '';
            
            return `
            <div class="file-item-compact ${isActive ? 'active' : ''}" onclick="EditorComponent.loadPmSpellcheckFile('${esc}')">
                <div class="flex items-center gap-2">
                    <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile('${esc}',this.checked)" class="flex-shrink-0">
                    <div class="flex-auto min-width-0">
                        <span class="file-item-name">${esc}</span>
                    </div>
                </div>
                <div class="file-item-meta">
                    <span>${f.size_display || ''}</span>
                    ${doneDot}
                    <div class="file-item-actions">
                        <button onclick="event.stopPropagation();TranslationWorker.spellcheckFileInProject('${esc}')" title="Soát lỗi AI">${Icons.spellcheck}</button>
                    </div>
                </div>
            </div>`;
        }).join('');
    }
};

window.ProjectManager = ProjectManager;
