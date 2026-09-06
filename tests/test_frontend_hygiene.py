"""Khóa vệ sinh frontend: dữ liệu ngoài vào innerHTML/href phải qua esc()/safeHref()."""

import re
from pathlib import Path

JS_DIR = Path(__file__).resolve().parent.parent / "web" / "js"
INDEX_HTML = Path(__file__).resolve().parent.parent / "web" / "index.html"

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
