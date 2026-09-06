"""Chia văn bản thành các chunk tự nhiên <= max_chars.

Thuật toán smartHardSplit: tìm điểm cắt trong dải 20%-80% quanh mốc 50%,
ưu tiên: \\n\\n -> \\n -> kết thúc câu -> khoảng trắng -> cắt cứng.
"""

import re
from typing import List


def _find_best_cut(text: str, min_pos: int, max_pos: int, target_pos: int) -> int:
    # 1. Dấu xuống dòng đôi \n\n (ngắt đoạn văn)
    doubles = [m.start() for m in re.finditer(r"\n[ \t]*\n", text) if min_pos <= m.start() <= max_pos]
    if doubles:
        return min(doubles, key=lambda p: abs(p - target_pos))

    # 2. Dấu xuống dòng đơn \n
    singles = [m.start() for m in re.finditer(r"\n", text) if min_pos <= m.start() <= max_pos]
    if singles:
        return min(singles, key=lambda p: abs(p - target_pos))

    # 3. Kết thúc câu (. ! ? 。！？) kèm khoảng trắng
    sentences = [
        m.end() for m in re.finditer(r"[\.!\?。！？]\s+", text) if min_pos <= m.end() <= max_pos
    ]
    if sentences:
        return min(sentences, key=lambda p: abs(p - target_pos))

    # 4. Khoảng trắng thông thường
    spaces = [m.start() for m in re.finditer(r"\s+", text) if min_pos <= m.start() <= max_pos]
    if spaces:
        return min(spaces, key=lambda p: abs(p - target_pos))

    # 5. Cắt cứng tại 50% nếu văn bản không có khoảng trắng
    return target_pos


def split_text(text: str, max_chars: int = 16000) -> List[str]:
    if max_chars is None or max_chars <= 0:
        raise ValueError(f"max_chunk_chars phải lớn hơn 0, nhận được: {max_chars!r}")
    if not text or not text.strip():
        return []

    if len(text) <= max_chars:
        return [text]

    min_pos = int(len(text) * 0.2)
    max_pos = int(len(text) * 0.8)
    target_pos = int(len(text) * 0.5)

    cut = _find_best_cut(text, min_pos, max_pos, target_pos)
    part1 = text[:cut].rstrip()
    part2 = text[cut:].lstrip()

    result = []
    for part in (part1, part2):
        if len(part) > max_chars:
            result.extend(split_text(part, max_chars))
        elif part:
            result.append(part)
    return result
