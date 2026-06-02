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
    // ===== PROJECT CARD FUNCTIONS =====
    
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
                ProjectManager.openProject(window.currentProject.slug);
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
