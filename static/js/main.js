/* Novel Translator - main.js v5.0 (Tachyons Redesign) */

let prompts = window.initialPrompts || {};
let currentOutputFile = '';
let allFiles = [];
let selectedFiles = new Set();
let availableModels = window.initialAvailableModels || [];
let defaultModel = window.initialDefaultModel || '';
let currentDoneFile = '';
let currentGenre = '';
let currentLoadedFile = null; // track file loaded for editing

document.addEventListener('DOMContentLoaded', function () {
    initTabs();
    initPromptTabs();
    initDialogs();

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
    const tempEl = document.getElementById('temperature');
    if (tempEl) {
        tempEl.addEventListener('input', function () {
            document.getElementById('temp-value').textContent = this.value;
        });
    }

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
            if (!files.length) { el.innerHTML = '<div class="pa4 tc silver i">Không có file trong input</div>'; return; }
            el.innerHTML = files.map(f => {
                const esc = f.path.replace(/'/g, "\\'");
                const nameEsc = f.name.replace(/'/g, "\\'");
                const activeClass = selectedFiles.has(f.path) ? 'active' : '';
                return `<div class="nt-file-item ${activeClass}">
                    <div class="flex items-center flex-auto">
                        <input type="checkbox" class="nt-checkbox mr2 pointer" ${selectedFiles.has(f.path) ? 'checked' : ''} onchange="toggleFile('${esc}',this.checked)">
                        <div class="flex-auto pointer" onclick="loadFile('${nameEsc}')">
                            <span class="fw6 dark-gray db f6">${f.name}${f.is_done ? '<span class="f7 bg-green white br2 ph1 pv1 ml2 fw5">Done</span>' : ''}</span>
                            <span class="f7 silver">${f.size_display}</span>
                        </div>
                    </div>
                    <div class="nt-file-actions">
                        <button class="nt-file-action-btn" onclick="event.stopPropagation();markFileDone('${esc}')" title="Đánh dấu hoàn thành">✅</button>
                        <button class="nt-file-action-btn" onclick="event.stopPropagation();deleteInputFile('${esc}')" title="Xóa file">🗑️</button>
                        <button class="nt-file-action-btn nt-btn-outline" onclick="event.stopPropagation();translateSingleFile('${esc}')" title="Dịch ngay">⚡</button>
                    </div>
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
            if (!files.length) { el.innerHTML = '<div class="pa4 tc silver i">Chưa có file đã dịch</div>'; return; }
            el.innerHTML = files.map(f => {
                const nameEsc = f.name.replace(/'/g, "\\'");
                const badge = f.location === 'output'
                    ? '<span class="f7 bg-light-silver white br2 ph1 pv1 ml2 fw5">output</span>'
                    : '<span class="f7 bg-green white br2 ph1 pv1 ml2 fw5">done</span>';
                return `<div class="nt-file-item">
                    <div class="flex-auto pointer" onclick="viewDoneFile('${nameEsc}','${f.location}')">
                        <span class="fw6 dark-gray db f6">${f.name} ${badge}</span>
                        <span class="f7 silver">${(f.word_count || 0).toLocaleString()} từ &bull; ${f.size_display}</span>
                    </div>
                    <div class="nt-file-actions">
                        ${f.location === 'done' ? `<button class="nt-file-action-btn" onclick="event.stopPropagation();moveBackToInput('${nameEsc}')" title="Trả về input">↩</button>` : ''}
                        <button class="nt-file-action-btn" onclick="event.stopPropagation();deleteDoneFile('${nameEsc}','${f.location}')" title="Xóa file">🗑️</button>
                    </div>
                </div>`;
            }).join('');
        });
}

function toggleFile(path, checked) {
    checked ? selectedFiles.add(path) : selectedFiles.delete(path);
    loadFiles(); // Re-render to show active class
}

function updateSelectedCount() {
    document.getElementById('selected-count').textContent = selectedFiles.size;
    const translateBtn = document.getElementById('btn-translate-count');
    if (translateBtn) translateBtn.textContent = selectedFiles.size + ' file';
}

function selectAll() {
    allFiles.forEach(f => selectedFiles.add(f.path));
    loadFiles();
}

function deselectAll() {
    selectedFiles.clear();
    loadFiles();
}

function loadFile(filename) {
    fetch('/api/file/' + encodeURIComponent(filename)).then(r => r.json()).then(data => {
        document.getElementById('source-text').value = data.content || '';
        currentLoadedFile = { name: filename, path: data.path || '' };
        document.getElementById('btn-save-file').classList.remove('dn');
    });
}

function viewDoneFile(filename, location) {
    const ep = location === 'output' ? '/api/output-file/' : '/api/done/';
    fetch(ep + encodeURIComponent(filename))
        .then(r => r.json())
        .then(data => {
            document.getElementById('done-text').value = data.content;
            currentDoneFile = filename;
            document.getElementById('done-result-container').classList.add('dn');
            document.getElementById('done-result-container').classList.remove('flex');
            addDoneLog('Đã tải: ' + filename, 'success');
        }).catch(e => addDoneLog('Lỗi tải file: ' + e.message, 'error'));
}

function moveBackToInput(filename) {
    if (!confirm('Di chuyển file "' + filename + '" về input?')) return;
    fetch('/api/move-back-to-input', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename }) })
        .then(r => r.json()).then(data => { if (data.success) { loadFiles(); loadDoneFiles(); loadStats(); } });
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('collapsed');
    const btn = document.getElementById('btn-toggle-sidebar');
    btn.textContent = sidebar.classList.contains('collapsed') ? '▶' : '☰';
}

function saveCurrentFile() {
    if (!currentLoadedFile || !currentLoadedFile.path) {
        alert('Chưa tải file nào để lưu!');
        return;
    }
    const content = document.getElementById('source-text').value;
    fetch('/api/files', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath: currentLoadedFile.path, content })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            addLog('💾 Đã lưu: ' + currentLoadedFile.name, 'success');
            loadFiles();
            loadStats();
        } else {
            addLog('❌ Lỗi lưu: ' + (data.error || ''), 'error');
        }
    });
}

function deleteInputFile(filepath) {
    if (!confirm('Xóa vĩnh viễn file này?')) return;
    fetch('/api/files', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath })
    }).then(r => r.json()).then(data => {
        if (data.success) { loadFiles(); loadStats(); }
        else { alert('Lỗi xóa: ' + (data.error || '')); }
    });
}

function markFileDone(filepath) {
    fetch('/api/move-to-done', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath })
    }).then(r => r.json()).then(data => {
        if (data.success) { loadFiles(); loadDoneFiles(); loadStats(); }
        else { alert('Lỗi: ' + (data.error || '')); }
    });
}

function deleteDoneFile(filename, location) {
    if (!confirm('Xóa vĩnh viễn file "' + filename + '"?')) return;
    fetch('/api/done-files', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, location })
    }).then(r => r.json()).then(data => {
        if (data.success) { loadDoneFiles(); loadStats(); }
        else { alert('Lỗi xóa: ' + (data.error || '')); }
    });
}

function loadOutputFiles() {
    fetch('/api/output-files')
        .then(r => r.json())
        .then(files => {
            const el = document.getElementById('output-list');
            if (!files.length) { el.innerHTML = '<div class="pa4 tc silver i">Chưa có file</div>'; return; }
            el.innerHTML = files.map(f =>
                `<div class="flex items-center justify-between pa2 bb b--black-10 hover-bg-near-white">
                    <span class="f6 fw5 dark-gray">${f.name}</span>
                    <a href="/api/download/${f.name}" target="_blank" class="nt-btn nt-btn-outline f7">Tải xuống</a>
                </div>`
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
