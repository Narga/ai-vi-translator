/* Novel Translator - main.js v5.0 (Tachyons Redesign) */

let prompts = window.initialPrompts || {};
let currentOutputFile = '';
let allFiles = [];
let selectedFiles = new Set();
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
    loadModels();
    loadGenres();

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

    // Language change -> reload prompts
    const langEl = document.getElementById('input-lang');
    if (langEl) {
        langEl.addEventListener('change', function () {
            loadPromptsForLang(this.value);
        });
    }
});

// ============================================================
// UI Initializations
// ============================================================
function initTabs() {
    const navLinks = document.querySelectorAll('.nt-nav-link');
    const sections = document.querySelectorAll('.nt-tab-content');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('data-tab');

            // Update Nav Classes
            navLinks.forEach(n => {
                n.classList.remove('active', 'bg-light-blue', 'blue', 'bl', 'bw2');
                n.classList.add('color-inherit');
            });
            link.classList.remove('color-inherit');
            link.classList.add('active', 'bg-light-blue', 'blue', 'bl', 'bw2');

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
    const pTabs = document.querySelectorAll('.nt-tab-btn');
    const pContents = document.querySelectorAll('.nt-ptab-content');

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
            content.classList.remove('dn');
            content.classList.add('flex');
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
// Models & Token Estimation
// ============================================================
let currentModelInfo = null; // cache model info

function loadModels() {
    fetch('/api/models')
        .then(r => r.json())
        .then(data => {
            const sel = document.getElementById('model');
            if (data.models && data.models.length > 0) availableModels = data.models;
            sel.innerHTML = availableModels.map(m =>
                `<option value="${m}" ${m === (data.default || defaultModel) ? 'selected' : ''}>${m}</option>`
            ).join('');
            // Auto-fetch info for selected model
            const selected = sel.value;
            if (selected) fetchModelInfo(selected);
        })
        .catch(() => {
            const sel = document.getElementById('model');
            sel.innerHTML = availableModels.map(m =>
                `<option value="${m}" ${m === defaultModel ? 'selected' : ''}>${m}</option>`
            ).join('');
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
        if (data.error) { alert(data.error); return; }
        currentProject = data;
        selectedFiles.clear();

        // Update header
        document.getElementById('project-header').classList.remove('dn');
        document.getElementById('project-tabs').classList.remove('dn');
        document.getElementById('project-empty-state').classList.add('dn');
        document.getElementById('project-title').textContent = data.name;
        document.getElementById('project-desc').textContent = data.description || '';
        document.getElementById('proj-source-count').textContent = data.source_count;
        document.getElementById('proj-translated-count').textContent = data.translated_count;
        document.getElementById('proj-source-words').textContent = (data.source_words || 0).toLocaleString();

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
        return `<div class="nt-file-item">
            <div class="flex-auto pointer" onclick="loadProjectFile('${esc}','translated')">
                <span class="fw6 dark-gray db f6">${f.name}</span>
                <span class="f7 silver">${f.size_display}</span>
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
        } else {
            document.getElementById('done-text').value = data.content || '';
            currentDoneFile = filename;
        }
    });
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
        } else alert(data.error || 'Lỗi');
    });
}

function translateSelectedInProject() {
    if (!currentProject || selectedFiles.size === 0) { alert('Chưa chọn file!'); return; }
    const files = Array.from(selectedFiles);
    fetch(`/api/projects/${currentProject.slug}/translate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files })
    }).then(r => r.json()).then(data => {
        if (data.status === 'started') startSSEProgress();
        else alert(data.error || 'Lỗi');
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
        if (data.success) alert('Đã lưu prompt dự án!');
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
    Promise.all(saves).then(() => alert('Đã lưu profile dự án!'));
}

function showCreateProjectDialog() {
    const name = prompt('Tên dự án mới:');
    if (!name) return;
    const desc = prompt('Mô tả (tùy chọn):', '');
    fetch('/api/projects', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description: desc || '' })
    }).then(r => r.json()).then(data => {
        if (data.success) { loadProjects(); selectProject(data.slug); }
        else alert(data.error || 'Lỗi tạo dự án');
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

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('collapsed');
    const btn = document.getElementById('btn-toggle-sidebar');
    btn.textContent = sidebar.classList.contains('collapsed') ? '▶' : '☰';
}

// Keep old functions for backward compat (they are no-ops now)
function loadFiles() { loadProjects(); }
function loadDoneFiles() { }
function loadOutputFiles() { }

function loadFile(filename) {
    if (currentProject) {
        loadProjectFile(filename, 'sources');
    }
}

function viewDoneFile(filename, location) {
    if (currentProject) {
        loadProjectFile(filename, 'translated');
    }
}

function moveBackToInput(filename) {
    if (currentProject) moveBackInProject(filename);
}


// ============================================================
// Stats
// ============================================================
function loadStats() {
    fetch('/api/stats').then(r => r.json()).then(data => {
        document.getElementById('api-keys-count').textContent = data.api_keys_count || data.api_keys || 0;
        document.getElementById('cache-count').textContent = data.cache_files || 0;
        document.getElementById('cache-size').textContent = data.cache_size_mb || 0;
        document.getElementById('translated-words').textContent = (data.translated_words || 0).toLocaleString();
        document.getElementById('pending-words').textContent = (data.pending_words || 0).toLocaleString();
        document.getElementById('output-count').textContent = data.output_files || 0;
        document.getElementById('input-files-count').textContent = data.input_files_count || 0;
        document.getElementById('done-files-count').textContent = data.done_files_count || 0;
    });
}

function clearCache() {
    if (!confirm('Xóa sạch bộ nhớ Cache dịch thuật?')) return;
    fetch('/api/cache/clear', { method: 'POST' }).then(r => r.json()).then(data => {
        alert('Đã dọn dẹp ' + data.deleted + ' files nháp.');
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
    if (!text.trim()) { alert('Vui lòng nhập văn bản hoặc chọn file!'); return; }

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
            input_lang: document.getElementById('input-lang').value,
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

function translateSelected() {
    if (!selectedFiles.size) { alert('Vui lòng chọn ít nhất 1 file bên danh sách kết quả!'); return; }
    const btn = document.getElementById('btn-translate-selected');

    btn.disabled = true;
    btn.innerHTML = '🔄 <span class="nt-btn-spinner dib"></span> Đang xử lý...';

    document.getElementById('log-container').classList.add('dn');
    document.getElementById('log-container').innerHTML = '';

    addLog(`Đẩy ${selectedFiles.size} file vào tiến trình...`, 'info');

    fetch('/api/translate-batch', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            files: Array.from(selectedFiles),
            model: document.getElementById('model').value,
            input_lang: document.getElementById('input-lang').value,
            temperature: parseFloat(document.getElementById('temperature').value),
            chunk_size: parseInt(document.getElementById('chunk-size').value),
            use_cache: document.getElementById('use-cache').checked,
            prompts: getActivePrompts()
        })
    }).then(r => r.json()).then(data => {
        if (data.error) { addLog(data.error, 'error'); resetButton(btn, true); }
        else connectToProgress(btn, true);
    }).catch(e => { addLog(e.message, 'error'); resetButton(btn, true); });
}

function translateSingleFile(filepath) {
    document.getElementById('log-container').classList.add('dn');
    document.getElementById('log-container').innerHTML = '';
    addLog('Bắt đầu dịch file: ' + filepath, 'info');

    fetch('/api/translate-file', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            filepath, model: document.getElementById('model').value,
            input_lang: document.getElementById('input-lang').value,
            temperature: parseFloat(document.getElementById('temperature').value),
            chunk_size: parseInt(document.getElementById('chunk-size').value),
            use_cache: document.getElementById('use-cache').checked,
            prompts: getActivePrompts()
        })
    }).then(r => r.json()).then(data => {
        if (data.error) addLog(data.error, 'error');
        else connectToProgress();
    }).catch(e => addLog(e.message, 'error'));
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
        .then(() => alert('Đã sao chép vào Clipboard!'))
        .catch(() => alert('Copy thất bại'));
}
function downloadResult() {
    if (currentOutputFile) window.open('/api/download/' + currentOutputFile, '_blank');
    else alert('Chưa xác định file output!');
}

// ============================================================
// Done Tab (Retranslate/Correction)
// ============================================================
function runRetranslate() {
    const text = document.getElementById('done-text').value;
    if (!text.trim()) { alert('Chưa tải nội dung file gốc!'); return; }
    runDoneTranslationProcess(text, 'retranslate');
}
function runCorrection() {
    const text = document.getElementById('done-text').value;
    if (!text.trim()) { alert('Chưa tải nội dung file gốc!'); return; }
    runDoneTranslationProcess(text, 'correction');
}
function runBoth() {
    const text = document.getElementById('done-text').value;
    if (!text.trim()) { alert('Chưa tải nội dung file gốc!'); return; }
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
            chunk_size: parseInt(document.getElementById('chunk-size').value),
            input_lang: document.getElementById('input-lang').value
        })
    }).then(r => r.json()).then(data => {
        if (data.error) { addDoneLog('Lỗi xử lý: ' + data.error, 'error'); hideProgress('done-progress-container'); return; }

        // This is a simplified fallback for non-SSE text translate API
        hideProgress('done-progress-container');
        const result = data.translated || text;

        if (appendResult) document.getElementById('done-text').value = result;
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
        .then(() => alert('Đã chép nội dung đã sửa!'))
        .catch(() => alert('Copy thất bại'));
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

    document.getElementById('genre-empty-state').classList.add('dn');
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

    if (!name) { alert('Tên thể loại không được rỗng!'); return; }

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
            alert('Lỗi khởi tạo: ' + (data.error || 'Unknown Error'));
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
// Prompts (language-based, legacy fallback)
// ============================================================
function loadPromptsForLang(lang) {
    fetch('/api/prompts?lang=' + lang).then(r => r.json()).then(data => { prompts = data; });
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
