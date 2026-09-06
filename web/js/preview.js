// --- Preview Markdown/HTML on-demand (modal <dialog>, xem docs/18 §3) ---
// .md → marked + DOMPurify trong .doc-markdown; .html → iframe sandbox câm script.
// Mọi chuỗi động (title/filename) gán bằng textContent, KHÔNG innerHTML.
async function openPreview(paneId, label) {
    const pane = $(paneId);
    if (!pane) return;
    const text = pane.textContent || '';
    if (!text.trim()) { toast('Không có nội dung để preview', true); return; }
    const fname = (typeof _wsSrc !== 'undefined' && _wsSrc) ? _wsSrc
        : (typeof _wsRes !== 'undefined' && _wsRes) ? _wsRes : '';
    // 1. Nhận dạng định dạng: đuôi file trước, heuristic nội dung sau
    let format = 'markdown';
    if (fname) {
        const ext = (fname.split('.').pop() || '').toLowerCase();
        if (ext === 'md' || ext === 'markdown') format = 'markdown';
        else if (ext === 'html' || ext === 'htm' || ext === 'xhtml') format = 'html';
    } else {
        const hasDoc = /<!DOCTYPE html>|<html[\s>]|<body[\s>]/i.test(text);
        const nStruct = (text.match(/<(div|p|h[1-6]|section|article|table|ul|ol)[>\s]/gi) || []).length;
        if (hasDoc || nStruct >= 3) format = 'html';
    }
    // 2. Lazy-load vendor đúng nhánh cần
    try {
        await loadScriptOnce('vendor/marked.min.js');
        if (format === 'markdown') await loadScriptOnce('vendor/dompurify.min.js');
    } catch (e) { toast(e.message, true); return; }
    // 3. Dựng dialog (textContent cho mọi chuỗi động)
    const prevBtn = document.activeElement;
    $('prevTitle').textContent = 'Preview — ' + label;
    $('prevSub').textContent = (fname ? fname + ' • ' : '') + (format === 'html' ? 'HTML' : 'Markdown');
    const body = $('prevBody');
    body.innerHTML = '';
    if (format === 'markdown') {
        const div = document.createElement('div');
        div.className = 'doc-markdown';
        div.innerHTML = DOMPurify.sanitize(marked.parse(text));
        body.appendChild(div);
    } else {
        const fr = document.createElement('iframe');
        fr.setAttribute('sandbox', '');
        fr.setAttribute('referrerpolicy', 'no-referrer');
        fr.style.cssText = 'width:100%;height:60vh;border:none;display:block;';
        body.appendChild(fr);
        prevDlg.showModal();
        $('prevClose').focus();
        fr.srcdoc = text; // gán sau khi vào DOM (tránh timing issue)
        prevDlg.onclose = () => { if (prevBtn && prevBtn.focus) prevBtn.focus(); };
        return;
    }
    prevDlg.showModal();
    $('prevClose').focus();
    prevDlg.onclose = () => { if (prevBtn && prevBtn.focus) prevBtn.focus(); };
}
