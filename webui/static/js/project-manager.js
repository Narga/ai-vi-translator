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
        const editor = document.getElementById('pm-result-text');
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

// Column map for toggle/restore
const COL_MAP = {
    'file': { sidebar: 'pm-file-sidebar', btn: 'btn-toggle-file-col' },
    'source': { editor: 'pm-source-editor', btn: 'btn-toggle-source-col' },
    'result': { editor: 'pm-result-editor', btn: 'btn-toggle-result-col' },
    'spell-file': { sidebar: 'pm-spell-file-sidebar', btn: 'btn-toggle-spell-file-col' },
    'spell-source': { editor: 'pm-spell-source-editor', btn: 'btn-toggle-spell-source-col' },
    'spell-result': { editor: 'pm-spell-result-editor', btn: 'btn-toggle-spell-result-col' }
};

const ProjectManager = {
    // ===== PROJECT CARD FUNCTIONS =====
    
    async refreshProjectCards(options = {}) {
        const btn = document.getElementById('btn-refresh-projects');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '↻ Đang tải...';
        }
        
        try {
            await this.loadProjectCards();
            if (options.showToast !== false) {
                UiHelpers.showToast('Đã làm mới danh sách dự án', 'success');
            }
        } catch (error) {
            console.error(error);
            if (options.showToast !== false) {
                UiHelpers.showToast('Lỗi làm mới: ' + error.message, 'error');
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '↻ Làm mới';
            }
        }
    },

    loadProjectCards() {
        return fetch('/api/projects')
        .then(r => r.json())
        .then(projects => {
            const container = document.getElementById('project-cards-container');
            if (!container) return;
            
            if (!projects.length) {
                container.innerHTML = '<div class="pa4 tc silver i">Chưa có dự án nào. Hãy tạo dự án mới!</div>';
                return;
            }
            
            container.innerHTML = ''; // Clear current cards

            const template = document.getElementById('tpl-project-card');
            if (!template) {
                console.error('Template tpl-project-card not found');
                return;
            }

            projects.forEach(p => {
                const statusClass = p.status === 'Hoàn thành' ? 'done' : 'pending';
                const statusText = p.status || 'Đang thực hiện';
                const statusIcon = statusClass === 'done' ? '✅' : '⏳';
                const createdDate = p.created_at ? new Date(p.created_at).toLocaleDateString('vi-VN') : '—';
                
                const clone = template.content.cloneNode(true);
                
                // Title
                const titleEl = clone.querySelector('.js-title');
                titleEl.textContent = p.book_title || p.name;
                titleEl.onclick = () => ProjectManager.openProject(p.slug);
                
                // Author
                const authorEl = clone.querySelector('.js-author');
                if (p.author) {
                    authorEl.textContent = p.author;
                } else {
                    authorEl.style.display = 'none';
                }
                
                // Description
                const descEl = clone.querySelector('.js-desc');
                if (p.description) {
                    descEl.textContent = p.description;
                } else {
                    descEl.style.display = 'none';
                }
                
                // Buttons
                clone.querySelector('.js-btn-open').onclick = () => ProjectManager.openProject(p.slug);
                clone.querySelector('.js-btn-archive').onclick = () => ProjectManager.archiveProjectFromList(p.slug);
                clone.querySelector('.js-btn-export').onclick = () => ProjectManager.exportProject(p.slug);
                clone.querySelector('.js-btn-delete').onclick = () => ProjectManager.deleteProjectCard(p.slug);
                
                // Meta
                clone.querySelector('.js-meta-files').textContent = `📁 ${p.source_count || 0} files`;
                clone.querySelector('.js-meta-translated').textContent = `✅ ${p.translated_count || 0} đã xong`;
                clone.querySelector('.js-meta-date').textContent = `📅 ${createdDate}`;
                
                const genreEl = clone.querySelector('.js-meta-genre');
                if (p.genre) {
                    genreEl.textContent = `📖 ${p.genre}`;
                    genreEl.style.display = '';
                }
                
                // Status
                const statusEl = clone.querySelector('.js-status');
                statusEl.textContent = `${statusIcon} ${statusText}`;
                statusEl.className = `project-card-status ${statusClass}`;
                
                container.appendChild(clone);
            });
        })
        .catch(err => {
            console.error('Error loading project cards:', err);
            const container = document.getElementById('project-cards-container');
            if (container) container.innerHTML = '<div class="pa4 tc red">Lỗi tải danh sách dự án</div>';
            throw err;
        });
    },

    createNewProject() {
        const bookTitle = document.getElementById('new-project-book-title')?.value?.trim() || '';
        const author = document.getElementById('new-project-author')?.value?.trim() || '';
        const genre = document.getElementById('new-project-genre-new')?.value?.trim() || '';
        const description = document.getElementById('new-project-desc-new')?.value?.trim() || '';

        if (!bookTitle) {
            UiHelpers.showToast('Chưa nhập tên tác phẩm', 'error');
            return;
        }

        fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ book_title: bookTitle, author, genre, description })
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
            UiHelpers.showToast('Đã tạo dự án: ' + (data.name || bookTitle), 'success');
            // Clear form
            ['new-project-book-title', 'new-project-author', 'new-project-desc-new'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            const genreEl = document.getElementById('new-project-genre-new');
            if (genreEl) genreEl.value = '';
            // Reload cards and open new project
            ProjectManager.loadProjectCards();
            if (data.slug) ProjectManager.openProject(data.slug);
        })
        .catch(e => UiHelpers.showToast('Lỗi tạo dự án: ' + e.message, 'error'));
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
            
            // Khởi tạo drag-and-drop cho sidebar
            setTimeout(() => ProjectManager.initDragDrop(), 100);
            
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
    
    _showPanel(prefix, panels, tabName) {
        panels.forEach(p => {
            const el = document.getElementById(prefix + p);
            if (el) {
                if (p === tabName) { el.style.display = ''; el.classList.remove('dn'); }
                else { el.style.display = 'none'; el.classList.add('dn'); }
            }
        });
    },

    showPmInfoTab(tabName) {
        this._showPanel('pm-info-panel-', ['style-guide', 'relationship', 'glossary', 'summary'], tabName);
    },
    
    toggleColumn(colName) {
        const col = COL_MAP[colName];
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
                const c = COL_MAP[col];
                if (c) {
                    const el = document.getElementById(c.sidebar || c.editor);
                    const btn = document.getElementById(c.btn);
                    if (el) el.style.display = 'none';
                    if (btn) btn.classList.remove('active');
                }
            }
        });
    },
    
    // ===== FILE SELECTION FUNCTIONS =====
    
    toggleProjectFile(name, checked) {
        if (checked) window.selectedFiles.add(name);
        else window.selectedFiles.delete(name);
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

    resetSelection() {
        window.selectedFiles.clear();
        window.selectedTranslatedFiles.clear();
        ProjectManager.updateSelectAllButton();
        ProjectManager.updateSelectAllTranslatedButton();
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
        ProjectManager.renderPmFileList(allSources);
        ProjectManager.renderPmSpellcheckFileList(allSources);
    },

    showPmPromptTab(tabName) {
        this._showPanel('pm-prompt-panel-', ['main', 'summary', 'relationships', 'glossary', 'chinh-ta'], tabName);
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

    // ===== FILE OPERATIONS =====

    async deleteProjectFile(filename, section) {
        if (!await showConfirm('Xóa vĩnh viễn "' + filename + '"?', { danger: true })) return;
        fetch(`/api/projects/${window.currentProject.slug}/file/${section}/${filename}`, {
            method: 'DELETE', headers: { 'Content-Type': 'application/json' }
        }).then(r => r.json()).then(() => {
            ProjectManager.openProject(window.currentProject.slug);
        });
    },

    async deleteSelectedSpellFiles() {
        const selected = window.selectedFiles;
        if (!selected || selected.size === 0) {
            UiHelpers.showToast('Chưa chọn tập tin nào', 'error');
            return;
        }
        const count = selected.size;
        if (!await showConfirm('Xóa vĩnh viễn ' + count + ' tập tin đã chọn?', { danger: true })) return;
        const slug = window.currentProject.slug;
        const promises = [...selected].map(filename =>
            fetch(`/api/projects/${slug}/file/spelling/${filename}`, {
                method: 'DELETE', headers: { 'Content-Type': 'application/json' }
            }).then(r => r.json())
        );
        Promise.all(promises).then(() => {
            selected.clear();
            ProjectManager.openProject(slug);
            UiHelpers.showToast('Đã xóa ' + count + ' tập tin', 'success');
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
                UiHelpers.showToast('Đã đổi tên file thành công', 'success');
                ProjectManager.openProject(window.currentProject.slug);
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
        }).then(r => r.json()).then(() => ProjectManager.openProject(window.currentProject.slug));
    },

    // ===== 3-COLUMN FILE LIST RENDERING =====



    // ===== DRAG AND DROP UPLOAD =====

    initDragDrop() {
        // Khởi tạo drag-and-drop cho tất cả sidebar hiện có
        // Gọi lại sau khi mở project để đảm bảo sidebar đã render
        const sidebars = document.querySelectorAll('.file-list-sidebar');
        
        sidebars.forEach(sidebar => {
            // Tránh gắn event listener nhiều lần
            if (sidebar.dataset.dragDropInit) return;
            sidebar.dataset.dragDropInit = 'true';

            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                sidebar.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                });
            });

            sidebar.addEventListener('dragenter', (e) => {
                e.preventDefault();
                sidebar.classList.add('drag-over');
            });

            sidebar.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'copy';
            });

            sidebar.addEventListener('dragleave', (e) => {
                e.preventDefault();
                if (!sidebar.contains(e.relatedTarget)) {
                    sidebar.classList.remove('drag-over');
                }
            });

            sidebar.addEventListener('drop', (e) => {
                e.preventDefault();
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

    uploadProjectFile() {
        if (!window.currentProject) {
            UiHelpers.showToast('Chưa chọn dự án!', 'error');
            return;
        }
        
        // Tìm input file đang active (có thể là pm-upload-source-file hoặc pm-upload-spell-file)
        const fileInput = document.getElementById('pm-upload-source-file') || 
                          document.getElementById('pm-upload-spell-file');
        if (!fileInput) return;
        
        const files = fileInput.files;
        if (!files.length) return;
        
        Array.from(files).forEach(file => {
            ProjectManager.uploadSingleFile(file);
        });
        
        // Reset input
        fileInput.value = '';
    },
    
    // ===== PROJECT MANAGEMENT WORKSPACE RENDERING =====
    
    // Generic file item renderer
    _renderFileItems(el, sources, options) {
        if (!el) return;
        if (!sources || !sources.length) {
            el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file</div>';
            return;
        }
        el.innerHTML = sources.map(f => {
            const esc = escapeHtml(f.name);
            const isActive = window.currentProjectFile === f.name;
            const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
            const dot = options.getDot ? options.getDot(f, isActive) : '';
            const dirty = options.getDirty ? options.getDirty(f, isActive) : '';
            const actions = options.getActions(esc);
            return `
            <div class="file-item-compact ${isActive ? 'active' : ''}" onclick="${options.getOnclick(esc)}">
                <div class="flex items-center gap-2">
                    <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile('${esc}',this.checked)" class="flex-shrink-0">
                    <div class="flex-auto min-width-0">
                        <span class="file-item-name">${esc}${dirty}</span>
                    </div>
                </div>
                <div class="file-item-meta">
                    <span>${f.size_display || ''}</span>
                    ${dot}
                    <div class="file-item-actions">${actions}</div>
                </div>
            </div>`;
        }).join('');
    },

    renderPmFileList(sources) {
        this._renderFileItems(document.getElementById('pm-file-list'), sources, {
            getOnclick: esc => `EditorComponent.loadPmProjectFile('${esc}','sources')`,
            getDirty: (f, isActive) => isActive && DirtyState.isDirty('pm-result-text') ? '<span class="red fw6 ml1">*</span>' : '',
            getDot: f => f.has_translation ? '<span class="file-done-dot" title="Đã dịch xong"></span>' : '',
            getActions: esc => `
                <button onclick="event.stopPropagation();TranslationWorker.translateFileInProject('${esc}')" title="Dịch">${Icons.translate}</button>
                <button onclick="event.stopPropagation();ProjectManager.renameProjectFile('${esc}','sources')" title="Đổi tên">${Icons.rename}</button>
                <button onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','sources')" title="Xóa" class="red">${Icons.delete}</button>`
        });
    },

    renderPmSpellcheckFileList(sources) {
        this._renderFileItems(document.getElementById('pm-spellcheck-file-list'), sources, {
            getOnclick: esc => `EditorComponent.loadPmSpellcheckFile('${esc}')`,
            getDot: f => {
                const status = (window.currentProject.file_status && window.currentProject.file_status[f.name]) || 'Chờ';
                return status === 'Xong' ? '<span class="file-done-dot" title="Đã soát xong"></span>' : '<span class="silver f8">Chờ</span>';
            },
            getActions: esc => `
                <button onclick="event.stopPropagation();TranslationWorker.spellcheckFileInProject('${esc}')" title="Soát lỗi AI">${Icons.spellcheck}</button>`
        });
    },

    // ===== PROJECT INFO MODAL =====
    showProjectInfoModal() {
        if (!window.currentProject) return;
        const p = window.currentProject;
        const nameEl = document.getElementById('proj-info-name');
        const descEl = document.getElementById('proj-info-desc');
        const genreEl = document.getElementById('proj-info-genre');
        const srcCountEl = document.getElementById('proj-info-src-count');
        const trCountEl = document.getElementById('proj-info-tr-count');
        const createdEl = document.getElementById('proj-info-created');
        if (nameEl) nameEl.value = p.name || '';
        if (descEl) descEl.value = p.description || '';
        if (genreEl) genreEl.value = p.genre || '';
        if (srcCountEl) srcCountEl.textContent = (p.sources || []).length;
        if (trCountEl) trCountEl.textContent = (p.translated || []).length;
        if (createdEl) createdEl.textContent = p.created_at || '—';
        ModalManager.show('project-info-modal');
    },

    hideProjectInfoModal() {
        ModalManager.hide('project-info-modal');
    },

    saveProjectInfo() {
        if (!window.currentProject) return;
        const name = document.getElementById('proj-info-name')?.value?.trim();
        const description = document.getElementById('proj-info-desc')?.value?.trim() || '';
        const genre = document.getElementById('proj-info-genre')?.value?.trim() || '';
        if (!name) { UiHelpers.showToast('Tên dự án không được trống', 'error'); return; }
        fetch(`/api/projects/${window.currentProject.slug}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, genre })
        }).then(r => r.json()).then(data => {
            if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
            UiHelpers.showToast('Đã cập nhật thông tin dự án', 'success');
            ProjectManager.hideProjectInfoModal();
            ProjectManager.openProject(window.currentProject.slug);
        }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
    },

    archiveProjectFromModal() {
        if (!window.currentProject) return;
        const slug = window.currentProject.slug;
        // Kiểm tra archive đã tồn tại chưa
        fetch(`/api/projects/${slug}/archive`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strategy: 'check' })
        }).then(r => r.json()).then(data => {
            if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
            if (data.exists) {
                // Archive đã tồn tại → hỏi overwrite hay copy
                showConfirm('Bản lưu trữ đã tồn tại. Ghi đè?', { confirmText: 'Ghi đè', cancelText: 'Tạo bản mới' }).then(overwrite => {
                    const strategy = overwrite ? 'overwrite' : 'copy';
                    fetch(`/api/projects/${slug}/archive`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ strategy })
                    }).then(r => r.json()).then(d => {
                        if (d.error) { UiHelpers.showToast(d.error, 'error'); return; }
                        UiHelpers.showToast('Đã lưu trữ dự án', 'success');
                        ProjectManager.hideProjectInfoModal();
                        ProjectManager.backToList();
                        ProjectManager.loadProjectCards();
                    }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
                });
            } else {
                // Chưa có archive → tạo mới
                fetch(`/api/projects/${slug}/archive`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ strategy: 'overwrite' })
                }).then(r => r.json()).then(d => {
                    if (d.error) { UiHelpers.showToast(d.error, 'error'); return; }
                    UiHelpers.showToast('Đã lưu trữ dự án', 'success');
                    ProjectManager.hideProjectInfoModal();
                    ProjectManager.backToList();
                    ProjectManager.loadProjectCards();
                }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
            }
        }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
    },

    deleteProjectFromModal() {
        if (!window.currentProject) return;
        showConfirm('XÓA VĨNH VIỄN dự án "' + window.currentProject.name + '"? KHÔNG THỂ KHÔI PHỤC!', { danger: true }).then(ok => {
            if (!ok) return;
            fetch(`/api/projects/${window.currentProject.slug}`, { method: 'DELETE' })
                .then(r => r.json()).then(data => {
                    if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
                    UiHelpers.showToast('Đã xóa dự án', 'success');
                    ProjectManager.hideProjectInfoModal();
                    ProjectManager.backToList();
                    ProjectManager.loadProjectCards();
                }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
        });
    },

    archiveProjectFromList(slug) {
        // Kiểm tra archive đã tồn tại chưa
        fetch(`/api/projects/${slug}/archive`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strategy: 'check' })
        }).then(r => r.json()).then(data => {
            if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
            if (data.exists) {
                // Archive đã tồn tại → hỏi overwrite hay copy
                showConfirm('Bản lưu trữ đã tồn tại. Ghi đè?', { confirmText: 'Ghi đè', cancelText: 'Tạo bản mới' }).then(overwrite => {
                    const strategy = overwrite ? 'overwrite' : 'copy';
                    fetch(`/api/projects/${slug}/archive`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ strategy })
                    }).then(r => r.json()).then(d => {
                        if (d.error) { UiHelpers.showToast(d.error, 'error'); return; }
                        UiHelpers.showToast('Đã lưu trữ dự án', 'success');
                        ProjectManager.loadProjectCards();
                    }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
                });
            } else {
                // Chưa có archive → tạo mới
                fetch(`/api/projects/${slug}/archive`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ strategy: 'overwrite' })
                }).then(r => r.json()).then(d => {
                    if (d.error) { UiHelpers.showToast(d.error, 'error'); return; }
                    UiHelpers.showToast('Đã lưu trữ dự án', 'success');
                    ProjectManager.loadProjectCards();
                }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
            }
        }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
    },

    // ===== ARCHIVE =====
    restoreProject(filename) {
        showConfirm('Khôi phục dự án từ "' + filename + '"?').then(ok => {
            if (!ok) return;
            fetch('/api/archive/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename })
            }).then(r => r.json()).then(data => {
                if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
                UiHelpers.showToast('Đã khôi phục dự án', 'success');
                ApiClient.loadArchiveList();
                ProjectManager.loadProjectCards();
            }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
        });
    },

    deleteArchive(filename) {
        showConfirm('XÓA VĨNH VIỄN bản lưu trữ "' + filename + '"?', { danger: true }).then(ok => {
            if (!ok) return;
            fetch('/api/archive/' + encodeURIComponent(filename), {
                method: 'DELETE'
            }).then(r => r.json()).then(data => {
                if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
                UiHelpers.showToast('Đã xóa bản lưu trữ', 'success');
                ApiClient.loadArchiveList();
            }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
        });
    },

    downloadArchive(filename) {
        window.location.href = '/api/archive/' + encodeURIComponent(filename) + '/download';
    },

    // ===== CHUNK CONFIG =====
    showChunkConfig() {
        ModalManager.show('chunk-config-modal');
    },

    hideChunkConfig() {
        ModalManager.hide('chunk-config-modal');
    },

    confirmChunking() {
        if (!window.currentProject) return;
        UiHelpers.showToast('Đang chia chunk...', 'success');
        ProjectManager.hideChunkConfig();
    },

    // ===== MERGE FILES =====
    async mergeTranslatedFiles() {
        if (!window.currentProject) return;
        if (!await showConfirm('Ghép tất cả file đã dịch thành 1 file?')) return;
        fetch(`/api/projects/${window.currentProject.slug}/merge`, { method: 'POST' })
            .then(r => r.json()).then(data => {
                if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
                UiHelpers.showToast('Đã ghép file: ' + (data.output || ''), 'success');
                ProjectManager.openProject(window.currentProject.slug);
            }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
    },

    selectAllTranslatedFiles() {
        const checkboxes = document.querySelectorAll('#pm-translated-file-list input[type="checkbox"]');
        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
        checkboxes.forEach(cb => {
            cb.checked = !allChecked;
            const name = cb.closest('.file-item-compact')?.querySelector('.file-item-name')?.textContent?.trim();
            if (name) {
                if (!allChecked) window.selectedTranslatedFiles.add(name);
                else window.selectedTranslatedFiles.delete(name);
            }
        });
    },

    createNewProject() {
        const bookTitle = document.getElementById('new-project-book-title')?.value?.trim() || '';
        const author = document.getElementById('new-project-author')?.value?.trim() || '';
        const genre = document.getElementById('new-project-genre-new')?.value?.trim() || '';
        const description = document.getElementById('new-project-desc-new')?.value?.trim() || '';

        if (!bookTitle) {
            UiHelpers.showToast('Chưa nhập tên tác phẩm', 'error');
            return;
        }

        fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ book_title: bookTitle, author, genre, description })
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
            UiHelpers.showToast('Đã tạo dự án: ' + (data.name || bookTitle), 'success');
            ['new-project-book-title', 'new-project-author', 'new-project-desc-new'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            const genreEl = document.getElementById('new-project-genre-new');
            if (genreEl) genreEl.value = '';
            ProjectManager.loadProjectCards();
            if (data.slug) ProjectManager.openProject(data.slug);
        })
        .catch(e => UiHelpers.showToast('Lỗi tạo dự án: ' + e.message, 'error'));
    }
};

window.ProjectManager = ProjectManager;
