// --- So sánh nguồn ↔ kết quả: từng dòng, 2 cột / liền mạch (xem docs/18 Task F) ---
// Thuật toán: diff-match-patch line-mode (vendor, lazy-load). Render bằng DOM +
// textContent từng dòng — không innerHTML chuỗi động.
let _diffRows = null; // [{t:'='|'-'|'+', a:num|null, b:num|null, text}]
let _diffMode = 'side';

async function openDiff() {
    const a = $('tSrc') ? $('tSrc').textContent : '';
    const b = $('tOut') ? $('tOut').textContent : '';
    if (!a.trim() && !b.trim()) { toast('Cả hai editor đều trống.', true); return; }
    if (a.length + b.length > 500 * 1024) { toast('Nội dung quá lớn (>500KB), không so sánh.', true); return; }
    try {
        await loadScriptOnce('vendor/diff_match_patch.js');
    } catch (e) { toast(e.message, true); return; }
    const fname = (typeof _wsSrc !== 'undefined' && _wsSrc) ? _wsSrc : '';
    $('diffSub').textContent = (fname ? fname + ' • ' : '') + 'Nguồn ↔ Kết quả';
    _diffRows = diffRows(a, b);
    paintDiff();
    const prevBtn = document.activeElement;
    diffDlg.showModal();
    $('diffClose').focus();
    diffDlg.onclose = () => { if (prevBtn && prevBtn.focus) prevBtn.focus(); };
}

function diffRows(a, b) {
    const dmp = new diff_match_patch();
    dmp.Diff_Timeout = 2; // nguồn↔dịch khác ngôn ngữ → diff lớn, chặn blowup
    const lc = dmp.diff_linesToChars_(a, b);
    const diffs = dmp.diff_main(lc.chars1, lc.chars2, false);
    dmp.diff_charsToLines_(diffs, lc.lineArray);
    const rows = [];
    let na = 0, nb = 0;
    diffs.forEach(d => {
        const op = d[0], lines = d[1].split('\n');
        if (lines.length && lines[lines.length - 1] === '') lines.pop();
        lines.forEach(ln => {
            if (op === 0) { na++; nb++; rows.push({ t: '=', a: na, b: nb, text: ln }); }
            else if (op === -1) { na++; rows.push({ t: '-', a: na, b: null, text: ln }); }
            else { nb++; rows.push({ t: '+', a: null, b: nb, text: ln }); }
        });
    });
    return rows;
}

function diffMode(m) {
    _diffMode = m;
    $('diffModeSide').className = 'btn' + (m === 'side' ? ' pri' : '');
    $('diffModeUni').className = 'btn' + (m === 'uni' ? ' pri' : '');
    paintDiff();
}

// Wrap dòng dài trong bảng diff (mặc định BẬT để dễ đọc; tắt khi cần dò cột)
let _diffWrap = true;
function diffWrapTog() {
    _diffWrap = !_diffWrap;
    $('diffWrapBtn').className = 'btn' + (_diffWrap ? ' pri' : '');
    paintDiff();
}

function paintDiff() {
    const body = $('diffBody');
    body.innerHTML = '';
    if (!_diffRows || !_diffRows.length) {
        const p = document.createElement('p');
        p.textContent = 'Hai bên giống nhau hoàn toàn.';
        body.appendChild(p); return;
    }
    const table = document.createElement('table');
    table.className = 'table-minimal diff-tbl' + (_diffWrap ? '' : ' nowrap');
    const nEq = _diffRows.filter(r => r.t === '=').length;
    const nCh = _diffRows.length - nEq;
    if (_diffMode === 'side') {
        // Gom cặp -/+ liền kề thành 1 hàng 2 cột (so như Novel Translator)
        const merged = [];
        for (let i = 0; i < _diffRows.length; i++) {
            const r = _diffRows[i];
            if (r.t === '=') { merged.push({ l: r, r: r }); continue; }
            const dels = [], inss = [];
            while (i < _diffRows.length && _diffRows[i].t !== '=') {
                if (_diffRows[i].t === '-') dels.push(_diffRows[i]);
                else inss.push(_diffRows[i]);
                i++;
            }
            i--;
            const n = Math.max(dels.length, inss.length);
            for (let k = 0; k < n; k++) merged.push({ l: dels[k] || null, r: inss[k] || null });
        }
        merged.forEach(m => {
            const tr = document.createElement('tr');
            tr.appendChild(diffCell(m.l, 'a'));
            tr.appendChild(diffCell(m.r, 'b'));
            table.appendChild(tr);
        });
    } else {
        _diffRows.forEach(r => {
            const tr = document.createElement('tr');
            const tag = r.t === '=' ? '' : r.t === '-' ? '− ' : '+ ';
            tr.appendChild(diffCell(r, tag ? 'u' : 'a'));
            if (tag) tr.firstChild.textContent = tag + tr.firstChild.textContent;
            table.appendChild(tr);
        });
    }
    const info = document.createElement('p');
    info.style.color = 'var(--text-muted)';
    info.textContent = `${_diffRows.length} dòng, ${nCh} dòng khác biệt — ${_diffMode === 'side' ? '2 cột' : 'liền mạch'}.`;
    body.appendChild(info);
    body.appendChild(table);
}

function diffCell(r, side) {
    const td = document.createElement('td');
    td.className = 'diff-' + (!r ? 'empty' : r.t === '=' ? 'eq' : r.t === '-' ? 'del' : 'add');
    if (!r) { td.textContent = ''; return td; }
    const no = side === 'a' ? r.a : side === 'b' ? r.b : (r.a || r.b);
    td.textContent = (no == null ? '' : no + ' ') + r.text;
    return td;
}
