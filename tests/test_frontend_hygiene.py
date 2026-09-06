"""Khóa vệ sinh frontend: dữ liệu ngoài vào innerHTML/href phải qua esc()/safeHref()."""

from pathlib import Path

JS_DIR = Path(__file__).resolve().parent.parent / "web" / "js"


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
