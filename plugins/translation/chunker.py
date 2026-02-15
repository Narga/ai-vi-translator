# src/smart_chunker.py - v2.6.1
# Tác giả: Narga
# Chức năng: Module xử lý thông minh cho việc cắt file.
# THAY ĐỔI v2.6.1:
# - Sửa lỗi biến không tồn tại/nhầm tên (pos/length/start) → current_pos/text_len/chunk_start.
# - Bảo đảm cập nhật current_pos sau mỗi lần cắt.
# - Thêm fallback cắt cứng nếu không tìm thấy dấu câu hợp lệ trong cửa sổ [min..max].
# - Giữ cơ chế gộp các mảnh chunk nhỏ để giảm mảnh vụn.

import os
import re
import chardet
import logging
from typing import List, Tuple

# Biểu thức chính quy để nhận dạng tiêu đề chương, hỗ trợ song ngữ Việt-Anh.
TITLE_PATTERNS = [
    re.compile(r"^\s*((chương|hồi|quyển|cuốn|phần)\s+\d+.*)", re.IGNORECASE),
    re.compile(r"^\s*((chapter|part|section)\s+\d+.*)", re.IGNORECASE),
    re.compile(r"^\s*(mở\s+đầu|giới\s+thiệu|ngoại\s+truyện|vĩ\s+thanh)", re.IGNORECASE),
    re.compile(r"^\s*(prologue|epilogue|introduction)", re.IGNORECASE),
]

# Module-level delimiter patterns (compiled once for performance)
# Format: (delimiter_string, weight, is_multi_char)
DELIMITERS = [
    (".!?。！？", 1.0, False),
    ("\n\n", 0.9, True),
    ("\n", 0.7, True),
    (". ", 0.6, True),
    (", ", 0.3, True),
    (" ", 0.1, True),
]


def read_and_detect_encoding(file_path: str) -> str:
    """
    Đọc nội dung file và tự động phát hiện bảng mã (encoding).

    Args:
        file_path (str): Đường dẫn đến file cần đọc.

    Returns:
        str: Nội dung file đã được giải mã sang Unicode, hoặc chuỗi rỗng nếu lỗi.
    """
    logging.info(f"🔍 Đang đọc file: {os.path.basename(file_path)}")
    try:
        with open(file_path, "rb") as f:
            raw_data = f.read()
        result = chardet.detect(raw_data)
        encoding = result.get("encoding") or "utf-8"
        logging.info(
            f"✅ Phát hiện encoding: {encoding} (độ tin cậy {result.get('confidence', 0):.0%})"
        )
        return raw_data.decode(encoding, errors="replace")
    except Exception as e:
        logging.error(f"❌ Lỗi đọc file {file_path}: {e}")
        return ""


def wrap_titles(text: str) -> str:
    """
    Quét qua văn bản và bọc các dòng được xác định là tiêu đề trong `**...**`.

    Args:
        text (str): Khối văn bản đầu vào.

    Returns:
        str: Khối văn bản với các tiêu đề đã được định dạng.
    """
    output_lines = []
    for line in text.splitlines():
        stripped_line = line.strip()
        is_title = any(p.match(stripped_line) for p in TITLE_PATTERNS)
        if stripped_line and is_title:
            output_lines.append(f"**{stripped_line}**")
        else:
            output_lines.append(line)
    return "\n".join(output_lines)


def _find_best_cut_position(
    text: str, window_start: int, min_end: int, ideal_end: int, max_chars: int
) -> Tuple[int, float]:
    """
    Tìm vị trí cắt tốt nhất trong cửa sổ [min_end..ideal_end] dựa vào dấu câu/dấu xuống dòng.

    Heuristic:
      - Ưu tiên các dấu câu mạnh ('.!?。！？') > đoạn xuống dòng đôi > xuống dòng đơn > dấu câu nhẹ > khoảng trắng.
      - Gần "điểm lý tưởng" (window_start + 0.8 * max_chars) sẽ có điểm cao hơn.

    Returns:
      (best_cut_pos, best_score) - nếu không tìm thấy, trả về (-1, -1).
    """
    # Use module-level DELIMITERS for performance
    best_cut_pos, best_score = -1, -1.0
    focus = window_start + int(0.8 * max_chars)  # điểm "đẹp" mong muốn

    # Quét ngược để ưu tiên cắt gần cuối cửa sổ, giảm rủi ro cắt quá ngắn
    for i in range(ideal_end - 1, min_end - 1, -1):
        ch = text[i]
        for token, weight, is_substr in DELIMITERS:
            match = False
            cut_pos = -1  # Initialize to avoid unbound error
            if not is_substr:
                # Token là "alphabet" ký tự, so khớp trực tiếp
                if ch in token:
                    match = True
                    cut_pos = i + 1
            else:
                # Token là chuỗi (có thể dài 1-2 ký tự), so khớp substring tại vị trí i-len+1..i
                L = len(token)
                if i - L + 1 >= window_start and text[i - L + 1 : i + 1] == token:
                    match = True
                    cut_pos = i + 1

            if match and cut_pos >= 0:
                proximity = 1.0 - abs(i - focus) / max(
                    1.0, 0.4 * max_chars
                )  # giá trị trong [0..~]
                proximity = max(
                    0.0, min(1.0, proximity)
                )  # chặn trong [0..1] để ổn định
                score = weight * proximity
                if score > best_score:
                    best_score = score
                    best_cut_pos = cut_pos
        # Nếu đã có điểm rất cao, có thể dừng sớm (tối ưu nhẹ)
        if best_score >= 0.98:
            break

    return best_cut_pos, best_score


def intelligent_chunking(full_text: str, min_chars: int, max_chars: int) -> List[str]:
    """
    Thuật toán cắt file thông minh dựa trên ngữ cảnh.

    Args:
        full_text (str): Toàn bộ nội dung văn bản cần chia.
        min_chars (int): Kích thước tối thiểu mong muốn cho mỗi chunk.
        max_chars (int): Kích thước tối đa cho mỗi chunk.

    Returns:
        List[str]: Danh sách các chunk văn bản đã được chia.
    """
    if not full_text or not full_text.strip():
        return []

    logging.info(
        f"🌀 Bắt đầu cắt file thông minh (khoảng {min_chars:,} - {max_chars:,} ký tự)..."
    )

    # Tiền xử lý nhẹ: bọc tiêu đề để giữ ranh giới rõ ràng
    text_to_chunk = wrap_titles(full_text)

    chunks: List[str] = []
    current_pos = 0
    text_len = len(text_to_chunk)

    while current_pos < text_len:
        chunk_start = current_pos
        remaining = text_len - current_pos

        # Nếu phần còn lại đủ nhỏ, lấy hết một lần để giảm số mảnh.
        if remaining <= int(max_chars * 1.2):
            chunk = text_to_chunk[current_pos:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Xác định cửa sổ cắt
        ideal_end = min(current_pos + max_chars, text_len)
        min_end = min(current_pos + min_chars, text_len)

        # Tìm vị trí cắt tốt nhất trong cửa sổ [min_end..ideal_end]
        best_cut_pos, best_score = _find_best_cut_position(
            text_to_chunk, current_pos, min_end, ideal_end, max_chars
        )

        if best_cut_pos < 0:
            # Không tìm thấy delimiter phù hợp → fallback: cắt cứng ở ideal_end
            best_cut_pos = ideal_end
            logging.warning(
                "⚠️ Không tìm thấy điểm cắt tối ưu trong cửa sổ → thực hiện cắt cứng."
            )

        # Trích chunk và cập nhật vị trí
        chunk = text_to_chunk[chunk_start:best_cut_pos].strip()
        if chunk:
            chunks.append(chunk)
        current_pos = best_cut_pos

    # Hậu xử lý: gộp các chunk quá nhỏ vào chunk trước đó để tránh mảnh vụn
    if len(chunks) >= 2:
        merged_chunks: List[str] = []
        temp = chunks[0]
        for c in chunks[1:]:
            if len(c) < int(min_chars * 0.3):
                logging.info("🔗 Gộp chunk nhỏ vào chunk trước đó.")
                temp += "\n\n" + c
            else:
                merged_chunks.append(temp)
                temp = c
        merged_chunks.append(temp)
        chunks = merged_chunks

    if chunks:
        avg_size = sum(len(c) for c in chunks) / len(chunks)
        logging.info(
            f"✅ Cắt file hoàn tất: {len(chunks)} chunks, kích thước TB: {avg_size:,.0f} ký tự."
        )

    return chunks


def process_text_for_chunking(text: str, min_chars: int, max_chars: int) -> List[str]:
    """
    Hàm điều phối chính cho việc chia chunk.
    Kiểm tra kích thước văn bản và quyết định có cần chia nhỏ hay không.

    Args:
        text (str): Nội dung cần xử lý.
        min_chars (int): Kích thước tối thiểu mỗi chunk.
        max_chars (int): Kích thước tối đa mỗi chunk.

    Returns:
        List[str]: Một hoặc nhiều chunk tùy kích thước đầu vào.
    """
    if len(text or "") <= max_chars:
        return [wrap_titles(text)]
    return intelligent_chunking(text, min_chars, max_chars)


def chunk_text_generator(full_text: str, min_chars: int, max_chars: int):
    """
    Generator-based chunking cho memory-efficient processing.
    Yields chunks one at a time thay vì load all vào memory.

    Args:
        full_text (str): Toàn bộ nội dung văn bản cần chia.
        min_chars (int): Kích thước tối thiểu mong muốn cho mỗi chunk.
        max_chars (int): Kích thước tối đa cho mỗi chunk.

    Yields:
        str: Từng chunk một
    """
    if not full_text or not full_text.strip():
        return

    text_to_chunk = wrap_titles(full_text)
    current_pos = 0
    text_len = len(text_to_chunk)

    while current_pos < text_len:
        chunk_start = current_pos
        remaining = text_len - current_pos

        if remaining <= int(max_chars * 1.2):
            chunk = text_to_chunk[current_pos:].strip()
            if chunk:
                yield chunk
            break

        ideal_end = min(current_pos + max_chars, text_len)
        min_end = min(current_pos + min_chars, text_len)

        best_cut_pos, _ = _find_best_cut_position(
            text_to_chunk, current_pos, min_end, ideal_end, max_chars
        )

        if best_cut_pos < 0:
            best_cut_pos = ideal_end

        chunk = text_to_chunk[chunk_start:best_cut_pos].strip()
        if chunk:
            yield chunk

        current_pos = best_cut_pos
