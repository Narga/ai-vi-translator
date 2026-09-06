import re

import pytest

from core.chunker import split_text


def _norm(t: str) -> str:
    # Contract chuẩn hóa (review §9.8): so sánh sau khi xóa MỌI whitespace,
    # vì split rstrip/lstrip ở điểm cắt + join "\n\n" đều thêm/bớt whitespace.
    return re.sub(r"\s+", "", t)


@pytest.mark.parametrize("size", [10, 16000, 100000])
@pytest.mark.parametrize("text", [
    "ascii simple text " * 5000,
    "Tiếng Việt có dấu ễ ộ ư đ. " * 2000,
    "x" * 50000,
    ("đoạn rất dài không ngắt " * 5000).replace(" ", ""),
    "",
    "   \n\t  ",
])
def test_chunks_within_limit_and_rejoin(text, size):
    if not text.strip():
        assert split_text(text, size) == []
        return
    chunks = split_text(text, size)
    assert all(len(c) <= size for c in chunks)
    assert _norm("\n\n".join(chunks)) == _norm(text)


def test_max_chars_tiny_no_hang():
    chunks = split_text("abcdef", 1)
    assert all(len(c) <= 1 for c in chunks)
    assert "".join(chunks) == "abcdef"


def test_max_chars_invalid():
    with pytest.raises(ValueError):
        split_text("abc", 0)
    with pytest.raises(ValueError):
        split_text("abc", -5)


def test_empty_and_whitespace():
    assert split_text("") == []
    assert split_text("   \n\n  ") == []


def test_short_text():
    text = "Đoạn văn ngắn."
    assert split_text(text, max_chars=1000) == [text]


def test_split_at_double_newline():
    p1 = "Đoạn 1.\n\n" * 50
    p2 = "Đoạn 2.\n\n" * 50
    chunks = split_text(p1 + p2, max_chars=len(p1) + 100)
    assert len(chunks) >= 2


def test_split_without_spaces():
    text = "A" * 1000
    chunks = split_text(text, max_chars=600)
    assert len(chunks) == 2


def test_no_content_loss():
    text = ("Câu mở đầu. " * 200 + "\n\n" + "Đoạn hai! " * 200).strip()
    chunks = split_text(text, max_chars=2000)
    # Mọi câu nguồn phải còn nguyên trong các chunk (quy ước whitespace chuẩn hóa)
    joined = " ".join(" ".join(c.split()) for c in chunks)
    for sentence in ("Câu mở đầu.", "Đoạn hai!"):
        assert sentence in joined
