let prompts = window.initialPrompts || {};
let currentOutputFile = '';
let allFiles = [];
let selectedFiles = new Set();
let availableModels = window.initialAvailableModels || [];
let defaultModel = window.initialDefaultModel || '';
let currentDoneFile = '';

document.addEventListener('DOMContentLoaded', function() {
    loadFiles();
    loadDoneFiles();
    loadOutputFiles();
    loadStats();
    loadModels();
    setInterval(loadStats, 30000);
    setInterval(loadOutputFiles, 10000);
    setInterval(loadDoneFiles, 10000);
    
    document.getElementById('temperature').addEventListener('input', function() {
        document.getElementById('temp-value').textContent = this.value;
    });
    
    document.getElementById('prompt-main-text').value = prompts.main || '';
    document.getElementById('prompt-retranslate-text').value = prompts.retranslate || '';
    document.getElementById('prompt-correction-text').value = prompts.correction || '';
});

function loadModels() {
    fetch('/api/models')
        .then(r => r.json())
        .then(data => {
            const modelSelect = document.getElementById('model');
            if (data.models && data.models.length > 0) {
                availableModels = data.models;
            }
            modelSelect.innerHTML = availableModels.map(m => 
                `<option value="${m}" ${m === data.default ? 'selected' : ''}>${m}</option>`
            ).join('');
        })
        .catch(() => {
            const modelSelect = document.getElementById('model');
            modelSelect.innerHTML = availableModels.map(m => 
                `<option value="${m}" ${m === defaultModel ? 'selected' : ''}>${m}</option>`
            ).join('');
        });
}

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('tab-' + tab).classList.add('active');
}

function loadFiles() {
    fetch('/api/files')
        .then(r => r.json())
        .then(files => {
            allFiles = files;
            const container = document.getElementById('file-list');
            if (files.length === 0) {
                container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Không có file trong input</p>';
                return;
            }
            
            container.innerHTML = files.map((f, i) => {
                const isSelected = selectedFiles.has(f.path);
                return `<div class="file-item">
                    <input type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleFile('${f.path.replace(/'/g, "\\'")}', this.checked)">
                    <div class="file-info" onclick="loadFile('${f.name.replace(/'/g, "\\'")}')">
                        <span class="file-name">${f.name}${f.is_done ? '<span class="file-badge badge-done">Đã dịch</span>' : ''}</span>
                        <span class="file-size">${f.size_display}</span>
                    </div>
                    <div class="file-actions">
                        <button class="btn btn-sm btn-warning" onclick="event.stopPropagation(); translateSingleFile('${f.path.replace(/'/g, "\\'")}')">Dịch</button>
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
            const container = document.getElementById('done-list');
            if (files.length === 0) {
                container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Chưa có file đã dịch</p>';
                return;
            }
            
            container.innerHTML = files.map(f => {
                const locationBadge = f.location === 'output' ? '<span class="badge-pending" style="font-size: 0.7em; margin-left: 5px;">output</span>' : '<span class="badge-done" style="font-size: 0.7em; margin-left: 5px;">done</span>';
                return `<div class="file-item done-item">
                <div class="file-info" onclick="viewDoneFile('${f.name.replace(/'/g, "\\'")}', '${f.location}')">
                    <span class="file-name">${f.name} ${locationBadge} (${f.word_count?.toLocaleString() || 0} từ)</span>
                    <span class="file-size">${f.size_display}</span>
                </div>
                <div class="file-actions">
                    <button class="btn btn-sm" onclick="event.stopPropagation(); translateSingleFile('workspace/input/${f.name.replace(/'/g, "\\'")}', true)">Dịch lại</button>
                    ${f.location === 'done' ? `<button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); moveBackToInput('${f.name.replace(/'/g, "\\'")}')">↩</button>` : ''}
                    <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); viewDoneFile('${f.name.replace(/'/g, "\\'")}', '${f.location}')">Xem</button>
                </div>
            </div>`;
            }).join('');
        });
}

function toggleFile(path, checked) {
    if (checked) {
        selectedFiles.add(path);
    } else {
        selectedFiles.delete(path);
    }
    updateSelectedCount();
}

function updateSelectedCount() {
    document.getElementById('selected-count').textContent = selectedFiles.size;
}

function selectAll() {
    const checkboxes = document.querySelectorAll('#file-list input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.checked = true;
        const fileItem = cb.closest('.file-item');
        const fileName = fileItem.querySelector('.file-info').getAttribute('onclick').match(/'([^']+)'/)[1];
        selectedFiles.add('workspace/input/' + fileName);
    });
    updateSelectedCount();
}

function deselectAll() {
    selectedFiles.clear();
    const checkboxes = document.querySelectorAll('#file-list input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
    updateSelectedCount();
}

function translateSelected() {
    if (selectedFiles.size === 0) {
        alert('Vui lòng chọn ít nhất 1 file!');
        return;
    }
    
    const files = Array.from(selectedFiles);
    const btn = event.target;
    btn.disabled = true;
    btn.innerHTML = '🔄 Đang dịch... ';
    
    document.getElementById('progress-container').classList.add('active');
    document.getElementById('log-container').classList.add('active');
    document.getElementById('log-container').innerHTML = '';
    
    addLog(`Bắt đầu dịch ${files.length} file...`, 'info');
    
    fetch('/api/translate-batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            files: files,
            model: document.getElementById('model').value,
            input_lang: document.getElementById('input-lang').value,
            temperature: parseFloat(document.getElementById('temperature').value),
            chunk_size: parseInt(document.getElementById('chunk-size').value),
            use_cache: document.getElementById('use-cache').checked,
            prompts: {
                main: document.getElementById('prompt-main-text').value,
                retranslate: document.getElementById('prompt-retranslate-text').value,
                correction: document.getElementById('prompt-correction-text').value
            }
        })
    }).then(r => r.json()).then(data => {
        if (data.error) {
            addLog(data.error, 'error');
            btn.disabled = false;
            btn.innerHTML = '🚀 Dịch file đã chọn';
        } else {
            connectToProgress();
        }
    }).catch(e => {
        addLog(e.message, 'error');
        btn.disabled = false;
        btn.innerHTML = '🚀 Dịch file đã chọn';
    });
}

function translateSingleFile(filepath, isRetranslate = false) {
    const btn = event.target;
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '...';
    }
    
    document.getElementById('progress-container').classList.add('active');
    document.getElementById('log-container').classList.add('active');
    document.getElementById('log-container').innerHTML = '';
    
    addLog(`Bắt đầu dịch file...`, 'info');
    
    fetch('/api/translate-file', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            filepath: filepath,
            model: document.getElementById('model').value,
            input_lang: document.getElementById('input-lang').value,
            temperature: parseFloat(document.getElementById('temperature').value),
            chunk_size: parseInt(document.getElementById('chunk-size').value),
            use_cache: document.getElementById('use-cache').checked,
            prompts: {
                main: document.getElementById('prompt-main-text').value,
                retranslate: document.getElementById('prompt-retranslate-text').value,
                correction: document.getElementById('prompt-correction-text').value
            }
        })
    }).then(r => r.json()).then(data => {
        if (data.error) {
            addLog(data.error, 'error');
            if (btn) { btn.disabled = false; btn.innerHTML = 'Dịch'; }
        } else {
            connectToProgress();
        }
    }).catch(e => {
        addLog(e.message, 'error');
        if (btn) { btn.disabled = false; btn.innerHTML = 'Dịch'; }
    });
}

function loadFile(filename) {
    fetch('/api/file/' + encodeURIComponent(filename))
        .then(r => r.json())
        .then(data => {
            const textarea = document.getElementById('source-text');
            textarea.value += (textarea.value ? '\n\n' : '') + data.content;
            addLog('Đã tải: ' + data.name, 'info');
        })
        .catch(e => addLog('Lỗi: ' + e.message, 'error'));
}

function loadDoneFile(filename) {
    fetch('/api/done/' + encodeURIComponent(filename))
        .then(r => r.json())
        .then(data => {
            const textarea = document.getElementById('source-text');
            textarea.value += (textarea.value ? '\n\n' : '') + data.content;
            addLog('Đã tải: ' + data.name, 'info');
        })
        .catch(e => addLog('Lỗi: ' + e.message, 'error'));
}

function viewDoneFile(filename, location) {
    const endpoint = location === 'output' 
        ? '/api/output-file/' + encodeURIComponent(filename)
        : '/api/done/' + encodeURIComponent(filename);
    fetch(endpoint)
        .then(r => r.json())
        .then(data => {
            document.getElementById('done-text').value = data.content;
            currentDoneFile = filename;
            document.getElementById('done-result-container').classList.remove('active');
            addDoneLog('Đã tải: ' + filename + ' (' + location + ')', 'info');
        })
        .catch(e => addDoneLog('Lỗi: ' + e.message, 'error'));
}


function addDoneLog(message, type) {
    const container = document.getElementById('done-log-container');
    container.classList.add('active');
    const entry = document.createElement('div');
    entry.className = 'log-entry ' + type;
    entry.textContent = '[' + new Date().toLocaleTimeString() + '] ' + message;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function showDoneProgress(percent, text) {
    document.getElementById('done-progress-container').classList.add('active');
    document.getElementById('done-progress-fill').style.width = percent + '%';
    document.getElementById('done-progress-fill').textContent = percent + '%';
    document.getElementById('done-progress-text').textContent = text;
}

function hideDoneProgress() {
    document.getElementById('done-progress-container').classList.remove('active');
}

function runRetranslate() {
    const text = document.getElementById('done-text').value;
    if (!text.trim()) {
        addDoneLog('Chưa có nội dung để dịch lại', 'error');
        return;
    }
    runTranslationProcess(text, 'retranslate');
}

function runCorrection() {
    const text = document.getElementById('done-text').value;
    if (!text.trim()) {
        addDoneLog('Chưa có nội dung để sửa', 'error');
        return;
    }
    runTranslationProcess(text, 'correction');
}

function runBoth() {
    const text = document.getElementById('done-text').value;
    if (!text.trim()) {
        addDoneLog('Chưa có nội dung để xử lý', 'error');
        return;
    }
    addDoneLog('Bắt đầu Retranslate...', 'info');
    runTranslationProcess(text, 'retranslate', () => {
        addDoneLog('Tiếp tục Correction...', 'info');
        const retanslatedText = document.getElementById('done-result-text').value;
        runTranslationProcess(retanslatedText, 'correction', null, true);
    });
}

function runTranslationProcess(text, mode, callback, appendResult) {
    const model = document.getElementById('model').value;
    const temperature = parseFloat(document.getElementById('temperature').value);
    const chunkSize = parseInt(document.getElementById('chunk-size').value);
    
    showDoneProgress(0, 'Đang chuẩn bị...');
    addDoneLog('Bắt đầu ' + (mode === 'retranslate' ? 'Retranslate' : 'Correction') + '...', 'info');
    
    fetch('/api/translate-text', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            text: text,
            mode: mode,
            prompts: prompts,
            model: model,
            temperature: temperature,
            chunk_size: chunkSize,
            input_lang: document.getElementById('input-lang').value
        })
    }).then(r => r.json()).then(data => {
        if (data.error) {
            addDoneLog('Lỗi: ' + data.error, 'error');
            hideDoneProgress();
            return;
        }
        
        if (data.chunks && data.chunks.length > 0) {
            let processed = 0;
            data.chunks.forEach((chunk, i) => {
                fetch('/api/translate-chunk', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        chunk: chunk,
                        mode: mode,
                        prompts: prompts,
                        model: model,
                        temperature: temperature,
                        input_lang: document.getElementById('input-lang').value
                    })
                }).then(r => r.json()).then(result => {
                    processed++;
                    const percent = Math.round((processed / data.chunks.length) * 100);
                    showDoneProgress(percent, 'Đang xử lý: ' + processed + '/' + data.chunks.length);
                    
                    if (processed === data.chunks.length) {
                        hideDoneProgress();
                        const finalText = data.full_text || result.translated;
                        if (appendResult) {
                            document.getElementById('done-text').value = finalText;
                        } else {
                            document.getElementById('done-result-text').value = finalText;
                        }
                        document.getElementById('done-result-container').classList.add('active');
                        addDoneLog(mode === 'retranslate' ? 'Retranslate hoàn tất!' : 'Correction hoàn tất!', 'success');
                        if (callback) callback();
                    }
                });
            });
        } else {
            hideDoneProgress();
            if (appendResult) {
                document.getElementById('done-text').value = data.translated || text;
            } else {
                document.getElementById('done-result-text').value = data.translated || text;
            }
            document.getElementById('done-result-container').classList.add('active');
            addDoneLog(mode === 'retranslate' ? 'Retranslate hoàn tất!' : 'Correction hoàn tất!', 'success');
            if (callback) callback();
        }
    }).catch(e => {
        addDoneLog('Lỗi: ' + e.message, 'error');
        hideDoneProgress();
    });
}

function copyDoneResult() {
    const text = document.getElementById('done-result-text').value;
    navigator.clipboard.writeText(text).then(() => {
        addDoneLog('Đã copy vào clipboard', 'success');
    }).catch(() => {
        addDoneLog('Lỗi copy', 'error');
    });
}

function downloadDoneResult() {
    const text = document.getElementById('done-result-text').value;
    if (!text) {
        addDoneLog('Không có nội dung để tải', 'error');
        return;
    }
    const filename = currentDoneFile ? currentDoneFile.replace('.txt', '_fixed.txt') : 'translated_fixed.txt';
    const blob = new Blob([text], {type: 'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    addDoneLog('Đã tải: ' + filename, 'success');
}

function moveBackToInput(filename) {
    if (!confirm('Di chuyển file này về input?')) return;
    fetch('/api/move-back-to-input', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({filename: filename})
    }).then(r => r.json()).then(data => {
        if (data.success) {
            loadFiles();
            loadDoneFiles();
            addLog('Đã di chuyển file về input', 'success');
        }
    });
}

function loadOutputFiles() {
    fetch('/api/output-files')
        .then(r => r.json())
        .then(files => {
            const container = document.getElementById('output-list');
            if (files.length === 0) {
                container.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">Chưa có file</p>';
                return;
            }
            container.innerHTML = files.map(f => '<div class="output-item"><span>'+f.name+'</span><a href="/api/download/'+f.name+'" target="_blank">Tải</a></div>').join('');
        });
}

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
    fetch('/api/cache/clear', {method: 'POST'}).then(r => r.json()).then(data => {
        alert('Đã xóa ' + data.deleted + ' files');
        loadStats();
    });
}

function loadPromptsForLang(lang) {
    fetch('/api/prompts?lang=' + lang).then(r => r.json()).then(data => {
        prompts = data;
        document.getElementById('prompt-main-text').value = data.main || '';
        document.getElementById('prompt-retranslate-text').value = data.retranslate || '';
        document.getElementById('prompt-correction-text').value = data.correction || '';
    });
}

function switchPromptTab(tab) {
    document.querySelectorAll('.prompt-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.prompt-editor').forEach(e => e.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('prompt-' + tab).classList.add('active');
}

function savePrompts() {
    const lang = document.getElementById('input-lang').value;
    fetch('/api/prompts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            lang: lang,
            prompts: {
                main: document.getElementById('prompt-main-text').value,
                retranslate: document.getElementById('prompt-retranslate-text').value,
                correction: document.getElementById('prompt-correction-text').value
            }
        })
    }).then(r => r.json()).then(data => {
        alert(data.success ? 'Đã lưu prompts!' : 'Lỗi: ' + data.error);
    });
}

function startTranslation() {
    const btn = document.getElementById('translate-btn');
    const text = document.getElementById('source-text').value;
    if (!text.trim()) return alert('Vui lòng nhập văn bản!');
    
    btn.disabled = true;
    btn.innerHTML = '🔄 Đang dịch... <span class="loading"></span>';
    
    document.getElementById('progress-container').classList.add('active');
    document.getElementById('result-container').classList.remove('active');
    document.getElementById('log-container').classList.add('active');
    document.getElementById('log-container').innerHTML = '';
    
    addLog('Bắt đầu dịch nội dung...', 'info');
    
    fetch('/api/translate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            text: text,
            model: document.getElementById('model').value,
            input_lang: document.getElementById('input-lang').value,
            temperature: parseFloat(document.getElementById('temperature').value),
            chunk_size: parseInt(document.getElementById('chunk-size').value),
            use_cache: document.getElementById('use-cache').checked,
            prompts: {
                main: document.getElementById('prompt-main-text').value,
                retranslate: document.getElementById('prompt-retranslate-text').value,
                correction: document.getElementById('prompt-correction-text').value
            }
        })
    }).then(r => r.json()).then(data => {
        if (data.error) {
            addLog(data.error, 'error');
            resetButton(btn);
        } else {
            connectToProgress(btn);
        }
    }).catch(e => {
        addLog(e.message, 'error');
        resetButton(btn);
    });
}

function connectToProgress(btn = null) {
    const evtSource = new EventSource('/api/progress');
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-text').textContent = 'Đang kết nối...';
    
    evtSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        if (data.type === 'progress') {
            const percent = data.percent;
            document.getElementById('progress-fill').style.width = percent + '%';
            document.getElementById('progress-fill').textContent = percent + '%';
            document.getElementById('progress-text').textContent = data.message;
            
        } else if (data.type === 'log') {
            addLog(data.message, data.level);
            
        } else if (data.type === 'complete') {
            evtSource.close();
            document.getElementById('progress-text').textContent = 'Hoàn tất!';
            document.getElementById('progress-fill').style.width = '100%';
            
            if (data.output_file) {
                currentOutputFile = data.output_file;
                document.getElementById('result-text').value = "Đã lưu vào file: " + data.output_file;
            } else {
                document.getElementById('result-text').value = data.translated_text || '';
            }
            
            document.getElementById('result-container').classList.add('active');
            
            let statsHtml = `
                <span class="result-stat">⏱️ ${data.duration?.toFixed(1) || 0}s</span>
                <span class="result-stat">💬 ${data.chunks_count || 0} chunks</span>
                <span class="result-stat">🔤 ${data.char_count?.toLocaleString() || 0} chars</span>
            `;
            if (data.api_key_used) statsHtml += `<span class="result-stat">🔑 ${data.api_key_used}</span>`;
            document.getElementById('result-stats').innerHTML = statsHtml;
            
            resetButton(btn);
            loadOutputFiles();
            loadStats();
            loadFiles();
            loadDoneFiles();
        } else if (data.type === 'error') {
            evtSource.close();
            addLog(data.message, 'error');
            resetButton(btn);
        }
    };
    
    evtSource.onerror = function() {
        evtSource.close();
    };
}

function addLog(message, type) {
    const container = document.getElementById('log-container');
    container.classList.add('active');
    const entry = document.createElement('div');
    entry.className = 'log-entry ' + type;
    entry.textContent = '[' + new Date().toLocaleTimeString() + '] ' + message;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function resetButton(btn) {
    if (!btn) btn = document.getElementById('translate-btn');
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '🚀 Bắt đầu dịch';
        
        const fileBtns = document.querySelectorAll('.btn-warning');
        fileBtns.forEach(b => {
            if (b.innerHTML === '...') {
                b.disabled = false;
                b.innerHTML = 'Dịch';
            }
        });
        
        const batchBtn = document.querySelector('.btn-success');
        if (batchBtn && batchBtn.disabled) {
            batchBtn.disabled = false;
            batchBtn.innerHTML = '🚀 Dịch file đã chọn';
        }
    }
}

function copyResult() {
    const text = document.getElementById('result-text').value;
    navigator.clipboard.writeText(text).then(() => {
        addLog('Đã copy vào clipboard', 'success');
    }).catch(() => {
        addLog('Lỗi copy', 'error');
    });
}

function downloadResult() {
    if (currentOutputFile) {
        window.open('/api/download/' + currentOutputFile, '_blank');
    }
}
