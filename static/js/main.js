/* Novel Translator - main.js v4.1.0 */
/* Oat.ink handles tabs natively via <ot-tabs>, no custom tab JS needed */

let prompts = window.initialPrompts || {};
let currentOutputFile = '';
let allFiles = [];
let selectedFiles = new Set();
let availableModels = window.initialAvailableModels || [];
let defaultModel = window.initialDefaultModel || '';
let currentDoneFile = '';
let currentGenre = '';

document.addEventListener('DOMContentLoaded', function () {
    loadFiles();
    loadDoneFiles();
    loadOutputFiles();
    loadStats();
    loadModels();
    loadGenres();
    setInterval(loadStats, 30000);
    setInterval(loadOutputFiles, 10000);
    setInterval(loadDoneFiles, 10000);

    // Temperature slider
    document.getElementById('temperature').addEventListener('input', function () {
        document.getElementById('temp-value').textContent = this.value;
    });

    // Core action buttons
    document.getElementById('translate-btn').addEventListener('click', startTranslation);
    document.getElementById('btn-translate-selected').addEventListener('click', translateSelected);
    document.getElementById('btn-select-all').addEventListener('click', selectAll);
    document.getElementById('btn-deselect-all').addEventListener('click', deselectAll);
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
    document.getElementById('btn-new-genre').addEventListener('click', () => {
        document.getElementById('new-genre-dialog').showModal();
    });
    document.getElementById('btn-delete-genre').addEventListener('click', deleteGenre);
    document.getElementById('btn-save-genre').addEventListener('click', saveGenre);
    document.getElementById('btn-activate-genre').addEventListener('click', activateGenre);
    document.getElementById('btn-confirm-new-genre').addEventListener('click', createGenre);

    // Auto-generate slug from name
    document.getElementById('new-genre-name').addEventListener('input', function () {
        const slug = this.value.toLowerCase()
            .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .replace(/đ/g, 'd').replace(/Đ/g, 'D')
            .replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
        document.getElementById('new-genre-slug').value = slug;
    });

    // Language change -> reload prompts
    document.getElementById('input-lang').addEventListener('change', function () {
        loadPromptsForLang(this.value);
    });
});

// ============================================================
// Models
// ============================================================
function loadModels() {
    fetch('/api/models')
        .then(r => r.json())
        .then(data => {
            const sel = document.getElementById('model');
            if (data.models && data.models.length > 0) availableModels = data.models;
            sel.innerHTML = availableModels.map(m =>
                `<option value="${m}" ${m === (data.default || defaultModel) ? 'selected' : ''}>${m}</option>`
            ).join('');
        })
        .catch(() => {
            const sel = document.getElementById('model');
            sel.innerHTML = availableModels.map(m =>
                `<option value="${m}" ${m === defaultModel ? 'selected' : ''}>${m}</option>`
            ).join('');
        });
}

// ============================================================
// File Management
// ============================================================
function loadFiles() {
    fetch('/api/files')
        .then(r => r.json())
        .then(files => {
            allFiles = files;
            const el = document.getElementById('file-list');
            if (!files.length) { el.innerHTML = '<p class="muted">Không có file trong input</p>'; return; }
            el.innerHTML = files.map(f => {
                const esc = f.path.replace(/'/g, "\\'");
                const nameEsc = f.name.replace(/'/g, "\\'");
                return `<div class="file-item">
                    <input type="checkbox" ${selectedFiles.has(f.path) ? 'checked' : ''} onchange="toggleFile('${esc}',this.checked)">
                    <div class="file-info" onclick="loadFile('${nameEsc}')">
                        <span class="file-name">${f.name}${f.is_done ? '<span class="badge success" style="font-size:0.7em;margin-left:5px">Done</span>' : ''}</span>
                        <span class="file-size">${f.size_display}</span>
                    </div>
                    <button data-variant="warning" style="padding:4px 8px;font-size:0.8em" onclick="event.stopPropagation();translateSingleFile('${esc}')">Dịch</button>
                </div>`;
            }).join('');
            updateSelectedCount();
        });
}

function loadDoneFiles() {
    fetch('/api/done-files')
        .then(r => r.json())
        .then(files => {
            const el = document.getElementById('done-list');
            if (!files.length) { el.innerHTML = '<p class="muted">Chưa có file đã dịch</p>'; return; }
            el.innerHTML = files.map(f => {
                const nameEsc = f.name.replace(/'/g, "\\'");
                const locBadge = f.location === 'output'
                    ? '<span class="badge" style="font-size:0.7em;margin-left:5px">output</span>'
                    : '<span class="badge success" style="font-size:0.7em;margin-left:5px">done</span>';
                return `<div class="file-item done-item">
                    <div class="file-info" onclick="viewDoneFile('${nameEsc}','${f.location}')">
                        <span class="file-name">${f.name} ${locBadge} (${(f.word_count || 0).toLocaleString()} từ)</span>
                        <span class="file-size">${f.size_display}</span>
                    </div>
                    ${f.location === 'done' ? `<button class="outline" style="padding:4px 8px;font-size:0.8em" onclick="event.stopPropagation();moveBackToInput('${nameEsc}')">↩</button>` : ''}
                </div>`;
            }).join('');
        });
}

function toggleFile(path, checked) {
    checked ? selectedFiles.add(path) : selectedFiles.delete(path);
    updateSelectedCount();
}
function updateSelectedCount() { document.getElementById('selected-count').textContent = selectedFiles.size; }
function selectAll() {
    document.querySelectorAll('#file-list input[type="checkbox"]').forEach(cb => cb.checked = true);
    allFiles.forEach(f => selectedFiles.add(f.path));
    updateSelectedCount();
}
function deselectAll() {
    selectedFiles.clear();
    document.querySelectorAll('#file-list input[type="checkbox"]').forEach(cb => cb.checked = false);
    updateSelectedCount();
}

function loadFile(filename) {
    fetch('/api/file/' + encodeURIComponent(filename))
        .then(r => r.json())
        .then(data => {
            const ta = document.getElementById('source-text');
            ta.value += (ta.value ? '\n\n' : '') + data.content;
            addLog('Đã tải: ' + data.name, 'info');
        }).catch(e => addLog('Lỗi: ' + e.message, 'error'));
}

function viewDoneFile(filename, location) {
    const ep = location === 'output' ? '/api/output-file/' : '/api/done/';
    fetch(ep + encodeURIComponent(filename))
        .then(r => r.json())
        .then(data => {
            document.getElementById('done-text').value = data.content;
            currentDoneFile = filename;
            document.getElementById('done-result-container').classList.remove('active');
            addDoneLog('Đã tải: ' + filename, 'info');
        }).catch(e => addDoneLog('Lỗi: ' + e.message, 'error'));
}

function moveBackToInput(filename) {
    if (!confirm('Di chuyển file này về input?')) return;
    fetch('/api/move-back-to-input', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename }) })
        .then(r => r.json()).then(data => { if (data.success) { loadFiles(); loadDoneFiles(); } });
}

function loadOutputFiles() {
    fetch('/api/output-files')
        .then(r => r.json())
        .then(files => {
            const el = document.getElementById('output-list');
            if (!files.length) { el.innerHTML = '<p class="muted">Chưa có file</p>'; return; }
            el.innerHTML = files.map(f =>
                `<div class="file-item"><span class="file-name">${f.name}</span><a href="/api/download/${f.name}" target="_blank"><button class="outline" style="padding:4px 8px;font-size:0.8em">Tải</button></a></div>`
            ).join('');
        });
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
    if (!confirm('Xóa tất cả cache?')) return;
    fetch('/api/cache/clear', { method: 'POST' }).then(r => r.json()).then(data => {
        if (typeof ot !== 'undefined') ot.toast('Đã xóa ' + data.deleted + ' files', 'Cache', { variant: 'success' });
        else alert('Đã xóa ' + data.deleted + ' files');
        loadStats();
    });
}

// ============================================================
// Translation
// ============================================================
function getActivePrompts() {
    return prompts; // Currently loaded prompts (from genre or default)
}

function startTranslation() {
    const btn = document.getElementById('translate-btn');
    const text = document.getElementById('source-text').value;
    if (!text.trim()) { alert('Vui lòng nhập văn bản!'); return; }

    btn.disabled = true;
    btn.textContent = '🔄 Đang dịch...';
    document.getElementById('progress-container').classList.add('active');
    document.getElementById('result-container').classList.remove('active');
    document.getElementById('log-container').classList.add('active');
    document.getElementById('log-container').innerHTML = '';
    addLog('Bắt đầu dịch...', 'info');

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
    if (!selectedFiles.size) { alert('Chọn ít nhất 1 file!'); return; }
    const btn = document.getElementById('btn-translate-selected');
    btn.disabled = true; btn.textContent = '🔄 Đang dịch...';
    document.getElementById('progress-container').classList.add('active');
    document.getElementById('log-container').classList.add('active');
    document.getElementById('log-container').innerHTML = '';
    addLog(`Dịch ${selectedFiles.size} file...`, 'info');

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
        if (data.error) { addLog(data.error, 'error'); btn.disabled = false; btn.textContent = '🚀 Dịch đã chọn'; }
        else connectToProgress();
    }).catch(e => { addLog(e.message, 'error'); btn.disabled = false; btn.textContent = '🚀 Dịch đã chọn'; });
}

function translateSingleFile(filepath) {
    document.getElementById('progress-container').classList.add('active');
    document.getElementById('log-container').classList.add('active');
    document.getElementById('log-container').innerHTML = '';
    addLog('Dịch file...', 'info');

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

function connectToProgress(btn = null) {
    const evtSource = new EventSource('/api/progress');
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-text').textContent = 'Kết nối...';

    evtSource.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
            document.getElementById('progress-fill').style.width = data.percent + '%';
            document.getElementById('progress-fill').textContent = data.percent + '%';
            document.getElementById('progress-text').textContent = data.message;
        } else if (data.type === 'complete') {
            evtSource.close();
            document.getElementById('progress-text').textContent = 'Hoàn tất!';
            document.getElementById('progress-fill').style.width = '100%';
            if (data.output_file) {
                currentOutputFile = data.output_file;
                document.getElementById('result-text').value = "Đã lưu: " + data.output_file;
            } else {
                document.getElementById('result-text').value = data.translated_text || '';
            }
            document.getElementById('result-container').classList.add('active');
            document.getElementById('result-stats').innerHTML =
                `<span class="result-stat">💬 ${data.chunks_count || 0} chunks</span>
                 <span class="result-stat">🔤 ${(data.char_count || 0).toLocaleString()} chars</span>`;
            resetButton(btn);
            loadOutputFiles(); loadStats(); loadFiles(); loadDoneFiles();
            if (typeof ot !== 'undefined') ot.toast('Dịch hoàn tất!', 'Thành công', { variant: 'success' });
        } else if (data.type === 'error') {
            evtSource.close(); addLog(data.message, 'error'); resetButton(btn);
        } else if (data.type === 'info') {
            addLog(data.message, 'info');
        }
    };
    evtSource.onerror = function () { evtSource.close(); };
}

// ============================================================
// Done Tab (Retranslate/Correction)
// ============================================================
function runRetranslate() {
    const text = document.getElementById('done-text').value;
    if (!text.trim()) { addDoneLog('Chưa có nội dung', 'error'); return; }
    runTranslationProcess(text, 'retranslate');
}
function runCorrection() {
    const text = document.getElementById('done-text').value;
    if (!text.trim()) { addDoneLog('Chưa có nội dung', 'error'); return; }
    runTranslationProcess(text, 'correction');
}
function runBoth() {
    const text = document.getElementById('done-text').value;
    if (!text.trim()) { addDoneLog('Chưa có nội dung', 'error'); return; }
    addDoneLog('Retranslate...', 'info');
    runTranslationProcess(text, 'retranslate', () => {
        addDoneLog('Correction...', 'info');
        runTranslationProcess(document.getElementById('done-result-text').value, 'correction', null, true);
    });
}

function runTranslationProcess(text, mode, callback, appendResult) {
    showDoneProgress(0, 'Chuẩn bị...');
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
        if (data.error) { addDoneLog('Lỗi: ' + data.error, 'error'); hideDoneProgress(); return; }
        hideDoneProgress();
        const result = data.translated || text;
        if (appendResult) document.getElementById('done-text').value = result;
        else document.getElementById('done-result-text').value = result;
        document.getElementById('done-result-container').classList.add('active');
        addDoneLog(mode + ' hoàn tất!', 'success');
        if (callback) callback();
    }).catch(e => { addDoneLog('Lỗi: ' + e.message, 'error'); hideDoneProgress(); });
}

function showDoneProgress(p, t) {
    document.getElementById('done-progress-container').classList.add('active');
    document.getElementById('done-progress-fill').style.width = p + '%';
    document.getElementById('done-progress-fill').textContent = p + '%';
    document.getElementById('done-progress-text').textContent = t;
}
function hideDoneProgress() { document.getElementById('done-progress-container').classList.remove('active'); }

function copyDoneResult() {
    navigator.clipboard.writeText(document.getElementById('done-result-text').value)
        .then(() => addDoneLog('Copied!', 'success')).catch(() => addDoneLog('Copy failed', 'error'));
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
            if (!sets.length) { el.innerHTML = '<p class="muted">Chưa có thể loại nào</p>'; return; }
            el.innerHTML = sets.map(s =>
                `<div class="genre-item ${s.slug === currentGenre ? 'active' : ''}" onclick="selectGenre('${s.slug}')">
                    <div>
                        <div class="genre-name">${s.name}</div>
                        <div class="genre-desc">${s.description || ''}</div>
                    </div>
                    <span class="badge">${s.has_main ? '✓' : '○'}</span>
                </div>`
            ).join('');
        });
}

function selectGenre(slug) {
    currentGenre = slug;
    document.getElementById('btn-delete-genre').disabled = false;
    fetch('/api/prompt-sets/' + slug)
        .then(r => r.json())
        .then(data => {
            document.getElementById('genre-editor').style.display = 'block';
            document.getElementById('genre-editor-title').textContent = '📝 ' + (data.meta.name || slug);
            document.getElementById('genre-editor-desc').textContent = data.meta.description || '';
            document.getElementById('genre-main-text').value = data.prompts.main || '';
            document.getElementById('genre-retranslate-text').value = data.prompts.retranslate || '';
            document.getElementById('genre-correction-text').value = data.prompts.correction || '';
            loadGenres(); // Refresh active state
        });
}

function createGenre(e) {
    e.preventDefault();
    const name = document.getElementById('new-genre-name').value.trim();
    const slug = document.getElementById('new-genre-slug').value.trim() ||
        name.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
    const desc = document.getElementById('new-genre-desc').value.trim();

    if (!name) { alert('Nhập tên thể loại!'); return; }

    fetch('/api/prompt-sets', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, slug, description: desc, prompts: { main: '', retranslate: '', correction: '' } })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            document.getElementById('new-genre-dialog').close();
            document.getElementById('new-genre-name').value = '';
            document.getElementById('new-genre-slug').value = '';
            document.getElementById('new-genre-desc').value = '';
            loadGenres();
            selectGenre(data.slug);
            if (typeof ot !== 'undefined') ot.toast('Đã tạo thể loại: ' + name, 'Thành công', { variant: 'success' });
        } else {
            alert('Lỗi: ' + (data.error || 'Unknown'));
        }
    });
}

function saveGenre() {
    if (!currentGenre) return;
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
            showGenreAlert('Đã lưu prompt cho: ' + currentGenre, 'success');
            if (typeof ot !== 'undefined') ot.toast('Đã lưu!', 'Prompt', { variant: 'success' });
        }
    });
}

function activateGenre() {
    if (!currentGenre) return;
    fetch('/api/prompt-sets/' + currentGenre + '/activate', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                // Reload active prompts
                prompts = {
                    main: document.getElementById('genre-main-text').value,
                    retranslate: document.getElementById('genre-retranslate-text').value,
                    correction: document.getElementById('genre-correction-text').value
                };
                showGenreAlert(data.message, 'success');
                if (typeof ot !== 'undefined') ot.toast(data.message, 'Prompt', { variant: 'success' });
            }
        });
}

function deleteGenre() {
    if (!currentGenre) return;
    if (!confirm('Xóa thể loại "' + currentGenre + '"?')) return;
    fetch('/api/prompt-sets/' + currentGenre, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                currentGenre = '';
                document.getElementById('genre-editor').style.display = 'none';
                document.getElementById('btn-delete-genre').disabled = true;
                loadGenres();
                if (typeof ot !== 'undefined') ot.toast('Đã xóa!', 'Prompt', { variant: 'success' });
            }
        });
}

function showGenreAlert(msg, variant) {
    const el = document.getElementById('genre-alert');
    el.style.display = 'block';
    el.setAttribute('data-variant', variant);
    el.innerHTML = '<strong>' + (variant === 'success' ? '✅' : '⚠️') + '</strong> ' + msg;
    setTimeout(() => { el.style.display = 'none'; }, 3000);
}

// ============================================================
// Prompts (language-based, legacy)
// ============================================================
function loadPromptsForLang(lang) {
    fetch('/api/prompts?lang=' + lang).then(r => r.json()).then(data => { prompts = data; });
}

// ============================================================
// Utilities
// ============================================================
function addLog(message, type) {
    const el = document.getElementById('log-container');
    el.classList.add('active');
    const entry = document.createElement('div');
    entry.className = 'log-entry ' + type;
    entry.textContent = '[' + new Date().toLocaleTimeString() + '] ' + message;
    el.appendChild(entry);
    el.scrollTop = el.scrollHeight;
}
function addDoneLog(message, type) {
    const el = document.getElementById('done-log-container');
    el.classList.add('active');
    const entry = document.createElement('div');
    entry.className = 'log-entry ' + type;
    entry.textContent = '[' + new Date().toLocaleTimeString() + '] ' + message;
    el.appendChild(entry);
    el.scrollTop = el.scrollHeight;
}

function resetButton(btn) {
    if (!btn) btn = document.getElementById('translate-btn');
    if (btn) { btn.disabled = false; btn.textContent = '🚀 Bắt đầu dịch'; }
    const batchBtn = document.getElementById('btn-translate-selected');
    if (batchBtn && batchBtn.disabled) { batchBtn.disabled = false; batchBtn.textContent = '🚀 Dịch đã chọn'; }
}

function copyResult() {
    navigator.clipboard.writeText(document.getElementById('result-text').value)
        .then(() => addLog('Copied!', 'success')).catch(() => addLog('Copy failed', 'error'));
}
function downloadResult() {
    if (currentOutputFile) window.open('/api/download/' + currentOutputFile, '_blank');
}
