"""Unit heuristic warnings (không gọi AI)."""

from core.quality import warn_output


def test_empty():
    assert warn_output("nguồn", "") == ["empty"]
    assert warn_output("nguồn", "   ") == ["empty"]


def test_too_short():
    assert "too_short" in warn_output("a" * 100, "ngắn")


def test_mostly_unchanged():
    src = "Câu văn mẫu để kiểm tra trùng lặp nội dung. " * 10
    assert "mostly_unchanged" in warn_output(src, src)
    assert "mostly_unchanged" not in warn_output(src, "Bản dịch hoàn toàn khác hẳn. " * 10)


def test_md_structure_lost():
    src = "# A\n## B\n- x\n- y\n> z\ntext " * 5
    assert "md_structure_lost" in warn_output(src, "plain text " * 20)
    assert "md_structure_lost" not in warn_output(src, src)


def test_possibly_truncated():
    assert "possibly_truncated" in warn_output("nguồn dài. " * 10, "kết quả còn dở dang,")
    assert "possibly_truncated" not in warn_output("nguồn.", "kết quả xong.")


def test_normal_no_warnings():
    assert warn_output("Nguồn vừa phải. " * 20, "Bản dịch đầy đủ ý nghĩa. " * 20) == []
