# smart_chunker.py - v1.2
import os
import re
import chardet
import logging
from typing import List

TITLE_PATTERN = re.compile(
    r'^\s*((chương|hồi|quyển|cuốn)\s+\d+.*|mở\s+đầu|giới\s+thiệu|ngoại\s+truyện|vĩ\s+thanh)\s*$',
    re.IGNORECASE | re.UNICODE
)

def read_and_detect_encoding(file_path: str) -> str:
    logging.info(f"🔍 Đang đọc file: {os.path.basename(file_path)}")
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding'] or 'utf-8'
        logging.info(f"✅ Phát hiện encoding: {encoding}. Độ tin cậy: {result['confidence']:.0%}")
        return raw_data.decode(encoding)
    except FileNotFoundError:
        logging.error(f"❌ Lỗi: Không tìm thấy file '{file_path}'")
        return ""
    except Exception as e:
        logging.error(f"❌ Lỗi khi đọc file: {e}")
        return ""

def smart_chunking(text: str, chunk_size: int) -> List[str]:
    logging.info(f"🌀 Bắt đầu quá trình chia chunk thông minh (kích thước mục tiêu: ~{chunk_size} ký tự)...")
    chunks = []
    lines = text.splitlines()
    current_chunk = []
    current_length = 0
    for line in lines:
        line_stripped = line.strip()
        if TITLE_PATTERN.match(line_stripped):
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            current_chunk.append(f"**{line_stripped}**")
            current_length += len(line_stripped) + 4
        else:
            if current_length + len(line) > chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            current_chunk.append(line)
            current_length += len(line) + 1
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    logging.info(f"✅ Đã chia văn bản thành {len(chunks)} chunk.")
    return chunks