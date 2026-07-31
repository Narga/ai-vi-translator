"""Regression tests for HTML → Markdown conversion contract.

Covers the issues documented in docs/wip/plan_2026-07-31_html-to-markdown-audit.md:
- html2text import must not break module import when the extra is absent.
- post_clean must not strip image alt text.
- convert_html_to_markdown must propagate errors instead of writing a
  sentinel string into the output file.
- normalize_html_file must not create an output file on conversion failure.
"""

import importlib
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# P0: dependency contract
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_epub2text_module():
    """Keep the converter module in a clean state after import-mutation tests."""
    yield
    import plugins.epub_converter.epub_to_text.epub2text as _m

    importlib.reload(_m)


def test_epub2text_module_imports_without_html2text(monkeypatch):
    """Module import must not fail even when the epub extra is not installed."""
    monkeypatch.setitem(sys.modules, "html2text", None)
    mod = importlib.import_module(
        "plugins.epub_converter.epub_to_text.epub2text"
    )
    reloaded = importlib.reload(mod)
    assert reloaded.HAS_HTML2TEXT is False


def test_convert_html_to_markdown_raises_on_missing_html2text(monkeypatch):
    mod = importlib.import_module("plugins.epub_converter.epub_to_text.epub2text")
    monkeypatch.setattr(mod, "HAS_HTML2TEXT", False)
    with pytest.raises(ImportError, match="html2text"):
        mod.convert_html_to_markdown("<p>x</p>")


# ---------------------------------------------------------------------------
# P1a: alt text preservation
# ---------------------------------------------------------------------------


def test_post_clean_preserves_image_alt_text():
    from core.source_normalizer import post_clean

    md = "Mô tả ảnh:\n\n![Bìa truyện](images/cover.jpg)\n\nTiếp theo."
    assert "![Bìa truyện](images/cover.jpg)" in post_clean(md)


def test_post_clean_inline_reference_links_still_work():
    from core.source_normalizer import post_clean

    md = "Xem [tại đây] [1].\n\n[1]: https://example.com/page"
    assert "[tại đây](https://example.com/page)" in post_clean(md)


# ---------------------------------------------------------------------------
# P1b: error propagation instead of sentinel string
# ---------------------------------------------------------------------------


def test_normalize_html_file_raises_on_conversion_error(tmp_path, monkeypatch):
    """Output file must not be created when conversion fails."""
    import core.source_normalizer as sn

    src = tmp_path / "chapter.html"
    src.write_text("<html><body><p>Nội dung</p></body></html>", encoding="utf-8")

    def boom(html, preserve_underline=False):
        raise ValueError("boom")

    monkeypatch.setattr(sn, "convert_html_to_markdown", boom)

    with pytest.raises(ValueError, match="boom"):
        sn.normalize_html_file(str(src))

    assert not (tmp_path / "chapter.md").exists()


# ---------------------------------------------------------------------------
# Round-trip: full pipeline keeps semantic content
# ---------------------------------------------------------------------------


def test_normalize_html_file_end_to_end(tmp_path):
    from core.source_normalizer import normalize_html_file

    src = tmp_path / "chapter.html"
    src.write_text(
        """
<html><head><title>T</title><style>body{color:red}</style></head>
<body>
<h1>Chương 1</h1>
<p>Đoạn <b>đậm</b> và <i>nghiêng</i>.</p>
<p><img src="img/a.png" alt="Minh họa chương 1"/></p>
<!-- comment -->
</body></html>
""".strip(),
        encoding="utf-8",
    )

    out = Path(normalize_html_file(str(src)))
    assert out.exists()
    md = out.read_text(encoding="utf-8")
    assert "# Chương 1" in md
    assert "**đậm**" in md
    assert "Minh họa chương 1" in md  # alt text preserved
    assert "img/a.png" in md
    assert "<!--" not in md
    assert "color:red" not in md  # style stripped
