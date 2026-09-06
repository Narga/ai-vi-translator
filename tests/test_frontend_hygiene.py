"""Khóa vệ sinh frontend: dữ liệu ngoài vào innerHTML/href phải qua esc()/safeHref()."""

import hashlib
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JS_DIR = REPO / "web" / "js"
VENDOR_DIR = REPO / "web" / "vendor"
INDEX_HTML = REPO / "web" / "index.html"

# sha256 đã ghi CHANGELOG — vendor bị đổi ngoài ý muốn là test đỏ ngay
VENDOR_HASHES = {
    "marked.min.js": "69451c8541c9c1e7a4bf3ffc6f73c4d89633de92bfbe3e484dfe182ef8091f88",
    "dompurify.min.js": "f263b05369e050fa175d4ecb9c9358eb4253602d510297adfb31df48b2f1c4d5",
    "diff_match_patch.js": "9a79cf031ac7c2e366416181051acb3e6d2cacf79c5354148f4c71ea20c7e4a3",
}

# ID do JS tự tạo lúc chạy (không có trong HTML tĩnh) — allowlist kín, thêm mới phải ghi lý do
DYNAMIC_IDS = {"toast"}


def _all_js():
    return "".join((JS_DIR / f).read_text(encoding="utf-8") for f in sorted(
        p.name for p in JS_DIR.glob("*.js")))


def test_no_dangling_dom_references():
    html = INDEX_HTML.read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', html))
    used = set(re.findall(r"\$\('([^']+)'\)", _all_js()))
    dangling = {u for u in used if u not in ids} - DYNAMIC_IDS
    assert not dangling, f"JS trỏ ID không tồn tại trong HTML (gây TypeError chết script): {dangling}"


def _src(name):
    return (JS_DIR / name).read_text(encoding="utf-8")


def test_no_raw_provider_interpolation():
    s = _src("settings.js")
    assert '"${p.id}"' not in s and ">${p.name}<" not in s  # phải esc(p.id)/esc(p.name)
    assert "${esc(p.id)}" in s and "${esc(p.name)}" in s
    assert '"${d.quota_url}"' not in s and ".href=d.docs_url" not in s


def test_safehref_whitelist():
    s = _src("settings.js")
    assert "function safeHref" in s
    assert "https?" in s  # chỉ https? được qua, còn lại thành "#"
    assert 'safeHref(d.quota_url)' in s and 'safeHref(d.docs_url)' in s


def test_vendor_integrity():
    for name, want in VENDOR_HASHES.items():
        p = VENDOR_DIR / name
        assert p.exists(), f"thiếu web/vendor/{name} (commit kèm theo manifesto §9)"
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        assert got == want, f"{name} đã bị thay đổi (muốn {want[:12]}…, thấy {got[:12]}…)"


def test_load_script_once_shared():
    s = _src("app.js")
    assert "function loadScriptOnce" in s  # vendor lazy-load, không <script defer> toàn app
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "vendor/" not in html  # không script vendor tĩnh trong index


def test_preview_wiring():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "openPreview('tSrc'" in html and "openPreview('tOut'" in html
    assert 'id="prevDlg"' in html and 'aria-labelledby="prevTitle"' in html
    assert 'aria-label="Đóng xem trước"' in html
    assert "js/preview.js" in html


def test_preview_safety():
    s = _src("preview.js")
    assert ".textContent" in s and ".value" not in s  # pane là div, đọc textContent
    assert "DOMPurify.sanitize(marked.parse(" in s  # markdown qua sanitize
    assert 'sandbox' in s and "allow-" not in s  # iframe câm, không allow-*
    assert 'referrerpolicy' in s
    assert "loadScriptOnce('vendor/marked.min.js')" in s
    # không gán raw filename/title/path vào innerHTML (targeted trên file mới)
    for pat in ("innerHTML = fname", "innerHTML = label", "innerHTML=`${fname",
                "innerHTML = title", "+ fname +", "+ label +"):
        assert pat not in s, f"preview.js chèn chuỗi động raw vào HTML: {pat}"


def test_docs_tab_wiring():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-v="docs"' in html and 'id="v-docs"' in html
    assert "js/docs.js" in html and "loadDocList()" in html
    assert 'id="docList"' in html and 'id="docBody"' in html


def test_docs_safety():
    s = _src("docs.js")
    # list/title/path dựng bằng DOM + textContent; innerHTML chỉ để xóa trắng
    # hoặc gán HTML đã qua DOMPurify.sanitize
    assert "document.createElement" in s and ".textContent" in s
    import re as _re
    non_empty = [m for m in _re.findall(r"\.innerHTML\s*=\s*([^;]+);", s)
                 if m.strip() not in ("''", '""')
                 and not m.strip().startswith("DOMPurify.sanitize(")]
    assert not non_empty, f"docs.js gán innerHTML không sanitize: {non_empty}"
    assert "DOMPurify.sanitize(marked.parse(" in s  # .md qua sanitize
    assert "loadScriptOnce('vendor/marked.min.js')" in s
    assert "<iframe" not in s  # viewer không render HTML (bất biến an ninh)


def test_workspace_toolbar_regroup():
    html = INDEX_HTML.read_text(encoding="utf-8")
    # preview/save per-editor trong hrow, không còn trong #wTools
    assert "openPreview('tSrc'" in html and "openPreview('tOut'" in html
    assert "saveSrc()" in html and "saveRes()" in html
    tools = html.split('id="wTools"')[1].split('id="wActions"')[0]
    assert "openPreview" not in tools and "saveTl()" not in tools
    assert "wsRenameSel" not in tools and "wsDelSel" not in tools and "fltToggle" not in tools
    assert "copyTl()" not in tools and "wrapTog()" not in tools and "findDlg" not in tools
    # header Kết quả: Wrap → Preview → Tìm kiếm → Diff → Copy → Save
    order = ["wrapTog()", "openPreview('tOut'", "findDlg.showModal()",
             "openDiff()", "copyTl()", "saveRes()"]
    idx = [html.index(x) for x in order]
    assert idx == sorted(idx), "thứ tự nút header Kết quả sai"
    # khối actions căn phải, đúng thứ tự Gửi → Hủy → Dịch lại → Xóa trắng
    acts = html.split('id="wActions"')[1].split("</span>")[0]
    ai = [acts.index(x) for x in ("sendOpen()", "cancelTl()", "retryTl()", "clearTl()")]
    assert ai == sorted(ai), "thứ tự khối actions sai"
    assert "#wActions{margin-left:auto" in open(REPO / "web" / "css" / "app.css").read()
    # +prompts dropdown + info luôn hiện (workspace không còn <details>)
    ws = html.split('id="v-workspace"')[1].split('id="v-prompts"')[0]
    assert "<details" not in ws
    assert 'id="wExtraBtn"' in html and 'id="wExtraPanel"' in html
    assert 'id="wInfoBar"' in html and 'id="wExtraEst"' in html and 'id="wFileInfo"' in html
    # filter panel neo dưới nút (relative wrapper), label mỗi dòng
    assert "flt-h" in html and html.index('id="fltPanel"') > html.index('id="fltToolBtn"')
    assert "position:relative" in html
    # tab Tài liệu tự nạp khi mở (app.js gọi; sidebar không onclick inline vì bị ghi đè)
    assert '<button data-v="docs">' in html
    assert 'onclick="loadDocList()"' in html  # chỉ còn nút ↻ refresh tay
    assert "loadDocList()" in open(REPO / "web" / "js" / "app.js").read()
    # lọc/đổi tên/xóa cùng dòng tiêu đề Tập tin, đúng thứ tự
    i_f, i_r, i_d = html.index("fltToggle"), html.index("wsRenameSel"), html.index("wsDelSel")
    assert i_f < i_r < i_d
    assert "js/batch.js" in html  # helper skip dùng chung


def test_diff_wiring_and_safety():
    import re as _re
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "openDiff()" in html and 'id="diffDlg"' in html
    assert 'aria-labelledby="diffTitle"' in html and 'aria-label="Đóng so sánh"' in html
    assert "js/diff.js" in html
    s = _src("diff.js")
    assert "document.createElement" in s and ".textContent" in s
    non_empty = [m for m in _re.findall(r"\.innerHTML\s*=\s*([^;]+);", s)
                 if m.strip() not in ("''", '""')]
    assert not non_empty, f"diff.js gán innerHTML không rỗng: {non_empty}"
    assert "loadScriptOnce('vendor/diff_match_patch.js')" in s
    assert "diff_linesToChars_" in s and "Diff_Timeout" in s
    assert "<iframe" not in s
    assert 'id="diffWrapBtn"' in html and "diffWrapTog()" in s  # wrap content cạnh chọn cột
