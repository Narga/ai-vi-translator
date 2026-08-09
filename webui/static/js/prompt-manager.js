// ============================================================
// prompt-manager.js — Library + Project prompt management
// ============================================================

const PromptManager = {
    // ------------------------------------------------------------
    // Library Management (Library Only)
    // ------------------------------------------------------------

    currentLibrarySet: '',
    PROMPT_KEYS: ['main', 'summary', 'relationships', 'glossary', 'chinh_ta'],

    // ------------------------------------------------------------
    // Library CRUD (Library Only)
    // ------------------------------------------------------------

    loadLibrary() {
        fetch('/api/prompts/library')
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(sets => {
                const el = document.getElementById('library-list');
                if (!el) return;
                if (!sets.length) { el.innerHTML = '<div class="pa4 tc silver i">Chưa có bộ prompt nào</div>'; return; }
                el.innerHTML = sets.map(s =>
                    `<div class="nt-library-item pointer pa3 bb b--black-10 flex items-center justify-between transition-colors ${s.slug === PromptManager.currentLibrarySet ? 'bg-light-blue bl bw2 b--blue' : ''}" onclick="PromptManager.selectLibrarySet('${s.slug}')">
                        <div class="flex flex-column" style="flex: 1; min-width: 0; padding-right: 8px;">
                            <span class="fw6 dark-gray db truncate">${s.name || s.slug}</span>
                            <span class="f7 silver mt1 db truncate">${s.description || 'Không mô tả'}</span>
                        </div>
                        <span class="f7 fw6 br2 ph2 pv1 flex-shrink-0 ${s.has_main ? '' : 'bg-light-gray silver'}">${s.has_main ? '🟢' : 'Trống'}</span>
                    </div>`
                ).join('');
            });
    },

    selectLibrarySet(slug) {
        PromptManager.currentLibrarySet = slug;
        this.loadLibrary();

        // Load library set contents into prompt editor
        fetch(`/api/prompts/library/${slug}`)
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(data => {
                const set = data.data || data;
                const meta = set.meta || {};
                PromptManager.currentLibraryName = meta.name || set.slug;
                PromptManager.currentLibraryDesc = meta.description || '';

                this.PROMPT_KEYS.forEach(key => {
                    const el = document.getElementById(`set-${key}-text`);
                    if (el) {
                        el.value = set.prompts && set.prompts[key] || '';
                    }
                });
                // Update header with set name and description
                const nameEl = document.getElementById('library-prompt-title');
                const descEl = document.getElementById('library-prompt-desc');
                if (nameEl) nameEl.textContent = PromptManager.currentLibraryName;
                if (descEl) descEl.textContent = PromptManager.currentLibraryDesc || 'Không mô tả';

                // Toggle delete and info buttons
                const deleteBtn = document.getElementById('btn-delete-library-set');
                const infoBtn = document.getElementById('btn-info-library-set');
                if (deleteBtn) {
                    if (slug === 'default') {
                        deleteBtn.classList.add('dn');
                    } else {
                        deleteBtn.classList.remove('dn');
                    }
                }
                if (infoBtn) {
                    infoBtn.classList.remove('dn');
                }
            });
    },

    saveLibrarySet() {
        if (!PromptManager.currentLibrarySet) return;
        const payload = {};
        this.PROMPT_KEYS.forEach(key => {
            const el = document.getElementById(`set-${key}-text`);
            payload[key] = el ? el.value : '';
        });

        const btn = document.getElementById('btn-save-library-set');
        if (btn) { btn.disabled = true; btn.textContent = '...Đang lưu...'; }

        fetch(`/api/prompts/library/${PromptManager.currentLibrarySet}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompts: payload,
                name: PromptManager.currentLibraryName || PromptManager.currentLibrarySet,
                description: PromptManager.currentLibraryDesc || ''
            })
        })
            .then(r => { if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`); return r.json(); })
            .then(data => {
                if (data.success) {
                    UiHelpers.showToast('Đã lưu bộ prompt!', 'success');
                    PromptManager.loadLibrary();
                } else {
                    UiHelpers.showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
                }
            })
            .catch(err => {
                console.error('saveLibrarySet error:', err);
                UiHelpers.showToast('Lỗi kết nối server!', 'error');
            })
            .finally(() => {
                if (btn) { btn.disabled = false; btn.textContent = 'Lưu'; }
            });
    },

    showNewLibraryModal() {
        const nameEl = document.getElementById('new-library-name');
        const descEl = document.getElementById('new-library-desc');
        if (nameEl) nameEl.value = '';
        if (descEl) descEl.value = '';
        ModalManager.show('new-library-modal');
    },

    confirmCreateLibrary() {
        const name = (document.getElementById('new-library-name')?.value || '').trim();
        const description = (document.getElementById('new-library-desc')?.value || '').trim();
        if (!name) { UiHelpers.showToast('Vui lòng nhập tên bộ prompt!', 'error'); return; }

        const slug = name.toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/đ/g, 'd')
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/(^-|-$)/g, '');

        if (!slug) { UiHelpers.showToast('Tên không hợp lệ!', 'error'); return; }

        fetch('/api/prompts/library', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, slug, description, prompts: {} })
        })
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
        })
        .then(data => {
            if (data.success) {
                UiHelpers.showToast(`Đã tạo bộ prompt: ${name}`, 'success');
                ModalManager.hide('new-library-modal');
                PromptManager.loadLibrary();
                PromptManager.loadProjectPromptsFromWorkspace();
                PromptManager.selectLibrarySet(data.slug);
            } else {
                UiHelpers.showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
            }
        })
        .catch(err => {
            console.error('Create library set error:', err);
            UiHelpers.showToast('Lỗi kết nối server!', 'error');
        });
    },

    showEditLibraryModal() {
        if (!PromptManager.currentLibrarySet) return;
        const inputName = document.getElementById('edit-library-name');
        const inputDesc = document.getElementById('edit-library-desc');

        if (inputName) inputName.value = PromptManager.currentLibraryName || '';
        if (inputDesc) inputDesc.value = PromptManager.currentLibraryDesc || '';

        ModalManager.show('edit-library-modal');
    },

    confirmEditLibrary() {
        if (!PromptManager.currentLibrarySet) return;
        const name = (document.getElementById('edit-library-name')?.value || '').trim();
        const description = (document.getElementById('edit-library-desc')?.value || '').trim();
        if (!name) { UiHelpers.showToast('Vui lòng nhập tên bộ prompt!', 'error'); return; }

        const prompts = {};
        this.PROMPT_KEYS.forEach(key => {
            const el = document.getElementById(`set-${key}-text`);
            prompts[key] = el ? el.value : '';
        });

        const btn = document.getElementById('btn-confirm-edit-library');
        if (btn) { btn.disabled = true; btn.textContent = '...Đang lưu...'; }

        fetch(`/api/prompts/library/${PromptManager.currentLibrarySet}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, prompts })
        })
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
        })
        .then(data => {
            if (data.success) {
                UiHelpers.showToast('Đã cập nhật thông tin bộ prompt!', 'success');
                ModalManager.hide('edit-library-modal');
                
                PromptManager.currentLibraryName = name;
                PromptManager.currentLibraryDesc = description;

                PromptManager.loadLibrary();
                PromptManager.loadProjectPromptsFromWorkspace();
                const nameEl = document.getElementById('library-prompt-title');
                const descEl = document.getElementById('library-prompt-desc');
                if (nameEl) nameEl.textContent = name;
                if (descEl) descEl.textContent = description || 'Không mô tả';
            } else {
                UiHelpers.showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
            }
        })
        .catch(err => {
            console.error('Edit library set error:', err);
            UiHelpers.showToast('Lỗi kết nối server!', 'error');
        })
        .finally(() => {
            if (btn) { btn.disabled = false; btn.textContent = 'Cập nhật'; }
        });
    },

    async deleteLibrarySet() {
        if (!PromptManager.currentLibrarySet) return;
        if (PromptManager.currentLibrarySet === 'default') {
            UiHelpers.showToast('Không thể xóa bộ mặc định', 'error');
            return;
        }
        if (!await showConfirm('Xóa bộ prompt "' + PromptManager.currentLibrarySet + '"?', { danger: true })) return;

        fetch('/api/prompts/library/' + PromptManager.currentLibrarySet, { method: 'DELETE' })
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(data => {
                if (data.success) {
                    PromptManager.currentLibrarySet = '';
                    PromptManager.loadLibrary();
                    PromptManager.loadProjectPromptsFromWorkspace();
                    // Clear the editors
                    this.PROMPT_KEYS.forEach(key => {
                        const el = document.getElementById(`set-${key}-text`);
                        if (el) el.value = '';
                    });
                    const nameEl = document.getElementById('library-prompt-title');
                    const descEl = document.getElementById('library-prompt-desc');
                    if (nameEl) nameEl.textContent = 'Chưa chọn bộ prompt';
                    if (descEl) descEl.textContent = 'Mô tả...';
                    const deleteBtn = document.getElementById('btn-delete-library-set');
                    if (deleteBtn) deleteBtn.classList.add('dn');

                    UiHelpers.showToast('Đã xóa bộ prompt', 'success');
                } else {
                    UiHelpers.showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
                }
            })
            .catch(err => {
                console.error('Delete library set error:', err);
                UiHelpers.showToast('Lỗi kết nối server!', 'error');
            });
    },

    // ------------------------------------------------------------------
    // Project Prompts (Workspace / Project Override Only)
    // ------------------------------------------------------------------

    _getActiveWorkspacePromptTabKey() {
        const tab = window.activeWorkspacePromptTab || 'main';
        return tab === 'chinh-ta' ? 'chinh_ta' : tab;
    },

    loadProjectPromptsFromWorkspace() {
        if (!window.currentProject) return;
        const slug = window.currentProject.slug;
        fetch(`/api/projects/${slug}/prompts`)
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(data => {
                this.PROMPT_KEYS.forEach(key => {
                    const htmlKey = key === 'chinh_ta' ? 'chinh-ta' : key;
                    const el = document.getElementById(`pm-proj-prompt-${htmlKey}`);
                    if (el) el.value = data[key] || '';
                });

                // Populate library set dropdown
                fetch('/api/prompts/library')
                    .then(r => {
                        if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                        return r.json();
                    })
                    .then(sets => {
                    const sel = document.getElementById('pm-prompt-library-select');
                    if (sel) {
                        let opts = '<option value="">— Chọn bộ prompt —</option>';
                        sets.forEach(s => {
                            opts += `<option value="${s.slug}">${s.name || s.slug}</option>`;
                        });
                        sel.innerHTML = opts;
                    }
                });
            })
            .catch(err => console.error('Error loading project prompts:', err));
    },

    saveProjectPromptsFromWorkspace() {
        if (!window.currentProject) {
            UiHelpers.showToast('Không tìm thấy dự án!', 'error');
            return;
        }
        const payload = {};
        this.PROMPT_KEYS.forEach(key => {
            const htmlKey = key === 'chinh_ta' ? 'chinh-ta' : key;
            const el = document.getElementById(`pm-proj-prompt-${htmlKey}`);
            payload[key] = el ? el.value : '';
        });

        const btn = document.querySelector('button[onclick="PromptManager.saveProjectPromptsFromWorkspace()"]') ||
                    document.querySelector('button[onclick="PromptManager.saveProjectPrompts()"]');
        if (btn) { btn.disabled = true; btn.textContent = '...Đang lưu...'; }

        fetch(`/api/projects/${window.currentProject.slug}/prompts`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(r => { if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`); return r.json(); })
        .then(data => {
            if (data.success) {
                UiHelpers.showToast('Đã lưu Chỉ dẫn dự án!', 'success');
                this.PROMPT_KEYS.forEach(key => {
                    const htmlKey = key === 'chinh_ta' ? 'chinh-ta' : key;
                    DirtyState.clean(`pm-proj-prompt-${htmlKey}`);
                });
                PromptManager.loadProjectPromptsFromWorkspace();
            } else {
                UiHelpers.showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
            }
        })
        .catch(err => {
            console.error('saveProjectPromptsFromWorkspace error:', err);
            UiHelpers.showToast('Lỗi kết nối server!', 'error');
        })
        .finally(() => {
            if (btn) { btn.disabled = false; btn.textContent = 'Lưu'; }
        });
    },

    importFromLibraryToWorkspace() {
        if (!window.currentProject) {
            UiHelpers.showToast('Chưa chọn dự án!', 'error');
            return;
        }
        const sel = document.getElementById('pm-prompt-library-select');
        const librarySlug = sel ? sel.value : '';
        if (!librarySlug) {
            UiHelpers.showToast('Vui lòng chọn bộ prompt nguồn!', 'error');
            return;
        }

        const activeTab = window.activeWorkspacePromptTab || 'main';
        const key = activeTab === 'chinh-ta' ? 'chinh_ta' : activeTab;

        fetch(`/api/prompts/library/${librarySlug}`)
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(data => {
                const set = data.data || data;
                const content = set.prompts && set.prompts[key] || '';

                const textareaId = `pm-proj-prompt-${activeTab}`;
                const textarea = document.getElementById(textareaId);
                if (textarea) {
                    textarea.value = content;
                    DirtyState.mark(textareaId);
                    UiHelpers.showToast(`Đã nhập chỉ dẫn '${activeTab}' từ bộ '${set.name || set.slug}' (Chưa lưu)`, 'info');
                }
            })
            .catch(err => {
                console.error('importFromLibraryToWorkspace error:', err);
                UiHelpers.showToast('Lỗi kết nối khi nạp thư viện!', 'error');
            });
    },

    // Backwards compatibility wrappers
    loadProjectPrompts() {
        this.loadProjectPromptsFromWorkspace();
    },

    saveProjectPrompts() {
        this.saveProjectPromptsFromWorkspace();
    },

    importFromLibrary(key, librarySlug) {
        this.importFromLibraryToWorkspace();
    },

    // ------------------------------------------------------------------
    // Guidelines (giữ nguyên từ cũ)
    // ------------------------------------------------------------------

    GUIDELINE_TAB_MAP: {
        'style-guide':  { field: 'style_guide',  elId: 'pm-guide-style-guide',  modelId: 'style-guide-model' },
        'relationship': { field: 'characters',   elId: 'pm-guide-relationship', modelId: 'relationship-model' },
        'glossary':     { field: 'glossary',     elId: 'pm-guide-glossary',     modelId: 'glossary-model' },
        'summary':      { field: 'summary',      elId: 'pm-guide-summary',      modelId: 'summary-model' },
    },

    loadGuidelineTab(tab) {
        if (!window.currentProject) return;
        const mapping = PromptManager.GUIDELINE_TAB_MAP[tab];
        if (!mapping) return;

        PromptManager._populateModelSelect('pm-info-model');

        fetch(`/api/projects/${window.currentProject.slug}/guidelines`)
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(data => {
                const el = document.getElementById(mapping.elId);
                if (el) el.value = data[mapping.field] || '';
            })
            .catch(e => console.error('loadGuidelineTab error:', e));
    },

    _populateModelSelect(selId) {
        const sel = document.getElementById(selId);
        const mainSel = document.getElementById('model');
        if (!sel || !mainSel) return;
        let opts = '<option value="">— Chọn Model —</option>';
        for (const opt of mainSel.options) {
            if (opt.value) opts += `<option value="${opt.value}">${opt.text}</option>`;
        }
        sel.innerHTML = opts;
    },

    saveGuidelineField(fieldKey) {
        if (!window.currentProject) return;
        const reverseMap = {
            'style_guide': 'pm-guide-style-guide',
            'relationship': 'pm-guide-relationship',
            'glossary': 'pm-guide-glossary',
            'summary': 'pm-guide-summary',
        };
        const elId = reverseMap[fieldKey];
        const el = document.getElementById(elId);
        if (!el) return;

        const backendKey = fieldKey === 'relationship' ? 'characters' : fieldKey;

        fetch(`/api/projects/${window.currentProject.slug}/guidelines`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [backendKey]: el.value })
        })
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                return r.json();
            })
            .then(res => {
                if (res.success) UiHelpers.showToast('Đã lưu thành công!', 'success');
                else UiHelpers.showToast(res.error || 'Lỗi lưu', 'error');
            })
            .catch(e => UiHelpers.showToast(e.message, 'error'));
    },

    aiGenerateContent(fieldKey) {
        if (!window.currentProject) { UiHelpers.showToast('Chưa chọn dự án!', 'error'); return; }
        if (window._contentTabGenerating) { return; }
        window._contentTabGenerating = true;

        const modelSelMap = {
            'style_guide': 'style-guide-model',
            'relationship': 'relationship-model',
            'glossary': 'glossary-model',
            'summary': 'summary-model',
        };
        const outputElMap = {
            'style_guide': 'pm-guide-style-guide',
            'relationship': 'pm-guide-relationship',
            'glossary': 'pm-guide-glossary',
            'summary': 'pm-guide-summary',
        };

        const modelSel = document.getElementById(modelSelMap[fieldKey]);
        const model = modelSel ? modelSel.value : '';
        const outputEl = document.getElementById(outputElMap[fieldKey]);
        const btn = document.querySelector(`button[onclick*="aiGenerateContent('${fieldKey}')"]`) || document.querySelector('#pm-btn-generate-content');

        if (btn) {
            btn.dataset.originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '🔄 <span class="nt-btn-spinner dib"></span> Đang phân tích...';
        }
        if (outputEl) { outputEl.placeholder = '⏳ AI đang phân tích...'; outputEl.disabled = true; }

        fetch(`/api/projects/${window.currentProject.slug}/summarize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model, content_type: fieldKey })
        })
            .then(async r => {
                const isJson = r.headers.get('content-type')?.includes('application/json');
                const data = isJson ? await r.json() : null;
                if (!r.ok) throw new Error(data?.error || `Lỗi server: ${r.status}`);
                return data;
            })
            .then(data => {
                if (data.status === 'started' && data.job_id) {
                    TranslationWorker.connectToProgress(btn, false, data.job_id, 1, function(evt) {
                        const assetFile = evt.asset_file || fieldKey + '.txt';
                        fetch(`/api/projects/${window.currentProject.slug}/file/assets/${assetFile}`)
                            .then(r => {
                                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                                return r.json();
                            })
                            .then(data => {
                                if (outputEl && data.content) outputEl.value = data.content;
                                UiHelpers.showToast(`Đã tạo và lưu vào assets/${assetFile}`, 'success');
                            })
                            .catch(e => {
                                UiHelpers.showToast('Lỗi tải kết quả: ' + e.message, 'error');
                            })
                            .finally(function() {
                                window._contentTabGenerating = false;
                            });
                    });
                } else {
                    throw new Error(data?.error || 'Không nhận được job_id');
                }
            })
            .catch(e => {
                TranslationWorker.resetButton(btn);
                if (outputEl) { outputEl.disabled = false; outputEl.placeholder = ''; }
                UiHelpers.showToast('Lỗi: ' + e.message, 'error');
                window._contentTabGenerating = false;
            });
    },

    saveGuidelineFromInfoTab() {
        const fieldKey = window.pmActiveInfoTab || 'style_guide';
        const saveKeyMap = {
            'style_guide': 'style_guide',
            'relationship': 'relationship',
            'glossary': 'glossary',
            'summary': 'summary',
        };
        PromptManager.saveGuidelineField(saveKeyMap[fieldKey] || fieldKey);
    },

    aiGenerateFromInfoTab() {
        if (!window.currentProject) { UiHelpers.showToast('Chưa chọn dự án!', 'error'); return; }
        if (window._infoTabGenerating) { return; }
        window._infoTabGenerating = true;

        const sourceSelect = document.getElementById('pm-info-source-file');
        const sourceFile = sourceSelect ? sourceSelect.value : '';
        if (!sourceFile) {
            UiHelpers.showToast('Vui lòng chọn tập tin nguồn trước khi Generate', 'error');
            window._infoTabGenerating = false;
            return;
        }

        const modelSel = document.getElementById('pm-info-model');
        const model = modelSel ? modelSel.value : '';
        const fieldKey = window.pmActiveInfoTab || 'style_guide';

        const outputElMap = {
            'style_guide': 'pm-guide-style-guide',
            'relationship': 'pm-guide-relationship',
            'glossary': 'pm-guide-glossary',
            'summary': 'pm-guide-summary',
        };
        const outputEl = document.getElementById(outputElMap[fieldKey]);
        const btn = document.querySelector('#pm-info-generate-btn') || document.querySelector('button[onclick*="aiGenerateFromInfoTab"]');

        if (btn) {
            btn.dataset.originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '🔄 <span class="nt-btn-spinner dib"></span> Đang phân tích...';
        }
        if (outputEl) { outputEl.placeholder = '⏳ AI đang phân tích...'; outputEl.disabled = true; }

        fetch(`/api/projects/${window.currentProject.slug}/summarize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model, source_file: sourceFile, content_type: fieldKey })
        })
            .then(async r => {
                const isJson = r.headers.get('content-type')?.includes('application/json');
                const data = isJson ? await r.json() : null;
                if (!r.ok) throw new Error(data?.error || `Lỗi server: ${r.status}`);
                return data;
            })
            .then(data => {
                if (data.status === 'started' && data.job_id) {
                    TranslationWorker.connectToProgress(btn, false, data.job_id, 1, function(evt) {
                        const assetFile = evt.asset_file || fieldKey + '.txt';
                        fetch(`/api/projects/${window.currentProject.slug}/file/assets/${assetFile}`)
                            .then(r => {
                                if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                                return r.json();
                            })
                            .then(data => {
                                if (outputEl && data.content) outputEl.value = data.content;
                                UiHelpers.showToast(`Đã tạo và lưu vào assets/${assetFile}`, 'success');
                            })
                            .catch(e => {
                                UiHelpers.showToast('Lỗi tải kết quả: ' + e.message, 'error');
                            })
                            .finally(function() {
                                window._infoTabGenerating = false;
                            });
                    });
                } else {
                    throw new Error(data?.error || 'Không nhận được job_id');
                }
            })
            .catch(e => {
                TranslationWorker.resetButton(btn);
                if (outputEl) { outputEl.disabled = false; outputEl.placeholder = ''; }
                UiHelpers.showToast('Lỗi: ' + e.message, 'error');
                window._infoTabGenerating = false;
            });
    }
};

window.PromptManager = PromptManager;
