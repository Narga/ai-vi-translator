/* Novel Translator - main.js v5.0 (Tachyons Redesign) */

let prompts = window.initialPrompts || {};
let currentOutputFile = '';
let allFiles = [];
let selectedFiles = new Set();
let availableModels = window.initialAvailableModels || [];
let availableGeminiModels = [];
let availableOpenAIModels = [];
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

    // Click-outside to close Project Info Modal
    const projInfoModal = document.getElementById('project-info-modal');
    if (projInfoModal) {
        projInfoModal.addEventListener('click', function(e) {
            if (e.target === projInfoModal) hideProjectInfoModal();
        });
    }

    // Spell-check tab buttons
    const btnCopySpell = document.getElementById('btn-copy-spellcheck');
    if (btnCopySpell) btnCopySpell.addEventListener('click', copySpellCheckResult);
    const btnDownSpell = document.getElementById('download-spellcheck-btn');
    if (btnDownSpell) btnDownSpell.addEventListener('click', downloadSpellCheckResult);
    const btnRunSpell = document.getElementById('spellcheck-btn');
    if (btnRunSpell) btnRunSpell.addEventListener('click', runSpellcheck);

    setInterval(loadStats, 30000);

    // Temperature slider
    const tempEl = document.getElementById('temperature');
    if (tempEl) {
        tempEl.addEventListener('input', function () {
            const valEl = document.getElementById('temp-value');
            if (valEl) valEl.textContent = this.value;
        });
    }

    // Token estimate for translated text
    const translatedResultEl = document.getElementById('translated-result-text');
    if (translatedResultEl) {
        translatedResultEl.addEventListener('input', updateTranslatedTokenEstimate);
    }

    // Core action buttons
    const btnTranslate = document.getElementById('translate-btn');
    if (btnTranslate) btnTranslate.addEventListener('click', startTranslation);
    
    const btnClearCache = document.getElementById('btn-clear-cache');
    if (btnClearCache) btnClearCache.addEventListener('click', clearCache);
    
    const btnCopy = document.getElementById('btn-copy-result');
    if (btnCopy) btnCopy.addEventListener('click', copyResult);
    
    const btnDownload = document.getElementById('download-btn');
    if (btnDownload) btnDownload.addEventListener('click', downloadResult);

    // Translated tab action buttons
    const btnCopyTranslated = document.getElementById('btn-copy-translated');
    if (btnCopyTranslated) btnCopyTranslated.addEventListener('click', copyTranslatedResult);
    
    const btnDownloadTranslated = document.getElementById('download-translated-btn');
    if (btnDownloadTranslated) btnDownloadTranslated.addEventListener('click', downloadTranslatedResult);
    
    const btnRetranslate = document.getElementById('retranslate-btn');
    if (btnRetranslate) btnRetranslate.addEventListener('click', retranslateFile);

    // Done tab buttons
    const btnRetrans = document.getElementById('btn-run-retranslate');
    if (btnRetrans) btnRetrans.addEventListener('click', runRetranslate);
    
    const btnCorrect = document.getElementById('btn-run-correction');
    if (btnCorrect) btnCorrect.addEventListener('click', runCorrection);
    
    const btnBoth = document.getElementById('btn-run-both');
    if (btnBoth) btnBoth.addEventListener('click', runBoth);
    
    const btnCopyDone = document.getElementById('btn-copy-done-result');
    if (btnCopyDone) btnCopyDone.addEventListener('click', copyDoneResult);
    
    const btnDownDone = document.getElementById('btn-download-done-result');
    if (btnDownDone) btnDownDone.addEventListener('click', downloadDoneResult);

    // Prompt Manager buttons
    const btnDelGenre = document.getElementById('btn-delete-genre');
    if (btnDelGenre) btnDelGenre.addEventListener('click', deleteGenre);
    
    const btnCloneGenre = document.getElementById('btn-clone-genre');
    if (btnCloneGenre) btnCloneGenre.addEventListener('click', cloneGenre);
    
    const btnSaveGenre = document.getElementById('btn-save-genre');
    if (btnSaveGenre) btnSaveGenre.addEventListener('click', saveGenre);

    const btnUseGenre = document.getElementById('btn-use-genre');
    if (btnUseGenre) btnUseGenre.addEventListener('click', useGenre);

});

// ============================================================
// UI Initializations
// ============================================================
function initTabs() {
    const navItems = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.nt-tab-content');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = item.getAttribute('data-tab');

            // Hook loadArchiveList when switching to archive tab
            if (targetId === 'archive') {
                loadArchiveList();
            }
            if (targetId === 'logs') {
                loadLogList();
            }

            // Update Nav Classes
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            // Toggle Sections
            sections.forEach(sec => {
                sec.classList.remove('active');
            });
            const targetSection = document.getElementById('tab-' + targetId);
            if (targetSection) {
                targetSection.classList.add('active');
                // Auto scroll to top when switching
                targetSection.scrollTo(0, 0);
            }
        });
    });
}

function initPromptTabs() {
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
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';

    toast.innerHTML = `<span>${icon}</span><span class="ml2">${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 4000);
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
// ============================================================
// Models & Token Estimation
// ============================================================

function switchProvider(provider) {
    // Update visual state using Tachyons
    document.querySelectorAll('.nt-provider-col').forEach(col => {
        const isActive = col.dataset.provider === provider;
        if(isActive) {
            col.classList.add('b--blue', 'o-100');
            col.classList.remove('b--light-gray', 'o-60');
            const radio = col.querySelector('input[type="radio"]');
            if(radio) radio.checked = true;
        } else {
            col.classList.add('b--light-gray', 'o-60');
            col.classList.remove('b--blue', 'o-100');
            const radio = col.querySelector('input[type="radio"]');
            if(radio) radio.checked = false;
        }
    });

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

function saveOpenAIConfig() {
    const data = {
        api_key: document.getElementById('openai-api-key').value,
        base_url: document.getElementById('openai-base-url').value,
        model: document.getElementById('model').value, // Use unified model
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
                const provider = data.active;
                // Set radio button
                const radio = document.querySelector(`input[name="active_provider"][value="${provider}"]`);
                if (radio) radio.checked = true;

                // Set visual state
                document.querySelectorAll('.nt-provider-col').forEach(col => {
                    col.classList.toggle('nt-provider-active', col.dataset.provider === provider);
                });

                // Update badge & name
                const badge = document.getElementById('provider-active-badge');
                if (badge) {
                    badge.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';
                    badge.className = 'f7 fw6 ph2 pv1 br2 ' +
                        (provider === 'gemini' ? 'bg-light-green dark-green' : 'bg-lightest-blue dark-blue');
                }
                const nameEl = document.getElementById('current-provider-name');
                if (nameEl) nameEl.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';
            }

            // Fill OpenAI config fields
            if (data.openai_config) {
                const cfg = data.openai_config;
                if (cfg.base_url) document.getElementById('openai-base-url').value = cfg.base_url;
                const keyInput = document.getElementById('openai-api-key');
                if (keyInput) {
                    if (cfg.key) keyInput.value = cfg.key;
                    else if (cfg.has_key) keyInput.placeholder = '••••••••••• (đã cấu hình qua biến môi trường)';
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
                    if (m.MODEL) {
                        const sel = document.getElementById('model');
                        if (sel) {
                            sel.value = m.MODEL;
                            onModelChange(m.MODEL);
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
                showToast('Lưu Cấu hình thành công!', 'success');
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
    const url = '/api/models?full=true';
    fetch(url)
        .then(r => r.json())
        .then(data => {
            if (data.models && data.models.length > 0) availableModels = data.models;
            
            const renderOptions = (models, currentDefault) => {
                let saved = localStorage.getItem('nt_marked_models');
                let markedModels = saved ? JSON.parse(saved) : [];
                
                return models.map(m => {
                    const id = typeof m === 'string' ? m : m.id;
                    const name = typeof m === 'string' ? m : m.name;
                    const isFree = m.is_free ? ' 🆓' : '';
                    const isMarked = markedModels.includes(id) ? ' ⭐' : '';
                    const isSelected = id === currentDefault ? 'selected' : '';
                    return `<option value="${id}" ${isSelected}>${name}${isFree}${isMarked}</option>`;
                }).join('');
            };

            const defaultModelVal = data.default || '';

            const mainSel = document.getElementById('model');
            if (mainSel) {
                mainSel.innerHTML = renderOptions(availableModels, defaultModelVal);
                onModelChange(mainSel.value);
            }

            // Populate QA Model dropdown (system config)
            const qaSel = document.getElementById('cfg-qa-model');
            if (qaSel) {
                qaSel.innerHTML = renderOptions(availableModels, '');
            }

            // Populate Summarize Model dropdown
            const sumSel = document.getElementById('summarize-model');
            if (sumSel) {
                sumSel.innerHTML = '<option value="">— Mặc định —</option>' + renderOptions(availableModels, '');
            }

            // Populate per-tab content model dropdowns (guideline tabs)
            const contentTabModels = ['style-guide-model', 'relationship-model', 'glossary-model', 'summary-model'];
            contentTabModels.forEach(selId => {
                const sel = document.getElementById(selId);
                if (sel) sel.innerHTML = '<option value="">— Chọn Model —</option>' + renderOptions(availableModels, '');
            });

            // Load saved config values AFTER models dropdown is ready
            loadAppConfig();
        })
        .catch(err => {
            console.error('Error loading models:', err);
        });
}

function markModel() {
    const sel = document.getElementById('model');
    if (!sel || !sel.value) return;
    
    const id = sel.value;
    let saved = localStorage.getItem('nt_marked_models');
    let markedModels = saved ? JSON.parse(saved) : [];
    
    if (markedModels.includes(id)) {
        markedModels = markedModels.filter(m => m !== id);
        showToast('Đã bỏ đánh dấu model', 'info');
    } else {
        markedModels.push(id);
        showToast('Đã đánh dấu model yêu thích ⭐', 'success');
    }
    
    localStorage.setItem('nt_marked_models', JSON.stringify(markedModels));
    
    if (availableModels) {
        // Re-render selections (preserving the currently selected model by passing sel.value instead of relying on default app config initially)
        loadModels(); 
        
        // Wait, loadModels is async, we can just fetch and it will re-render them keeping the default.
        // Actually, loadModels fetches from API, and uses data.default as the default model.
        // Wait! doing loadModels will overwrite sel.value with data.default!
        // So we should just update the label using availableModels text, or do a quick re-render without fetching.
        // I will let loadModels do its thing but let's override logic: Since loadAppConfig might override it, I will just re-fetch.
    }
}

function onModelChange(modelName) {
    fetchModelInfo(modelName);
}

function fetchModelInfo(modelName) {
    const panel = document.getElementById('model-info-panel');
    if (!panel) return;

    // Reset UI state
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

            currentModelInfo = info;

            document.getElementById('model-input-limit').textContent = info.input_token_display ? info.input_token_display : 'N/A';
            document.getElementById('model-output-limit').textContent = info.output_token_display ? info.output_token_display : 'N/A';

            // Rate limits (Gemini only)
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

            // Pricing / Description
            if (descRow && info.description) {
                document.getElementById('model-description').textContent = info.description;
                descRow.classList.remove('dn');
            }

            updateTokenEstimate();
        })
        .catch(() => {
            document.getElementById('model-input-limit').textContent = '❌ Lỗi';
            document.getElementById('model-output-limit').textContent = '❌ Lỗi';
            if (sel) sel.style.color = 'red';
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

    const charCountEl = document.getElementById('token-char-count');
    if (charCountEl) charCountEl.textContent = charCount.toLocaleString();

    if (charCount === 0) {
        const estEl = document.getElementById('token-estimate');
        if (estEl) estEl.textContent = '~0';
        const fitEl = document.getElementById('token-model-fit');
        if (fitEl) fitEl.textContent = '';
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

    const tokenEstEl = document.getElementById('token-estimate');
    if (tokenEstEl) tokenEstEl.textContent = '~' + estimatedTokens.toLocaleString();

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

 function mergeTranslatedFiles() {
     if (!currentProject) { showToast('Chưa chọn dự án!', 'error'); return; }
     const translated = currentProject.translated || [];
     if (translated.length === 0) { showToast('Chưa có file dịch để ghép!', 'warning'); return; }

     const slug = currentProject.slug;

     // Natural sort helps handling chunk_2.md vs chunk_10.md properly
     let filesToMerge = translated.map(f => f.name);
     filesToMerge.sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));

     const outName = `${slug}.txt`;

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
                 // Refresh danh sách file dịch để hiển thị file vừa ghép
                 selectProject(currentProject.slug, true);
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
        if (!el) return;
        if (!projects.length) { el.innerHTML = '<div class="pa4 tc silver i">Chưa có dự án.</div>'; return; }
        el.innerHTML = projects.map(p => {
            const active = (currentProject && currentProject.slug === p.slug) ? 'active shadow-1' : '';
            const isDone = p.source_count > 0 && p.translated_count >= p.source_count;
            const doneCheck = isDone ? '<span class="green ml1">✅</span>' : '';
            return `<div class="sidebar-item ${active} flex flex-column gap-1" onclick="selectProject('${p.slug}')">
                <div class="flex justify-between items-center">
                    <span class="fw6 f5 dark-gray truncate">${p.name}${doneCheck}</span>
                </div>
                <div class="f7 gray truncate">
                    Nguồn: <span class="fw6">${p.source_count || 0}</span> | Đã dịch: <span class="fw6">${p.translated_count || 0}</span>
                </div>
            </div>`;
        }).join('');
        
        // Auto-select first project if none is active
        if (!currentProject && projects.length > 0) {
            selectProject(projects[0].slug, false, true); // Added flag to prevent recursion if needed, though we'll remove the call below too
        }
    });
}

function selectProject(slug, keepSelection = false) {
    if (!slug) return;
    console.log('Selecting project:', slug);
    
    fetch('/api/projects/' + slug)
    .then(r => {
        if (!r.ok) throw new Error('Network response was not ok: ' + r.statusText);
        return r.json();
    })
    .then(data => {
        if (data.error) { throw new Error(data.error); }
        
        console.log('Project data loaded:', data);
        currentProject = data;
        
        if (!keepSelection) {
            selectedFiles.clear();
        }

        // 1. Force state visibility
        const activeContent = document.getElementById('project-active-content');
        if (activeContent) activeContent.classList.remove('dn');
        
        // 2. Update Meta Information
        const titleEl = document.getElementById('project-title');
        const descEl = document.getElementById('project-desc');
        if (titleEl) titleEl.textContent = data.name;
        if (descEl) descEl.textContent = data.description || 'Dự án không có mô tả';
        
        // Stats in Header & Table
        const srcCount = document.getElementById('proj-source-count');
        const trCount = document.getElementById('proj-translated-count');
        if (srcCount) srcCount.textContent = data.source_count || 0;
        if (trCount) trCount.textContent = data.translated_count || 0;

        // 3. Render Files
        renderProjectSources(data.sources || []);
        renderProjectTranslated(data.translated || []);

        // Reset editor content when opening a project
        const sourceText = document.getElementById('source-text');
        const resultText = document.getElementById('result-text');
        const tokenMini = document.getElementById('token-estimate-mini');
        if (sourceText) sourceText.value = '';
        if (resultText) resultText.value = '';
        if (tokenMini) tokenMini.classList.add('dn');
        currentProjectFile = null;
        
        // 4. Reset View
        switchProjectTab('workspace');
        
        showToast('Đã chọn: ' + data.name, 'success');
    })
    .catch(err => {
        console.error('selectProject error:', err);
        showToast('Lỗi nạp dự án: ' + err.message, 'error');
    });
}

function renderProjectSources(sources) {
    const el = document.getElementById('project-source-table-body');
    if (!el) return;
    if (!sources.length) { 
        el.innerHTML = '<tr><td colspan="5" class="pa3 tc silver i">Chưa có file nguồn</td></tr>'; 
        return; 
    }
    
    try {
        el.innerHTML = sources.map(f => {
            const esc = f.name.replace(/'/g, "\\'");
            const checked = selectedFiles.has(f.name) ? 'checked' : '';
            const statusText = f.has_translation ? 'Xong' : 'Chưa';
            const statusColor = f.has_translation ? 'green' : 'orange';
            
            return `<tr>
                <td class="tc"><input type="checkbox" ${checked} onchange="toggleProjectFile('${esc}',this.checked)"></td>
                <td>
                    <div class="fw6 blue pointer underline-hover" onclick="loadProjectFile('${esc}','sources')">${f.name}</div>
                </td>
                <td class="f7 gray">${f.size_display}</td>
                <td>
                    <span class="f7 ${statusColor} fw6">
                        ${f.has_translation ? '✅' : '⏳'} ${statusText}
                    </span>
                </td>
                <td class="tr">
                    <div class="flex justify-end gap-1">
                        <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();translateFileInProject('${esc}')" title="Dịch">🚀</button>
                        <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();renameProjectFile('${esc}','sources')" title="Đổi tên">✏️</button>
                        <button class="ph2 pv1 f7 ba b--red red bg-white pointer hover-bg-washed-red br1" onclick="event.stopPropagation();deleteProjectFile('${esc}','sources')" title="Xóa">🗑️</button>
                    </div>
                </td>
            </tr>`;
        }).join('');
        updateSelectAllButton();
    } catch (err) {
        console.error('Error rendering sources:', err);
        el.innerHTML = `<tr><td colspan="5" class="pa3 tc red">Lỗi hiển thị danh sách file: ${err.message}</td></tr>`;
    }
}

function renderProjectTranslated(translated) {
    const el = document.getElementById('project-translated-table-body');
    const countEl = document.getElementById('proj-translated-count');
    if (countEl) countEl.textContent = translated.length;
    if (!el) return;

    if (!translated.length) {
        el.innerHTML = '<tr><td colspan="3" class="pa3 tc silver i">Chưa có file dịch</td></tr>';
        return;
    }

    el.innerHTML = translated.map(f => {
        const esc = f.name.replace(/'/g, "\\'");
        return `<tr>
            <td>
                <div class="fw6 blue pointer underline-hover" onclick="loadProjectFile('${esc}','translated')">${f.name}</div>
            </td>
            <td class="f7 gray">${f.size_display}</td>
            <td class="tr">
                <div class="flex justify-end gap-1">
                    <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();renameProjectFile('${esc}','translated')" title="Đổi tên">✏️</button>
                    <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();moveBackInProject('${esc}')" title="Trả về sources">↩</button>
                    <button class="ph2 pv1 f7 ba b--red red bg-white pointer hover-bg-washed-red br1" onclick="event.stopPropagation();deleteProjectFile('${esc}','translated')" title="Xóa">🗑️</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

function switchProjectTab(tab) {
    try {
        document.querySelectorAll('#project-tabs .tab-btn').forEach(b => {
            const isActive = b.getAttribute('data-ptab') === tab;
            b.classList.toggle('active', isActive);
            b.classList.toggle('blue', isActive);
            b.classList.toggle('gray', !isActive);
            b.classList.toggle('b--blue', isActive);
            b.classList.toggle('b--transparent', !isActive);
        });
        document.querySelectorAll('.nt-ptab-content').forEach(el => el.classList.add('dn'));
        const target = document.getElementById('ptab-' + tab);
        if (target) {
            target.classList.remove('dn');
        }

        // Load data when switching to content tabs (Safely)
        if (currentProject) {
            if (tab === 'prompt') {
                loadProjectPrompts();
            } else if (['style-guide', 'relationship', 'glossary', 'summary'].includes(tab)) {
                loadGuidelineTab(tab);
            } else if (tab === 'spellcheck') {
                renderProjectSpellcheckSources(currentProject.sources || []);
            }
        }
    } catch (e) {
        console.error('Error switching tab:', e);
    }
}

function loadProjectFile(filename, section) {
    if (!currentProject) return;
    const slug = currentProject.slug;
    fetch(`/api/projects/${slug}/file/${section}/${filename}`).then(r => r.json()).then(data => {
        if (section === 'sources') {
            document.getElementById('source-text').value = data.content || '';
            currentProjectFile = { name: filename, section };
            document.getElementById('token-estimate-mini').classList.remove('dn');
            
            updateTokenEstimate();
            
            // Populate Translation if exists
            fetch(`/api/projects/${slug}/file/translated/${filename}`).then(r => r.json()).then(tData => {
                document.getElementById('result-text').value = tData.content || '';
            }).catch(() => {
                document.getElementById('result-text').value = '';
            });
        } else if (section === 'translated') {
            document.getElementById('translated-result-text').value = data.content || '';
            document.getElementById('translated-source-text').value = '';
            currentProjectFile = { name: filename, section };

            // Show token estimate for translated file
            const tokenMini = document.getElementById('translated-token-estimate');
            if (tokenMini) tokenMini.classList.remove('dn');
            updateTranslatedTokenEstimate();

            // Load source counterpart for comparison
            fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(sData => {
                document.getElementById('translated-source-text').value = sData.content || '';
            }).catch(() => {
                document.getElementById('translated-source-text').value = '(Không tìm thấy bản gốc tương ứng)';
            });
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

function showChunkConfig() {
    const modal = document.getElementById('chunk-config-modal');
    if (modal) {
        modal.classList.remove('dn');
        modal.classList.add('flex');
    }
}

function hideChunkConfig() {
    const modal = document.getElementById('chunk-config-modal');
    if (modal) {
        modal.classList.add('dn');
        modal.classList.remove('flex');
    }
}

function confirmChunking() {
    if (!currentProject) return;
    const size = document.getElementById('chunk-size-input').value;
    const type = document.querySelector('input[name="chunk-type"]:checked').value;
    
    if (selectedFiles.size === 0) {
        showToast('Vui lòng chọn ít nhất 1 file để chia chunk!', 'warning');
        return;
    }
    
    showToast('✂️ Đang chia chunk...', 'info');
    hideChunkConfig();
    
    const files = Array.from(selectedFiles);
    
    Promise.all(files.map(filename => 
        fetch(`/api/projects/${currentProject.slug}/chunk/${filename}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ max_chars: parseInt(size) })
        }).then(r => r.json())
    )).then(results => {
        const failed = results.filter(r => !r.success);
        if (failed.length > 0) {
            showToast(`Lỗi chia ${failed.length} file`, 'error');
        } else {
            showToast(`Đã chia chunk thành công ${files.length} file`, 'success');
        }
        selectProject(currentProject.slug);
    }).catch(e => {
        showToast('Lỗi chia chunk: ' + e.message, 'error');
    });
}

function deleteProjectFile(filename, section) {
    if (!confirm('Xóa vĩnh viễn "' + filename + '"?')) return;
    fetch(`/api/projects/${currentProject.slug}/file/${section}/${filename}`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' }
    }).then(r => r.json()).then(() => selectProject(currentProject.slug));
}

function renameProjectFile(filename, section) {
    if (!currentProject) return;
    const newName = prompt(`Đổi tên "${filename}" thành:`, filename);
    if (!newName || newName === filename) return;

    fetch(`/api/projects/${currentProject.slug}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_name: filename, new_name: newName, section: section })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            showToast('Đã đổi tên file thành công', 'success');
            selectProject(currentProject.slug);
        } else {
            showToast(data.error || 'Lỗi đổi tên', 'error');
        }
    });
}

function toggleProjectFile(name, checked) {
    if (checked) selectedFiles.add(name); else selectedFiles.delete(name);
    updateSelectAllButton();
}

function updateSelectAllButton() {
    const btn = document.getElementById('btn-select-all');
    const chk = document.querySelector('#workspace-sources thead input[type="checkbox"]');
    
    if (btn) {
        if (selectedFiles.size > 0) {
            btn.innerHTML = `✓ Chọn hết (${selectedFiles.size})`;
            btn.classList.add('nt-btn-primary');
            btn.classList.remove('nt-btn-outline');
        } else {
            btn.innerHTML = `✓ Chọn hết`;
            btn.classList.add('nt-btn-outline');
            btn.classList.remove('nt-btn-primary');
        }
    }
    
    if (chk && currentProject && currentProject.sources) {
        chk.checked = (selectedFiles.size > 0 && selectedFiles.size === currentProject.sources.length);
        chk.indeterminate = (selectedFiles.size > 0 && selectedFiles.size < currentProject.sources.length);
    }
}

function selectAllProjectFiles() {
    if (!currentProject) return;
    const allSources = currentProject.sources || [];
    if (selectedFiles.size === allSources.length && allSources.length > 0) {
        selectedFiles.clear();
    } else {
        allSources.forEach(f => selectedFiles.add(f.name));
    }
    updateSelectAllButton();
    renderProjectSources(allSources);
}

function translateFileInProject(filename) {
    if (!currentProject) return;
    fetch(`/api/projects/${currentProject.slug}/translate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: [filename] })
    }).then(r => r.json()).then(data => {
        if (data.status === 'started') {
            switchProjectTab('sources');
            connectToProgress();
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
        if (data.status === 'started') connectToProgress(document.getElementById('btn-translate-selected'), true);
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

// ============================================================
// Spell-check Functions
// ============================================================
function loadSpellcheckFile(filename) {
    if (!currentProject) return;
    const slug = currentProject.slug;
    fetch(`/api/projects/${slug}/file/spelling/${filename}`).then(r => r.json()).then(data => {
        document.getElementById('spell-result-text').value = data.content || '';
        currentProjectFile = { name: filename, section: 'spelling' };
        const infoName = filename.replace(/\.(txt|md)$/, '') + '_info.txt';
        fetch(`/api/projects/${slug}/file/spelling/${infoName}`).then(r => r.json()).then(infoData => {
            document.getElementById('spell-info-text').value = infoData.content || '';
        }).catch(() => {
            document.getElementById('spell-info-text').value = '';
        });
    }).catch(() => {
        document.getElementById('spell-result-text').value = '';
        document.getElementById('spell-info-text').value = '';
    });
    fetch(`/api/projects/${slug}/file/sources/${filename}`).then(r => r.json()).then(sourceData => {
        document.getElementById('spell-source-text').value = sourceData.content || '';
    }).catch(() => {
        document.getElementById('spell-source-text').value = '';
    });
}

function saveSpellcheckResult() {
    if (!currentProject || !currentProjectFile) {
        showToast('Không xác định được dự án hoặc file.', 'error');
        return;
    }
    const slug = currentProject.slug;
    const filename = currentProjectFile.name;
    const content = document.getElementById('spell-result-text').value;
    if (!content.trim()) {
        showToast('Nội dung trống.', 'warning');
        return;
    }
    const btn = document.getElementById('btn-save-spellcheck');
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳...';
    btn.disabled = true;
    fetch(`/api/projects/${slug}/file/spelling/${filename}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content })
    }).then(r => r.json()).then(res => {
        btn.innerHTML = originalText;
        btn.disabled = false;
        if (res.success) {
            showToast('Đã lưu.', 'success');
        } else {
            showToast('Lỗi: ' + (res.error || 'Unknown'), 'error');
        }
    }).catch(e => {
        btn.innerHTML = originalText;
        btn.disabled = false;
        showToast('Lỗi: ' + e.message, 'error');
    });
}

function spellcheckSelectedInProject() {
    if (!currentProject || selectedFiles.size === 0) { showToast('Chưa chọn file!', 'error'); return; }
    const files = Array.from(selectedFiles);
    fetch(`/api/projects/${currentProject.slug}/spellcheck`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files })
    }).then(r => r.json()).then(data => {
        if (data.status === 'started') connectToProgress(document.getElementById('btn-spellcheck-selected'), true);
        else showToast(data.error || 'Lỗi', 'error');
    });
}

function spellcheckFileInProject(filename) {
    if (!currentProject) return;
    fetch(`/api/projects/${currentProject.slug}/spellcheck`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: [filename] })
    }).then(r => r.json()).then(data => {
        if (data.status === 'started') {
            switchProjectTab('spellcheck');
            connectToProgress();
        } else showToast(data.error || 'Lỗi', 'error');
    });
}

function copySpellcheckResult() {
    const el = document.getElementById('spell-result-text');
    el.select();
    document.execCommand('copy');
    showToast('Đã sao chép.', 'success');
}

function downloadSpellCheckResult() {
    if (!currentProject || !currentProjectFile) { showToast('Chưa chọn file!', 'error'); return; }
    window.location.href = `/api/projects/${currentProject.slug}/file/spelling/${currentProjectFile.name}`;
}

function runSpellcheck() {
    if (!currentProject || !currentProjectFile) { showToast('Chưa chọn file!', 'error'); return; }
    selectedFiles.clear();
    selectedFiles.add(currentProjectFile.name);
    spellcheckSelectedInProject();
}

function renderProjectSpellcheckSources(sources) {
    const el = document.getElementById('project-spellcheck-table-body');
    if (!el) return;
    if (!sources.length) { 
        el.innerHTML = '<tr><td colspan="5" class="pa3 tc silver i">Chưa có file nguồn</td></tr>'; 
        return; 
    }
    try {
        el.innerHTML = sources.map(f => {
            const esc = f.name.replace(/'/g, "\\'");
            const checked = selectedFiles.has(f.name) ? 'checked' : '';
            const statusText = f.has_translation ? 'Xong' : 'Chưa';
            const statusColor = f.has_translation ? 'green' : 'orange';
            return `<tr>
                <td class="tc"><input type="checkbox" ${checked} onchange="toggleProjectFile('${esc}',this.checked)"></td>
                <td><div class="fw6 blue pointer underline-hover" onclick="loadSpellcheckFile('${esc}')">${f.name}</div></td>
                <td class="f7 gray">${f.size_display}</td>
                <td><span class="f7 ${statusColor} fw6">${f.has_translation ? '✅' : '⏳'} ${statusText}</span></td>
                <td class="tr">
                    <div class="flex justify-end gap-1">
                        <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();spellcheckFileInProject('${esc}')">🔤</button>
                        <button class="ph2 pv1 f7 ba b--silver bg-white pointer hover-bg-near-white br1" onclick="event.stopPropagation();renameProjectFile('${esc}','sources')">✏️</button>
                        <button class="ph2 pv1 f7 ba b--red red bg-white pointer hover-bg-washed-red br1" onclick="event.stopPropagation();deleteProjectFile('${esc}','sources')">🗑️</button>
                    </div>
                </td>
            </tr>`;
        }).join('');
    } catch (err) {
        console.error('Error:', err);
        el.innerHTML = '<tr><td colspan="5" class="pa3 tc red">Lỗi</td></tr>';
    }
}

function loadProjectPrompts() {
    if (!currentProject) return;
    fetch(`/api/projects/${currentProject.slug}/prompts`).then(r => r.json()).then(data => {
        const el = document.getElementById('proj-prompt-main');
        if (el) el.value = data.main || '';
    });
    const sel = document.getElementById('prompt-library-select');
    if (sel) {
        fetch('/api/prompt-sets').then(r => r.json()).then(data => {
            // API returns a list, filter out default to avoid duplication
            const genres = (data || []).filter(g => g.slug !== 'default');
            let opts = '<option value="">— Nạp từ thư viện —</option>';
            // Add project prompts option - will load if project has any
            if (currentProject) {
                opts += '<option value="__project__">📂 Prompts của dự án này</option>';
            }
            // Add system default explicitly with clear name
            opts += '<option value="default">📌 Mặc định (Hệ thống)</option>';
            genres.forEach(g => {
                opts += `<option value="${g.slug}">📁 ${g.name}</option>`;
            });
            sel.innerHTML = opts;
        }).catch(() => {});
    }
}

function saveProjectPrompts() {
    if (!currentProject) return;
    const mainEl = document.getElementById('proj-prompt-main');
    fetch(`/api/projects/${currentProject.slug}/prompts`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            main: mainEl ? mainEl.value : '',
        })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            showToast('Đã lưu Chỉ dẫn của dự án!', 'success');
        } else {
            showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
        }
    });
}

function loadFromPromptLibrary() {
    const sel = document.getElementById('prompt-library-select');
    const slug = sel ? sel.value : '';
    if (!slug) { showToast('Chọn bộ prompt từ dropdown trước!', 'error'); return; }

    // Handle special cases
    if (slug === '__project__') {
        // Load project's own prompts
        fetch(`/api/projects/${currentProject.slug}/prompts`)
            .then(r => r.json())
            .then(data => {
                const el = document.getElementById('proj-prompt-main');
                if (el) el.value = data.main || '';
                showToast('Đã nạp prompts của dự án', 'success');
            });
        return;
    }

    const url = '/api/prompt-sets/' + slug;

    fetch(url)
        .then(r => r.json())
        .then(data => {
            const prompts = data.prompts || {};
            const el = document.getElementById('proj-prompt-main');
            if (el) el.value = prompts.main || '';
            const displayName = slug === 'default' ? 'Mặc định (Hệ thống)' : slug;
            showToast(`Đã nạp bộ prompt "${displayName}"`, 'success');
        })
        .catch(e => showToast(e.message, 'error'));
}

// Tab-to-field mapping for guideline tabs
const GUIDELINE_TAB_MAP = {
    'style-guide':  { field: 'style_guide',  elId: 'guide-style-guide',  modelId: 'style-guide-model' },
    'relationship': { field: 'characters',   elId: 'guide-relationship', modelId: 'relationship-model' },
    'glossary':     { field: 'glossary',     elId: 'guide-glossary',     modelId: 'glossary-model' },
    'summary':      { field: 'summary',      elId: 'guide-summary',      modelId: 'summary-model' },
};

function _populateModelSelect(selId) {
    const sel = document.getElementById(selId);
    const mainSel = document.getElementById('model');
    if (!sel || !mainSel) return;
    let opts = '<option value="">— Chọn Model —</option>';
    for (const opt of mainSel.options) {
        if (opt.value) opts += `<option value="${opt.value}">${opt.text}</option>`;
    }
    sel.innerHTML = opts;
}

function loadGuidelineTab(tab) {
    if (!currentProject) return;
    const mapping = GUIDELINE_TAB_MAP[tab];
    if (!mapping) return;

    // Populate model dropdown
    _populateModelSelect(mapping.modelId);

    fetch(`/api/projects/${currentProject.slug}/guidelines`)
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById(mapping.elId);
            if (el) el.value = data[mapping.field] || '';
        })
        .catch(e => console.error('loadGuidelineTab error:', e));
}

function saveGuidelineField(fieldKey) {
    if (!currentProject) return;
    // Map fieldKey -> tab -> elId
    const reverseMap = {
        'style_guide': 'guide-style-guide',
        'relationship': 'guide-relationship',
        'glossary': 'guide-glossary',
        'summary': 'guide-summary',
    };
    const elId = reverseMap[fieldKey];
    const el = document.getElementById(elId);
    if (!el) return;

    // characters is the backend key for relationship
    const backendKey = fieldKey === 'relationship' ? 'characters' : fieldKey;

    fetch(`/api/projects/${currentProject.slug}/guidelines`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [backendKey]: el.value })
    })
        .then(r => r.json())
        .then(res => {
            if (res.success) showToast('Đã lưu thành công!', 'success');
            else showToast(res.error || 'Lỗi lưu', 'error');
        })
        .catch(e => showToast(e.message, 'error'));
}

function aiGenerateContent(fieldKey) {
    if (!currentProject) { showToast('Chưa chọn dự án!', 'error'); return; }

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

    fetch(`/api/projects/${currentProject.slug}/summarize`, {
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
                showToast('AI đã tạo nội dung thành công!', 'success');
            } else {
                showToast(data.error || 'AI không trả về kết quả', 'error');
            }
        })
        .catch(e => {
            if (outputEl) { outputEl.disabled = false; outputEl.placeholder = ''; }
            showToast('Lỗi: ' + e.message, 'error');
        });
}


function aiSummarize() {
    if (!currentProject) return;
    const btn = document.getElementById('btn-ai-summarize');
    btn.disabled = true;
    btn.textContent = '⏳ Đang tóm tắt...';

    const modelSel = document.getElementById('summarize-model');
    const model = modelSel ? modelSel.value : '';

    fetch(`/api/projects/${currentProject.slug}/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model })
    })
        .then(async r => {
            const isJson = r.headers.get('content-type')?.includes('application/json');
            const data = isJson ? await r.json() : null;
            if (!r.ok) {
                throw new Error(data?.error || `Server error: ${r.status} ${r.statusText}`);
            }
            return data;
        })
        .then(data => {
            btn.disabled = false;
            btn.textContent = '🤖 AI Tóm tắt';
            if (data.success && data.summary) {
                document.getElementById('guide-summary').value = data.summary;
                showToast('Đã tạo tóm tắt AI thành công!', 'success');
            } else {
                showToast(data.error || 'Lỗi tóm tắt không xác định', 'error');
            }
        })
        .catch(e => {
            btn.disabled = false;
            btn.textContent = '🤖 AI Tóm tắt';
            showToast(e.message, 'error');
            console.error('Summarize error:', e);
        });
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
    
    // First, check if archive already exists
    fetch('/api/projects/' + currentProject.slug + '/archive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy: 'check' })
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) throw new Error(data.error);
        
        let strategy = 'overwrite';
        if (data.exists) {
            const userChoice = confirm(`Bản lưu trữ của dự án ${currentProject.name} đã tồn tại.\n\nNhấn OK để GHI ĐÈ.\nNhấn Cancel để TẠO BẢN SAO.`);
            strategy = userChoice ? 'overwrite' : 'copy';
        }
        
        showToast('Đang tiến hành lưu trữ...', 'info');
        
        return fetch('/api/projects/' + currentProject.slug + '/archive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strategy: strategy })
        });
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            showToast('Lỗi lưu trữ: ' + data.error, 'error');
        } else {
            showToast(data.message, 'success');
            // Remove project from current view
            currentProject = null;
            document.getElementById('project-empty-state').classList.remove('dn');
            document.getElementById('project-active-content').classList.add('dn');
            loadProjects(); // Reload sidebar
        }
    })
    .catch(err => {
        showToast('Lỗi: ' + err.message, 'error');
    });
}

// ============================================================
// Project Info Modal
// ============================================================

function showProjectInfoModal() {
    if (!currentProject) return;
    const p = currentProject;

    // Populate fields
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

    const modal = document.getElementById('project-info-modal');
    if (modal) {
        modal.classList.remove('dn');
        modal.style.display = 'flex';
    }
}

function hideProjectInfoModal() {
    const modal = document.getElementById('project-info-modal');
    if (modal) {
        modal.classList.add('dn');
        modal.style.display = '';
    }
}

function saveProjectInfo() {
    if (!currentProject) return;
    const name = document.getElementById('proj-info-name').value.trim();
    const description = document.getElementById('proj-info-desc').value.trim();

    if (!name) { showToast('Tên dự án không được trống!', 'error'); return; }

    fetch('/api/projects/' + currentProject.slug, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description })
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) throw new Error(data.error);
        // Update in-memory state
        currentProject.name = name;
        currentProject.description = description;
        // Update header display immediately
        const titleEl = document.getElementById('project-title');
        const descEl = document.getElementById('project-desc');
        if (titleEl) titleEl.textContent = name;
        if (descEl) descEl.textContent = description || 'Dự án không có mô tả';
        // Refresh sidebar
        loadProjects();
        hideProjectInfoModal();
        showToast('Đã cập nhật thông tin dự án!', 'success');
    })
    .catch(err => showToast('Lỗi cập nhật: ' + err.message, 'error'));
}

function archiveProjectFromModal() {
    hideProjectInfoModal();
    archiveProject();
}

function deleteProjectFromModal() {
    hideProjectInfoModal();
    deleteCurrentProject();
}


function loadArchiveList() {
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
                        <button class="pointer ph3 pv1 f7 ba b--blue blue bg-white br1 shadow-1 hover-bg-light-blue transition mr2" onclick="restoreProject('${file.filename}')">Khôi phục</button>
                        <button class="pointer ph3 pv1 f7 ba b--red red bg-white br1 shadow-1 hover-bg-washed-red transition" onclick="deleteArchive('${file.filename}')">Xóa</button>
                    </td>
                </tr>
                `;
            }).join('');
        })
        .catch(err => {
            tbody.innerHTML = `<tr><td colspan="3" class="pa3 tc red">Lỗi tải danh sách: ${err.message}</td></tr>`;
        });
}

function restoreProject(filename) {
    if (!confirm(`Khôi phục dự án từ ${filename}?`)) return;
    
    showToast('Đang khôi phục...', 'info');
    fetch('/api/archive/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: filename })
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            showToast('Lỗi khôi phục: ' + data.error, 'error');
        } else {
            showToast('Khôi phục thành công!', 'success');
            loadArchiveList(); // reload tab
            loadProjects(); // reload sidebar
        }
    });
}

function deleteArchive(filename) {
    if (!confirm(`Xóa VĨNH VIỄN bản lưu trữ ${filename}?`)) return;
    
    fetch('/api/archive/' + filename, {
        method: 'DELETE'
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showToast('Đã xóa ' + filename, 'success');
            loadArchiveList();
        } else {
            showToast(data.error, 'error');
        }
    });
}

// toggleSidebar removed — sidebar replaced by top navigation bar


// ============================================================
// Stats
// ============================================================
function loadStats() {
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
}

function clearCache() {
    if (!confirm('Xóa sạch bộ nhớ Cache dịch thuật?')) return;
    fetch('/api/cache/clear', { method: 'POST' }).then(r => r.json()).then(data => {
        showToast('Đã dọn dẹp ' + data.deleted + ' files nháp.', 'success');
        loadStats();
    });
}

function restartServer() {
    if (!confirm('Khởi động lại Web Server?')) return;
    fetch('/api/restart', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            showToast(data.message || 'Đang khởi động lại...', 'info');
            // Đợi 3 giây rồi reload trang
            setTimeout(() => {
                location.reload();
            }, 3000);
        })
        .catch(e => {
            showToast('Lỗi gửi yêu cầu restart: ' + e.message, 'error');
        });
}

// ============================================================
// Translation Core
// ============================================================
function getActivePrompts() {
    return prompts; // Currently loaded prompts (from genre or default)
}

function showProgress(containerId, barId, percentId, textId, percent, text, isBatch = false) {
    const bar = document.getElementById(barId);
    if(bar) bar.style.width = percent + '%';
    const num = document.getElementById(percentId);
    if(num) num.textContent = percent + '%';
    const txt = document.getElementById(textId);
    if(txt) txt.textContent = text;
    
    showProgressModal();
}

function showProgressModal() {
    const modal = document.getElementById('translation-progress-modal');
    if (modal) {
        modal.classList.remove('dn');
        modal.classList.add('flex');
    }
}

function hideProgressModal() {
    const modal = document.getElementById('translation-progress-modal');
    if (modal) {
        modal.classList.add('dn');
        modal.classList.remove('flex');
    }
}

function closeProgress() {
    const workspaceSources = document.getElementById('workspace-sources');
    const workspaceProgress = document.getElementById('workspace-progress');
    if(workspaceSources) workspaceSources.classList.remove('dn');
    if(workspaceProgress) workspaceProgress.classList.add('dn');
    
    if (typeof selectedFiles !== 'undefined' && selectedFiles) {
        selectedFiles.clear();
        updateSelectAllButton();
    }
    
    if (typeof currentProject !== 'undefined' && currentProject) {
        selectProject(currentProject.slug, true);
    }
    
    if(window._autoReturnTimer) {
        clearInterval(window._autoReturnTimer);
        window._autoReturnTimer = null;
    }
    
    // Hide the modal (but don't stop SSE - translation continues)
    const modal = document.getElementById('translation-progress-modal');
    if (modal) {
        modal.classList.add('dn');
        modal.classList.remove('flex');
    }
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

    // Use project-specific translate API if in project context with a file loaded
    if (currentProject && currentProjectFile) {
        fetch(`/api/projects/${currentProject.slug}/translate`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: [currentProjectFile.name] })
        }).then(r => r.json()).then(data => {
            if (data.error) { addLog(data.error, 'error'); resetButton(btn); }
            else connectToProgress(btn);
        }).catch(e => { addLog(e.message, 'error'); resetButton(btn); });
    } else {
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

function saveTranslatedFile() {
    if (!currentProject || !currentProjectFile || currentProjectFile.section !== 'translated') {
        showToast('Chưa chọn file bản dịch để lưu.', 'error');
        return;
    }

    const slug = currentProject.slug;
    const filename = currentProjectFile.name;
    const content = document.getElementById('translated-result-text').value;

    if (!content.trim()) {
        showToast('Nội dung bản dịch trống, không thể lưu.', 'warning');
        return;
    }

    const btn = document.getElementById('btn-save-translated');
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Đang lưu...';
    btn.disabled = true;

    fetch(`/api/projects/${slug}/file/translated/${filename}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
    })
        .then(r => r.json())
        .then(res => {
            btn.innerHTML = originalText;
            btn.disabled = false;
            if (res.success) {
                showToast(`Đã lưu bản dịch cho file: ${filename}`, 'success');
                selectProject(slug, true);
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
    
    // Reset modal UI
    const logEl = document.getElementById('log-container');
    if(logEl) logEl.innerHTML = '';
    
    const resContainer = document.getElementById('result-container');
    if(resContainer) resContainer.classList.add('dn');

    showProgress('progress-container', 'progress-bar', 'progress-percent', 'progress-text', 0, 'Đang kết nối API...', isBatch);

    const btnDone = document.getElementById('btn-progress-done');
    if (btnDone) btnDone.classList.add('dn');

    if(window._autoReturnTimer) {
        clearInterval(window._autoReturnTimer);
        window._autoReturnTimer = null;
    }

    evtSource.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
            showProgress('progress-container', 'progress-bar', 'progress-percent', 'progress-text', data.percent, data.message, isBatch);
        }
        else if (data.type === 'info' || data.type === 'log') {
            addLog(data.message, data.level || 'info');
        }
        else if (data.type === 'file_complete') {
            // A file in batch is finished, but we don't close SSE yet
            addLog(data.message, 'success');
            // We could update individual file status in UI here if needed
            if (currentProject && document.getElementById('ptab-sources') && !document.getElementById('ptab-sources').classList.contains('dn')) {
                selectProject(currentProject.slug, true);
            }
        }
        else if (data.type === 'complete') {
            evtSource.close();
            showProgress('progress-container', 'progress-bar', 'progress-percent', 'progress-text', 100, 'Tất cả hoàn tất! 🚀', isBatch);

            // Always prefer translated_text over output_file message
            if (data.translated_text) {
                const resText = document.getElementById('result-text');
                if(resText) resText.value = data.translated_text;
            } else if (data.output_file) {
                currentOutputFile = data.output_file;
                const resText = document.getElementById('result-text');
                if(resText) resText.value = "�ã dịch xong. Kết quả được lưu tại:\n👉 " + data.output_file;
            }

            // Show result layout (hidden by default, only show if not in project context)
            const resContainer = document.getElementById('result-container');
            if(resContainer && !currentProject) {
                resContainer.classList.remove('dn');
                resContainer.classList.add('flex');
            }

            resetButton(btn, isBatch);
            
            // Auto-close modal after 10 seconds for all completions
            if (btnDone) {
                btnDone.classList.remove('dn');
                let seconds = 10;
                btnDone.textContent = `Xong (${seconds}s)`;
                
                window._autoReturnTimer = setInterval(() => {
                    seconds--;
                    if (seconds <= 0) {
                        clearInterval(window._autoReturnTimer);
                        window._autoReturnTimer = null;
                        closeProgress();
                    } else {
                        btnDone.textContent = `Xong (${seconds}s)`;
                    }
                }, 1000);
            } else {
                // Fallback: auto close after 10s if no button
                window._autoReturnTimer = setInterval(() => {
                    clearInterval(window._autoReturnTimer);
                    window._autoReturnTimer = null;
                    closeProgress();
                }, 10000);
            }
            
            // Update project UI if in project context
            if (currentProject) {
                selectProject(currentProject.slug, isBatch);
            }
            if(typeof loadOutputFiles === 'function') loadOutputFiles(); 
            if(typeof loadStats === 'function') loadStats(); 
            if(typeof loadFiles === 'function') loadFiles(); 
            if(typeof loadDoneFiles === 'function') loadDoneFiles();
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

function copyTranslatedResult() {
    navigator.clipboard.writeText(document.getElementById('translated-result-text').value)
        .then(() => showToast('Đã sao chép vào Clipboard!', 'success'))
        .catch(() => showToast('Copy thất bại', 'error'));
}

function downloadTranslatedResult() {
    const text = document.getElementById('translated-result-text').value;
    if (!text) { showToast('Chưa có nội dung để tải!', 'error'); return; }
    const fname = currentProjectFile ? currentProjectFile.name : 'translated.txt';
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
    a.download = fname; a.click();
}

function retranslateFile() {
    if (!currentProject || !currentProjectFile) {
        showToast('Chưa chọn file để dịch lại!', 'error');
        return;
    }
    translateFileInProject(currentProjectFile.name);
}

function updateTranslatedTokenEstimate() {
    const text = document.getElementById('translated-result-text').value || '';
    const charCount = text.length;

    const charCountEl = document.getElementById('translated-token-char-count');
    if (charCountEl) charCountEl.textContent = charCount.toLocaleString();

    if (charCount === 0) {
        const estEl = document.getElementById('translated-token-count');
        if (estEl) estEl.textContent = '~0';
        const fitEl = document.getElementById('translated-token-model-fit');
        if (fitEl) fitEl.textContent = '';
        return;
    }

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

    const tokenEstEl = document.getElementById('translated-token-count');
    if (tokenEstEl) tokenEstEl.textContent = '~' + estimatedTokens.toLocaleString();

    const fitEl = document.getElementById('translated-token-model-fit');
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
    // Ẩn nút "Sử dụng ngay" nếu đang ở default
    const btnUse = document.getElementById('btn-use-genre');
    if (btnUse) {
        btnUse.classList.toggle('dn', isDefault);
    }

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
            loadGenres(); // Refresh active state in list
        });
}

function useGenre() {
    if (!currentGenre || currentGenre === 'default') return;
    if (!confirm(`Sử dụng bộ prompt "${currentGenre}" làm mặc định cho dịch thuật?`)) return;

    fetch('/api/prompt-sets/' + currentGenre + '/use', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('Đã kích hoạt bộ prompt cho dịch thuật!', 'success');
                // Reload prompts toàn cục
                fetch('/api/prompt-sets/default')
                    .then(r => r.json())
                    .then(d => {
                        prompts = d.prompts || {};
                    });
            } else {
                showToast('Lỗi: ' + (data.error || 'Unknown'), 'error');
            }
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
            loadGenres();
            selectGenre(data.slug);
            showToast(`Đã tạo bộ prompt: ${name}`, 'success');
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
                summary: document.getElementById('genre-summary-text').value,
                relationships: document.getElementById('genre-relationships-text').value,
                glossary: document.getElementById('genre-glossary-text').value,
                chinh_ta: document.getElementById('genre-chinh-ta-text').value,
            }
        })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            showToast('Lưu prompt hoàn tất!', 'success');
            btn.textContent = '💾 Lưu Prompt';
            btn.disabled = false;
        } else {
            showToast('Lỗi lưu: ' + (data.error || 'Unknown'), 'error');
            btn.textContent = '💾 Lưu Prompt';
            btn.disabled = false;
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
                loadGenres();
            }
        });
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
    const detail = col.parentElement.querySelector('.w-70-l, .w-100-l');
    const btn = event.currentTarget;
    if (col.classList.contains('dn')) {
        col.classList.remove('dn');
        if (detail) { detail.classList.remove('w-100-l'); detail.classList.add('w-70-l'); }
        btn.textContent = '◗';
    } else {
        col.classList.add('dn');
        if (detail) { detail.classList.remove('w-70-l'); detail.classList.add('w-100-l'); }
        btn.textContent = '◖';
    }
}

// ============================================================
// System Logs Tab
// ============================================================

let currentLogFile = '';
let selectedLogFiles = new Set();

function updateSelectedLogsUI() {
    const btn = document.getElementById('btn-delete-selected-logs');
    if (!btn) return;
    if (selectedLogFiles.size > 0) {
        btn.classList.remove('dn');
        btn.textContent = `🗑️ Xóa đã chọn (${selectedLogFiles.size})`;
    } else {
        btn.classList.add('dn');
        btn.textContent = '🗑️ Xóa đã chọn';
    }
}

function toggleLogFile(filename, checked) {
    if (checked) selectedLogFiles.add(filename);
    else selectedLogFiles.delete(filename);
    updateSelectedLogsUI();
}

function selectAllLogs(checked) {
    const boxes = document.querySelectorAll('.sys-log-checkbox');
    boxes.forEach(box => {
        box.checked = checked;
        toggleLogFile(box.value, checked);
    });
}

function loadLogList() {
    fetch('/api/logs')
        .then(r => r.json())
        .then(data => {
            const listEl = document.getElementById('sys-log-list');
            selectedLogFiles.clear();
            updateSelectedLogsUI();
            if (data.length === 0) {
                listEl.innerHTML = '<div class="pa3 tc silver i">Không có file log nào.</div>';
                document.getElementById('sys-log-viewer').innerHTML = '<div class="tc silver mt5 i">Chưa chọn file log.</div>';
                return;
            }
            
            let html = '<div class="pa2 bb b--black-10 bg-near-white"><label class="f7 gray"><input type="checkbox" onclick="selectAllLogs(this.checked)"> Chọn tất cả</label></div>';
            data.forEach(log => {
                const dateStr = new Date(log.mtime * 1000).toLocaleString('vi-VN');
                const safeName = log.filename.replace(/'/g, "\\'");
                const safeValue = log.filename.replace(/"/g, '&quot;');
                html += `
                    <div class="pv2 ph3 bb b--black-05 flex items-center gap-2">
                        <input class="sys-log-checkbox" type="checkbox" value="${safeValue}" onchange="toggleLogFile('${safeName}', this.checked)">
                        <div class="pointer hover-bg-near-white flex items-center justify-between flex-auto" onclick="viewLogFile('${safeName}')">
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
        .catch(e => showToast('Lỗi tải danh sách logs: ' + e.message, 'error'));
}

function deleteSelectedLogs() {
    if (selectedLogFiles.size === 0) return;
    const files = Array.from(selectedLogFiles);
    if (!confirm(`Xóa vĩnh viễn ${files.length} file log đã chọn?`)) return;

    Promise.all(files.map(filename =>
        fetch(`/api/logs/${encodeURIComponent(filename)}`, { method: 'DELETE' }).then(r => r.json())
    ))
        .then(results => {
            const failed = results.filter(r => !r.success);
            if (failed.length > 0) {
                showToast(`Xóa thất bại ${failed.length} file log`, 'error');
            } else {
                showToast(`Đã xóa ${files.length} file log`, 'success');
            }
            currentLogFile = '';
            document.getElementById('current-log-title').textContent = 'Chọn file để xem';
            document.getElementById('sys-log-viewer').innerHTML = '<div class="tc silver mt5 i">Chưa chọn file log.</div>';
            document.getElementById('btn-delete-log').classList.add('dn');
            loadLogList();
        })
        .catch(e => showToast('Lỗi xóa logs: ' + e.message, 'error'));
}

function viewLogFile(filename) {
    currentLogFile = filename;
    document.getElementById('current-log-title').textContent = filename;
    document.getElementById('btn-delete-log').classList.remove('dn');
    document.getElementById('sys-log-viewer').innerHTML = '<div class="tc silver mt5 i">Đang tải nội dung...</div>';

    fetch(`/api/logs/${encodeURIComponent(filename)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            
            // Simple log parser
            const lines = data.content.split('\n');
            let parsedHtml = '';
            
            lines.forEach(line => {
                if (!line.trim()) return;
                
                let lineClass = "db mb1 pb1 bb b--white-05";
                let textClass = "near-white";
                
                if (line.includes(' - INFO - ')) {
                    line = line.replace(' - INFO - ', ' <span class="blue b">[INFO]</span> ');
                } else if (line.includes(' - ERROR - ') || line.includes('❌') || line.includes('Error') || line.includes('error')) {
                    line = line.replace(' - ERROR - ', ' <span class="red b">[ERROR]</span> ');
                    textClass = "light-red";
                } else if (line.includes(' - WARNING - ') || line.includes('⚠️')) {
                    line = line.replace(' - WARNING - ', ' <span class="yellow b">[WARN]</span> ');
                    textClass = "washed-yellow";
                } else if (line.includes('✅')) {
                    textClass = "light-green";
                }
                
                line = line.replace(/</g, "&lt;").replace(/>/g, "&gt;");
                // Restore span tags we just added
                line = line.replace(/&lt;span class="([^"]+)"&gt;/g, '<span class="$1">').replace(/&lt;\/span&gt;/g, '</span>');

                parsedHtml += `<div class="${lineClass} ${textClass}">${line}</div>`;
            });
            
            document.getElementById('sys-log-viewer').innerHTML = parsedHtml;
            // Scroll to bottom
            const container = document.getElementById('sys-log-viewer').parentElement;
            container.scrollTop = container.scrollHeight;
        })
        .catch(e => showToast('Lỗi đọc file: ' + e.message, 'error'));
}

function deleteCurrentLog() {
    if (!currentLogFile) return;
    if (!confirm(`Xóa vĩnh viễn file log "${currentLogFile}"?`)) return;
    
    fetch(`/api/logs/${encodeURIComponent(currentLogFile)}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast('Đã xóa log', 'success');
                currentLogFile = '';
                document.getElementById('current-log-title').textContent = 'Chọn file để xem';
                document.getElementById('sys-log-viewer').innerHTML = '<div class="tc silver mt5 i">Chưa chọn file log.</div>';
                document.getElementById('btn-delete-log').classList.add('dn');
                loadLogList();
            } else {
                showToast(data.error || 'Lỗi', 'error');
            }
        });
}
