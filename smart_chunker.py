# smart_chunker.py - v1.0
# Module chịu trách nhiệm đọc và chia nhỏ file văn bản một cách thông minh.

import os
import re
import chardet
from typing import List

# Pattern để nhận dạng tiêu đề chương
# Hỗ trợ: Chương/Hồi/Quyển/Cuốn + số, và các từ khóa như Mở đầu, Ngoại truyện...
TITLE_PATTERN = re.compile(
    r'^\s*((chương|hồi|quyển|cuốn)\s+\d+.*|mở\s+đầu|giới\s+thiệu|ngoại\s+truyện|vĩ\s+thanh)\s*$',
    re.IGNORECASE | re.UNICODE
)

def read_and_detect_encoding(file_path: str) -> str:
    """
    Đọc file và tự động phát hiện encoding bằng chardet.
    Fallback về UTF-8 nếu không phát hiện được.
    """
    print(f"🔍 Đang đọc file: {os.path.basename(file_path)}")
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        
        result = chardet.detect(raw_data)
        encoding = result['encoding'] or 'utf-8'
        print(f"✅ Phát hiện encoding: {encoding}. Độ tin cậy: {result['confidence']:.0%}")
        
        return raw_data.decode(encoding)
    except FileNotFoundError:
        print(f"❌ Lỗi: Không tìm thấy file '{file_path}'")
        return ""
    except Exception as e:
        print(f"❌ Lỗi khi đọc file: {e}")
        return ""

def smart_chunking(text: str, chunk_size: int) -> List[str]:
    """
    Thực hiện chia chunk thông minh.
    Ưu tiên: Chia theo chương -> Chia theo đoạn văn -> Cắt cứng.
    Tự động bọc tiêu đề trong dấu **...**.
    """
    print(f"🌀 Bắt đầu quá trình chia chunk thông minh (kích thước mục tiêu: ~{chunk_size} ký tự)...")
    chunks = []
    lines = text.splitlines()
    current_chunk = []
    current_length = 0

    for line in lines:
        line_stripped = line.strip()
        
        # Kiểm tra nếu dòng là một tiêu đề chương
        if TITLE_PATTERN.match(line_stripped):
            # Nếu chunk hiện tại có nội dung, lưu nó lại trước khi bắt đầu chunk mới
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            
            # Thêm tiêu đề đã được bọc vào chunk mới
            current_chunk.append(f"**{line_stripped}**")
            current_length += len(line_stripped) + 4 # +4 cho dấu **...**
        else:
            # Nếu thêm dòng này sẽ vượt quá kích thước chunk, lưu chunk hiện tại
            if current_length + len(line) > chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            
            current_chunk.append(line)
            current_length += len(line) + 1 # +1 cho ký tự xuống dòng

    # Thêm chunk cuối cùng nếu còn
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    
    print(f"✅ Đã chia văn bản thành {len(chunks)} chunk.")
    return chunks

# Có thể chạy độc lập để kiểm thử
if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print("Cách dùng: python smart_chunker.py <đường_dẫn_tới_file>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"Lỗi: File '{input_file}' không tồn tại.")
        sys.exit(1)

    content = read_and_detect_encoding(input_file)
    if content:
        chunks = smart_chunking(content, chunk_size=24000)
        # In ra 50 ký tự đầu của mỗi chunk để kiểm tra
        for i, chunk in enumerate(chunks):
            print(f"\n--- Chunk {i+1} ({len(chunk)} ký tự) ---")
            print(chunk[:150] + "...")