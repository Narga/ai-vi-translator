// ============================================================
// provider-manager.js — Gemini + OpenAI Provider management (v7.3.0)
// ============================================================

// ---- Gemini Provider ----
const GeminiProvider = {
    saveKeys() {
        const textarea = document.getElementById('config-api-keys');
        const keysText = textarea.value.trim();
        if (!keysText) { UiHelpers.showToast('Chưa nhập API key', 'error'); return; }

        fetch('/api/providers')
            .then(r => r.json())
            .then(data => {
                const gemini = (data.providers || []).find(p => p.type === 'gemini');
                if (!gemini) { UiHelpers.showToast('Không tìm thấy Gemini provider', 'error'); return; }

                const keys = keysText.split('\n').map(k => k.trim()).filter(Boolean);
                return fetch('/api/providers/' + encodeURIComponent(gemini.id), {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ api_keys: keys })
                });
            })
            .then(r => r && r.json())
            .then(data => {
                if (data && !data.error) UiHelpers.showToast('Đã lưu Gemini keys', 'success');
            })
            .catch(e => UiHelpers.showToast(e.message, 'error'));
    }
};
window.GeminiProvider = GeminiProvider;

// ---- OpenAI Provider ----
const OpenAIProvider = {
    _providers: [],

    loadProviders(callback) {
        fetch('/api/providers')
            .then(r => r.json())
            .then(data => {
                this._providers = (data.providers || []).filter(p => p.type === 'openai');
                const select = document.getElementById('openai-provider-select');
                if (!select) return;

                const currentValue = select.value;
                select.innerHTML = '<option value="">— Chọn provider —</option>';
                this._providers.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = p.name;
                    select.appendChild(opt);
                });

                // Auto-select active provider hoặc first
                if (currentValue && this._providers.find(p => p.id === currentValue)) {
                    select.value = currentValue;
                    this.onSelectProvider(currentValue);
                } else if (this._providers.length > 0) {
                    // Tìm active openai provider
                    const activeId = data.active_id;
                    const activeOpenai = this._providers.find(p => p.id === activeId);
                    const toSelect = activeOpenai || this._providers[0];
                    select.value = toSelect.id;
                    this.onSelectProvider(toSelect.id);
                }

                if (callback) callback();
            })
            .catch(e => console.error('Failed to load providers:', e));
    },

    onSelectProvider(id) {
        const provider = this._providers.find(p => p.id === id);
        if (!provider) return;
        const nameInput = document.getElementById('openai-provider-name');
        const keyInput = document.getElementById('openai-api-key');
        const urlInput = document.getElementById('openai-base-url');
        if (nameInput) nameInput.value = provider.name || '';
        if (keyInput) keyInput.value = provider.api_key || '';
        if (urlInput) urlInput.value = provider.base_url || '';
    },

    getSelectedProvider() {
        const select = document.getElementById('openai-provider-select');
        return select ? select.value : '';
    },

    addNew() {
        const nameInput = document.getElementById('openai-provider-name');
        const name = nameInput.value.trim();
        if (!name) { UiHelpers.showToast('Chưa nhập tên provider', 'error'); return; }
        if (!/^[a-zA-Z0-9\s]+$/.test(name)) {
            UiHelpers.showToast('Tên chỉ được chứa chữ, số và dấu cách', 'error'); return;
        }

        // Lấy API Key + Base URL hiện tại trên form (nếu user đã nhập)
        const apiKey = document.getElementById('openai-api-key').value.trim();
        const baseUrl = document.getElementById('openai-base-url').value.trim();

        fetch('/api/providers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, type: 'openai' })
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }

            const newId = data.provider ? data.provider.id : null;

            // Nếu user đã nhập API Key hoặc Base URL → lưu luôn vào provider mới
            if (newId && (apiKey || baseUrl)) {
                const updateBody = {};
                if (apiKey) updateBody.api_key = apiKey;
                if (baseUrl) updateBody.base_url = baseUrl;
                return fetch('/api/providers/' + encodeURIComponent(newId), {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updateBody)
                }).then(() => data);
            }
            return data;
        })
        .then(data => {
            this.loadProviders(() => {
                const select = document.getElementById('openai-provider-select');
                if (select && data.provider) {
                    select.value = data.provider.id;
                    this.onSelectProvider(data.provider.id);
                }
            });
            UiHelpers.showToast('Đã thêm "' + name + '"', 'success');
        })
        .catch(e => UiHelpers.showToast(e.message, 'error'));
    },

    editSelected() {
        const id = this.getSelectedProvider();
        if (!id) { UiHelpers.showToast('Chưa chọn provider', 'error'); return; }

        const name = document.getElementById('openai-provider-name').value.trim();
        const apiKey = document.getElementById('openai-api-key').value.trim();
        const baseUrl = document.getElementById('openai-base-url').value.trim();

        if (!name && !apiKey && !baseUrl) {
            UiHelpers.showToast('Chưa nhập thông tin để cập nhật', 'error'); return;
        }

        const body = {};
        if (name) body.name = name;
        if (apiKey) body.api_key = apiKey;
        if (baseUrl) body.base_url = baseUrl;

        fetch('/api/providers/' + encodeURIComponent(id), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
            // Reload providers nhưng giữ dropdown selection
            this.loadProviders(() => {
                const select = document.getElementById('openai-provider-select');
                if (select) {
                    select.value = id;
                    this.onSelectProvider(id);  // Fill lại name + key + url
                }
            });
            UiHelpers.showToast('Đã cập nhật "' + (data.provider ? data.provider.name : id) + '"', 'success');
        })
        .catch(e => UiHelpers.showToast(e.message, 'error'));
    },

    deleteSelected() {
        const id = this.getSelectedProvider();
        if (!id) { UiHelpers.showToast('Chưa chọn provider', 'error'); return; }
        const provider = this._providers.find(p => p.id === id);
        if (!provider) return;

        showConfirm('Xóa provider "' + provider.name + '"?').then(confirmed => {
            if (!confirmed) return;
            fetch('/api/providers/' + encodeURIComponent(id), { method: 'DELETE' })
                .then(r => r.json())
                .then(data => {
                    if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
                    this.loadProviders();
                    UiHelpers.showToast('Đã xóa "' + provider.name + '"', 'success');
                })
                .catch(e => UiHelpers.showToast(e.message, 'error'));
        });
    },

    saveCurrent() {
        const select = document.getElementById('openai-provider-select');
        const id = select.value;
        if (!id) { UiHelpers.showToast('Chưa chọn provider', 'error'); return; }

        const apiKey = document.getElementById('openai-api-key').value.trim();
        const baseUrl = document.getElementById('openai-base-url').value.trim();

        const body = {};
        if (apiKey) body.api_key = apiKey;
        if (baseUrl) body.base_url = baseUrl;

        fetch('/api/providers/' + encodeURIComponent(id), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
            return fetch('/api/providers/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ active_id: id })
            });
        })
        .then(r => r && r.json())
        .then(data => {
            if (data && data.success) {
                // Reload providers nhưng giữ dropdown selection
                this.loadProviders(() => {
                    const sel = document.getElementById('openai-provider-select');
                    if (sel) {
                        sel.value = id;
                        this.onSelectProvider(id);  // Fill lại name + key + url
                    }
                });
                UiHelpers.showToast('Đã lưu & kích hoạt ' + select.options[select.selectedIndex].text, 'success');
                ApiClient.loadModels();
            }
        })
        .catch(e => UiHelpers.showToast(e.message, 'error'));
    }
};
window.OpenAIProvider = OpenAIProvider;
