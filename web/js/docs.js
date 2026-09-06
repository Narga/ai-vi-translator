// --- Tab Tài liệu: đọc docs nội bộ, không rời app (xem docs/18 §5) ---
// Viewer CHỈ đọc source (.md render, còn lại <pre>) — không render HTML (bất biến an ninh).
let _docFiles = [];
async function loadDocList() {
    const list = $('docList');
    if (!list) return;
    try {
        _docFiles = await fetch('/api/docs').then(J);
    } catch (e) { list.innerHTML = ''; list.textContent = 'Lỗi tải danh sách: ' + e.message; return; }
    if (!_docFiles.length) { list.innerHTML = ''; list.textContent = 'Không có tài liệu nào.'; return; }
    renderDocList(_docFiles);
}
function renderDocList(files) {
    const list = $('docList');
    const groups = {};
    files.forEach(f => { const d = f.dir || ''; (groups[d] = groups[d] || []).push(f); });
    list.innerHTML = '';
    const mkBtn = f => {
        const b = document.createElement('button');
        b.className = 'doc-item';
        b.textContent = (f.ext === '.md' ? '📝 ' : f.ext === '.html' ? '🌐 ' : '📄 ') + f.name;
        b.title = f.path;
        b.onclick = () => loadDoc(f.path, b);
        return b;
    };
    (groups[''] || []).forEach(f => list.appendChild(mkBtn(f)));
    Object.keys(groups).sort().forEach(d => {
        if (!d) return;
        const h = document.createElement('p');
        h.className = 'doc-dir'; h.textContent = d;
        list.appendChild(h);
        groups[d].forEach(f => list.appendChild(mkBtn(f)));
    });
}
function filterDocs() {
    const kw = ($('docFilter').value || '').toLowerCase().trim();
    if (!kw) { renderDocList(_docFiles); return; }
    renderDocList(_docFiles.filter(f =>
        f.name.toLowerCase().includes(kw) || f.path.toLowerCase().includes(kw)));
}
async function loadDoc(path, btn) {
    document.querySelectorAll('.doc-item').forEach(x => x.classList.remove('on'));
    if (btn) btn.classList.add('on');
    const title = $('docTitle'), sub = $('docPath'), body = $('docBody');
    title.textContent = path.split('/').pop();
    sub.textContent = path;
    body.innerHTML = '';
    const wait = document.createElement('p');
    wait.textContent = '⏳ Đang tải…';
    body.appendChild(wait);
    let d;
    try {
        d = await fetch('/api/docs/content?path=' + encodeURIComponent(path)).then(J);
    } catch (e) {
        body.innerHTML = '';
        const p = document.createElement('p');
        p.className = 'err'; p.textContent = 'Lỗi: ' + e.message;
        body.appendChild(p); return;
    }
    body.innerHTML = '';
    if (d.ext === '.md') {
        try {
            await loadScriptOnce('vendor/marked.min.js');
            await loadScriptOnce('vendor/dompurify.min.js');
        } catch (e) { toast(e.message, true); return; }
        const div = document.createElement('div');
        div.className = 'doc-markdown';
        div.innerHTML = DOMPurify.sanitize(marked.parse(d.content));
        body.appendChild(div);
    } else {
        const pre = document.createElement('pre');
        pre.style.whiteSpace = 'pre-wrap';
        pre.textContent = d.content; // source thô, không render HTML
        body.appendChild(pre);
    }
    body.scrollTop = 0;
}
