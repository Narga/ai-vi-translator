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
        if (!DirtyState.isDirty('pm-result-text')) return;

        const editor = document.getElementById('pm-result-text');
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
                DirtyState.clean('pm-result-text');
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
            const header = document.querySelector('#pm-result-text')?.closest('.editor-pane-3col')?.querySelector('.pa2');
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

// ===== PROJECT WORKSPACE FUNCTIONS =====
const Icons = {
    upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
    chunk: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="4" x2="6" y2="20"/><line x1="18" y1="4" x2="18" y2="20"/><line x1="6" y1="12" x2="18" y2="12"/></svg>',
    translate: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 8l6 6"/><path d="M4 14l6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="M22 22l-5-10-5 10"/><path d="M14 18h6"/></svg>',
    merge: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/></svg>',
    rename: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>',
    delete: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>',
    spellcheck: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 16 6-12 6 12"/><path d="M8 12h8"/><path d="m16 20 2 2 4-4"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    wrap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M3 12h15a3 3 0 1 1 0 6h-4"/><path d="M3 18l4-4"/><path d="M3 14l4 4"/></svg>',
    convert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M16 13l-4 4-4-4"/></svg>'
};

window.Icons = Icons;

// Column map for toggle/restore
const COL_MAP = {
    'file': { sidebar: 'pm-file-sidebar', btn: 'btn-toggle-file-col' },
    'source': { editor: 'pm-source-editor', btn: 'btn-toggle-source-col' },
    'result': { editor: 'pm-result-editor', btn: 'btn-toggle-result-col' },
    'spell-source': { editor: 'pm-spell-source-editor', btn: 'btn-toggle-spell-source-col' },
    'spell-result': { editor: 'pm-spell-result-editor', btn: 'btn-toggle-spell-result-col' }
};

const ProjectManager = {
    // ===== FILE FILTER STATE =====
    fileFilters: {
        isOpen: false,
        sortBy: 'name',
        sortOrder: 'asc',
        keyword: ''
    },

    // ===== PROJECT CARD FUNCTIONS =====

    refreshWorkspace() {
        if (!window.currentProject) return;
        const slug = window.currentProject.slug;
        
        // Reload tất cả: project data, file lists, guidelines, prompts
        this.openProject(slug);
        PromptManager.loadProjectPrompts();
        PromptManager.loadGuidelineTab(window.pmActiveInfoTab || 'style_guide');
        
        UiHelpers.showToast('Đã làm mới workspace', 'success');
    },

    async refreshProjectCards(options = {}) {
        const btn = document.getElementById('btn-refresh-projects');
        const svgIcon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>';
        if (btn) {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.innerHTML = svgIcon;
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
                btn.style.opacity = '';
                btn.innerHTML = svgIcon;
            }
        }
    },

    loadProjectCards() {
        return fetch('/api/projects')
        .then(r => r.json())
        .then(projects => {
            const container = document.getElementById('project-cards-container');
            if (!container) return;
            
            container.innerHTML = ''; // Clear current cards

            const template = document.getElementById('tpl-project-card');
            if (!template) {
                console.error('Template tpl-project-card not found');
                return;
            }

            projects.forEach(p => {
                const clone = template.content.cloneNode(true);
                
                // Title
                const titleEl = clone.querySelector('.js-title');
                titleEl.textContent = p.name || p.book_title;
                titleEl.onclick = () => ProjectManager.openProject(p.slug);
                
                // Author
                const authorEl = clone.querySelector('.js-author');
                if (authorEl) {
                    authorEl.style.display = 'block';
                    if (p.author) {
                        authorEl.textContent = p.author;
                    } else {
                        authorEl.innerHTML = '&nbsp;';
                    }
                }
                
                // Description
                const descEl = clone.querySelector('.js-desc');
                if (p.description) {
                    descEl.textContent = p.description;
                } else {
                    descEl.textContent = 'Chưa có mô tả dự án.';
                }
                
                // Buttons
                clone.querySelector('.js-btn-info').onclick = () => ProjectManager.showProjectInfoFromList(p.slug);
                clone.querySelector('.js-btn-archive').onclick = () => ProjectManager.archiveProjectFromList(p.slug);
                clone.querySelector('.js-btn-export').onclick = () => ProjectManager.exportProject(p.slug);
                clone.querySelector('.js-btn-delete').onclick = () => ProjectManager.deleteProjectCard(p.slug);
                
                // Meta
                // Meta & Progress calculation
                const sourceCount = p.source_count || 0;
                const translatedCount = p.translated_count || 0;
                const percent = sourceCount > 0 ? Math.round((translatedCount / sourceCount) * 100) : 0;

                const filesInfoEl = clone.querySelector('.js-files-info');
                if (filesInfoEl) filesInfoEl.textContent = `${translatedCount}/${sourceCount} tập tin`;

                const percentEl = clone.querySelector('.js-progress-percent');
                if (percentEl) {
                    percentEl.textContent = `${percent}%`;
                    percentEl.style.color = percent === 100 ? 'var(--teal-secondary, #0D9488)' : 'var(--primary-indigo, #3730A3)';
                }

                const barFillEl = clone.querySelector('.js-progress-bar-fill');
                if (barFillEl) {
                    barFillEl.style.width = `${percent}%`;
                    barFillEl.style.backgroundColor = percent === 100 ? 'var(--teal-secondary, #0D9488)' : 'var(--primary-indigo, #3730A3)';
                }

                const dotEl = clone.querySelector('.js-status-dot');
                if (dotEl) {
                    dotEl.style.backgroundColor = percent === 100
                        ? 'var(--teal-secondary, #0D9488)'
                        : (percent > 0 ? 'var(--tertiary-amber, #752C00)' : 'var(--neutral-gray, #78767F)');
                }

                container.appendChild(clone);
            });

            // Append dashed "Tạo dự án mới" Card at the end of the grid
            const createCard = document.createElement('div');
            createCard.className = 'create-project-card-dashed pa4 flex flex-column items-center justify-center tc pointer';
            createCard.style.minHeight = '180px';
            createCard.onclick = () => ProjectManager.showCreateProjectModal();
            createCard.innerHTML = `
                <div class="br-100 flex items-center justify-center mb3 white" style="width: 48px; height: 48px; background-color: var(--primary-indigo, #3730A3);">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                </div>
                <h3 class="f5 fw6 dark-gray ma0 mb1">Tạo dự án mới</h3>
                <p class="f7 gray ma0">Bắt đầu dịch một tài liệu mới</p>
            `;
            container.appendChild(createCard);
        })
        .catch(err => {
            console.error('Error loading project cards:', err);
            const container = document.getElementById('project-cards-container');
            if (container) container.innerHTML = '<div class="pa4 tc red">Lỗi tải danh sách dự án</div>';
            throw err;
        });
    },

    showCreateProjectModal() {
        const modal = document.getElementById('modal-create-project');
        if (modal) modal.style.display = 'flex';
    },

    closeCreateProjectModal() {
        const modal = document.getElementById('modal-create-project');
        if (modal) modal.style.display = 'none';
    },

    createNewProject() {
        const bookTitle = document.getElementById('new-project-book-title')?.value?.trim() || '';
        const author = document.getElementById('new-project-author')?.value?.trim() || '';
        const description = document.getElementById('new-project-desc-new')?.value?.trim() || '';

        if (!bookTitle) {
            UiHelpers.showToast('Chưa nhập tên tác phẩm', 'error');
            return;
        }

        fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ book_title: bookTitle, author, description })
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
            // Reload cards, close modal, and open new project
            ProjectManager.loadProjectCards();
            ProjectManager.closeCreateProjectModal();
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
            
            const isSameProject = window.currentProject && window.currentProject.slug === slug;
            window.currentProject = data;
            localStorage.setItem('nt_active_project_slug', slug);

            if (!isSameProject) {
                // Reset file filters when opening a new project
                ProjectManager._resetFileFilters();
                
                try {
                    if (window.Alpine && Alpine.store('workspace')) {
                        Alpine.store('workspace').wsTab = 'editor';
                    }
                } catch (e) {}
            }

            if (window.PluginManager) {
                PluginManager.ensureLoaded()
                    .then(() => PluginManager.renderWorkspaceTabs())
                    .catch(e => console.warn("Failed to load plugins:", e));
            }
            
            // Update header
            const titleEl = document.getElementById('pm-project-title');
            const descEl = document.getElementById('pm-project-desc');
            if (titleEl) titleEl.textContent = data.name;
            if (descEl) descEl.textContent = data.description || 'Dự án không có mô tả';
            
            // Restore active workspace tab and sync UI display states
            const sourcesBtn = document.getElementById('pm-tab-sources');
            const translatedBtn = document.getElementById('pm-tab-translated');
            const spellingBtn = document.getElementById('pm-tab-spelling');

            if (translatedBtn && translatedBtn.classList.contains('active')) {
                ProjectManager.switchPmFileTab('translated');
            } else if (spellingBtn && spellingBtn.classList.contains('active')) {
                ProjectManager.switchPmFileTab('spelling');
            } else {
                ProjectManager.switchPmFileTab('sources');
            }
            
            // Populate dropdown source file cho tab Thông tin
            const sourceSelect = document.getElementById('pm-info-source-file');
            if (sourceSelect) {
                sourceSelect.innerHTML = '<option value="">— Chọn file nguồn —</option>';
                (data.sources || []).forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.name;
                    opt.textContent = f.name;
                    sourceSelect.appendChild(opt);
                });
            }
            
            // Khôi phục trạng thái ẩn/hiện cột
            ProjectManager.restoreColumnStates();
            
            // Khởi tạo drag-and-drop cho sidebar
            setTimeout(() => ProjectManager.initDragDrop(), 100);

            // Khởi tạo file filter events (click-outside, escape)
            ProjectManager.initFileFilterEvents();
            
            if (!isSameProject) {
                // Clear editors
                ['pm-source-text', 'pm-result-text', 'pm-spell-source-text', 'pm-spell-result-text'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.value = '';
                });
                window.currentProjectFile = null;
                
                UiHelpers.showToast('Đã mở: ' + data.name, 'success');
            }
        })
        .catch(err => {
            console.error('openProject error:', err);
            UiHelpers.showToast('Lỗi mở dự án: ' + err.message, 'error');
        });
    },
    
    refreshProjectFiles() {
        // Làm mới danh sách tập tin của dự án hiện tại MÀ KHÔNG đổi wsTab,
        // không xóa editor và không hiện toast "Đã mở".
        // Dùng sau khi chuyển đổi xong để tập tin mới xuất hiện ở sidebar.
        if (!window.currentProject || !window.currentProject.slug) return;
        const slug = window.currentProject.slug;

        fetch('/api/projects/' + slug)
            .then(r => r.json())
            .then(data => {
                if (data.error) return;
                const prev = window.currentProject;
                window.currentProject = Object.assign({}, prev, data);
                window.currentProject.slug = slug;

                // Giữ nguyên wsTab; chỉ vẽ lại danh sách của mini-tab đang active.
                const sourcesBtn = document.getElementById('pm-tab-sources');
                const translatedBtn = document.getElementById('pm-tab-translated');
                const spellingBtn = document.getElementById('pm-tab-spelling');
                if (translatedBtn && translatedBtn.classList.contains('active')) {
                    ProjectManager.switchPmFileTab('translated');
                } else if (spellingBtn && spellingBtn.classList.contains('active')) {
                    ProjectManager.switchPmFileTab('spelling');
                } else {
                    ProjectManager.switchPmFileTab('sources');
                }

                // Kiểm tra file đang mở còn tồn tại; reload hoặc dọn editor tương ứng.
                ProjectManager._syncOpenFileAfterRefresh(data);
            })
            .catch(() => {});
    },

    // Sau refresh metadata: nếu file đang mở còn trong section tương ứng thì reload nội dung,
    // nếu đã mất thì dọn editor + spellcheck log, highlight và currentProjectFile.
    _syncOpenFileAfterRefresh(data) {
        const cur = window.currentProjectFile;
        if (!cur || !cur.name) return;
        const sectionFiles = {
            sources: data.sources || [],
            translated: data.translated || [],
            spelling: data.spelling || [],
        };
        const exists = (sectionFiles[cur.section] || []).some(f => f.name === cur.name);
        const taIds = ['pm-source-text', 'pm-result-text', 'pm-spell-source-text', 'pm-spell-result-text'];

        if (exists) {
            // ponytail: chỉ reload editor khi file đang hiển thị (có nội dung), tránh ghi đè khi list vẫn ổn
            const hasContent = taIds.some(id => { const el = document.getElementById(id); return el && el.value; });
            if (!hasContent) return;
            if (cur.section === 'spelling') {
                EditorComponent.loadPmSpellcheckFile(cur.name);
            } else {
                EditorComponent.loadPmProjectFile(cur.name, cur.section);
            }
            return;
        }

        // File đã bị xóa/đổi tên — dọn editor để không hiển thị "file ma"
        taIds.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
        const logEl = document.getElementById('pm-spell-log-content');
        if (logEl) logEl.textContent = '';
        ['pm-opened-file-status', 'pm-spell-opened-file-status'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '';
        });
        window.currentProjectFile = null;
        ProjectManager.highlightActiveFile && ProjectManager.highlightActiveFile(null);
        UiHelpers.showToast('Tập tin đang mở không còn tồn tại, đã đóng editor.', 'warning');
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

        if (window.PluginManager) {
            PluginManager.setWorkspaceTab('editor');
        }
        const pluginTabs = document.getElementById('pm-plugin-workspace-tabs');
        if (pluginTabs) pluginTabs.innerHTML = '';

        ProjectManager.loadProjectCards();
    },
    
    switchPmFileTab(tab) {
        // Close filter menu when switching tabs (keep filter values)
        ProjectManager.closeFileFilterMenu();

        const sourcesBtn = document.getElementById('pm-tab-sources');
        const translatedBtn = document.getElementById('pm-tab-translated');
        const spellingBtn = document.getElementById('pm-tab-spelling');
        const translationWs = document.getElementById('pm-translation-workspace');
        const spellcheckWs = document.getElementById('pm-spellcheck-workspace');
        const translationToggles = document.querySelectorAll('.pm-toggle-translation');
        const spellcheckToggles = document.querySelectorAll('.pm-toggle-spellcheck');
        const headerTransInfo = document.getElementById('pm-header-translation-info');
        const headerSpellInfo = document.getElementById('pm-header-spellcheck-info');

        // Clear all selections when switching tabs
        window.selectedFiles.clear();
        window.selectedTranslatedFiles.clear();

        if (tab === 'sources') {
            if (sourcesBtn) sourcesBtn.classList.add('active');
            if (translatedBtn) translatedBtn.classList.remove('active');
            if (spellingBtn) spellingBtn.classList.remove('active');
            if (translationWs) translationWs.style.display = '';
            if (spellcheckWs) spellcheckWs.style.display = 'none';
            if (headerTransInfo) headerTransInfo.style.display = '';
            if (headerSpellInfo) headerSpellInfo.style.display = 'none';
            translationToggles.forEach(el => el.classList.remove('dn'));
            spellcheckToggles.forEach(el => el.classList.add('dn'));
            ProjectManager.renderPmFileList(window.currentProject?.sources || []);
            ProjectManager.updateSelectAllButton();
        } else if (tab === 'translated') {
            if (sourcesBtn) sourcesBtn.classList.remove('active');
            if (translatedBtn) translatedBtn.classList.add('active');
            if (spellingBtn) spellingBtn.classList.remove('active');
            if (translationWs) translationWs.style.display = '';
            if (spellcheckWs) spellcheckWs.style.display = 'none';
            if (headerTransInfo) headerTransInfo.style.display = '';
            if (headerSpellInfo) headerSpellInfo.style.display = 'none';
            translationToggles.forEach(el => el.classList.remove('dn'));
            spellcheckToggles.forEach(el => el.classList.add('dn'));
            ProjectManager.renderPmTranslatedList(window.currentProject?.translated || []);
            ProjectManager.updateSelectAllTranslatedButton();
        } else if (tab === 'spelling') {
            if (sourcesBtn) sourcesBtn.classList.remove('active');
            if (translatedBtn) translatedBtn.classList.remove('active');
            if (spellingBtn) spellingBtn.classList.add('active');
            if (translationWs) translationWs.style.display = 'none';
            if (spellcheckWs) spellcheckWs.style.display = '';
            if (headerTransInfo) headerTransInfo.style.display = 'none';
            if (headerSpellInfo) headerSpellInfo.style.display = '';
            translationToggles.forEach(el => el.classList.add('dn'));
            spellcheckToggles.forEach(el => el.classList.remove('dn'));
            ProjectManager.renderPmSpellcheckedList();
            ProjectManager.updateSelectAllButton();
        } else {
            // Default to sources
            if (sourcesBtn) sourcesBtn.classList.add('active');
            if (translatedBtn) translatedBtn.classList.remove('active');
            if (spellingBtn) spellingBtn.classList.remove('active');
            if (translationWs) translationWs.style.display = '';
            if (spellcheckWs) spellcheckWs.style.display = 'none';
            if (headerTransInfo) headerTransInfo.style.display = '';
            if (headerSpellInfo) headerSpellInfo.style.display = 'none';
            translationToggles.forEach(el => el.classList.remove('dn'));
            spellcheckToggles.forEach(el => el.classList.add('dn'));
            ProjectManager.renderPmFileList(window.currentProject?.sources || []);
            ProjectManager.updateSelectAllButton();
        }

        // Cập nhật lại layout cho các cột sau khi chuyển tab
        ProjectManager.updateColumnLayout();
    },
    
    renderPmTranslatedList(translated) {
        const el = document.getElementById('pm-file-list');
        if (!el) return;

        const filtered = this.applyFileFilters(translated);

        if (!filtered || !filtered.length) {
            el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file dịch</div>';
            return;
        }

        el.innerHTML = filtered.map(f => {
            const esc = escapeHtml(f.name);
            const isActive = window.currentProjectFile?.name === f.name;
            const checked = window.selectedTranslatedFiles.has(f.name) ? 'checked' : '';
            const isSelected = window.selectedTranslatedFiles.has(f.name);
            
            return `
            <div class="file-item-compact ${isActive ? 'active' : ''} ${isSelected ? 'selected' : ''}" data-filename="${esc}" onclick="EditorComponent.loadPmProjectFile(this.dataset.filename,'translated')">
                <div class="flex items-center gap-2">
                    <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleTranslatedFile(this.closest('.file-item-compact').dataset.filename,this.checked,event)" class="flex-shrink-0">
                    <div class="flex-auto min-width-0">
                        <span class="file-item-name">${esc}</span>
                    </div>
                </div>
                <div class="file-item-meta">
                    <div class="flex items-center gap-1">
                        <span>${f.size_display || ''}</span>
                    </div>
                    <div class="file-item-actions">
                        <button onclick="event.stopPropagation();TranslationWorker.spellcheckFileInProject(this.closest('.file-item-compact').dataset.filename,'translated')" title="Soát lỗi AI">${Icons.spellcheck}</button>
                        <button onclick="event.stopPropagation();ProjectManager.renameProjectFile(this.closest('.file-item-compact').dataset.filename,'translated')" title="Đổi tên">${Icons.rename}</button>
                        <button onclick="event.stopPropagation();ProjectManager.deleteProjectFile(this.closest('.file-item-compact').dataset.filename,'translated')" title="Xóa" class="red">${Icons.delete}</button>
                    </div>
                </div>
            </div>`;
        }).join('');
    },
    
    switchPmSpellTab() {},
    
    renderPmSpellcheckedList() {
        const el = document.getElementById('pm-file-list');
        if (!el) return;
        
        if (!window.currentProject) {
            el.innerHTML = '<div class="pa3 tc silver i f7">Chưa chọn dự án</div>';
            return;
        }
        
        const slug = window.currentProject.slug;
        fetch(`/api/projects/${slug}/files/spelling`)
            .then(r => r.json())
            .then(files => {
                // Phòng thủ: lọc bỏ file _info.txt nếu backend chưa kịp lọc
                const visibleFiles = files.filter(f => !f.name.endsWith('_info.txt'));
                const filtered = ProjectManager.applyFileFilters(visibleFiles);
                if (!filtered.length) {
                    el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file đã soát</div>';
                    ProjectManager.updateSelectAllButton();
                    return;
                }
                el.innerHTML = filtered.map(f => {
                    const esc = escapeHtml(f.name);
                    const isActive = window.currentProjectFile?.name === f.name;
                    const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
                    
                    return `
                    <div class="file-item-compact ${isActive ? 'active' : ''}" data-filename="${esc}" onclick="EditorComponent.loadPmSpellcheckFile(this.dataset.filename)">
                        <div class="flex items-center gap-2">
                            <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile(this.closest('.file-item-compact').dataset.filename,this.checked,event)" class="flex-shrink-0">
                            <div class="flex-auto min-width-0">
                                <span class="file-item-name">${esc}</span>
                            </div>
                        </div>
                        <div class="file-item-meta">
                            <div class="flex items-center gap-1">
                                <span>${f.size_display || ''}</span>
                                <span class="file-done-dot" title="Đã soát xong"></span>
                            </div>
                            <div class="file-item-actions">
                                <button onclick="event.stopPropagation();ProjectManager.deleteProjectFile(this.closest('.file-item-compact').dataset.filename,'spelling')" title="Xóa" class="red">${Icons.delete}</button>
                            </div>
                        </div>
                    </div>`;
                }).join('');
                ProjectManager.updateSelectAllButton();
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
        // Map tab UI name → backend content_type
        const tabToContentType = {
            'style-guide': 'style_guide',
            'relationship': 'relationship',
            'glossary': 'glossary',
            'summary': 'summary',
        };
        window.pmActiveInfoTab = tabToContentType[tabName] || 'style_guide';

        // Toggle active class và màu chữ trên các nút subtab
        document.querySelectorAll('.pm-info-tab-btn').forEach(btn => {
            const isActive = btn.dataset.infoTab === window.pmActiveInfoTab;
            btn.classList.toggle('active', isActive);
            if (isActive) {
                btn.classList.remove('gray');
                btn.classList.add('dark-gray');
            } else {
                btn.classList.add('gray');
                btn.classList.remove('dark-gray');
            }
        });

        // Load nội dung từ backend nếu cần
        PromptManager.loadGuidelineTab(tabName);
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
        const sidebar = document.getElementById('pm-file-sidebar');
        if (!sidebar) return;
        
        const editorContainer = sidebar.closest('.workspace-layout-3col');
        if (!editorContainer) return;

        // Tìm workspace đang hoạt động (không bị ẩn display: none)
        const activeWorkspace = Array.from(editorContainer.children).find(child => {
            return (child.id === 'pm-translation-workspace' || child.id === 'pm-spellcheck-workspace') &&
                   child.style.display !== 'none';
        });

        if (!activeWorkspace) return;

        const editorsContainer = activeWorkspace.querySelector('.editors-container-2col');
        const editorPanes = activeWorkspace.querySelectorAll('.editor-pane-3col');

        if (!editorsContainer) return;

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
    },
    
    restoreColumnStates() {
        const columns = ['file', 'source', 'result', 'spell-source', 'spell-result'];
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
    
    lastCheckedFileIndex: -1,
    lastCheckedTranslatedIndex: -1,

    toggleProjectFile(name, checked, event = null) {
        let files = [];
        if (window.currentProject && window.currentProject.sources) {
            files = ProjectManager.applyFileFilters(window.currentProject.sources);
        }
        const fileNames = files.map(f => typeof f === 'string' ? f : f.name);
        const currentIndex = fileNames.indexOf(name);

        if (event && event.shiftKey && ProjectManager.lastCheckedFileIndex !== -1 && currentIndex !== -1) {
            const start = Math.min(ProjectManager.lastCheckedFileIndex, currentIndex);
            const end = Math.max(ProjectManager.lastCheckedFileIndex, currentIndex);
            
            for (let i = start; i <= end; i++) {
                const fn = fileNames[i];
                if (checked) window.selectedFiles.add(fn);
                else window.selectedFiles.delete(fn);
            }
            
            document.querySelectorAll('#pm-file-list input[type="checkbox"]').forEach(cb => {
                const cbName = cb.closest('.file-item-compact').dataset.filename;
                if (fileNames.indexOf(cbName) >= start && fileNames.indexOf(cbName) <= end) {
                    cb.checked = checked;
                    cb.closest('.file-item-compact').classList.toggle('selected', checked);
                }
            });
        } else {
            if (checked) window.selectedFiles.add(name);
            else window.selectedFiles.delete(name);
        }
        
        const row = document.querySelector(`#pm-file-list .file-item-compact[data-filename="${CSS.escape(name)}"]`);
        if (row) row.classList.toggle('selected', checked);
        
        ProjectManager.lastCheckedFileIndex = currentIndex;
        ProjectManager.updateSelectAllButton();
    },

    toggleTranslatedFile(filename, checked, event = null) {
        let files = [];
        if (window.currentProject && window.currentProject.translated) {
            files = ProjectManager.applyFileFilters(window.currentProject.translated);
        }
        const fileNames = files.map(f => typeof f === 'string' ? f : f.name);
        const currentIndex = fileNames.indexOf(filename);

        if (event && event.shiftKey && ProjectManager.lastCheckedTranslatedIndex !== -1 && currentIndex !== -1) {
            const start = Math.min(ProjectManager.lastCheckedTranslatedIndex, currentIndex);
            const end = Math.max(ProjectManager.lastCheckedTranslatedIndex, currentIndex);
            
            for (let i = start; i <= end; i++) {
                const fn = fileNames[i];
                if (checked) window.selectedTranslatedFiles.add(fn);
                else window.selectedTranslatedFiles.delete(fn);
            }
            
            document.querySelectorAll('#pm-file-list input[type="checkbox"]').forEach(cb => {
                const cbName = cb.closest('.file-item-compact').dataset.filename;
                if (fileNames.indexOf(cbName) >= start && fileNames.indexOf(cbName) <= end) {
                    cb.checked = checked;
                    cb.closest('.file-item-compact').classList.toggle('selected', checked);
                }
            });
        } else {
            if (checked) window.selectedTranslatedFiles.add(filename);
            else window.selectedTranslatedFiles.delete(filename);
        }

        const row = document.querySelector(`#pm-file-list .file-item-compact[data-filename="${CSS.escape(filename)}"]`);
        if (row) row.classList.toggle('selected', checked);
        
        ProjectManager.lastCheckedTranslatedIndex = currentIndex;
        ProjectManager.updateSelectAllTranslatedButton();
    },

    highlightActiveFile(filename) {
        document.querySelectorAll('#pm-file-list .file-item-compact').forEach(el => {
            const isThisActive = el.dataset.filename === filename;
            el.classList.toggle('active', isThisActive);
        });
    },

    updateSelectAllButton() {
        const chkSidebar = document.getElementById('chk-select-all-sidebar');
        const countSpans = document.querySelectorAll('#selected-files-count, #pm-selected-files-count');
        const infoSpans = document.querySelectorAll('#pm-selected-files-info');

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

        if (window.currentProject) {
            // Update Project sources sidebar select-all checkbox
            if (chkSidebar && window.currentProject.sources) {
                const sourcesBtn = document.getElementById('pm-tab-sources');
                const translatedBtn = document.getElementById('pm-tab-translated');
                const spellingBtn = document.getElementById('pm-tab-spelling');

                const isSourcesActive = sourcesBtn && sourcesBtn.classList.contains('active');
                const isTranslatedActive = translatedBtn && translatedBtn.classList.contains('active');
                const isSpellingActive = spellingBtn && spellingBtn.classList.contains('active');

                if (isSourcesActive) {
                    const filtered = this.applyFileFilters(window.currentProject.sources);
                    const total = filtered.length;
                    chkSidebar.checked = total > 0 && window.selectedFiles.size === total;
                    chkSidebar.indeterminate = window.selectedFiles.size > 0 && window.selectedFiles.size < total;
                } else if (isSpellingActive) {
                    const checkboxes = document.querySelectorAll('#pm-file-list input[type="checkbox"]');
                    if (checkboxes.length > 0) {
                        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                        const someChecked = Array.from(checkboxes).some(cb => cb.checked);
                        chkSidebar.checked = allChecked;
                        chkSidebar.indeterminate = someChecked && !allChecked;
                    } else {
                        chkSidebar.checked = false;
                        chkSidebar.indeterminate = false;
                    }
                } else {
                    // Translated tab - use filtered count
                    const filtered = this.applyFileFilters(window.currentProject.translated || []);
                    const total = filtered.length;
                    chkSidebar.checked = total > 0 && window.selectedTranslatedFiles.size === total;
                    chkSidebar.indeterminate = window.selectedTranslatedFiles.size > 0 && window.selectedTranslatedFiles.size < total;
                }
            }
        }
    },

    updateSelectAllTranslatedButton() {
        const chkSidebar = document.getElementById('chk-select-all-sidebar');
        if (!window.currentProject) return;

        // Update Project translated sidebar select-all checkbox
        if (chkSidebar && window.currentProject.translated) {
            const translatedBtn = document.getElementById('pm-tab-translated');
            const isTranslatedActive = translatedBtn && translatedBtn.classList.contains('active');
            if (isTranslatedActive) {
                const filtered = this.applyFileFilters(window.currentProject.translated);
                const total = filtered.length;
                chkSidebar.checked = total > 0 && window.selectedTranslatedFiles.size === total;
                chkSidebar.indeterminate = window.selectedTranslatedFiles.size > 0 && window.selectedTranslatedFiles.size < total;
            }
        }
        
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

    selectAllProjectFiles(checked) {
        if (!window.currentProject) return;
        const allSources = window.currentProject.sources || [];
        
        // If checked is not boolean, toggle based on current size
        if (typeof checked !== 'boolean') {
            checked = !(window.selectedFiles.size === allSources.length && allSources.length > 0);
        }
        
        if (checked) {
            allSources.forEach(f => window.selectedFiles.add(f.name));
        } else {
            allSources.forEach(f => window.selectedFiles.delete(f.name));
        }
        ProjectManager.updateSelectAllButton();
        ProjectManager.renderPmFileList(allSources);
    },

    showPmPromptTab(tabName) {
        this._showPanel('pm-prompt-panel-', ['main', 'summary', 'relationships', 'glossary', 'chinh-ta'], tabName);
        window.activeWorkspacePromptTab = tabName;
        document.querySelectorAll('.pm-prompt-tab-btn').forEach(btn => {
            const onclick = btn.getAttribute('onclick') || '';
            const isActive = onclick.includes(`'${tabName}'`);
            btn.classList.toggle('active', isActive);
            if (isActive) {
                btn.classList.remove('gray');
                btn.classList.add('dark-gray');
            } else {
                btn.classList.add('gray');
                btn.classList.remove('dark-gray');
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

    // ===== FILE OPERATIONS =====

    async deleteProjectFile(filename, section) {
        if (!await showConfirm('Xóa vĩnh viễn "' + filename + '"?', { danger: true })) return;
        fetch(`/api/projects/${window.currentProject.slug}/file/${section}/${filename}`, {
            method: 'DELETE', headers: { 'Content-Type': 'application/json' }
        }).then(r => r.json()).then(() => {
            // Dọn editor nếu file đang mở bị xóa
            if (window.currentProjectFile && window.currentProjectFile.name === filename) {
                ProjectManager._closeEditorAfterFileDelete();
            } else {
                ProjectManager.openProject(window.currentProject.slug);
            }
        });
    },

    _closeEditorAfterFileDelete() {
        const taIds = ['pm-source-text', 'pm-result-text', 'pm-spell-source-text', 'pm-spell-result-text'];
        taIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        ['pm-opened-file-status', 'pm-spell-opened-file-status'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '';
        });
        const logEl = document.getElementById('pm-spell-log-content');
        if (logEl) logEl.textContent = '';
        window.currentProjectFile = null;
        ProjectManager.openProject(window.currentProject.slug);
    },

    async deleteSelectedFiles(section = 'sources') {
        const selected = (section === 'translated') ? window.selectedTranslatedFiles : window.selectedFiles;
        if (!selected || selected.size === 0) {
            UiHelpers.showToast('Chưa chọn tập tin nào', 'error');
            return;
        }
        if (!window.currentProject) {
            UiHelpers.showToast('Chưa chọn dự án', 'error');
            return;
        }
        const count = selected.size;
        if (!await showConfirm(`Xóa vĩnh viễn ${count} tập tin trong ${section}?`, { danger: true })) return;
        const slug = window.currentProject.slug;
        let successCount = 0;
        let failCount = 0;
        const promises = [...selected].map(filename =>
            fetch(`/api/projects/${slug}/file/${section}/${filename}`, {
                method: 'DELETE', headers: { 'Content-Type': 'application/json' }
            })
                .then(r => r.json())
                .then(data => { if (data.success !== false) successCount++; else failCount++; })
                .catch(() => failCount++)
        );
        await Promise.all(promises);
        selected.clear();
        ProjectManager.openProject(slug);
        if (failCount > 0) {
            UiHelpers.showToast(`Đã xóa ${successCount}, lỗi ${failCount} tập tin`, 'error');
        } else {
            UiHelpers.showToast(`Đã xóa ${count} tập tin`, 'success');
        }
    },

    async deleteSelectedSpellFiles() {
        return this.deleteSelectedFiles('spelling');
    },

    async deleteSelectedSourceFiles() {
        return this.deleteSelectedFiles('sources');
    },

    async deleteSelectedTranslatedFiles() {
        return this.deleteSelectedFiles('translated');
    },

    async deleteSelectedSidebarFiles() {
        const sourcesBtn = document.getElementById('pm-tab-sources');
        const translatedBtn = document.getElementById('pm-tab-translated');
        const spellingBtn = document.getElementById('pm-tab-spelling');
        const isSourcesActive = sourcesBtn && sourcesBtn.classList.contains('active');
        const isTranslatedActive = translatedBtn && translatedBtn.classList.contains('active');
        const isSpellingActive = spellingBtn && spellingBtn.classList.contains('active');
        if (isSourcesActive) return this.deleteSelectedSourceFiles();
        if (isTranslatedActive) return this.deleteSelectedTranslatedFiles();
        if (isSpellingActive) return this.deleteSelectedSpellFiles();
        return this.deleteSelectedSourceFiles();
    },

    async deleteSelectedSpellSidebarFiles() {
        return this.deleteSelectedSpellFiles();
    },

    selectAllSidebarFiles(checked) {
        // If checked is not boolean, read it from checkbox
        if (typeof checked !== 'boolean') {
            const chk = document.getElementById('chk-select-all-sidebar');
            checked = chk ? chk.checked : false;
        }

        const sourcesBtn = document.getElementById('pm-tab-sources');
        const translatedBtn = document.getElementById('pm-tab-translated');
        const spellingBtn = document.getElementById('pm-tab-spelling');

        const isSourcesActive = sourcesBtn && sourcesBtn.classList.contains('active');
        const isTranslatedActive = translatedBtn && translatedBtn.classList.contains('active');
        const isSpellingActive = spellingBtn && spellingBtn.classList.contains('active');

        if (isTranslatedActive) {
            // Use filtered list for translated tab
            const allTranslated = window.currentProject?.translated || [];
            const filtered = ProjectManager.applyFileFilters(allTranslated);
            if (checked) {
                filtered.forEach(f => window.selectedTranslatedFiles.add(f.name));
            } else {
                filtered.forEach(f => window.selectedTranslatedFiles.delete(f.name));
            }
            ProjectManager.updateSelectAllTranslatedButton();
            ProjectManager.renderPmTranslatedList(allTranslated);
        } else if (isSpellingActive) {
            // For spelling tab, select all visible spelling files (filtered)
            if (!window.currentProject) return;
            const slug = window.currentProject.slug;
            fetch(`/api/projects/${slug}/files/spelling`)
                .then(r => r.json())
                .then(files => {
                    const visibleFiles = files.filter(f => !f.name.endsWith('_info.txt'));
                    const filtered = ProjectManager.applyFileFilters(visibleFiles);
                    if (checked) {
                        filtered.forEach(f => window.selectedFiles.add(f.name));
                    } else {
                        filtered.forEach(f => window.selectedFiles.delete(f.name));
                    }
                    ProjectManager.updateSelectAllButton();
                    ProjectManager.renderPmSpellcheckedList();
                });
        } else {
            // Default to sources - use filtered list
            const allSources = window.currentProject?.sources || [];
            const filtered = ProjectManager.applyFileFilters(allSources);
            if (checked) {
                filtered.forEach(f => window.selectedFiles.add(f.name));
            } else {
                filtered.forEach(f => window.selectedFiles.delete(f.name));
            }
            ProjectManager.updateSelectAllButton();
            ProjectManager.renderPmFileList(allSources);
        }
    },

    selectAllSpellcheckFiles() {},

    getSelectedFilesForCurrentTab() {
        // Determine based on active tab
        const sourcesBtn = document.getElementById('pm-tab-sources');
        const translatedBtn = document.getElementById('pm-tab-translated');
        const spellingBtn = document.getElementById('pm-tab-spelling');
        
        if (translatedBtn && translatedBtn.classList.contains('active')) {
            return window.selectedTranslatedFiles;
        }
        if (spellingBtn && spellingBtn.classList.contains('active')) {
            return window.selectedTranslatedFiles;
        }
        return window.selectedFiles;
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

    showBatchRenameModal() {
        if (!window.currentProject) { UiHelpers.showToast('Chưa chọn dự án!', 'error'); return; }
        const selected = this.getSelectedFilesForCurrentTab();
        if (selected.size === 0) { UiHelpers.showToast('Chọn file cần đổi tên trước!', 'error'); return; }

        const files = Array.from(selected);
        const countEl = document.getElementById('batch-rename-count');
        const previewEl = document.getElementById('batch-rename-preview');
        const patternEl = document.getElementById('batch-rename-pattern');

        if (countEl) countEl.textContent = files.length;
        if (previewEl) previewEl.innerHTML = files.map(f => `<div class="pa1 bb b--black-05">${f}</div>`).join('');

        // Auto-detect pattern from first file
        if (patternEl && files.length > 0) {
            const first = files[0];
            const match = first.match(/^(.*?)(\d+)(.*)$/);
            if (match) {
                const prefix = match[1];
                const num = match[2];
                const suffix = match[3];
                patternEl.value = prefix + '{N}' + suffix;
                document.getElementById('batch-rename-start').value = parseInt(num);
                document.getElementById('batch-rename-zeropad').value = num.length;
            } else {
                patternEl.value = '{N}';
            }
        }

        ModalManager.show('batch-rename-modal');
    },

    executeBatchRename() {
        if (!window.currentProject) return;
        const selected = this.getSelectedFilesForCurrentTab();
        if (selected.size === 0) return;

        const pattern = document.getElementById('batch-rename-pattern')?.value || '';
        const start = parseInt(document.getElementById('batch-rename-start')?.value || '1');
        const zeropad = parseInt(document.getElementById('batch-rename-zeropad')?.value || '2');
        const oldNames = Array.from(selected);

        if (!pattern) { UiHelpers.showToast('Nhập pattern đổi tên!', 'error'); return; }

        // Determine current section
        const sourcesBtn = document.getElementById('pm-tab-sources');
        const translatedBtn = document.getElementById('pm-tab-translated');
        const spellingBtn = document.getElementById('pm-tab-spelling');
        let section = 'sources';
        if (translatedBtn && translatedBtn.classList.contains('active')) section = 'translated';
        else if (spellingBtn && spellingBtn.classList.contains('active')) section = 'spelling';

        const btn = document.getElementById('btn-confirm-batch-rename');
        if (btn) { btn.disabled = true; btn.textContent = 'Đang đổi tên...'; }

        fetch(`/api/projects/${window.currentProject.slug}/rename-batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ section, pattern, start, zeropad, old_names: oldNames })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const renamed = data.renamed || 0;
                const errors = (data.results || []).filter(r => r.error);
                UiHelpers.showToast(`Đã đổi tên ${renamed}/${oldNames.length} file`, errors.length > 0 ? 'warning' : 'success');
                ModalManager.hide('batch-rename-modal');
                ProjectManager.clearSelectionForCurrentTab();
                ProjectManager.openProject(window.currentProject.slug);
            } else {
                UiHelpers.showToast(data.error || 'Lỗi đổi tên', 'error');
            }
        })
        .catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'))
        .finally(() => {
            if (btn) { btn.disabled = false; btn.textContent = 'Đổi tên'; }
        });
    },

    clearSelectionForCurrentTab() {
        const selected = this.getSelectedFilesForCurrentTab();
        selected.clear();
        ProjectManager.updateSelectAllButton();
        ProjectManager.updateSelectAllTranslatedButton();
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
        
        // Only source file upload is supported now
        const fileInput = document.getElementById('pm-upload-source-file');
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
            const isActive = window.currentProjectFile?.name === f.name;
            const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
            const isSelected = window.selectedFiles.has(f.name);
            const dot = options.getDot ? options.getDot(f, isActive) : '';
            const dirty = options.getDirty ? options.getDirty(f, isActive) : '';
            const actions = options.getActions(f);
            return `
            <div class="file-item-compact ${isActive ? 'active' : ''} ${isSelected ? 'selected' : ''}" data-filename="${esc}" onclick="${options.getOnclick()}">
                <div class="flex items-center gap-2">
                    <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile(this.closest('.file-item-compact').dataset.filename,this.checked,event)" class="flex-shrink-0">
                    <div class="flex-auto min-width-0">
                        <span class="file-item-name">${esc}${dirty}</span>
                    </div>
                </div>
                <div class="file-item-meta">
                    <div class="flex items-center gap-1">
                        <span>${f.size_display || ''}</span>
                        ${dot}
                    </div>
                    <div class="file-item-actions">${actions}</div>
                </div>
            </div>`;
        }).join('');
    },

    renderPmFileList(sources) {
        const filtered = this.applyFileFilters(sources);
        this._renderFileItems(document.getElementById('pm-file-list'), filtered, {
            getOnclick: () => `EditorComponent.loadPmProjectFile(this.dataset.filename,'sources')`,
            getDirty: (f, isActive) => isActive && DirtyState.isDirty('pm-result-text') ? '<span class="red fw6 ml1">*</span>' : '',
            getDot: f => f.has_translation ? '<span class="file-done-dot" title="Đã dịch xong"></span>' : '',
            getActions: () => `
                <button onclick="event.stopPropagation();TranslationWorker.translateFileInProject(this.closest('.file-item-compact').dataset.filename)" title="Dịch">${Icons.translate}</button>
                <button onclick="event.stopPropagation();TranslationWorker.spellcheckFileInProject(this.closest('.file-item-compact').dataset.filename,'sources')" title="Soát lỗi AI">${Icons.spellcheck}</button>
                <button onclick="event.stopPropagation();ProjectManager.renameProjectFile(this.closest('.file-item-compact').dataset.filename,'sources')" title="Đổi tên">${Icons.rename}</button>
                <button onclick="event.stopPropagation();ProjectManager.deleteProjectFile(this.closest('.file-item-compact').dataset.filename,'sources')" title="Xóa" class="red">${Icons.delete}</button>`
        });
    },

    renderPmSpellcheckFileList() {},

    // ===== FILE FILTER METHODS =====

    toggleFileFilterMenu() {
        this.fileFilters.isOpen = !this.fileFilters.isOpen;
        const menu = document.getElementById('pm-file-filter-menu');
        if (menu) {
            menu.classList.toggle('dn', !this.fileFilters.isOpen);
        }
        if (this.fileFilters.isOpen) {
            this.syncFileFilterMenuState();
        }
    },

    closeFileFilterMenu() {
        if (!this.fileFilters.isOpen) return;
        this.fileFilters.isOpen = false;
        const menu = document.getElementById('pm-file-filter-menu');
        if (menu) menu.classList.add('dn');
    },

    syncFileFilterMenuState() {
        const sortByRadios = document.querySelectorAll('input[name="pm-filter-sort-by"]');
        sortByRadios.forEach(r => { r.checked = r.value === this.fileFilters.sortBy; });
        const sortOrderRadios = document.querySelectorAll('input[name="pm-filter-sort-order"]');
        sortOrderRadios.forEach(r => { r.checked = r.value === this.fileFilters.sortOrder; });
        const kwInput = document.getElementById('pm-filter-keyword-input');
        if (kwInput) kwInput.value = this.fileFilters.keyword;
    },

    setFileFilterSortBy(value) {
        this.fileFilters.sortBy = value;
        this._reRenderActiveFileTab();
    },

    setFileFilterSortOrder(value) {
        this.fileFilters.sortOrder = value;
        this._reRenderActiveFileTab();
    },

    setFileFilterKeyword(value) {
        this.fileFilters.keyword = value;
        this._reRenderActiveFileTab();
    },

    _reRenderActiveFileTab() {
        const sourcesBtn = document.getElementById('pm-tab-sources');
        const translatedBtn = document.getElementById('pm-tab-translated');
        const spellingBtn = document.getElementById('pm-tab-spelling');

        if (sourcesBtn && sourcesBtn.classList.contains('active')) {
            this.renderPmFileList(window.currentProject?.sources || []);
            this.updateSelectAllButton();
        } else if (translatedBtn && translatedBtn.classList.contains('active')) {
            this.renderPmTranslatedList(window.currentProject?.translated || []);
            this.updateSelectAllTranslatedButton();
        } else if (spellingBtn && spellingBtn.classList.contains('active')) {
            this.renderPmSpellcheckedList();
        }
    },

    applyFileFilters(files) {
        if (!files || !files.length) return [];
        const { sortBy, sortOrder, keyword } = this.fileFilters;
        let result = [...files];

        if (keyword) {
            const kw = keyword.toLowerCase();
            result = result.filter(f => f.name.toLowerCase().includes(kw));
        }

        result.sort((a, b) => {
            let cmp = 0;
            if (sortBy === 'ext') {
                const extA = (a.name.split('.').pop() || '').toLowerCase();
                const extB = (b.name.split('.').pop() || '').toLowerCase();
                cmp = extA.localeCompare(extB, 'vi');
                if (cmp === 0) cmp = a.name.localeCompare(b.name, 'vi');
            } else {
                cmp = a.name.localeCompare(b.name, 'vi');
            }
            return sortOrder === 'desc' ? -cmp : cmp;
        });

        return result;
    },

    _getFileFilterEventsBound: false,
    initFileFilterEvents() {
        if (this._getFileFilterEventsBound) return;
        this._getFileFilterEventsBound = true;

        document.addEventListener('click', (e) => {
            if (!this.fileFilters.isOpen) return;
            const wrap = document.querySelector('.file-filter-menu-wrap');
            if (wrap && !wrap.contains(e.target)) {
                this.closeFileFilterMenu();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.fileFilters.isOpen) {
                this.closeFileFilterMenu();
            }
        });
    },

    _resetFileFilters() {
        this.fileFilters.sortBy = 'name';
        this.fileFilters.sortOrder = 'asc';
        this.fileFilters.keyword = '';
        this.fileFilters.isOpen = false;
        const menu = document.getElementById('pm-file-filter-menu');
        if (menu) menu.classList.add('dn');
    },

    // ===== PROJECT INFO MODAL =====
    showProjectInfoFromList(slug) {
        fetch('/api/projects/' + slug)
        .then(r => r.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            window.currentProject = data;
            this.showProjectInfoModal();
        })
        .catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
    },

    showProjectInfoModal() {
        if (!window.currentProject) return;
        const p = window.currentProject;
        const nameEl = document.getElementById('proj-info-name');
        const authorEl = document.getElementById('proj-info-author');
        const descEl = document.getElementById('proj-info-desc');
        const srcCountEl = document.getElementById('proj-info-src-count');
        const trCountEl = document.getElementById('proj-info-tr-count');
        const createdEl = document.getElementById('proj-info-created');
        if (nameEl) nameEl.value = p.name || p.book_title || '';
        if (authorEl) authorEl.value = p.author || '';
        if (descEl) descEl.value = p.description || '';
        if (srcCountEl) srcCountEl.textContent = (p.sources || []).length;
        if (trCountEl) trCountEl.textContent = (p.translated || []).length;
        if (createdEl) {
            if (p.created_at) {
                const d = new Date(p.created_at);
                if (!isNaN(d.getTime())) {
                    const pad = n => String(n).padStart(2, '0');
                    const hours = pad(d.getHours());
                    const mins = pad(d.getMinutes());
                    const day = pad(d.getDate());
                    const month = pad(d.getMonth() + 1);
                    const year = d.getFullYear();
                    createdEl.textContent = `${hours}:${mins} ${day}/${month}/${year}`;
                } else {
                    createdEl.textContent = p.created_at;
                }
            } else {
                createdEl.textContent = '—';
            }
        }
        ModalManager.show('project-info-modal');
    },

    hideProjectInfoModal() {
        ModalManager.hide('project-info-modal');
    },

    saveProjectInfo() {
        if (!window.currentProject) return;
        const name = document.getElementById('proj-info-name')?.value?.trim();
        const author = document.getElementById('proj-info-author')?.value?.trim() || '';
        const description = document.getElementById('proj-info-desc')?.value?.trim() || '';
        if (!name) { UiHelpers.showToast('Tên dự án không được trống', 'error'); return; }
        fetch(`/api/projects/${window.currentProject.slug}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, author, description })
        }).then(r => r.json()).then(data => {
            if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
            UiHelpers.showToast('Đã cập nhật thông tin dự án', 'success');
            ProjectManager.hideProjectInfoModal();
            const newSlug = data.slug || window.currentProject.slug;
            const listView = document.getElementById('projects-list-view');
            if (listView && listView.style.display !== 'none') {
                ProjectManager.loadProjectCards();
            } else {
                ProjectManager.openProject(newSlug);
            }
        }).catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
    },

    async clearProjectTM() {
        if (!window.currentProject) return;
        const slug = window.currentProject.slug;
        const name = window.currentProject.name || slug;
        if (!await showConfirm('Bạn có chắc chắn muốn đặt lại bộ nhớ dịch của dự án "' + name + '" không?\nHành động này sẽ xóa sạch toàn bộ dữ liệu bộ nhớ dịch riêng của dự án này và không thể khôi phục.', { danger: true })) return;

        fetch(`/api/projects/${slug}/tm/clear`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        }).then(r => r.json()).then(data => {
            if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
            UiHelpers.showToast(`Đã xóa ${data.deleted || 0} mục TM`, 'success');
        }).catch(e => UiHelpers.showToast('Lỗi xóa TM: ' + e.message, 'error'));
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
    getChunkTargetFilename() {
        const current = window.currentProjectFile;
        if (current && typeof current === 'object' && current.section === 'sources' && current.name) {
            return current.name;
        }
        if (typeof current === 'string') {
            return current;
        }
        if (window.selectedFiles && window.selectedFiles.size === 1) {
            return Array.from(window.selectedFiles)[0];
        }
        return null;
    },

    showChunkConfig() {
        if (!window.currentProject) {
            UiHelpers.showToast('Chưa chọn dự án', 'error');
            return;
        }
        const filename = ProjectManager.getChunkTargetFilename();
        if (!filename) {
            UiHelpers.showToast('Chọn một tập tin nguồn để chia chunk', 'error');
            return;
        }
        const modal = document.getElementById('chunk-config-modal');
        if (modal) {
            modal.dataset.filename = filename;
        }
        const input = document.getElementById('chunk-size-input');
        if (input && !input.value) {
            input.value = '100000';
        }
        ModalManager.show('chunk-config-modal');
    },

    hideChunkConfig() {
        ModalManager.hide('chunk-config-modal');
    },

    async confirmChunking() {
        if (!window.currentProject) {
            UiHelpers.showToast('Chưa chọn dự án', 'error');
            return;
        }

        const modal = document.getElementById('chunk-config-modal');
        const filename = modal?.dataset.filename || ProjectManager.getChunkTargetFilename();
        if (!filename) {
            UiHelpers.showToast('Chọn một tập tin nguồn để chia chunk', 'error');
            return;
        }

        const maxChars = parseInt(document.getElementById('chunk-size-input')?.value || '0', 10);
        if (!Number.isFinite(maxChars) || maxChars < 1000) {
            UiHelpers.showToast('Giới hạn chunk phải từ 1000 ký tự trở lên', 'error');
            return;
        }

        try {
            UiHelpers.showToast('Đang chia chunk...', 'success');
            const slug = window.currentProject.slug;
            const res = await fetch(`/api/projects/${slug}/chunk/${encodeURIComponent(filename)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ max_chars: maxChars })
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                throw new Error(data.error || 'Không thể chia chunk');
            }
            ProjectManager.hideChunkConfig();
            UiHelpers.showToast(data.message || `Đã chia thành ${data.chunks || 0} chunk`, 'success');
            await ProjectManager.openProject(slug);
        } catch (error) {
            UiHelpers.showToast('Lỗi chia chunk: ' + error.message, 'error');
        }
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

    selectAllTranslatedFiles(checked) {
        if (!window.currentProject) return;
        const allTranslated = window.currentProject.translated || [];
        
        // If checked is not boolean, toggle based on current size
        if (typeof checked !== 'boolean') {
            checked = !(window.selectedTranslatedFiles.size === allTranslated.length && allTranslated.length > 0);
        }
        
        if (checked) {
            allTranslated.forEach(f => window.selectedTranslatedFiles.add(f.name));
        } else {
            allTranslated.forEach(f => window.selectedTranslatedFiles.delete(f.name));
        }
        ProjectManager.updateSelectAllTranslatedButton();
        ProjectManager.renderPmTranslatedList(allTranslated);
    },

};

window.ProjectManager = ProjectManager;
