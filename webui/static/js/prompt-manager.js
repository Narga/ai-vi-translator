// ============================================================
// prompt-manager.js — Library + Project prompt management
// ============================================================

const PromptManager = {
    currentLibrarySet: '',
    PROMPT_KEYS: ['main', 'summary', 'relationships', 'glossary', 'chinh_ta'],

    // ------------------------------------------------------------------
    // Library CRUD
    // ------------------------------------------------------------------

    loadLibrary() {
        fetch('/api/prompts/library')
            .then(r => r.json())
            .then(sets => {
                const el = document.getElementById('library-list');
                if (!el) return;
                if (!sets.length) { el.innerHTML = '<div class="pa4 tc silver i">Chưa có bộ prompt nào</div>'; return; }
                el.innerHTML = sets.map(s =>
                    `<div class="nt-library-item pointer pa3 bb b--black-10 flex items-center justify-between transition-colors ${s.slug === PromptManager.currentLibrarySet ? 'bg-light-blue bl bw2 b--blue' : ''}" onclick="PromptManager.selectLibrarySet('${s.slug}')">
                        <div>
                            <div class="fw6 dark-gray">${s.name || s.slug}</div>
                            <div class="f7 silver mt1">${s.description || 'Không mô tả'}</div>
                        </div>
                        <span class="f7 fw6 br2 ph2 pv1 ${s.has_main ? '' : 'bg-light-gray silver'}">${s.has_main ? '🟢' : 'Trống'}</span>
                    </div>`
                ).join('');
            });
    },

    selectLibrarySet(slug) {
        PromptManager.currentLibrarySet = slug;
        this.loadLibrary();

        // Populate import dropdowns
        this.PROMPT_KEYS.forEach(key => {
            const sel = document.getElementById(`proj-${key}-import`);
            if (!sel) return;
            let opts = '<option value="">— Nạp từ thư viện —</option>';
            // Fetch library list to populate
            fetch('/api/prompts/library').then(r => r.json()).then(sets => {
                sets.forEach(s => {
                    opts += `<option value="${s.slug}">${s.name || s.slug}</option>`;
                });
                sel.innerHTML = opts;
            });
        });
    },

    showNewLibraryModal() {
        const name = prompt('Tên bộ prompt mới:');
        if (!name) return;
        const slug = name.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

        fetch('/api/prompts/library', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, slug, prompts: {} })
        }).then(r => r.json()).then(data => {
            if (data.success) {
                UiHelpers.showToast(`Đã tạo bộ prompt: ${name}`, 'success');
                PromptManager.loadLibrary();
                PromptManager.selectLibrarySet(data.slug);
            } else {
                UiHelpers.showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
            }
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
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    PromptManager.currentLibrarySet = '';
                    PromptManager.loadLibrary();
                    UiHelpers.showToast('Đã xóa bộ prompt', 'success');
                }
            });
    },

    // ------------------------------------------------------------------
    // Project Prompts
    // ------------------------------------------------------------------

    loadProjectPrompts() {
        if (!window.currentProject) return;
        const slug = window.currentProject.slug;
        fetch(`/api/projects/${slug}/prompts`)
            .then(r => r.json())
            .then(data => {
                this.PROMPT_KEYS.forEach(key => {
                    const el = document.getElementById(`proj-${key}-text`);
                    if (el) el.value = data[key] || '';
                    const status = document.getElementById(`proj-${key}-status`);
                    if (status) {
                        const isCustom = data.status && data.status[key];
                        status.textContent = isCustom ? '✏️ Tùy chỉnh' : 'Mặc định';
                        status.className = isCustom ? 'f7 fw6 blue' : 'f7 silver';
                    }
                });
                this._updatePromptStatusBadge(data.is_custom || false);

                // Populate import dropdowns
                fetch('/api/prompts/library').then(r => r.json()).then(sets => {
                    this.PROMPT_KEYS.forEach(key => {
                        const sel = document.getElementById(`proj-${key}-import`);
                        if (!sel) return;
                        let opts = '<option value="">— Nạp từ thư viện —</option>';
                        sets.forEach(s => {
                            opts += `<option value="${s.slug}">${s.name || s.slug}</option>`;
                        });
                        sel.innerHTML = opts;
                    });
                });
            })
            .catch(err => console.error('Error loading project prompts:', err));
    },

    saveProjectPrompts() {
        if (!window.currentProject) {
            UiHelpers.showToast('Không tìm thấy dự án!', 'error');
            return;
        }
        const payload = {};
        this.PROMPT_KEYS.forEach(key => {
            const el = document.getElementById(`proj-${key}-text`);
            payload[key] = el ? el.value : '';
        });

        const btn = document.getElementById('btn-save-project-prompts');
        if (btn) { btn.disabled = true; btn.textContent = '...Đang lưu...'; }

        fetch(`/api/projects/${window.currentProject.slug}/prompts`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(r => { if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`); return r.json(); })
        .then(data => {
            if (data.success) {
                UiHelpers.showToast('Đã lưu Chỉ dẫn dự án!', 'success');
                PromptManager.loadProjectPrompts();
            } else {
                UiHelpers.showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
            }
        })
        .catch(err => {
            console.error('saveProjectPrompts error:', err);
            UiHelpers.showToast('Lỗi kết nối server!', 'error');
        })
        .finally(() => {
            if (btn) { btn.disabled = false; btn.textContent = 'Lưu'; }
        });
    },

    importFromLibrary(key, librarySlug) {
        if (!window.currentProject || !librarySlug) return;

        fetch(`/api/projects/${window.currentProject.slug}/prompts/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ library: librarySlug, key })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                UiHelpers.showToast(data.message, 'success');
                PromptManager.loadProjectPrompts();
                // Reset dropdown
                const sel = document.getElementById(`proj-${key}-import`);
                if (sel) sel.value = '';
            } else {
                UiHelpers.showToast(data.error || 'Lỗi nạp prompt', 'error');
            }
        })
        .catch(err => UiHelpers.showToast('Lỗi kết nối: ' + err.message, 'error'));
    },

    async resetProjectPrompts() {
        if (!window.currentProject) { UiHelpers.showToast('Chưa chọn dự án!', 'error'); return; }
        if (!await showConfirm('Xóa toàn bộ chỉ dẫn riêng của dự án?')) return;

        fetch(`/api/projects/${window.currentProject.slug}/prompts/reset`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                UiHelpers.showToast(data.message, 'success');
                PromptManager.loadProjectPrompts();
            } else {
                UiHelpers.showToast(data.error || 'Lỗi khi xóa chỉ dẫn', 'error');
            }
        })
        .catch(err => UiHelpers.showToast('Lỗi kết nối: ' + err.message, 'error'));
    },

    _updatePromptStatusBadge(isCustom) {
        const badge = document.getElementById('prompt-status-badge');
        if (badge) {
            if (isCustom) {
                badge.innerHTML = '✏️ Chỉ dẫn Dự án';
                badge.className = 'f7 fw6 blue ba b--blue pa1 br2 bg-washed-blue';
            } else {
                badge.innerHTML = '📌 Mặc định';
                badge.className = 'f7 fw6 silver ba b--black-10 pa1 br2';
            }
        }
        const resetBtn = document.getElementById('btn-reset-project-prompts');
        if (resetBtn) resetBtn.style.display = isCustom ? '' : 'none';
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
            .then(r => r.json())
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
            .then(r => r.json())
            .then(res => {
                if (res.success) UiHelpers.showToast('Đã lưu thành công!', 'success');
                else UiHelpers.showToast(res.error || 'Lỗi lưu', 'error');
            })
            .catch(e => UiHelpers.showToast(e.message, 'error'));
    },

    aiGenerateContent(fieldKey) {
        if (!window.currentProject) { UiHelpers.showToast('Chưa chọn dự án!', 'error'); return; }

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

        if (outputEl) { outputEl.placeholder = '⏳ AI đang tạo nội dung...'; outputEl.disabled = true; }

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
                if (outputEl) { outputEl.disabled = false; outputEl.placeholder = ''; }
                if (data.success && data.summary) {
                    if (outputEl) outputEl.value = data.summary;
                    UiHelpers.showToast('AI đã tạo nội dung thành công!', 'success');
                } else {
                    UiHelpers.showToast(data.error || 'AI không trả về kết quả', 'error');
                }
            })
            .catch(e => {
                if (outputEl) { outputEl.disabled = false; outputEl.placeholder = ''; }
                UiHelpers.showToast('Lỗi: ' + e.message, 'error');
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
        const sourceSelect = document.getElementById('pm-info-source-file');
        const sourceFile = sourceSelect ? sourceSelect.value : '';
        if (!sourceFile) {
            UiHelpers.showToast('Vui lòng chọn tập tin nguồn trước khi Generate', 'error');
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
        if (outputEl) { outputEl.placeholder = '⏳ AI đang tạo nội dung...'; outputEl.disabled = true; }

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
                if (outputEl) { outputEl.disabled = false; outputEl.placeholder = ''; }
                const content = data.content || data.summary;
                if (data.success && content) {
                    if (outputEl) outputEl.value = content;
                    const assetFile = data.asset_file || fieldKey + '.txt';
                    UiHelpers.showToast(`Đã tạo và lưu vào assets/${assetFile}`, 'success');
                } else {
                    UiHelpers.showToast(data.error || 'AI không trả về kết quả', 'error');
                }
            })
            .catch(e => {
                if (outputEl) { outputEl.disabled = false; outputEl.placeholder = ''; }
                UiHelpers.showToast('Lỗi: ' + e.message, 'error');
            });
    }
};

window.PromptManager = PromptManager;
