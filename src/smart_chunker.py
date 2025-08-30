# src/smart_chunker.py - v2.0.0
# Tác giả: Narga
# Chức năng: Module xử lý thông minh cho việc cắt file.

import os
import re
import chardet
import logging
from typing import List

# Biểu thức chính quy để nhận dạng tiêu đề chương, hỗ trợ song ngữ Việt-Anh.
TITLE_PATTERNS = [
    re.compile(r'^\s*((chương|hồi|quyển|cuốn|phần)\s+\d+.*)', re.IGNORECASE),
    re.compile(r'^\s*((chapter|part|section)\s+\d+.*)', re.IGNORECASE),
    re.compile(r'^\s*(mở\s+đầu|giới\s+thiệu|ngoại\s+truyện|vĩ\s+thanh)', re.IGNORECASE),
    re.compile(r'^\s*(prologue|epilogue|introduction)', re.IGNORECASE),
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
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        
        result = chardet.detect(raw_data)
        encoding = result.get('encoding') or 'utf-8'
        logging.info(f"✅ Phát hiện encoding: {encoding} (độ tin cậy {result.get('confidence',0):.0%})")
        
        return raw_data.decode(encoding)
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

    logging.info(f"🌀 Bắt đầu cắt file thông minh (khoảng {min_chars:,} - {max_chars:,} ký tự)...")
    
    text_to_chunk = wrap_titles(full_text)
    chunks, current_pos, text_len = [], 0, len(text_to_chunk)
    
    delimiters = [
        ('.!?。！？', 1.0), ('\n\n', 0.9), ('\n', 0.7),
        ('. ', 0.6), (', ', 0.3), (' ', 0.1)
    ]
    
    while current_pos < text_len:
        chunk_start = pos
        ideal_end = min(pos + max_chars, length)
        min_end = min(pos + min_chars, length)
        remaining = length - pos

        if remaining <= max_chars * 1.2:
            chunk = text_to_chunk[pos:].strip()
            if chunk: chunks.append(chunk)
            break
        
        best_cut_pos, best_score = -1, -1
        for chars, weight in delimiters:
            for i in range(ideal_end - 1, min_end - 1, -1):
                if text_to_chunk[i] in chars:
                    proximity = 1 - abs(i - (pos + 0.8 * max_chars)) / (0.4 * max_chars)
                    score = weight * proximity
                    if score > best_score:
                        best_score, best_cut_pos = score, i + 1
        
        if best_cut_pos < 0:
            best_cut_pos = ideal_end
            logging.warning(f"⚠️ Không tìm thấy điểm cắt tối ưu, thực hiện cắt cứng.")
        
        chunk = text_to_chunk[start:best_cut_pos].strip()
        if chunk: chunks.append(chunk)
        pos = best_cut_pos
    
    if len(chunks) >= 2:
        merged_chunks = []
        temp_chunk = chunks[0]
        for c in chunks[1:]:
            if len(c) < min_chars * 0.3:
                logging.info("🔗 Gộp chunk nhỏ vào chunk trước đó.")
                temp_chunk += "\n\n" + c
            else:
                merged_chunks.append(temp_chunk)
                temp_chunk = c
        merged_chunks.append(temp_chunk)
        chunks = merged_chunks

    if chunks:
        avg_size = sum(len(c) for c in chunks) / len(chunks)
        logging.info(f"✅ Cắt file hoàn tất: {len(chunks)} chunks, kích thước TB: {avg_size:,.0f} ký tự.")
    
    return chunks

def process_text_for_chunking(text: str, min_chars: int, max_chars: int) -> List[str]:
    """
    Hàm điều phối chính cho việc chia chunk.
    Kiểm tra kích thước văn bản và quyết định có cần chia nhỏ hay không.
    """
    if len(text or "") <= max_chars:
        return [wrap_titles(text)]
    return intelligent_chunking(text, min_chars, max_chars)