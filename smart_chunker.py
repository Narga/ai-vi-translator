# smart_chunker.py - v1.2
# Tác giả: Gemini & Narga
# Chức năng: Module chịu trách nhiệm đọc và chia nhỏ file văn bản.
# Đã được nâng cấp để sử dụng thuật toán "intelligent_chunking" tinh vi,
# kết hợp khả năng nhận diện tiêu đề chương và cắt đoạn theo ngữ cảnh.

import os
import re
import chardet
import logging
from typing import List

# Biểu thức chính quy để nhận dạng tiêu đề chương
# Hỗ trợ: Chương/Hồi/Quyển/Cuốn + số, và các từ khóa đặc biệt.
TITLE_PATTERN = re.compile(
    r'^\s*((chương|hồi|quyển|cuốn)\s+\d+.*|mở\s+đầu|giới\s+thiệu|ngoại\s+truyện|vĩ\s+thanh)\s*$',
    re.IGNORECASE | re.UNICODE
)

def read_and_detect_encoding(file_path: str) -> str:
    """
    Đọc nội dung file và tự động phát hiện bảng mã (encoding).
    Sử dụng chardet và có các phương án dự phòng thông dụng.
    """
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

def intelligent_chunking(full_text: str, min_chars: int, max_chars: int) -> List[str]:
    """
    Thuật toán cắt file thông minh dựa trên ngữ cảnh.
    1. Tìm điểm cắt tối ưu trong khoảng [min_chars, max_chars] dựa trên trọng số của dấu câu.
    2. Ưu tiên cắt ở cuối câu, cuối đoạn văn.
    3. Hậu xử lý để gộp các chunk quá nhỏ, tránh mất ngữ cảnh.
    """
    if not full_text or not full_text.strip():
        return []

    logging.info(f"🌀 Bắt đầu cắt file thông minh (khoảng {min_chars:,} - {max_chars:,} ký tự)...")
    
    # Bước 1: Tiền xử lý để đánh dấu các tiêu đề chương
    lines = full_text.splitlines()
    processed_lines = []
    for line in lines:
        stripped_line = line.strip()
        if TITLE_PATTERN.match(stripped_line):
            # Đánh dấu tiêu đề để chúng được giữ nguyên và dễ nhận diện
            processed_lines.append(f"**{stripped_line}**")
        else:
            processed_lines.append(line)
    text_to_chunk = "\n".join(processed_lines)
    
    chunks, current_pos, text_len = [], 0, len(text_to_chunk)
    
    # Trọng số cho các loại điểm cắt khác nhau
    delimiters = [
        ('.!?。！？', 1.0),    # Dấu kết câu (ưu tiên cao nhất)
        ('\n\n', 0.9),         # Ngắt đoạn
        ('\n', 0.7),           # Ngắt dòng
        ('. ', 0.6),           # Dấu chấm theo sau là khoảng trắng
        (', ', 0.3),           # Dấu phẩy
        (' ', 0.1)             # Khoảng trắng (ưu tiên thấp nhất)
    ]
    
    while current_pos < text_len:
        chunk_start = current_pos
        # Xác định khoảng tìm kiếm điểm cắt
        ideal_end = min(current_pos + max_chars, text_len)
        min_end = min(current_pos + min_chars, text_len)
        
        # Xử lý chunk cuối cùng: nếu phần còn lại không quá lớn, lấy hết
        remaining = text_len - current_pos
        if remaining <= max_chars * 1.2:
            chunk_text = text_to_chunk[current_pos:].strip()
            if chunk_text:
                chunks.append(chunk_text)
            break
        
        # Tìm điểm cắt tốt nhất dựa trên trọng số và vị trí
        best_cut_pos = -1
        best_score = -1
        
        for delimiters_set, weight in delimiters:
            # Tìm ngược từ vị trí lý tưởng về vị trí tối thiểu
            for pos in range(ideal_end - 1, min_end - 1, -1):
                if text_to_chunk[pos] in delimiters_set:
                    # Tính điểm dựa trên trọng số và độ gần với "điểm vàng" (80% của max_chars)
                    position_score = 1 - abs(pos - (current_pos + (max_chars * 0.8))) / (max_chars * 0.4)
                    total_score = weight * position_score
                    
                    if total_score > best_score:
                        best_score = total_score
                        best_cut_pos = pos + 1
        
        # Nếu không tìm được điểm cắt tối ưu, cắt cứng ở vị trí tối đa
        if best_cut_pos == -1:
            best_cut_pos = ideal_end
            logging.warning(f"⚠️ Không tìm thấy điểm cắt tối ưu cho chunk {len(chunks)+1}, thực hiện cắt cứng.")
        
        chunk_text = text_to_chunk[chunk_start:best_cut_pos].strip()
        if chunk_text:
            chunks.append(chunk_text)
        
        current_pos = best_cut_pos
    
    # Bước 3: Hậu xử lý, gộp các chunk quá nhỏ (< 30% kích thước min)
    if len(chunks) >= 2:
        final_chunks = []
        temp_chunk = chunks[0]
        for i in range(1, len(chunks)):
            if len(chunks[i]) < min_chars * 0.3:
                # Nếu chunk tiếp theo quá nhỏ, gộp vào chunk hiện tại
                temp_chunk += "\n\n" + chunks[i]
                logging.info(f"Gộp chunk {i+1} (quá nhỏ) vào chunk trước đó.")
            else:
                final_chunks.append(temp_chunk)
                temp_chunk = chunks[i]
        final_chunks.append(temp_chunk)
        chunks = final_chunks

    if chunks:
        avg_size = sum(len(chunk) for chunk in chunks) / len(chunks)
        logging.info(f"✅ Cắt file hoàn tất: {len(chunks)} chunks, kích thước trung bình: {avg_size:,.0f} ký tự.")
    
    return chunks

def process_text_for_chunking(text: str, min_chars: int, max_chars: int) -> List[str]:
    """
    Hàm điều phối chính cho việc chia chunk.
    Kiểm tra kích thước văn bản và quyết định có cần chia nhỏ hay không.
    """
    # Nếu văn bản đủ nhỏ, chỉ cần đánh dấu tiêu đề và trả về như một chunk duy nhất
    if len(text) <= max_chars:
        lines = text.splitlines()
        processed_lines = []
        for line in lines:
            stripped_line = line.strip()
            if TITLE_PATTERN.match(stripped_line):
                processed_lines.append(f"**{stripped_line}**")
            else:
                processed_lines.append(line)
        return ["\n".join(processed_lines)]
    else:
        # Nếu văn bản lớn, sử dụng thuật toán cắt thông minh
        return intelligent_chunking(text, min_chars, max_chars)