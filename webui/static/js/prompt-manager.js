// ============================================================
// prompt-manager.js — Genre-based prompt management
// ============================================================

const PromptManager = {
    currentGenre: '',

    loadGenres() {
        fetch('/api/prompt-sets')
            .then(r => r.json())
            .then(sets => {
                const el = document.getElementById('genre-list');
                if (!sets.length) { el.innerHTML = '<div class="pa4 tc silver i">Chưa có Thể Loại nào</div>'; return; }
                el.innerHTML = sets.map(s =>
                    `<div class="nt-genre-item pointer pa3 bb b--black-10 flex items-center justify-between transition-colors ${s.slug === PromptManager.currentGenre ? 'bg-light-blue bl bw2 b--blue' : ''}" onclick="PromptManager.selectGenre('${s.slug}')">
                        <div>
                            <div class="fw6 dark-gray">${s.name}</div>
                            <div class="f7 silver mt1">${s.description || 'Không mô tả'}</div>
                        </div>
                        <span class="f7 fw6 br2 ph2 pv1 ${s.has_main ? '' : 'bg-light-gray silver'}">${s.has_main ? '🟢' : 'Trống'}</span>
                    </div>`
                ).join('');

                if (!PromptManager.currentGenre && sets.length > 0) {
                    PromptManager.selectGenre(sets[0].slug);
                }
            });
    },

    selectGenre(slug) {
        PromptManager.currentGenre = slug;

        const isDefault = (slug === 'default');
        document.getElementById('btn-delete-genre').disabled = isDefault || !slug;
        const btnUse = document.getElementById('btn-use-genre');
        if (btnUse) btnUse.classList.toggle('dn', isDefault);

        if (isDefault) {
            document.getElementById('btn-delete-genre').title = 'Không thể xóa bộ mặc định';
        } else {
            document.getElementById('btn-delete-genre').title = '';
        }

        document.getElementById('genre-editor').classList.remove('dn');
        document.getElementById('genre-editor').classList.add('flex');

        fetch('/api/prompt-sets/' + slug)
            .then(r => r.json())
            .then(data => {
                document.getElementById('genre-editor-title').innerHTML = '<span class="mr2">📝</span> ' + (data.meta.name || slug);
                document.getElementById('genre-editor-desc').textContent = data.meta.description || '';
                document.getElementById('genre-main-text').value = data.prompts.main || '';
                document.getElementById('genre-summary-text').value = data.prompts.summary || '';
                document.getElementById('genre-relationships-text').value = data.prompts.relationships || '';
                document.getElementById('genre-glossary-text').value = data.prompts.glossary || '';
                document.getElementById('genre-chinh-ta-text').value = data.prompts.chinh_ta || '';
                PromptManager.loadGenres();
            });
    },

    async useGenre() {
        if (!PromptManager.currentGenre || PromptManager.currentGenre === 'default') return;
        if (!await showConfirm('Sử dụng bộ prompt "' + PromptManager.currentGenre + '" làm mặc định cho dịch thuật?')) return;

        fetch('/api/prompt-sets/' + PromptManager.currentGenre + '/use', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    UiHelpers.showToast('Đã kích hoạt bộ prompt cho dịch thuật!', 'success');
                    fetch('/api/prompt-sets/default')
                        .then(r => r.json())
                        .then(d => { window.prompts = d.prompts || {}; });
                } else {
                    UiHelpers.showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
                }
            });
    },

    cloneGenre() {
        if (!PromptManager.currentGenre) return;
        document.getElementById('new-genre-name').value = 'Bản sao ' + PromptManager.currentGenre;
        document.getElementById('new-genre-slug').value = 'ban-sao-' + PromptManager.currentGenre;
        document.getElementById('new-genre-desc').value = 'Nhân bản từ ' + PromptManager.currentGenre;
        window.isCloning = true;
        document.getElementById('new-genre-modal').style.display = 'flex';
    },

    createGenre(e) {
        if (e) e.preventDefault();
        const name = document.getElementById('new-genre-name').value.trim();
        const slug = document.getElementById('new-genre-slug').value.trim() ||
            name.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
        const desc = document.getElementById('new-genre-desc').value.trim();

        if (!name) { UiHelpers.showToast('Tên thể loại không được rỗng!', 'error'); return; }

        const promptsData = window.isCloning ? {
            main: document.getElementById('genre-main-text').value,
            summary: document.getElementById('genre-summary-text').value,
            relationships: document.getElementById('genre-relationships-text').value,
            glossary: document.getElementById('genre-glossary-text').value,
            chinh_ta: document.getElementById('genre-chinh-ta-text').value,
        } : { main: '', summary: '', relationships: '', glossary: '', chinh_ta: '' };
        window.isCloning = false;

        fetch('/api/prompt-sets', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, slug, description: desc, prompts: promptsData })
        }).then(r => r.json()).then(data => {
            if (data.success) {
                document.getElementById('new-genre-name').value = '';
                document.getElementById('new-genre-slug').value = '';
                document.getElementById('new-genre-desc').value = '';
                PromptManager.loadGenres();
                PromptManager.selectGenre(data.slug);
                UiHelpers.showToast(`Đã tạo bộ prompt: ${name}`, 'success');
            } else {
                UiHelpers.showToast('Lỗi khởi tạo: ' + (data.error || 'Unknown Error'), 'error');
            }
        });
    },

    saveGenre() {
        if (!PromptManager.currentGenre) {
            UiHelpers.showToast('Vui lòng chọn một bộ prompt trước khi lưu!', 'error');
            return;
        }
        const btn = document.getElementById('btn-save-genre');
        const originalText = btn.textContent;
        btn.textContent = '...Đang lưu...';
        btn.disabled = true;

        const payload = {
            prompts: {
                main: document.getElementById('genre-main-text').value,
                summary: document.getElementById('genre-summary-text').value,
                relationships: document.getElementById('genre-relationships-text').value,
                glossary: document.getElementById('genre-glossary-text').value,
                chinh_ta: document.getElementById('genre-chinh-ta-text').value,
            }
        };

        fetch('/api/prompt-sets/' + PromptManager.currentGenre, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(r => { if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`); return r.json(); })
        .then(data => {
            if (data.success) UiHelpers.showToast('Lưu prompt hoàn tất!', 'success');
            else UiHelpers.showToast('Lỗi lưu: ' + (data.error || 'Unknown'), 'error');
        })
        .catch(err => {
            console.error('saveGenre error:', err);
            UiHelpers.showToast('Lỗi kết nối server khi lưu prompt!', 'error');
        })
        .finally(() => {
            btn.textContent = originalText;
            btn.disabled = false;
        });
    },

    async deleteGenre() {
        if (!PromptManager.currentGenre) return;
        if (!await showConfirm('Hành động này KHÔNG THỂ KHÔI PHỤC. Chắc chắn xóa "' + PromptManager.currentGenre + '"?', { danger: true })) return;
        fetch('/api/prompt-sets/' + PromptManager.currentGenre, { method: 'DELETE' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    PromptManager.currentGenre = '';
                    document.getElementById('genre-empty-state').classList.remove('dn');
                    document.getElementById('genre-editor').classList.add('dn');
                    document.getElementById('genre-editor').classList.remove('flex');
                    document.getElementById('btn-delete-genre').disabled = true;
                    PromptManager.loadGenres();
                }
            });
    },

    loadProjectPrompts() {
        if (!window.currentProject) return;
        const slug = window.currentProject.slug;
        fetch(`/api/projects/${slug}/prompts`)
            .then(r => r.json())
            .then(data => {
                const fields = {
                    'proj-prompt-main': data.main,
                    'proj-prompt-summary': data.summary,
                    'proj-prompt-relationships': data.relationships,
                    'proj-prompt-glossary': data.glossary,
                    'proj-prompt-chinh-ta': data.chinh_ta
                };
                for (const [id, val] of Object.entries(fields)) {
                    const el = document.getElementById(id);
                    if (el) el.value = val || '';
                }
                PromptManager._updatePromptStatusBadge(data.is_custom || false);
            })
            .catch(err => console.error('Error loading project prompts:', err));

        const selIds = ['prompt-library-select', 'pm-prompt-library-select'];
        selIds.forEach(selId => {
            const sel = document.getElementById(selId);
            if (sel) {
                fetch('/api/prompt-sets').then(r => r.json()).then(data => {
                    const genres = (data || []).filter(g => g.slug !== 'default');
                    let opts = '<option value="">— Chọn bộ prompt —</option>';
                    opts += '<option value="default">📌 Mặc định (Hệ thống)</option>';
                    genres.forEach(g => { opts += `<option value="${g.slug}">📁 ${g.name}</option>`; });
                    sel.innerHTML = opts;
                }).catch(() => {});
            }
        });
    },

    saveProjectPrompts() {
        if (!window.currentProject) {
            UiHelpers.showToast('Không tìm thấy thông tin dự án hiện tại!', 'error');
            return;
        }
        const fields = {
            main: document.getElementById('proj-prompt-main'),
            summary: document.getElementById('proj-prompt-summary'),
            relationships: document.getElementById('proj-prompt-relationships'),
            glossary: document.getElementById('proj-prompt-glossary'),
            chinh_ta: document.getElementById('proj-prompt-chinh-ta')
        };
        
        const payload = {};
        for (const [key, el] of Object.entries(fields)) {
            payload[key] = el ? el.value : '';
        }

        const btn = document.getElementById('btn-save-project-prompts');
        if (btn) { btn.disabled = true; btn.textContent = '...Đang lưu...'; }

        fetch(`/api/projects/${window.currentProject.slug}/prompts`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(r => { if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`); return r.json(); })
        .then(data => {
            if (data.success) {
                UiHelpers.showToast('Đã lưu Chỉ dẫn của dự án!', 'success');
                PromptManager._updatePromptStatusBadge(true);
            } else {
                UiHelpers.showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
            }
        })
        .catch(err => {
            console.error('saveProjectPrompts error:', err);
            UiHelpers.showToast('Lỗi kết nối server khi lưu prompts!', 'error');
        })
        .finally(() => {
            if (btn) { btn.disabled = false; btn.innerHTML = '💾 Lưu chỉ dẫn dự án'; }
        });
    },

    async importPromptFromLibrary() {
        if (!window.currentProject) { UiHelpers.showToast('Chưa chọn dự án!', 'error'); return; }
        // Tìm dropdown đang active (có thể là old workspace hoặc projects tab)
        const sel = document.getElementById('pm-prompt-library-select') || document.getElementById('prompt-library-select');
        const genre = sel ? sel.value : '';
        if (!genre) { UiHelpers.showToast('Chọn bộ prompt từ thư viện trước!', 'error'); return; }

        const displayName = sel.options[sel.selectedIndex]?.text || genre;
        if (!await showConfirm('Áp dụng bộ "' + displayName + '" vào dự án?')) return;

        fetch(`/api/projects/${window.currentProject.slug}/prompts/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ genre })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                UiHelpers.showToast(data.message, 'success');
                PromptManager.loadProjectPrompts();
            } else {
                UiHelpers.showToast(data.error || 'Lỗi khi nạp prompt', 'error');
            }
        })
        .catch(err => UiHelpers.showToast('Lỗi kết nối: ' + err.message, 'error'));
    },

    async resetProjectPrompts() {
        if (!window.currentProject) { UiHelpers.showToast('Chưa chọn dự án!', 'error'); return; }
        if (!await showConfirm('Xóa toàn bộ chỉ dẫn riêng của dự án?')) return;

        fetch(`/api/projects/${window.currentProject.slug}/prompts`, { method: 'DELETE' })
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
        const badges = ['prompt-status-badge', 'pm-prompt-status-badge'];
        const resetBtns = ['btn-reset-project-prompts'];
        
        badges.forEach(badgeId => {
            const badge = document.getElementById(badgeId);
            if (!badge) return;
            if (isCustom) {
                badge.innerHTML = '✏️ Chỉ dẫn Dự án';
                badge.className = 'f7 fw6 blue ba b--blue pa1 br2 bg-washed-blue';
            } else {
                badge.innerHTML = '📌 Chỉ dẫn Hệ thống';
                badge.className = 'f7 fw6 silver ba b--black-10 pa1 br2';
            }
        });
        
        resetBtns.forEach(btnId => {
            const resetBtn = document.getElementById(btnId);
            if (resetBtn) resetBtn.style.display = isCustom ? '' : 'none';
        });
    },

    GUIDELINE_TAB_MAP: {
        'style-guide':  { field: 'style_guide',  elId: 'guide-style-guide',  modelId: 'style-guide-model' },
        'relationship': { field: 'characters',   elId: 'guide-relationship', modelId: 'relationship-model' },
        'glossary':     { field: 'glossary',     elId: 'guide-glossary',     modelId: 'glossary-model' },
        'summary':      { field: 'summary',      elId: 'guide-summary',      modelId: 'summary-model' },
    },

    loadGuidelineTab(tab) {
        if (!window.currentProject) return;
        const mapping = PromptManager.GUIDELINE_TAB_MAP[tab];
        if (!mapping) return;

        PromptManager._populateModelSelect(mapping.modelId);

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
            'style_guide': 'guide-style-guide',
            'relationship': 'guide-relationship',
            'glossary': 'guide-glossary',
            'summary': 'guide-summary',
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
            'style_guide': 'guide-style-guide',
            'relationship': 'guide-relationship',
            'glossary': 'guide-glossary',
            'summary': 'guide-summary',
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
    }
};

window.PromptManager = PromptManager;
