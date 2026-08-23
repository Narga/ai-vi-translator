"""Tests for file_operations service: split_files + merge_files."""

from __future__ import annotations

import pytest
from pathlib import Path

from plugins.epub_converter.services.file_operations import (
    split_files,
    merge_files,
    SUPPORTED_SUFFIXES,
    _safe_project_file,
)


def _make_project(tmp_path: Path) -> Path:
    for section in ("sources", "translated", "spelling"):
        (tmp_path / section).mkdir(parents=True, exist_ok=True)
    return tmp_path


class TestSupportedSuffixes:
    def test_seven_suffixes(self):
        assert SUPPORTED_SUFFIXES == {".md", ".txt", ".html", ".htm", ".xhtml", ".json", ".csv"}


class TestSafeProjectFile:
    def test_valid_file(self, tmp_path):
        p = _make_project(tmp_path)
        f = p / "sources" / "a.md"
        f.write_text("x")
        result = _safe_project_file(p, "sources", "a.md")
        assert result == f.resolve()

    def test_path_traversal_rejected(self, tmp_path):
        p = _make_project(tmp_path)
        result = _safe_project_file(p, "sources", "../translated/a.md")
        assert result is None

    def test_not_a_file(self, tmp_path):
        p = _make_project(tmp_path)
        result = _safe_project_file(p, "sources", "missing.md")
        assert result is None

    def test_invalid_section(self, tmp_path):
        p = _make_project(tmp_path)
        result = _safe_project_file(p, "invalid", "a.md")
        assert result is None


class TestSplitFiles:
    def test_splits_using_chunker(self, tmp_path):
        p = _make_project(tmp_path)
        text = "Paragraph.\n\n" * 5000
        (p / "sources" / "big.md").write_text(text)
        result = split_files(p, "sources", ["big.md"], False, 1000, lambda m: None)
        assert result["status"] == "done"
        assert result["processed_count"] == 1
        assert len(result["output_paths"]) > 1
        assert all("_chunk_" in p for p in result["output_paths"])
        assert result["deleted_files"] == []

    def test_small_file_skipped(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "sources" / "small.md").write_text("Short text.")
        logs = []
        result = split_files(p, "sources", ["small.md"], False, 100000, logs.append)
        assert result["status"] == "done"
        assert result["processed_count"] == 0
        assert len(result["skipped_files"]) == 1
        assert "Quá nhỏ" in result["skipped_files"][0]["reason"]
        assert "100,000" in result["skipped_files"][0]["reason"]
        assert any("quá nhỏ" in log and "100,000" in log for log in logs)

    def test_unsupported_suffix_skipped(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "sources" / "f.xyz").write_text("x")
        result = split_files(p, "sources", ["f.xyz"], False, 1000, lambda m: None)
        assert result["skipped_files"][0]["filename"] == "f.xyz"

    def test_delete_source_after_success(self, tmp_path):
        p = _make_project(tmp_path)
        text = "Para.\n\n" * 5000
        src = p / "sources" / "big.md"
        src.write_text(text)
        result = split_files(p, "sources", ["big.md"], True, 1000, lambda m: None)
        assert result["status"] == "done"
        assert not src.exists()
        assert "big.md" in result["deleted_files"]

    def test_partial_on_write_error(self, tmp_path):
        p = _make_project(tmp_path)
        text = "Para.\n\n" * 5000
        (p / "sources" / "big.md").write_text(text)
        logs = []
        result = split_files(p, "sources", ["big.md"], False, 1000, logs.append)
        assert result["status"] in ("done", "partial")

    def test_invalid_filename(self, tmp_path):
        p = _make_project(tmp_path)
        result = split_files(p, "sources", ["../outside.md"], False, 1000, lambda m: None)
        assert result["status"] == "error"

    # LƯU Ý: max_chars validation (< 1000) xảy ra ở ROUTE (plugins.py L102),
    # KHÔNG ở service split_files(). Không test max_chars < 1000 ở service-level.


class TestMergeFiles:
    def test_merges_in_tick_order(self, tmp_path):
        p = _make_project(tmp_path)
        for name, content in [("a.md", "AAA"), ("b.md", "BBB"), ("c.md", "CCC")]:
            (p / "translated" / name).write_text(content)
        result = merge_files(p, "translated", ["a.md", "c.md", "b.md"], False, lambda m: None)
        assert result["status"] == "done"
        assert result["processed_count"] == 3
        out_name = result["output_paths"][0].split("/")[-1]
        assert out_name.startswith("merged_")
        content = (p / "translated" / out_name).read_text()
        assert content.index("AAA") < content.index("CCC") < content.index("BBB")

    def test_mixed_suffix_returns_error(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "translated" / "a.md").write_text("A")
        (p / "translated" / "b.txt").write_text("B")
        result = merge_files(p, "translated", ["a.md", "b.txt"], False, lambda m: None)
        assert result["status"] == "error"
        assert any("Mixed suffix" in f["reason"] for f in result["failed_files"])

    def test_empty_list_returns_error(self, tmp_path):
        p = _make_project(tmp_path)
        result = merge_files(p, "translated", [], False, lambda m: None)
        assert result["status"] == "error"

    def test_timestamp_no_overwrite(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "sources" / "a.md").write_text("A")
        (p / "sources" / "b.md").write_text("B")
        r1 = merge_files(p, "sources", ["a.md", "b.md"], False, lambda m: None)
        r2 = merge_files(p, "sources", ["a.md", "b.md"], False, lambda m: None)
        assert r1["output_paths"][0] != r2["output_paths"][0]

    def test_delete_after_success(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "sources" / "a.md").write_text("A")
        (p / "sources" / "b.md").write_text("B")
        result = merge_files(p, "sources", ["a.md", "b.md"], True, lambda m: None)
        assert result["status"] == "done"
        assert not (p / "sources" / "a.md").exists()
        assert not (p / "sources" / "b.md").exists()
        assert "a.md" in result["deleted_files"]
        assert "b.md" in result["deleted_files"]

    def test_does_not_delete_on_failure(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "sources" / "a.md").write_text("A")
        (p / "sources" / "b.md").write_text("B")
        (p / "sources" / "b.md").chmod(0o000)
        try:
            result = merge_files(p, "sources", ["a.md", "b.md"], True, lambda m: None)
            assert result["status"] == "error"
            assert (p / "sources" / "a.md").exists()
        finally:
            (p / "sources" / "b.md").chmod(0o644)

    def test_raw_text_merge_non_html(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "sources" / "a.json").write_text('{"a":1}')
        (p / "sources" / "b.json").write_text('{"b":2}')
        result = merge_files(p, "sources", ["a.json", "b.json"], False, lambda m: None)
        assert result["status"] == "done"
        out = (p / "sources" / result["output_paths"][0].split("/")[-1]).read_text()
        assert '"a":1' in out and '"b":2' in out

    def test_html_merge_uses_beautifulsoup(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "sources" / "a.html").write_text(
            "<!DOCTYPE html><html><head><title>A</title></head><body><p>A</p></body></html>"
        )
        (p / "sources" / "b.html").write_text(
            "<!DOCTYPE html><html><head><title>B</title></head><body><p>B</p></body></html>"
        )
        result = merge_files(p, "sources", ["a.html", "b.html"], False, lambda m: None)
        assert result["status"] == "done"
        out_name = result["output_paths"][0].split("/")[-1]
        out = (p / "sources" / out_name).read_text()
        assert "<title>A</title>" in out
        assert "<p>A</p>" in out
        assert "<p>B</p>" in out
        assert out.count("<body>") == 1


class TestMergeHtmlBodies:
    """Tests cho _merge_html_bodies. Chỉ chạy được sau khi apply Patch A."""

    def test_merges_multiple_bodies(self, tmp_path):
        from plugins.epub_converter.services.file_operations import _merge_html_bodies
        f1 = tmp_path / "a.html"
        f2 = tmp_path / "b.html"
        f1.write_text("<html><body><p>A</p></body></html>")
        f2.write_text("<html><body><p>B</p></body></html>")
        out = _merge_html_bodies([f1, f2], lambda m: None)
        assert out is not None
        assert "<p>A</p>" in out
        assert "<p>B</p>" in out
        assert out.count("<body>") == 1

    def test_snippet_without_body(self, tmp_path):
        from plugins.epub_converter.services.file_operations import _merge_html_bodies
        f1 = tmp_path / "a.html"
        f2 = tmp_path / "b.html"
        f1.write_text("<html><body><p>A</p></body></html>")
        f2.write_text("<p>B</p>")
        out = _merge_html_bodies([f1, f2], lambda m: None)
        assert out is not None
        assert "<p>B</p>" in out
