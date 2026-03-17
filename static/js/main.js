/* Novel Translator - main.js v5.0 (Tachyons Redesign) */

let prompts = window.initialPrompts || {};
let currentOutputFile = '';
let allFiles = [];
let selectedFiles = new Set();
let selectedTranslatedFiles = new Set();
let availableModels = window.initialAvailableModels || [];
let defaultModel = window.initialDefaultModel || '';
let currentDoneFile = '';
let currentGenre = '';
let currentProject = null; // { slug, meta, sources, translated }
let currentProjectFile = null; // { name, section } for save

document.addEventListener('DOMContentLoaded', function () {
    initTabs();
    initPromptTabs();
    initDialogs();

    loadProjects();
    loadStats();
    loadModels();  // loadAppConfig() is called inside after models are loaded
    loadGenres();
    loadApiKeys();
    initProvider();  // Load active AI provider state
    initProjectDialog();  // Wire project creation modal

    setInterval(loadStats, 30000);

    // Temperature slider
    const tempEl = document.getElementById('temperature');
    if (tempEl) {
        tempEl.addEventListener('input', function () {
            document.getElementById('temp-value').textContent = this.value;
        });
    }

    // Core action buttons
    document.getElementById('translate-btn').addEventListener('click', startTranslation);
    document.getElementById('btn-clear-cache').addEventListener('click', clearCache);
    document.getElementById('btn-copy-result').addEventListener('click', copyResult);
    document.getElementById('download-btn').addEventListener('click', downloadResult);

    // Done tab buttons
    document.getElementById('btn-run-retranslate').addEventListener('click', runRetranslate);
    document.getElementById('btn-run-correction').addEventListener('click', runCorrection);
    document.getElementById('btn-run-both').addEventListener('click', runBoth);
    document.getElementById('btn-copy-done-result').addEventListener('click', copyDoneResult);
    document.getElementById('btn-download-done-result').addEventListener('click', downloadDoneResult);

    // Prompt Manager buttons
    document.getElementById('btn-delete-genre').addEventListener('click', deleteGenre);
    document.getElementById('btn-clone-genre').addEventListener('click', cloneGenre);
    document.getElementById('btn-save-genre').addEventListener('click', saveGenre);
    document.getElementById('btn-activate-genre').addEventListener('click', activateGenre);

});

// ============================================================
// UI Initializations
// ============================================================
function initTabs() {
    const navItems = document.querySelectorAll('.nt-nav-item');
    const sections = document.querySelectorAll('.nt-tab-content');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = item.getAttribute('data-tab');

            // Update Nav Classes
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            // Toggle Sections
            sections.forEach(sec => {
                sec.classList.remove('block');
                sec.classList.add('dn');
            });
            document.getElementById('tab-' + targetId).classList.remove('dn');
            document.getElementById('tab-' + targetId).classList.add('block');
        });
    });
}

function initPromptTabs() {
    const pTabs = document.querySelectorAll('.genre-tab-btn');
    const pContents = document.querySelectorAll('.genre-ptab-content');

    pTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.getAttribute('data-ptab');
            pTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            pContents.forEach(c => {
                c.classList.remove('flex');
                c.classList.add('dn');
            });
            const content = document.getElementById('ptab-' + target);
            if (content) {
                content.classList.remove('dn');
                content.classList.add('flex');
            }
        });
    });
}

function initDialogs() {
    const modal = document.getElementById('new-genre-modal');

    document.getElementById('btn-new-genre').addEventListener('click', () => {
        modal.style.display = 'flex';
    });

    document.getElementById('btn-cancel-genre').addEventListener('click', () => {
        modal.style.display = 'none';
    });

    document.getElementById('btn-confirm-new-genre').addEventListener('click', (e) => {
        createGenre(e);
        modal.style.display = 'none';
    });

    // Auto-generate slug from name
    document.getElementById('new-genre-name').addEventListener('input', function () {
        const slug = this.value.toLowerCase()
            .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .replace(/đ/g, 'd').replace(/Đ/g, 'D')
            .replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
        document.getElementById('new-genre-slug').value = slug;
    });
}

// ============================================================
// Toast & API Keys
// ============================================================
function showToast(message, type = 'success') {
    const container = document.getElementById('nt-toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `nt-toast ${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';

    toast.innerHTML = `<span>${icon}</span><span class="flex-auto">${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fading-out');
        toast.addEventListener('animationend', () => toast.remove());
    }, 3000);
}

function loadApiKeys() {
    fetch('/api/keys')
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('config-api-keys');
            if (el) el.value = data.content || '';
        })
        .catch(e => console.error('Failed to load API keys:', e));
}

function saveApiKeys() {
    const keysText = document.getElementById('config-api-keys').value;
    fetch('/api/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: keysText })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('Đã lưu API Keys thành công', 'success');
            } else {
                showToast(data.error || 'Lỗi lưu API Keys', 'error');
            }
        })
        .catch(e => showToast(e.message, 'error'));
}

// ============================================================
// AI Provider Management (Gemini / OpenAI)
// ============================================================
function switchProvider(provider) {
    // Update visual state
    document.querySelectorAll('.nt-provider-col').forEach(col => {
        col.classList.toggle('nt-provider-active', col.dataset.provider === provider);
    });

    // Update badge
    const badge = document.getElementById('provider-active-badge');
    if (badge) {
        badge.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';
        badge.className = 'f7 fw6 ph2 pv1 br2 ' +
            (provider === 'gemini' ? 'bg-light-green dark-green' : 'bg-lightest-blue dark-blue');
    }

    // Save to backend
    fetch('/api/provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast(`Đã chuyển sang ${provider === 'gemini' ? 'Google Gemini' : 'OpenAI Compatible'}`, 'success');
                // Reload models for the new provider
                loadModels();
            } else {
                showToast(data.error || 'Lỗi chuyển provider', 'error');
            }
        })
        .catch(e => showToast(e.message, 'error'));
}

function fetchOpenAIModels() {
    const sel = document.getElementById('openai-model');
    if (!sel) return;
    sel.innerHTML = '<option>⏳ Đang tải...</option>';

    fetch('/api/openai/models')
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                sel.innerHTML = '<option>❌ ' + data.error + '</option>';
                showToast(data.error, 'error');
                return;
            }
            if (data.models && data.models.length > 0) {
                sel.innerHTML = data.models.map(m =>
                    `<option value="${m}">${m}</option>`
                ).join('');
                showToast(`Đã tải ${data.models.length} models`, 'success');
            } else {
                sel.innerHTML = '<option>Không có model nào</option>';
            }
        })
        .catch(e => {
            sel.innerHTML = '<option>❌ Lỗi kết nối</option>';
            showToast(e.message, 'error');
        });
}

function saveOpenAIConfig() {
    const data = {
        api_key: document.getElementById('openai-api-key').value,
        base_url: document.getElementById('openai-base-url').value,
        model: document.getElementById('openai-model').value,
    };

    fetch('/api/openai/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                showToast('Đã lưu cấu hình OpenAI', 'success');
            } else {
                showToast(res.error || 'Lỗi lưu config', 'error');
            }
        })
        .catch(e => showToast(e.message, 'error'));
}

function initProvider() {
    fetch('/api/provider')
        .then(r => r.json())
        .then(data => {
            if (data.active) {
                // Set radio button
                const radio = document.querySelector(`input[name="active_provider"][value="${data.active}"]`);
                if (radio) radio.checked = true;

                // Set visual state
                document.querySelectorAll('.nt-provider-col').forEach(col => {
                    col.classList.toggle('nt-provider-active', col.dataset.provider === data.active);
                });

                // Update badge
                const badge = document.getElementById('provider-active-badge');
                if (badge) {
                    badge.textContent = data.active === 'gemini' ? 'Gemini' : 'OpenAI';
                    badge.className = 'f7 fw6 ph2 pv1 br2 ' +
                        (data.active === 'gemini' ? 'bg-light-green dark-green' : 'bg-lightest-blue dark-blue');
                }
            }

            // Fill OpenAI config fields
            if (data.openai_config) {
                const cfg = data.openai_config;
                if (cfg.base_url) document.getElementById('openai-base-url').value = cfg.base_url;
                if (cfg.model) {
                    const sel = document.getElementById('openai-model');
                    sel.innerHTML = `<option value="${cfg.model}" selected>${cfg.model}</option>`;
                }
                if (cfg.has_key) {
                    document.getElementById('openai-api-key').placeholder = '••••••••••• (đã cấu hình)';
                }
            }
        })
        .catch(e => console.error('Failed to load provider info:', e));
}

function loadAppConfig() {
    fetch('/api/settings/app')
        .then(r => r.json())
        .then(data => {
            if (data.success && data.config) {
                const conf = data.config;
                // Bind to UI
                if (conf.MODEL) {
                    const m = conf.MODEL;
                    if (m.MODEL) document.getElementById('model').value = m.MODEL;
                    if (m.QA_MODEL) document.getElementById('cfg-qa-model').value = m.QA_MODEL;
                    if (m.THINKING_LEVEL) document.getElementById('cfg-thinking').value = m.THINKING_LEVEL;
                }
                if (conf.PROCESSING) {
                    const p = conf.PROCESSING;
                    if (p.MAX_CHARS_PER_CHUNK) document.getElementById('chunk-size').value = p.MAX_CHARS_PER_CHUNK;
                    if (p.CONTEXT_CHAR_COUNT !== undefined) document.getElementById('cfg-context').value = p.CONTEXT_CHAR_COUNT;
                    if (p.TEMPERATURE) {
                        document.getElementById('temperature').value = p.TEMPERATURE;
                        document.getElementById('temp-value').textContent = parseFloat(p.TEMPERATURE).toFixed(1);
                    }
                    if (p.REQUEST_DELAY) document.getElementById('cfg-delay').value = p.REQUEST_DELAY;
                }
                if (conf.DIRECTORIES) {
                    const d = conf.DIRECTORIES;
                    if (d.INPUT_DIR) document.getElementById('cfg-dir-in').value = d.INPUT_DIR;
                    if (d.OUTPUT_DIR) document.getElementById('cfg-dir-out').value = d.OUTPUT_DIR;
                    if (d.CACHE_DIR) document.getElementById('cfg-dir-cache').value = d.CACHE_DIR;
                    if (d.LOGS_DIR) document.getElementById('cfg-dir-logs').value = d.LOGS_DIR;
                    if (d.ARCHIVE_DIR_NAME) document.getElementById('cfg-dir-archive').value = d.ARCHIVE_DIR_NAME;
                }
                if (conf.CACHE && conf.CACHE.ENABLE_CACHE) {
                    document.getElementById('use-cache').checked = conf.CACHE.ENABLE_CACHE.toLowerCase() === 'true';
                }
            }
        })
        .catch(e => console.error('Failed to load App Config:', e));
}

function saveAppConfig() {
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
        DIRECTORIES: {
            INPUT_DIR: document.getElementById('cfg-dir-in').value,
            OUTPUT_DIR: document.getElementById('cfg-dir-out').value,
            CACHE_DIR: document.getElementById('cfg-dir-cache').value,
            LOGS_DIR: document.getElementById('cfg-dir-logs').value,
            ARCHIVE_DIR_NAME: document.getElementById('cfg-dir-archive').value
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
                showToast('Lưu Cấu hình thành công! Hãy khởi động lại App để cập nhật.', 'success');
            } else {
                showToast('Lưu bị lỗi: ' + (res.error || ''), 'error');
            }
        })
        .catch(e => showToast('Gặp lỗi khi lưu Cấu hình: ' + e, 'error'));
}

// ============================================================
// Models & Token Estimation
// ============================================================
let currentModelInfo = null; // cache model info

function loadModels() {
    fetch('/api/models')
        .then(r => r.json())
        .then(data => {
            if (data.models && data.models.length > 0) availableModels = data.models;
            const optionsHtml = availableModels.map(m =>
                `<option value="${m}" ${m === (data.default || defaultModel) ? 'selected' : ''}>${m}</option>`
            ).join('');

            // Populate Model Chính
            const sel = document.getElementById('model');
            sel.innerHTML = optionsHtml;

            // Populate QA Model dropdown
            const qaSel = document.getElementById('cfg-qa-model');
            if (qaSel) qaSel.innerHTML = optionsHtml;

            // Load saved config values AFTER models dropdown is ready
            loadAppConfig();

            // Auto-fetch info for selected model
            const selected = sel.value;
            if (selected) fetchModelInfo(selected);
        })
        .catch(() => {
            const optionsHtml = availableModels.map(m =>
                `<option value="${m}" ${m === defaultModel ? 'selected' : ''}>${m}</option>`
            ).join('');
            const sel = document.getElementById('model');
            sel.innerHTML = optionsHtml;
            const qaSel = document.getElementById('cfg-qa-model');
            if (qaSel) qaSel.innerHTML = optionsHtml;

            loadAppConfig();
        });
}

function onModelChange(modelName) {
    fetchModelInfo(modelName);
}

function fetchModelInfo(modelName) {
    const panel = document.getElementById('model-info-panel');
    if (!panel) return;

    // Show panel with loading state
    panel.classList.remove('dn');
    document.getElementById('model-input-limit').textContent = '⏳...';
    document.getElementById('model-output-limit').textContent = '⏳...';
    const loadHint = document.getElementById('model-loading-hint');
    if (loadHint) loadHint.classList.remove('dn');

    fetch('/api/model-info/' + encodeURIComponent(modelName))
        .then(r => r.json())
        .then(info => {
            if (loadHint) loadHint.classList.add('dn');

            if (info.error) {
                document.getElementById('model-input-limit').textContent = '❌ N/A';
                document.getElementById('model-output-limit').textContent = '❌ N/A';
                currentModelInfo = null;
                return;
            }

            currentModelInfo = info;

            document.getElementById('model-input-limit').textContent =
                info.input_token_display ? info.input_token_display + ' tokens' : 'N/A';
            document.getElementById('model-output-limit').textContent =
                info.output_token_display ? info.output_token_display + ' tokens' : 'N/A';

            // Rate limits
            const rlEl = document.getElementById('model-rate-limits');
            if (info.rate_limits && Object.keys(info.rate_limits).length > 0) {
                const labels = { RPM: '🔄 RPM', RPD: '📅 RPD', TPM: '⚡ TPM', TPD: '📊 TPD' };
                const descs = { RPM: 'Requests/phút', RPD: 'Requests/ngày', TPM: 'Tokens/phút', TPD: 'Tokens/ngày' };
                let html = '';
                for (const [key, val] of Object.entries(info.rate_limits)) {
                    const label = labels[key] || key;
                    const desc = descs[key] || key;
                    const formatted = typeof val === 'number' ? val.toLocaleString() : val;
                    html += `<div class="flex justify-between mb1">
                        <span class="silver" title="${desc}">${label}:</span>
                        <strong class="dark-gray">${formatted}</strong>
                    </div>`;
                }
                rlEl.innerHTML = html;
                rlEl.classList.remove('dn');
            } else {
                rlEl.classList.add('dn');
            }

            // Description
            const descRow = document.getElementById('model-desc-row');
            if (info.description) {
                document.getElementById('model-description').textContent = info.description;
                descRow.classList.remove('dn');
            } else {
                descRow.classList.add('dn');
            }

            // Update token fit check if text exists
            updateTokenEstimate();
        })
        .catch(() => {
            if (loadHint) loadHint.classList.add('dn');
            document.getElementById('model-input-limit').textContent = '❌ Lỗi';
            document.getElementById('model-output-limit').textContent = '❌ Lỗi';
            currentModelInfo = null;
        });
}

let _tokenEstimateTimer = null;
function updateTokenEstimate() {
    clearTimeout(_tokenEstimateTimer);
    _tokenEstimateTimer = setTimeout(_doTokenEstimate, 300);
}

function _doTokenEstimate() {
    const text = document.getElementById('source-text').value || '';
    const charCount = text.length;

    document.getElementById('token-char-count').textContent = charCount.toLocaleString();

    if (charCount === 0) {
        document.getElementById('token-estimate').textContent = '~0';
        document.getElementById('token-model-fit').textContent = '';
        return;
    }

    // Client-side quick estimation (same logic as backend)
    const cjkMatch = text.match(/[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]/g);
    const cjkCount = cjkMatch ? cjkMatch.length : 0;
    const cjkRatio = cjkCount / charCount;

    let tokensPerChar;
    if (cjkRatio > 0.5) tokensPerChar = 1 / 1.5;
    else if (cjkRatio > 0.2) tokensPerChar = 1 / 2.5;
    else tokensPerChar = 1 / 4.0;

    const estimatedTokens = Math.round(charCount * tokensPerChar);
    const promptOverhead = 2000;
    const totalInput = estimatedTokens + promptOverhead;

    document.getElementById('token-estimate').textContent = '~' + estimatedTokens.toLocaleString();

    // Check against model limits
    const fitEl = document.getElementById('token-model-fit');
    if (currentModelInfo && currentModelInfo.input_token_limit) {
        const limit = currentModelInfo.input_token_limit;
        const ratio = totalInput / limit;
        if (ratio > 0.9) {
            fitEl.innerHTML = '<span class="red fw6">⚠️ Gần/vượt limit!</span>';
        } else if (ratio > 0.5) {
            fitEl.innerHTML = '<span class="orange">⚡ ' + Math.round(ratio * 100) + '% input limit</span>';
        } else {
            fitEl.innerHTML = '<span class="green">✅ OK (' + Math.round(ratio * 100) + '% limit)</span>';
        }
    } else {
        fitEl.textContent = '';
    }
}

function toggleTranslatedFile(filename, isChecked) {
    if (isChecked) selectedTranslatedFiles.add(filename);
    else selectedTranslatedFiles.delete(filename);
}

function selectAllTranslatedFiles() {
    if (!currentProject || !currentProject.translated) return;
    const allCount = currentProject.translated.length;
    if (selectedTranslatedFiles.size === allCount) {
        selectedTranslatedFiles.clear(); // Bỏ chọn hết
    } else {
        currentProject.translated.forEach(f => selectedTranslatedFiles.add(f.name));
    }
    renderProjectTranslated(currentProject.translated);
}

function mergeTranslatedFiles() {
    if (!currentProject) { showToast('Chưa chọn dự án!', 'error'); return; }
    if (selectedTranslatedFiles.size === 0) { showToast('Vui lòng chọn ít nhất 1 file để ghép!', 'warning'); return; }

    const slug = currentProject.slug;

    // Convert Set to Array and Sort nicely 
    // Natural Sort helps handling chunk_2.md vs chunk_10.md properly
    let filesToMerge = Array.from(selectedTranslatedFiles);
    filesToMerge.sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));

    const outName = prompt("Nhập tên file xuất bản (ví dụ: Quyen1.txt):", `Full_${slug}.txt`);
    if (outName === null) return; // User cancelled

    const btn = document.getElementById('btn-merge-translated');
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Đang ghép nối...';
    btn.disabled = true;

    fetch(`/api/projects/${slug}/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            files: filesToMerge,
            output_filename: outName
        })
    })
        .then(r => r.json())
        .then(data => {
            btn.innerHTML = originalText;
            btn.disabled = false;

            if (data.success) {
                showToast(`Ghép thành công ${filesToMerge.length} file vào: ${data.file}`, 'success');
                // Gắn link Download popup
                if (confirm(`Đã lưu file kết quả tại output/${data.file}. Bạn có muốn mở để tải về luôn không?`)) {
                    window.open(`/api/projects/${slug}/file/output/${data.file}`, '_blank');
                }
            } else {
                showToast('Lỗi ghép file: ' + (data.error || 'Unknown'), 'error');
            }
        })
        .catch(e => {
            btn.innerHTML = originalText;
            btn.disabled = false;
            showToast('Lỗi mạng: ' + e.message, 'error');
        });
}

// ============================================================
// Project Management
// ============================================================
function loadProjects() {
    fetch('/api/projects').then(r => r.json()).then(projects => {
        const el = document.getElementById('project-list');
        if (!projects.length) { el.innerHTML = '<div class="pa4 tc silver i">Chưa có dự án. Tạo mới!</div>'; return; }
        el.innerHTML = projects.map(p => {
            const active = currentProject && currentProject.slug === p.slug ? 'active' : '';
            return `<div class="nt-project-card ${active}" onclick="selectProject('${p.slug}')">
                <div class="fw6 dark-gray f6">${p.name}</div>
                <div class="f7 silver mt1">Đang dịch: ${p.source_count} file | Hoàn tất: ${p.translated_count}</div>
            </div>`;
        }).join('');
    });
}

function selectProject(slug) {
    fetch('/api/projects/' + slug).then(r => r.json()).then(data => {
        if (data.error) { showToast(data.error, 'error'); return; }
        currentProject = data;
        selectedFiles.clear();
        selectedTranslatedFiles.clear(); // Clear translated selection too

        // Update header
        document.getElementById('project-header').classList.remove('dn');
        document.getElementById('project-tabs').classList.remove('dn');
        document.getElementById('project-empty-state').classList.add('dn');
        document.getElementById('project-title').textContent = data.name;
        document.getElementById('project-desc').textContent = data.description || '';
        document.getElementById('proj-source-count').textContent = data.source_count;
        document.getElementById('proj-translated-count').textContent = data.translated_count;
        document.getElementById('proj-source-words').textContent = (data.source_words || 0).toLocaleString();

        // Genre badge
        const genreBadge = document.getElementById('proj-genre-badge');
        const genreEl = document.getElementById('proj-genre');
        if (data.genre) {
            genreEl.textContent = data.genre;
            genreBadge.classList.remove('dn');
        } else {
            genreBadge.classList.add('dn');
        }

        // Render source files
        renderProjectSources(data.sources || []);
        renderProjectTranslated(data.translated || []);

        // Show sources sub-tab
        switchProjectTab('sources');

        // Highlight in list
        loadProjects();
    });
}

function renderProjectSources(sources) {
    const el = document.getElementById('project-source-list');
    if (!sources.length) { el.innerHTML = '<div class="pa3 tc silver i">Chưa có file nguồn</div>'; return; }
    el.innerHTML = sources.map(f => {
        const esc = f.name.replace(/'/g, "\\'");
        const checked = selectedFiles.has(f.name) ? 'checked' : '';
        const badge = f.has_translation ? '<span class="f7 bg-green white br2 ph1 pv1 ml2">✅</span>' : '';
        return `<div class="nt-file-item">
            <div class="flex items-center flex-auto">
                <input type="checkbox" class="nt-checkbox mr2" ${checked} onchange="toggleProjectFile('${esc}',this.checked)">
                <div class="flex-auto pointer" onclick="loadProjectFile('${esc}','sources')">
                    <span class="fw6 dark-gray db f6">${f.name} ${badge}</span>
                    <span class="f7 silver">${f.size_display}</span>
                </div>
            </div>
            <div class="nt-file-actions">
                <button class="nt-file-action-btn" onclick="event.stopPropagation();translateFileInProject('${esc}')" title="Dịch">⚡</button>
                <button class="nt-file-action-btn" onclick="event.stopPropagation();deleteProjectFile('${esc}','sources')" title="Xóa">🗑️</button>
            </div>
        </div>`;
    }).join('');
}

function renderProjectTranslated(translated) {
    const el = document.getElementById('project-translated-list');
    if (!translated.length) { el.innerHTML = '<div class="pa3 tc silver i">Chưa có file dịch</div>'; return; }
    el.innerHTML = translated.map(f => {
        const esc = f.name.replace(/'/g, "\\'");
        const checked = selectedTranslatedFiles.has(f.name) ? 'checked' : '';
        return `<div class="nt-file-item">
            <div class="flex items-center flex-auto">
                <input type="checkbox" class="nt-checkbox mr2" ${checked} onchange="toggleTranslatedFile('${esc}',this.checked)">
                <div class="flex-auto pointer" onclick="loadProjectFile('${esc}','translated')">
                    <span class="fw6 dark-gray db f6">${f.name}</span>
                    <span class="f7 silver">${f.size_display}</span>
                </div>
            </div>
            <div class="nt-file-actions">
                <button class="nt-file-action-btn" onclick="event.stopPropagation();moveBackInProject('${esc}')" title="Trả về sources">↩</button>
                <button class="nt-file-action-btn" onclick="event.stopPropagation();deleteProjectFile('${esc}','translated')" title="Xóa">🗑️</button>
            </div>
        </div>`;
    }).join('');
}

function switchProjectTab(tab) {
    document.querySelectorAll('.nt-tab-btn').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-ptab') === tab);
    });
    document.querySelectorAll('.nt-ptab-content').forEach(el => el.classList.add('dn'));
    const target = document.getElementById('ptab-' + tab);
    if (target) target.classList.remove('dn');

    // Load prompt/profile when switching
    if (tab === 'prompt' && currentProject) loadProjectPrompts();
    if (tab === 'profile' && currentProject) loadProjectProfile();
}

function loadProjectFile(filename, section) {
    if (!currentProject) return;
    const slug = currentProject.slug;
    fetch(`/api/projects/${slug}/file/${section}/${filename}`).then(r => r.json()).then(data => {
        if (section === 'sources') {
            document.getElementById('source-text').value = data.content || '';
            currentProjectFile = { name: filename, section };
            document.getElementById('btn-save-project-file').classList.remove('dn');
            // Show chunk controls
            const chunkControls = document.getElementById('chunk-controls');
            chunkControls.classList.remove('dn');
            document.getElementById('btn-chunk-file').setAttribute('data-filename', filename);
            updateTokenEstimate();
        } else {
            // Open Side-by-Side Editor
            currentDoneFile = filename;
            openSideBySideEditor(filename, data.content || '');
        }
    });
}

// ============================================================
// Side-by-Side Editor
// ============================================================
function openSideBySideEditor(filename, translatedContent) {
    if (!currentProject) return;
    const slug = currentProject.slug;

    // Hiển thị editor container + actions
    document.getElementById('sbs-editor-container').classList.remove('dn');
    document.getElementById('sbs-actions').classList.remove('dn');
    document.getElementById('sbs-filename').textContent = filename;
    document.getElementById('sbs-save-status').textContent = '';

    // Đổ nội dung bản dịch
    const transEl = document.getElementById('editor-translated');
    transEl.value = translatedContent;

    // Load bản gốc song song (tên file giống nhau, nằm trong sources/)
    const sourceEl = document.getElementById('editor-source');
    sourceEl.value = 'Đang tải bản gốc...';

    fetch(`/api/projects/${slug}/file/sources/${filename}`)
        .then(r => r.json())
        .then(data => {
            sourceEl.value = data.content || '(Không tìm thấy bản gốc)';
            updateEditorStats();
        })
        .catch(() => {
            sourceEl.value = '(Lỗi tải bản gốc)';
        });

    // Lắng nghe thay đổi để cập nhật stats
    transEl.oninput = updateEditorStats;

    // Sync scroll
    setupSyncScroll(sourceEl, transEl);
    updateEditorStats();
}

function saveSideBySideEditor() {
    if (!currentProject || !currentDoneFile) return;
    const slug = currentProject.slug;
    const content = document.getElementById('editor-translated').value;
    const statusEl = document.getElementById('sbs-save-status');
    statusEl.textContent = '💾 Đang lưu...';
    statusEl.className = 'f7 blue ml2';

    fetch(`/api/projects/${slug}/file/translated/${currentDoneFile}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            statusEl.textContent = '✅ Đã lưu lúc ' + new Date().toLocaleTimeString();
            statusEl.className = 'f7 green ml2';
        } else {
            statusEl.textContent = '❌ Lỗi: ' + (data.error || '');
            statusEl.className = 'f7 red ml2';
        }
    }).catch(e => {
        statusEl.textContent = '❌ ' + e.message;
        statusEl.className = 'f7 red ml2';
    });
}

function closeSideBySideEditor() {
    document.getElementById('sbs-editor-container').classList.add('dn');
    document.getElementById('sbs-actions').classList.add('dn');
    document.getElementById('editor-source').value = '';
    document.getElementById('editor-translated').value = '';
    document.getElementById('sbs-save-status').textContent = '';
}

function updateEditorStats() {
    const srcLen = (document.getElementById('editor-source').value || '').length;
    const transLen = (document.getElementById('editor-translated').value || '').length;
    document.getElementById('sbs-source-chars').textContent = srcLen.toLocaleString();
    document.getElementById('sbs-trans-chars').textContent = transLen.toLocaleString();
    document.getElementById('sbs-ratio').textContent = srcLen > 0
        ? (transLen / srcLen).toFixed(2) + 'x'
        : '—';
}

function setupSyncScroll(el1, el2) {
    let isSyncing = false;
    function sync(source, target) {
        if (isSyncing) return;
        isSyncing = true;
        const ratio = source.scrollTop / (source.scrollHeight - source.clientHeight || 1);
        target.scrollTop = ratio * (target.scrollHeight - target.clientHeight);
        isSyncing = false;
    }
    el1.onscroll = () => sync(el1, el2);
    el2.onscroll = () => sync(el2, el1);
}

function saveProjectFile() {
    if (!currentProject || !currentProjectFile) return;
    const content = document.getElementById('source-text').value;
    fetch(`/api/projects/${currentProject.slug}/file/${currentProjectFile.section}/${currentProjectFile.name}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
    }).then(r => r.json()).then(data => {
        if (data.success) { addLog('💾 Đã lưu: ' + currentProjectFile.name, 'success'); selectProject(currentProject.slug); }
        else addLog('❌ Lỗi lưu: ' + (data.error || ''), 'error');
    });
}

function uploadProjectFile() {
    if (!currentProject) { showToast('Chưa chọn dự án!', 'error'); return; }
    const fileInput = document.getElementById('upload-source-file');
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    showToast('📤 Đang tải file lên...', 'info');

    fetch(`/api/projects/${currentProject.slug}/upload`, {
        method: 'POST',
        body: formData
    }).then(r => r.json()).then(data => {
        if (data.success) {
            showToast(`Đã tải lên: ${data.filename} (${data.size_display})`, 'success');
            selectProject(currentProject.slug); // Reload danh sách file
        } else {
            showToast(data.error || 'Lỗi upload', 'error');
        }
        fileInput.value = ''; // Reset input
    }).catch(e => {
        showToast(e.message, 'error');
        fileInput.value = '';
    });
}

function chunkProjectFile() {
    if (!currentProject) { showToast('Chưa chọn dự án!', 'error'); return; }
    const btn = document.getElementById('btn-chunk-file');
    const filename = btn.getAttribute('data-filename');
    if (!filename) { showToast('Chưa chọn file để chia chunk!', 'error'); return; }

    const maxCharsInput = document.getElementById('inline-chunk-size');
    const maxChars = maxCharsInput && maxCharsInput.value
        ? parseInt(maxCharsInput.value)
        : parseInt(document.getElementById('chunk-size').value) || 100000;

    if (!confirm(`Chia "${filename}" thành các chunk (max ${maxChars.toLocaleString()} ký tự/chunk)?`)) return;

    showToast('✂️ Đang chia chunk...', 'info');

    fetch(`/api/projects/${currentProject.slug}/chunk/${filename}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_chars: maxChars })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            selectProject(currentProject.slug); // Reload danh sách file
        } else {
            showToast(data.error || 'Lỗi chia chunk', 'error');
        }
    }).catch(e => showToast(e.message, 'error'));
}

function deleteProjectFile(filename, section) {
    if (!confirm('Xóa vĩnh viễn "' + filename + '"?')) return;
    fetch(`/api/projects/${currentProject.slug}/file/${section}/${filename}`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' }
    }).then(r => r.json()).then(() => selectProject(currentProject.slug));
}

function toggleProjectFile(name, checked) {
    if (checked) selectedFiles.add(name); else selectedFiles.delete(name);
}

function selectAllProjectFiles() {
    if (!currentProject) return;
    (currentProject.sources || []).forEach(f => selectedFiles.add(f.name));
    renderProjectSources(currentProject.sources || []);
}

function translateFileInProject(filename) {
    if (!currentProject) return;
    fetch(`/api/projects/${currentProject.slug}/translate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: [filename] })
    }).then(r => r.json()).then(data => {
        if (data.status === 'started') {
            switchProjectTab('sources');
            startSSEProgress();
        } else showToast(data.error || 'Lỗi', 'error');
    });
}

function translateSelectedInProject() {
    if (!currentProject || selectedFiles.size === 0) { showToast('Chưa chọn file!', 'error'); return; }
    const files = Array.from(selectedFiles);
    fetch(`/api/projects/${currentProject.slug}/translate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files })
    }).then(r => r.json()).then(data => {
        if (data.status === 'started') startSSEProgress();
        else showToast(data.error || 'Lỗi', 'error');
    });
}

function moveBackInProject(filename) {
    if (!confirm('Trả "' + filename + '" về sources?')) return;
    fetch(`/api/projects/${currentProject.slug}/move-back`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename })
    }).then(r => r.json()).then(() => selectProject(currentProject.slug));
}

function loadProjectPrompts() {
    if (!currentProject) return;
    fetch(`/api/projects/${currentProject.slug}/prompts`).then(r => r.json()).then(data => {
        document.getElementById('proj-prompt-main').value = data.main || '';
        document.getElementById('proj-prompt-retranslate').value = data.retranslate || '';
        document.getElementById('proj-prompt-correction').value = data.correction || '';
    });
}

function saveProjectPrompts() {
    if (!currentProject) return;
    fetch(`/api/projects/${currentProject.slug}/prompts`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            main: document.getElementById('proj-prompt-main').value,
            retranslate: document.getElementById('proj-prompt-retranslate').value,
            correction: document.getElementById('proj-prompt-correction').value,
        })
    }).then(r => r.json()).then(data => {
        if (data.success) showToast('Đã lưu prompt dự án!', 'success');
    });
}

function loadProjectProfile() {
    if (!currentProject) return;
    const slug = currentProject.slug;
    Promise.all([
        fetch(`/api/projects/${slug}/file/profile/glossary.txt`).then(r => r.json()).catch(() => ({ content: '' })),
        fetch(`/api/projects/${slug}/file/profile/characters.txt`).then(r => r.json()).catch(() => ({ content: '' })),
        fetch(`/api/projects/${slug}/file/profile/style_guide.txt`).then(r => r.json()).catch(() => ({ content: '' })),
    ]).then(([g, c, s]) => {
        document.getElementById('proj-glossary').value = g.content || '';
        document.getElementById('proj-characters').value = c.content || '';
        document.getElementById('proj-style-guide').value = s.content || '';
    });
}

function saveProjectProfile() {
    if (!currentProject) return;
    const slug = currentProject.slug;
    const saves = [
        fetch(`/api/projects/${slug}/file/profile/glossary.txt`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: document.getElementById('proj-glossary').value })
        }),
        fetch(`/api/projects/${slug}/file/profile/characters.txt`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: document.getElementById('proj-characters').value })
        }),
        fetch(`/api/projects/${slug}/file/profile/style_guide.txt`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: document.getElementById('proj-style-guide').value })
        }),
    ];
    Promise.all(saves).then(() => showToast('Đã lưu profile dự án!', 'success'));
}

function showCreateProjectDialog() {
    const modal = document.getElementById('new-project-modal');
    // Populate genre dropdown from available genres
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
    // Clear form
    document.getElementById('new-project-name').value = '';
    document.getElementById('new-project-desc').value = '';
    modal.style.display = 'flex';
}

function initProjectDialog() {
    const modal = document.getElementById('new-project-modal');
    if (!modal) return;

    document.getElementById('btn-cancel-project').addEventListener('click', () => {
        modal.style.display = 'none';
    });

    document.getElementById('btn-confirm-new-project').addEventListener('click', () => {
        const name = document.getElementById('new-project-name').value.trim();
        if (!name) { showToast('Tên dự án không được trống!', 'error'); return; }
        const desc = document.getElementById('new-project-desc').value.trim();
        const genre = document.getElementById('new-project-genre').value;

        fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description: desc, genre })
        })
            .then(r => r.json())
            .then(data => {
                modal.style.display = 'none';
                if (data.success) {
                    showToast(`Đã tạo dự án "${name}"`, 'success');
                    loadProjects();
                    selectProject(data.slug);
                } else {
                    showToast(data.error || 'Lỗi tạo dự án', 'error');
                }
            })
            .catch(e => showToast(e.message, 'error'));
    });
}

function deleteCurrentProject() {
    if (!currentProject) return;
    if (!confirm('Xóa VĨNH VIỄN dự án "' + currentProject.name + '"? Tất cả dữ liệu sẽ bị mất!')) return;
    fetch('/api/projects/' + currentProject.slug, { method: 'DELETE' })
        .then(r => r.json()).then(() => {
            currentProject = null;
            document.getElementById('project-header').classList.add('dn');
            document.getElementById('project-tabs').classList.add('dn');
            document.querySelectorAll('.nt-ptab-content').forEach(el => el.classList.add('dn'));
            document.getElementById('project-empty-state').classList.remove('dn');
            loadProjects();
        });
}

function archiveProject() {
    if (!currentProject) return;
    window.location.href = '/api/projects/' + currentProject.slug + '/archive';
}

// toggleSidebar removed — sidebar replaced by top navigation bar


// ============================================================
// Stats
// ============================================================
function loadStats() {
    fetch('/api/stats').then(r => r.json()).then(data => {
        document.getElementById('api-keys-count').textContent = data.api_keys_count || data.api_keys || 0;
        document.getElementById('cache-count').textContent = data.cache_files || 0;
        document.getElementById('cache-size').textContent = data.cache_size_mb || 0;
        const pc = document.getElementById('project-count');
        const sc = document.getElementById('source-count');
        const tc = document.getElementById('translated-count');
        if (pc) pc.textContent = data.project_count || 0;
        if (sc) sc.textContent = data.total_sources || 0;
        if (tc) tc.textContent = data.total_translated || 0;
    });
}

function clearCache() {
    if (!confirm('Xóa sạch bộ nhớ Cache dịch thuật?')) return;
    fetch('/api/cache/clear', { method: 'POST' }).then(r => r.json()).then(data => {
        showToast('Đã dọn dẹp ' + data.deleted + ' files nháp.', 'success');
        loadStats();
    });
}

// ============================================================
// Translation Core
// ============================================================
function getActivePrompts() {
    return prompts; // Currently loaded prompts (from genre or default)
}

function showProgress(containerId, barId, percentId, textId, percent, text) {
    const c = document.getElementById(containerId);
    c.classList.remove('dn');
    document.getElementById(barId).style.width = percent + '%';
    document.getElementById(percentId).textContent = percent + '%';
    document.getElementById(textId).textContent = text;
}

function hideProgress(containerId) {
    document.getElementById(containerId).classList.add('dn');
}

function startTranslation() {
    const btn = document.getElementById('translate-btn');
    const text = document.getElementById('source-text').value;
    if (!text.trim()) { showToast('Vui lòng nhập văn bản hoặc chọn file!', 'error'); return; }

    btn.disabled = true;
    btn.innerHTML = '🔄 <span class="nt-btn-spinner dib"></span> Đang dịch...';

    document.getElementById('result-container').classList.add('dn');
    document.getElementById('result-container').classList.remove('flex');

    document.getElementById('log-container').classList.add('dn');
    document.getElementById('log-container').innerHTML = '';

    addLog('Bắt đầu dịch nội dung...', 'info');

    fetch('/api/translate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text, model: document.getElementById('model').value,
            temperature: parseFloat(document.getElementById('temperature').value),
            chunk_size: parseInt(document.getElementById('chunk-size').value),
            use_cache: document.getElementById('use-cache').checked,
            prompts: getActivePrompts()
        })
    }).then(r => r.json()).then(data => {
        if (data.error) { addLog(data.error, 'error'); resetButton(btn); }
        else connectToProgress(btn);
    }).catch(e => { addLog(e.message, 'error'); resetButton(btn); });
}

function saveChunkTranslation() {
    if (!currentProject || !currentProjectFile) {
        showToast('Không xác định được dự án hoặc file nguồn đang thao tác.', 'error');
        return;
    }

    const slug = currentProject.slug;
    const filename = currentProjectFile.name; // Tên file chunk gốc
    const content = document.getElementById('result-text').value;

    if (!content.trim()) {
        showToast('Nội dung dịch trống, không thể lưu.', 'warning');
        return;
    }

    const btn = document.getElementById('btn-save-translation');
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Đang lưu...';
    btn.disabled = true;

    fetch(`/api/projects/${slug}/file/translated/${filename}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content })
    })
        .then(r => r.json())
        .then(res => {
            btn.innerHTML = originalText;
            btn.disabled = false;
            if (res.success) {
                showToast(`Đã lưu bản dịch cho file: ${filename}`, 'success');
                // Refresh danh sách file dự án để cập nhật UI dấu tick hoàn thành
                if (typeof loadProjectFiles === 'function') {
                    loadProjectFiles(slug);
                }
            } else {
                showToast('Lỗi lưu file: ' + (res.error || 'Unknown'), 'error');
            }
        })
        .catch(e => {
            btn.innerHTML = originalText;
            btn.disabled = false;
            showToast('Lỗi mạng: ' + e.message, 'error');
        });
}





function connectToProgress(btn = null, isBatch = false) {
    const evtSource = new EventSource('/api/progress');
    showProgress('progress-container', 'progress-bar', 'progress-percent', 'progress-text', 0, 'Đang kết nối API...');
    document.getElementById('log-container').classList.remove('dn');
    document.getElementById('log-container').classList.add('block');

    evtSource.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
            showProgress('progress-container', 'progress-bar', 'progress-percent', 'progress-text', data.percent, data.message);
        }
        else if (data.type === 'info' || data.type === 'log') {
            addLog(data.message, data.level || 'info');
        }
        else if (data.type === 'complete') {
            evtSource.close();
            showProgress('progress-container', 'progress-bar', 'progress-percent', 'progress-text', 100, 'Tất cả hoàn tất! 🚀');

            if (data.output_file) {
                currentOutputFile = data.output_file;
                document.getElementById('result-text').value = "Đã dịch xong. Kết quả được lưu tại:\n👉 " + data.output_file;
            } else {
                document.getElementById('result-text').value = data.translated_text || '';
            }

            // Show result layout
            const resContainer = document.getElementById('result-container');
            resContainer.classList.remove('dn');
            resContainer.classList.add('flex');

            // Render Stats
            document.getElementById('result-stats').innerHTML =
                `<span class="bg-near-white br2 pa1 ph2 ba b--black-10">⏱️ ${(data.duration || 0).toFixed(1)}s</span>
                 <span class="bg-near-white br2 pa1 ph2 ba b--black-10">💬 ${data.chunks_count || 0} đoạn</span>
                 <span class="bg-near-white br2 pa1 ph2 ba b--black-10">🔤 ${(data.char_count || 0).toLocaleString()} ký tự</span>`;

            resetButton(btn, isBatch);
            if (currentProject && document.getElementById('ptab-sources') && !document.getElementById('ptab-sources').classList.contains('dn')) {
                selectProject(currentProject.slug);
            }
            loadOutputFiles(); loadStats(); loadFiles(); loadDoneFiles();
        }
        else if (data.type === 'error') {
            evtSource.close();
            addLog(data.message, 'error');
            resetButton(btn, isBatch);
        }
    };
    evtSource.onerror = function () { evtSource.close(); };
}

function addLog(message, type) {
    const el = document.getElementById('log-container');
    const entry = document.createElement('div');
    const typeClass = type === 'error' ? 'red fw6' : (type === 'success' ? 'green' : 'blue');
    entry.className = 'nt-log-entry mb1 ' + typeClass;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    el.appendChild(entry);
    el.scrollTop = el.scrollHeight;
}

function resetButton(btn, isBatch = false) {
    if (isBatch || (btn && btn.id === 'btn-translate-selected')) {
        const batchBtn = document.getElementById('btn-translate-selected');
        if (batchBtn) {
            batchBtn.disabled = false;
            batchBtn.innerHTML = `🚀 Dịch <span id="btn-translate-count">${selectedFiles.size} file</span> đã chọn`;
        }
    } else {
        if (!btn) btn = document.getElementById('translate-btn');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '🚀 Dịch Nội Dung';
        }
    }
}

function copyResult() {
    navigator.clipboard.writeText(document.getElementById('result-text').value)
        .then(() => showToast('Đã sao chép vào Clipboard!', 'success'))
        .catch(() => showToast('Copy thất bại', 'error'));
}
function downloadResult() {
    if (currentOutputFile) window.open('/api/download/' + currentOutputFile, '_blank');
    else showToast('Chưa xác định file output!', 'error');
}

// ============================================================
// Done Tab (Retranslate/Correction)
// ============================================================
function runRetranslate() {
    const text = document.getElementById('editor-translated').value;
    if (!text.trim()) { showToast('Chưa tải nội dung file dịch!', 'error'); return; }
    runDoneTranslationProcess(text, 'retranslate');
}
function runCorrection() {
    const text = document.getElementById('editor-translated').value;
    if (!text.trim()) { showToast('Chưa tải nội dung file dịch!', 'error'); return; }
    runDoneTranslationProcess(text, 'correction');
}
function runBoth() {
    const text = document.getElementById('editor-translated').value;
    if (!text.trim()) { showToast('Chưa tải nội dung file dịch!', 'error'); return; }
    addDoneLog('Đang tiến hành Retranslate...', 'info');
    runDoneTranslationProcess(text, 'retranslate', () => {
        addDoneLog('Bắt đầu rà soát Correction...', 'info');
        runDoneTranslationProcess(document.getElementById('done-result-text').value, 'correction', null, true);
    });
}

function runDoneTranslationProcess(text, mode, callback, appendResult) {
    showProgress('done-progress-container', 'done-progress-bar', 'done-progress-percent', 'done-progress-text', 0, 'Đang chuẩn bị Prompt và Tách khối...');
    document.getElementById('done-log-container').classList.remove('dn');
    document.getElementById('done-log-container').classList.add('block');
    document.getElementById('done-log-container').innerHTML = '';

    fetch('/api/translate-text', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text, mode, prompts: getActivePrompts(),
            model: document.getElementById('model').value,
            temperature: parseFloat(document.getElementById('temperature').value),
            chunk_size: parseInt(document.getElementById('chunk-size').value)
        })
    }).then(r => r.json()).then(data => {
        if (data.error) { addDoneLog('Lỗi xử lý: ' + data.error, 'error'); hideProgress('done-progress-container'); return; }

        // This is a simplified fallback for non-SSE text translate API
        hideProgress('done-progress-container');
        const result = data.translated || text;

        if (appendResult) document.getElementById('editor-translated').value = result;
        else document.getElementById('done-result-text').value = result;

        const resContainer = document.getElementById('done-result-container');
        resContainer.classList.remove('dn');
        resContainer.classList.add('flex');

        addDoneLog('Giai đoạn [' + mode + '] đã hoàn thành!', 'success');
        if (callback) callback();
    }).catch(e => { addDoneLog('Lỗi kết nối: ' + e.message, 'error'); hideProgress('done-progress-container'); });
}

function addDoneLog(message, type) {
    const el = document.getElementById('done-log-container');
    const entry = document.createElement('div');
    const typeClass = type === 'error' ? 'red fw6' : (type === 'success' ? 'green' : 'blue');
    entry.className = 'nt-log-entry mb1 ' + typeClass;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    el.appendChild(entry);
    el.scrollTop = el.scrollHeight;
}

function copyDoneResult() {
    navigator.clipboard.writeText(document.getElementById('done-result-text').value)
        .then(() => showToast('Đã chép nội dung đã sửa!', 'success'))
        .catch(() => showToast('Copy thất bại', 'error'));
}
function downloadDoneResult() {
    const text = document.getElementById('done-result-text').value;
    if (!text) return;
    const fname = currentDoneFile ? currentDoneFile.replace('.txt', '_fixed.txt') : 'fixed.txt';
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
    a.download = fname; a.click();
}

// ============================================================
// Genre-based Prompt Manager
// ============================================================
function loadGenres() {
    fetch('/api/prompt-sets')
        .then(r => r.json())
        .then(sets => {
            const el = document.getElementById('genre-list');
            if (!sets.length) { el.innerHTML = '<div class="pa4 tc silver i">Chưa có Thể Loại nào</div>'; return; }
            el.innerHTML = sets.map(s =>
                `<div class="nt-genre-item pointer pa3 bb b--black-10 flex items-center justify-between transition-colors ${s.slug === currentGenre ? 'bg-light-blue bl bw2 b--blue' : ''}" onclick="selectGenre('${s.slug}')">
                    <div>
                        <div class="fw6 dark-gray">${s.name}</div>
                        <div class="f7 silver mt1">${s.description || 'Không mô tả'}</div>
                    </div>
                    <span class="f7 fw6 br2 ph2 pv1 ${s.has_main ? 'bg-green white' : 'bg-light-gray silver'}">${s.has_main ? 'Đã có' : 'Trống'}</span>
                </div>`
            ).join('');

            // Auto select first genre if none selected
            if (!currentGenre && sets.length > 0) {
                selectGenre(sets[0].slug);
            }
        });
}

function selectGenre(slug) {
    currentGenre = slug;

    // Không cho xóa hoặc nạp với bộ Mặc định gốc
    const isDefault = (slug === 'default');
    document.getElementById('btn-delete-genre').disabled = isDefault || !slug;
    document.getElementById('btn-activate-genre').disabled = isDefault || !slug;

    if (isDefault) {
        document.getElementById('btn-delete-genre').title = 'Không thể xóa bộ mặc định';
        document.getElementById('btn-activate-genre').title = 'Đã là hệ thống mặc định';
    } else {
        document.getElementById('btn-delete-genre').title = '';
        document.getElementById('btn-activate-genre').title = '';
    }

    document.getElementById('genre-editor').classList.remove('dn');
    document.getElementById('genre-editor').classList.add('flex');

    fetch('/api/prompt-sets/' + slug)
        .then(r => r.json())
        .then(data => {
            document.getElementById('genre-editor-title').innerHTML = '<span class="mr2">📝</span> ' + (data.meta.name || slug);
            document.getElementById('genre-editor-desc').textContent = data.meta.description || '';
            document.getElementById('genre-main-text').value = data.prompts.main || '';
            document.getElementById('genre-retranslate-text').value = data.prompts.retranslate || '';
            document.getElementById('genre-correction-text').value = data.prompts.correction || '';
            loadGenres(); // Refresh active state in list
        });
}

function cloneGenre() {
    if (!currentGenre) return;
    const modal = document.getElementById('new-genre-modal');
    document.getElementById('new-genre-name').value = 'Bản sao ' + currentGenre;
    document.getElementById('new-genre-slug').value = 'ban-sao-' + currentGenre;
    document.getElementById('new-genre-desc').value = 'Nhân bản từ ' + currentGenre;

    window.isCloning = true;
    modal.style.display = 'flex';
}

function createGenre(e) {
    if (e) e.preventDefault();
    const name = document.getElementById('new-genre-name').value.trim();
    const slug = document.getElementById('new-genre-slug').value.trim() ||
        name.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
    const desc = document.getElementById('new-genre-desc').value.trim();

    if (!name) { showToast('Tên thể loại không được rỗng!', 'error'); return; }

    const promptsData = window.isCloning ? {
        main: document.getElementById('genre-main-text').value,
        retranslate: document.getElementById('genre-retranslate-text').value,
        correction: document.getElementById('genre-correction-text').value
    } : { main: '', retranslate: '', correction: '' };
    window.isCloning = false;

    fetch('/api/prompt-sets', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, slug, description: desc, prompts: promptsData })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            document.getElementById('new-genre-name').value = '';
            document.getElementById('new-genre-slug').value = '';
            document.getElementById('new-genre-desc').value = '';
            loadGenres();
            selectGenre(data.slug);
            showGenreAlert(`Đã tạo Profile: ${name}`, 'success');
        } else {
            showToast('Lỗi khởi tạo: ' + (data.error || 'Unknown Error'), 'error');
        }
    });
}

function saveGenre() {
    if (!currentGenre) return;
    const btn = document.getElementById('btn-save-genre');
    btn.textContent = '...Đang lưu...';
    btn.disabled = true;

    fetch('/api/prompt-sets/' + currentGenre, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            prompts: {
                main: document.getElementById('genre-main-text').value,
                retranslate: document.getElementById('genre-retranslate-text').value,
                correction: document.getElementById('genre-correction-text').value
            }
        })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            showGenreAlert('Lưu cấu trúc Prompt hoàn tất!', 'success');
            btn.textContent = '💾 Lưu Prompt';
            btn.disabled = false;
        }
    });
}

function activateGenre() {
    if (!currentGenre) return;
    if (!confirm('Xác nhận NẠP BỘ PROMPT NÀY vào bộ máy dịch thuật chính?')) return;

    fetch('/api/prompt-sets/' + currentGenre + '/activate', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                prompts = {
                    main: document.getElementById('genre-main-text').value,
                    retranslate: document.getElementById('genre-retranslate-text').value,
                    correction: document.getElementById('genre-correction-text').value
                };
                showGenreAlert('Nạp thông tin AI vào bộ xử lý Thành Công 🚀', 'success');
            }
        });
}

function deleteGenre() {
    if (!currentGenre) return;
    if (!confirm('Hành động này KHÔNG THỂ KHÔI PHỤC. Chắc chắn xóa thư mục the loai "' + currentGenre + '"?')) return;
    fetch('/api/prompt-sets/' + currentGenre, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                currentGenre = '';
                document.getElementById('genre-empty-state').classList.remove('dn');
                document.getElementById('genre-editor').classList.add('dn');
                document.getElementById('genre-editor').classList.remove('flex');
                document.getElementById('btn-delete-genre').disabled = true;
                document.getElementById('btn-activate-genre').disabled = true;
                loadGenres();
            }
        });
}

function showGenreAlert(msg, type) {
    const el = document.getElementById('genre-alert');
    const icon = document.getElementById('genre-alert-icon');
    const text = document.getElementById('genre-alert-text');

    el.classList.remove('dn', 'bg-dark-red', 'bg-green');

    if (type === 'success') {
        el.classList.add('bg-green');
        icon.textContent = '✅';
    } else {
        el.classList.add('bg-dark-red');
        icon.textContent = '⚠️';
    }

    text.textContent = msg;
    setTimeout(() => { el.classList.add('dn'); }, 4000);
}



// ============================================================
// Plugin Execution
// ============================================================

function toggleEpubForm() {
    const dir = document.getElementById('epub-direction').value;
    if (dir === 'epub_to_text') {
        document.getElementById('epub-to-text-form').classList.remove('dn');
        document.getElementById('text-to-epub-form').classList.add('dn');
    } else {
        document.getElementById('epub-to-text-form').classList.add('dn');
        document.getElementById('text-to-epub-form').classList.remove('dn');
    }
}

function pluginLog(logId, msg, type) {
    const el = document.getElementById(logId);
    el.classList.remove('dn');
    const entry = document.createElement('div');
    const cls = type === 'error' ? 'red fw6' : (type === 'success' ? 'green' : 'dark-gray');
    entry.className = 'mb1 ' + cls;
    entry.textContent = msg;
    el.appendChild(entry);
    el.scrollTop = el.scrollHeight;
}

function runEpubConverter() {
    const direction = document.getElementById('epub-direction').value;
    const logEl = document.getElementById('epub-log');
    logEl.innerHTML = '';
    logEl.classList.remove('dn');

    const btn = document.getElementById('btn-run-epub');
    btn.disabled = true;
    btn.textContent = '⏳ Đang chạy...';

    let payload = { direction };

    if (direction === 'epub_to_text') {
        payload.epub_path = document.getElementById('epub-path').value.trim();
        payload.out_dir = document.getElementById('epub-out-dir').value.trim() || 'workspace/input';
        payload.mode = document.getElementById('epub-mode').value;
        payload.ext = document.getElementById('epub-ext').value;
        payload.underline = document.getElementById('epub-underline').checked;
        payload.include_nonspine = document.getElementById('epub-nonspine').checked;

        if (!payload.epub_path) {
            pluginLog('epub-log', '❌ Vui lòng nhập đường dẫn file EPUB!', 'error');
            btn.disabled = false;
            btn.textContent = '🚀 Chạy EPUB Converter';
            return;
        }
    } else {
        payload.directory = document.getElementById('epub-book-dir').value.trim();
        payload.use_markdown = document.getElementById('epub-use-md').checked;
        payload.split_chapters = document.getElementById('epub-split-chapters').checked;

        if (!payload.directory) {
            pluginLog('epub-log', '❌ Vui lòng nhập đường dẫn thư mục sách!', 'error');
            btn.disabled = false;
            btn.textContent = '🚀 Chạy EPUB Converter';
            return;
        }
    }

    pluginLog('epub-log', '🔄 Đang gửi yêu cầu...', 'info');

    fetch('/api/plugins/epub-converter', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(r => r.json()).then(data => {
        if (data.plugin_id) {
            pollPluginProgress(data.plugin_id, 'epub-log', btn, '🚀 Chạy EPUB Converter');
        } else {
            pluginLog('epub-log', '❌ ' + (data.error || 'Lỗi không xác định'), 'error');
            btn.disabled = false;
            btn.textContent = '🚀 Chạy EPUB Converter';
        }
    }).catch(e => {
        pluginLog('epub-log', '❌ Lỗi kết nối: ' + e.message, 'error');
        btn.disabled = false;
        btn.textContent = '🚀 Chạy EPUB Converter';
    });
}

function runOcr() {
    const logEl = document.getElementById('ocr-log');
    logEl.innerHTML = '';
    logEl.classList.remove('dn');

    const btn = document.getElementById('btn-run-ocr');
    btn.disabled = true;
    btn.textContent = '⏳ Đang chạy...';

    const input_path = document.getElementById('ocr-input').value.trim();
    if (!input_path) {
        pluginLog('ocr-log', '❌ Vui lòng nhập đường dẫn file PDF/Ảnh!', 'error');
        btn.disabled = false;
        btn.textContent = '🚀 Chạy OCR Reader';
        return;
    }

    const skip_steps = {};
    if (document.getElementById('ocr-skip-cleanup').checked) skip_steps.cleanup = true;
    if (document.getElementById('ocr-skip-spell').checked) skip_steps.spell_check = true;

    const pagesRaw = document.getElementById('ocr-pages').value.trim();

    const payload = {
        input_path,
        output_path: document.getElementById('ocr-output').value.trim(),
        process_mode: document.getElementById('ocr-mode').value,
        skip_steps: Object.keys(skip_steps).length ? skip_steps : null,
        pages: pagesRaw || null
    };

    pluginLog('ocr-log', '🔄 Đang gửi yêu cầu OCR...', 'info');

    fetch('/api/plugins/ocr', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(r => r.json()).then(data => {
        if (data.plugin_id) {
            pollPluginProgress(data.plugin_id, 'ocr-log', btn, '🚀 Chạy OCR Reader');
        } else {
            pluginLog('ocr-log', '❌ ' + (data.error || 'Lỗi không xác định'), 'error');
            btn.disabled = false;
            btn.textContent = '🚀 Chạy OCR Reader';
        }
    }).catch(e => {
        pluginLog('ocr-log', '❌ Lỗi kết nối: ' + e.message, 'error');
        btn.disabled = false;
        btn.textContent = '🚀 Chạy OCR Reader';
    });
}

function pollPluginProgress(pluginId, logId, btn, btnLabel) {
    let lastCount = 0;

    const interval = setInterval(() => {
        fetch('/api/plugins/progress/' + pluginId)
            .then(r => r.json())
            .then(data => {
                // Render new messages
                const msgs = data.messages || [];
                for (let i = lastCount; i < msgs.length; i++) {
                    const isError = msgs[i].includes('❌') || msgs[i].includes('Lỗi');
                    const isSuccess = msgs[i].includes('✅') || msgs[i].includes('thành công');
                    pluginLog(logId, msgs[i], isError ? 'error' : (isSuccess ? 'success' : 'info'));
                }
                lastCount = msgs.length;

                if (data.status === 'done' || data.status === 'error') {
                    clearInterval(interval);
                    btn.disabled = false;
                    btn.textContent = btnLabel;

                    if (data.status === 'done' && data.result) {
                        if (data.result.output_dir) {
                            pluginLog(logId, `📂 Output: ${data.result.output_dir}`, 'success');
                        }
                        if (data.result.output_path) {
                            pluginLog(logId, `📄 File: ${data.result.output_path}`, 'success');
                        }
                        if (data.result.char_count) {
                            pluginLog(logId, `🔤 ${data.result.char_count.toLocaleString()} ký tự`, 'success');
                        }
                    }

                    // Refresh file lists in case output went to workspace
                    loadFiles();
                    loadOutputFiles();
                    loadStats();
                }
            })
            .catch(() => {
                clearInterval(interval);
                btn.disabled = false;
                btn.textContent = btnLabel;
            });
    }, 1000);
}

function toggleProjectList() {
    const col = document.getElementById('project-list-col');
    const btn = event.currentTarget;
    if (col.classList.contains('dn')) {
        col.classList.remove('dn');
        btn.textContent = '◗';
    } else {
        col.classList.add('dn');
        btn.textContent = '◖';
    }
}
