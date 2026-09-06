"""Heuristic cảnh báo output bất thường (không dùng model chấm điểm).
Chỉ cảnh báo, không tự sửa. Dùng sau khi nhận đủ chunk/file."""

import difflib
import re

_END_PUNCT = (".", "!", "?", "…", ":", ";", '"', "'", """, """, ")", "」", "』")


def _norm(t: str) -> str:
    return re.sub(r"\s+", "", t or "")


def _md_marks(t: str) -> int:
    return len(re.findall(r"(?m)^(#{1,6}\s|>\s*|[-*]\s|\d+\.\s)", t or ""))


def warn_output(source: str, out: str) -> list:
    """Trả danh sách mã cảnh báo cho 1 cặp nguồn/kết quả. Rỗng = bình thường."""
    warns = []
    s, o = _norm(source), _norm(out)
    if not o:
        return ["empty"]
    if s and len(o) < 0.5 * len(s):
        warns.append("too_short")
    if s and len(s) > 50 and difflib.SequenceMatcher(None, s, o).ratio() > 0.8:
        warns.append("mostly_unchanged")
    ms, mo = _md_marks(source), _md_marks(out)
    if ms >= 3 and mo < ms / 2:
        warns.append("md_structure_lost")
    tail = (out or "").rstrip()
    if tail and not tail.endswith(_END_PUNCT):
        warns.append("possibly_truncated")
    return warns
