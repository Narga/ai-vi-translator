// ============================================================
// api-client.js — API calls, data loading, config management
// ============================================================

const ApiClient = {
    fetchJson(url, options) {
        return fetch(url, options).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
        });
    },

    loadApiKeys() {
        fetch('/api/keys')
            .then(r => r.json())
            .then(data => {
                const el = document.getElementById('config-api-keys');
                if (el) el.value = data.content || '';
            })
            .catch(e => console.error('Failed to load API keys:', e));
    },

    saveApiKeys() {
        const keysText = document.getElementById('config-api-keys').value;
        fetch('/api/keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: keysText })
        })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    UiHelpers.showToast('Đã lưu API Keys thành công', 'success');
                } else {
                    UiHelpers.showToast(data.error || 'Lỗi lưu API Keys', 'error');
                }
            })
            .catch(e => UiHelpers.showToast(e.message, 'error'));
    },

    loadModels() {
        const sel = document.getElementById('model');
        if (sel) {
            sel.innerHTML = '<option>Đang tải models...</option>';
            sel.disabled = true;
        }

        // Xác định provider đang active
        const activeProvider = document.querySelector('input[name="active_provider"]:checked');
        const provider = activeProvider ? activeProvider.value : 'gemini';

        const url = provider === 'openai' ? '/api/openai/models?full=true' : '/api/models?full=true';

        fetch(url)
            .then(r => r.json())
            .then(data => {
                if (sel) sel.disabled = false;

                const renderOptions = (models, currentDefault) => {
                    let saved = localStorage.getItem('nt_marked_models');
                    let markedModels = saved ? JSON.parse(saved) : [];

                    if (!models || models.length === 0) {
                        return '<option value="">— Không có models —</option>';
                    }

                    return models.map(m => {
                        const id = typeof m === 'string' ? m : m.id;
                        const name = typeof m === 'string' ? m : m.name;
                        const isFree = m.is_free ? ' 🆓' : '';
                        const isMarked = markedModels.includes(id) ? ' ⭐' : '';
                        const isSelected = id === currentDefault ? 'selected' : '';
                        return `<option value="${id}" ${isSelected}>${name}${isFree}${isMarked}</option>`;
                    }).join('');
                };

                if (data.error) {
                    UiHelpers.showToast(data.error, 'error');
                    const emptyHtml = renderOptions([], '');
                    if (sel) sel.innerHTML = emptyHtml;
                    ['cfg-qa-model', 'summarize-model', 'style-guide-model', 'relationship-model',
                     'glossary-model', 'summary-model', 'pm-style-guide-model'].forEach(sid => {
                        const e = document.getElementById(sid);
                        if (e) e.innerHTML = sid === 'summarize-model'
                            ? '<option value="">— Mặc định —</option>' + emptyHtml
                            : '<option value="">— Chọn Model —</option>' + emptyHtml;
                    });
                    window.availableModels = [];
                    return;
                }

                if (data.models && data.models.length > 0) {
                    window.availableModels = data.models;
                } else {
                    window.availableModels = [];
                    UiHelpers.showToast('Không lấy được danh sách models. Kiểm tra lại API key và Base URL.', 'info');
                }

                const defaultModelVal = data.default || '';

                const mainSel = document.getElementById('model');
                if (mainSel) {
                    mainSel.innerHTML = renderOptions(window.availableModels, defaultModelVal);
                    ApiClient.onModelChange(mainSel.value);
                }

                const qaSel = document.getElementById('cfg-qa-model');
                if (qaSel) {
                    qaSel.innerHTML = renderOptions(window.availableModels, '');
                }

                const sumSel = document.getElementById('summarize-model');
                if (sumSel) {
                    sumSel.innerHTML = '<option value="">— Mặc định —</option>' + renderOptions(window.availableModels, '');
                }

                const contentTabModels = ['style-guide-model', 'relationship-model', 'glossary-model', 'summary-model', 'pm-style-guide-model'];
                contentTabModels.forEach(selId => {
                    const s = document.getElementById(selId);
                    if (s) s.innerHTML = '<option value="">— Chọn Model —</option>' + renderOptions(window.availableModels, '');
                });

                ApiClient.loadAppConfig();
            })
            .catch(err => {
                console.error('Error loading models:', err);
                if (sel) {
                    sel.disabled = false;
                    sel.innerHTML = '<option value="">— Lỗi kết nối —</option>';
                }
            });
    },

    markModel() {
        const sel = document.getElementById('model');
        if (!sel || !sel.value) return;
        
        const id = sel.value;
        let saved = localStorage.getItem('nt_marked_models');
        let markedModels = saved ? JSON.parse(saved) : [];
        
        if (markedModels.includes(id)) {
            markedModels = markedModels.filter(m => m !== id);
            UiHelpers.showToast('Đã bỏ đánh dấu model', 'info');
        } else {
            markedModels.push(id);
            UiHelpers.showToast('Đã đánh dấu model yêu thích ⭐', 'success');
        }
        
        localStorage.setItem('nt_marked_models', JSON.stringify(markedModels));
        ApiClient.loadModels();
    },

    onModelChange(modelName) {
        ApiClient.fetchModelInfo(modelName);
    },

    fetchModelInfo(modelName) {
        const panel = document.getElementById('model-info-panel');
        if (!panel) return;

        document.getElementById('model-input-limit').textContent = '⏳...';
        document.getElementById('model-output-limit').textContent = '⏳...';
        const rlEl = document.getElementById('model-rate-limits');
        if (rlEl) rlEl.classList.add('dn');
        const descRow = document.getElementById('model-desc-row');
        if (descRow) descRow.classList.add('dn');

        const sel = document.getElementById('model');
        if (sel) sel.style.color = '';

        fetch('/api/model-info/' + encodeURIComponent(modelName))
            .then(r => r.json())
            .then(info => {
                if (info.error) {
                    document.getElementById('model-input-limit').textContent = '❌ N/A';
                    document.getElementById('model-output-limit').textContent = '❌ N/A';
                    if (sel) sel.style.color = 'red';
                    return;
                }

                window.currentModelInfo = info;

                document.getElementById('model-input-limit').textContent = info.input_token_display ? info.input_token_display : 'N/A';
                document.getElementById('model-output-limit').textContent = info.output_token_display ? info.output_token_display : 'N/A';

                if (rlEl) {
                    if (info.provider === 'gemini' && info.rate_limits && Object.keys(info.rate_limits).length > 0) {
                        const labels = { RPM: '🔄 RPM', RPD: '📅 RPD', TPM: '⚡ TPM', TPD: '📊 TPD' };
                        let html = '';
                        for (const [key, val] of Object.entries(info.rate_limits)) {
                            const label = labels[key] || key;
                            const formatted = typeof val === 'number' ? val.toLocaleString() : val;
                            html += `<div class="flex justify-between mb1"><span class="silver">${label}:</span> <strong class="dark-gray">${formatted}</strong></div>`;
                        }
                        rlEl.innerHTML = html;
                        rlEl.classList.remove('dn');
                    }
                }

                if (descRow && info.description) {
                    document.getElementById('model-description').textContent = info.description;
                    descRow.classList.remove('dn');
                }

                EditorComponent.updateTokenEstimate();
            })
            .catch(() => {
                document.getElementById('model-input-limit').textContent = '❌ Lỗi';
                document.getElementById('model-output-limit').textContent = '❌ Lỗi';
                if (sel) sel.style.color = 'red';
            });
    },

    loadAppConfig() {
        fetch('/api/settings/app')
            .then(r => r.json())
            .then(data => {
                if (data.success && data.config) {
                    const conf = data.config;
                    if (conf.MODEL) {
                        const m = conf.MODEL;
                        if (m.MODEL) {
                            const sel = document.getElementById('model');
                            if (sel) {
                                sel.value = m.MODEL;
                                ApiClient.onModelChange(m.MODEL);
                            }
                        }
                        if (m.QA_MODEL) {
                            const qaSel = document.getElementById('cfg-qa-model');
                            if (qaSel) qaSel.value = m.QA_MODEL;
                        }
                        if (m.THINKING_LEVEL) {
                            const thinkSel = document.getElementById('cfg-thinking');
                            if (thinkSel) thinkSel.value = m.THINKING_LEVEL;
                        }
                    }
                    if (conf.PROCESSING) {
                        const p = conf.PROCESSING;
                        const chunkSizeEl = document.getElementById('chunk-size');
                        if (chunkSizeEl) chunkSizeEl.value = p.MAX_CHARS_PER_CHUNK;
                        
                        const contextEl = document.getElementById('cfg-context');
                        if (contextEl && p.CONTEXT_CHAR_COUNT !== undefined) contextEl.value = p.CONTEXT_CHAR_COUNT;
                        
                        if (p.TEMPERATURE) {
                            const tempInp = document.getElementById('temperature');
                            if (tempInp) tempInp.value = p.TEMPERATURE;
                            const tempVal = document.getElementById('temp-value');
                            if (tempVal) tempVal.textContent = parseFloat(p.TEMPERATURE).toFixed(1);
                        }
                        
                        const delayEl = document.getElementById('cfg-delay');
                        if (delayEl && p.REQUEST_DELAY) delayEl.value = p.REQUEST_DELAY;
                    }
                    if (conf.CACHE && conf.CACHE.ENABLE_CACHE) {
                        const cacheCheck = document.getElementById('use-cache');
                        if (cacheCheck) cacheCheck.checked = conf.CACHE.ENABLE_CACHE.toLowerCase() === 'true';
                    }
                }
            })
            .catch(e => console.error('Failed to load App Config:', e));
    },

    saveAppConfig() {
        const data = {
            MODEL: {
                MODEL: document.getElementById('model').value,
                QA_MODEL: document.getElementById('cfg-qa-model').value,
                THINKING_LEVEL: document.getElementById('cfg-thinking').value
            },
            PROCESSING: {
                MAX_CHARS_PER_CHUNK: document.getElementById('chunk-size').value,
                CONTEXT_CHAR_COUNT: document.getElementById('cfg-context').value,
                TEMPERATURE: document.getElementById('temperature').value,
                REQUEST_DELAY: document.getElementById('cfg-delay').value
            },
            CACHE: {
                ENABLE_CACHE: document.getElementById('use-cache').checked ? 'true' : 'false'
            }
        };

        fetch('/api/settings/app', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config: data })
        })
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    UiHelpers.showToast('Lưu Cấu hình thành công!', 'success');
                } else {
                    UiHelpers.showToast('Lưu bị lỗi: ' + (res.error || ''), 'error');
                }
            })
            .catch(e => UiHelpers.showToast('Gặp lỗi khi lưu Cấu hình: ' + e, 'error'));
    },

    loadStats() {
        fetch('/api/stats').then(r => r.json()).then(data => {
            const apiKeyEl = document.getElementById('api-keys-count');
            const cacheCountEl = document.getElementById('cache-count');
            const cacheSizeEl = document.getElementById('cache-size');
            const projCountEl = document.getElementById('project-count');
            const archiveCountEl = document.getElementById('archive-count');

            if (apiKeyEl) apiKeyEl.textContent = data.api_keys_count || data.api_keys || 0;
            if (cacheCountEl) cacheCountEl.textContent = data.cache_files || 0;
            if (cacheSizeEl) cacheSizeEl.textContent = data.cache_size_mb || 0;
            if (projCountEl) projCountEl.textContent = data.project_count || 0;
            if (archiveCountEl) archiveCountEl.textContent = data.archive_count || 0;
        });
    },

    loadArchiveList() {
        const tbody = document.getElementById('archive-list-body');
        if (!tbody) return;
        
        fetch('/api/archive')
            .then(r => r.json())
            .then(archives => {
                if (!archives || !archives.length) {
                    tbody.innerHTML = `<tr><td colspan="3" class="pa5 tc silver i flex-column-center">Không có bản lưu trữ nào.</td></tr>`;
                    return;
                }
                
                tbody.innerHTML = archives.map(file => {
                    const df = new Date(file.mtime * 1000).toLocaleString('vi-VN');
                    return `
                    <tr class="hover-bg-near-white transition">
                        <td class="pa3 bb b--border">
                            <span class="fw6 dark-gray f6">${file.filename}</span>
                            <div class="f7 silver mt1">Ngày lưu: ${df}</div>
                        </td>
                        <td class="pa3 bb b--border gray f6">${file.size_display}</td>
                        <td class="pa3 tr bb b--border">
                            <button class="pointer ph3 pv1 f7 ba b--blue blue bg-white br1 shadow-1 hover-bg-light-blue transition mr2" onclick="ProjectManager.restoreProject('${file.filename}')">Khôi phục</button>
                            <button class="pointer ph3 pv1 f7 ba b--red red bg-white br1 shadow-1 hover-bg-washed-red transition" onclick="ProjectManager.deleteArchive('${file.filename}')">Xóa</button>
                        </td>
                    </tr>
                    `;
                }).join('');
            })
            .catch(err => {
                tbody.innerHTML = `<tr><td colspan="3" class="pa3 tc red">Lỗi tải danh sách: ${err.message}</td></tr>`;
            });
    },

    loadLogList() {
        fetch('/api/logs')
            .then(r => r.json())
            .then(data => {
                const listEl = document.getElementById('sys-log-list');
                window.selectedLogFiles = new Set();
                UiHelpers.updateSelectedLogsUI();
                if (data.length === 0) {
                    listEl.innerHTML = '<div class="pa3 tc silver i">Không có file log nào.</div>';
                    document.getElementById('sys-log-viewer').innerHTML = '<div class="tc silver mt5 i">Chưa chọn file log.</div>';
                    return;
                }
                
                let html = '<div class="pa2 bb b--black-10 bg-near-white"><label class="f7 gray"><input type="checkbox" onclick="UiHelpers.selectAllLogs(this.checked)"> Chọn tất cả</label></div>';
                data.forEach(log => {
                    const dateStr = new Date(log.mtime * 1000).toLocaleString('vi-VN');
                    const safeName = log.filename.replace(/'/g, "\\'");
                    const safeValue = log.filename.replace(/"/g, '&quot;');
                    html += `
                        <div class="pv2 ph3 bb b--black-05 flex items-center gap-2">
                            <input class="sys-log-checkbox" type="checkbox" value="${safeValue}" onchange="UiHelpers.toggleLogFile('${safeName}', this.checked)">
                            <div class="pointer hover-bg-near-white flex items-center justify-between flex-auto" onclick="UiHelpers.viewLogFile('${safeName}')">
                                <div class="pr2" style="min-width:0;">
                                    <div class="f7 fw6 dark-gray truncate" style="max-width: 170px;">${log.filename}</div>
                                    <div class="f7 silver mt1 truncate" style="max-width: 170px;">${dateStr}</div>
                                </div>
                                <div class="f7 silver tr nowrap" style="min-width: 96px; max-width: 96px;">${log.size_display}</div>
                            </div>
                        </div>
                    `;
                });
                listEl.innerHTML = html;
            })
            .catch(e => UiHelpers.showToast('Lỗi tải danh sách logs: ' + e.message, 'error'));
    },

    async clearCache() {
        if (!await showConfirm('Xóa sạch bộ nhớ Cache dịch thuật?', { danger: true })) return;
        fetch('/api/cache/clear', { method: 'POST' }).then(r => r.json()).then(data => {
            UiHelpers.showToast('Đã dọn dẹp ' + data.deleted + ' files nháp.', 'success');
            ApiClient.loadStats();
        });
    },

    async restartServer() {
        if (!await showConfirm('Khởi động lại Web Server?')) return;
        fetch('/api/restart', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                UiHelpers.showToast(data.message || 'Đang khởi động lại...', 'info');
                setTimeout(() => { location.reload(); }, 3000);
            })
            .catch(e => {
                UiHelpers.showToast('Lỗi gửi yêu cầu restart: ' + e.message, 'error');
            });
    }
};

window.ApiClient = ApiClient;
