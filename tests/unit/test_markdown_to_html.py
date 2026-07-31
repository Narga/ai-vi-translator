"""Tests for the canonical Markdown → XHTML converter.

Contract: one engine (python-markdown) serves both the UI `.MD → HTML` task
and the `markdown_to_epub` route, so output is deterministic and parseable.
"""

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from plugins.epub_converter.services.text_converter import (
    convert_markdown_file,
    markdown_body_to_html,
    markdown_text_to_html_document,
)


def assert_xml_parseable(xhtml: str):
    body = xhtml.replace("<!DOCTYPE html>", "")
    ET.fromstring(body)  # raises on malformed XML


class TestMarkdownBody:
    def test_nested_list(self):
        out = markdown_body_to_html("- a\n    - b")
        assert out.count("<ul>") == 2
        assert "<li>a" in out

    def test_table(self):
        out = markdown_body_to_html("| A | B |\n|---|---|\n| 1 | 2 |")
        assert "<table>" in out and "<td>2</td>" in out

    def test_image_with_title(self):
        out = markdown_body_to_html('![alt](img/a.png "Title")')
        assert 'src="img/a.png"' in out
        assert 'alt="alt"' in out
        assert 'title="Title"' in out

    def test_strikethrough_not_promised(self):
        # Contract decision: ~~x~~ is NOT rendered as <del> (keep literal);
        # documented in plan §11 as needing an explicit dialect choice.
        out = markdown_body_to_html("~~gone~~")
        assert "gone" in out  # no silent wrapping

    def test_inline_code_not_formattted(self):
        out = markdown_body_to_inline_safe("`**not bold**`")
        assert "**not bold**" in out  # asterisks stay literal inside code

    def test_heading_levels(self):
        out = markdown_body_to_html("# H1\n\n### H3")
        assert "<h1>H1</h1>" in out
        assert "<h3>H3</h3>" in out

    def test_missing_markdown_dependency(self, monkeypatch):
        import plugins.epub_converter.services.text_converter as tc

        monkeypatch.setattr(tc, "HAS_MARKDOWN", False)
        with pytest.raises(ImportError, match="markdown"):
            markdown_body_to_html("x")


def markdown_body_to_inline_safe(md: str) -> str:
    # tiny helper for inline-only assertions
    return markdown_body_to_html(md)


class TestMarkdownDocument:
    def test_document_is_valid_xhtml(self):
        doc = markdown_text_to_html_document(
            "# Chương 1\n\nĐoạn có **đậm** và [liên kết](chap2.xhtml#s1).",
            "Chương 1",
        )
        assert_xml_parseable(doc)
        assert 'lang="vi"' in doc
        assert "<title>Chương 1</title>" in doc

    def test_title_escaped(self):
        doc = markdown_text_to_html_document("nội dung", '<b>"x"</b>')
        assert "&lt;b&gt;&quot;x&quot;&lt;/b&gt;" in doc
        assert_xml_parseable(doc)

    def test_unicode_preserved(self):
        doc = markdown_text_to_html_document("漢字《かな》 và ngữ", "T")
        assert "漢字《かな》 và ngữ" in doc


class TestConvertMarkdownFile:
    def test_writes_html_output(self, tmp_path):
        src = tmp_path / "chap.md"
        src.write_text("# A\n\nText.", encoding="utf-8")
        out = convert_markdown_file(src)
        assert out.suffix == ".html"
        assert_xml_parseable(out.read_text(encoding="utf-8"))

    def test_delete_source_only_when_different_path(self, tmp_path):
        src = tmp_path / "chap.md"
        src.write_text("# A", encoding="utf-8")
        out = convert_markdown_file(src, delete_source=True)
        assert out.exists()
        assert not src.exists()

    def test_no_delete_keeps_source(self, tmp_path):
        src = tmp_path / "chap.md"
        src.write_text("# A", encoding="utf-8")
        convert_markdown_file(src, delete_source=False)
        assert src.exists()

    def test_same_suffix_no_clobber(self, tmp_path):
        # Input .html converted to .html → writes to .converted.html
        src = tmp_path / "chap.html"
        src.write_text("# not really html but name collides", encoding="utf-8")
        out = convert_markdown_file(src)
        assert out.name == "chap.converted.html"
        assert src.exists()  # source untouched

    def test_reject_output_same_as_input(self, tmp_path):
        from plugins.epub_converter.services.text_converter import convert_html_file

        src = tmp_path / "chap.html"
        src.write_text("<p>x</p>", encoding="utf-8")
        with pytest.raises(ValueError, match="đích trùng với nguồn"):
            convert_html_file(src, src)
        assert src.read_text(encoding="utf-8") == "<p>x</p>"  # source not touched

    def test_md_to_html_reject_same_path(self, tmp_path):
        src = tmp_path / "chap.md"
        src.write_text("# A", encoding="utf-8")
        with pytest.raises(ValueError, match="đích trùng với nguồn"):
            convert_markdown_file(src, src)
