"""Unit core/fileops.py: guard/unique/strict/no-overwrite."""

import pytest

from core.fileops import guard_name, list_names, read_text_strict, unique_name, \
    write_bytes_no_overwrite


def test_guard_name():
    assert guard_name("  a.md ") == "a.md"
    for bad in ("", "   ", ".", "..", "a/b", "a\\b", "../x", None, 123):
        with pytest.raises(ValueError):
            guard_name(bad)


def test_unique_name_chain(tmp_path):
    (tmp_path / "a.md").write_text("1")
    assert unique_name(tmp_path, "a.md") == "a_conflict.md"
    (tmp_path / "a_conflict.md").write_text("2")
    assert unique_name(tmp_path, "a.md") == "a_conflict2.md"
    assert unique_name(tmp_path, "moi.md") == "moi.md"


def test_unique_name_edge_cases(tmp_path):
    (tmp_path / "a_conflict.md").write_text("x")
    assert unique_name(tmp_path, "a_conflict.md") == "a_conflict_conflict.md"  # stem sẵn _conflict
    (tmp_path / "noext").write_text("x")
    assert unique_name(tmp_path, "noext") == "noext_conflict"  # không ext
    (tmp_path / "book.v1.md").write_text("x")
    assert unique_name(tmp_path, "book.v1.md") == "book.v1_conflict.md"  # nhiều chấm
    (tmp_path / "é.md").write_text("x")  # NFC
    assert unique_name(tmp_path, "é.md") == "é_conflict.md"  # NFD trùng sau normalize


def test_strict_and_no_overwrite(tmp_path):
    (tmp_path / "bin.dat").write_bytes(b"\xff\xfe\x00binary")
    with pytest.raises(ValueError):
        read_text_strict(tmp_path / "bin.dat")
    (tmp_path / "a.txt").write_text("cũ", encoding="utf-8")
    assert read_text_strict(tmp_path / "a.txt") == "cũ"
    assert write_bytes_no_overwrite(tmp_path, "a.txt", b"moi") == "a_conflict.txt"
    assert (tmp_path / "a.txt").read_bytes() == "cũ".encode("utf-8")  # gốc nguyên
    assert (tmp_path / "a_conflict.txt").read_bytes() == b"moi"


def test_list_names_sorted(tmp_path):
    (tmp_path / "b.md").write_text("x")
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "c.exe").write_text("x")
    assert list_names(tmp_path) == ["a.txt", "b.md", "c.exe"]
    assert list_names(tmp_path, {".md"}) == ["b.md"]
    assert list_names(tmp_path / "khongco") == []
