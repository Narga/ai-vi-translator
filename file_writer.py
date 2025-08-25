# file_writer.py - v1.2.2
# Tác giả: Gemini & Narga
# Cập nhật: Chỉ tạo ra một file duy nhất [tên_truyện]_dich.txt.
# Loại bỏ việc tạo các file chương và file giới thiệu.

import os
import re
import glob
import logging
import shutil
from pathlib import Path
from typing import List

def save_progress_chunk(
    chunk_content: str, 
    chunk_index: int, 
    progress_dir: str, 
    encoding: str
) -> None:
    """Lưu nội dung của một chunk đã dịch vào thư mục tạm `progress`."""
    os.makedirs(progress_dir, exist_ok=True)
    file_path = os.path.join(progress_dir, f"chunk_{chunk_index:05d}.txt")
    with open(file_path, 'w', encoding=encoding) as f:
        f.write(chunk_content)

def assemble_final_files(
    progress_dir: str,
    output_dir: str,
    encoding: str
) -> None:
    """
    Đọc tất cả các chunk, ghép chúng lại thành một file duy nhất,
    và sau đó di chuyển các chunk vào thư mục `parts`.
    """
    logging.info("\n✅ Bắt đầu ghép file cuối cùng và lưu trữ các chunk...")
    
    progress_path = Path(progress_dir)
    output_path = Path(output_dir)
    # Tạo thư mục output nếu chưa có
    output_path.mkdir(parents=True, exist_ok=True)
    
    base_filename = output_path.name
    
    chunk_files = sorted(progress_path.glob("chunk_*.txt"))
    
    if not chunk_files:
        logging.warning("⚠️ Không tìm thấy file chunk nào để ghép.")
        return

    # Đọc và ghép nối nội dung từ tất cả các chunk
    full_translated_content = []
    for f in chunk_files:
        with open(f, 'r', encoding=encoding) as chunk_file:
            full_translated_content.append(chunk_file.read())
            
    final_text = "\n\n".join(full_translated_content)
    
    # Tạo file tổng hợp duy nhất
    final_filename = f"{base_filename}_dich.txt"
    final_filepath = output_path / final_filename
    try:
        with open(final_filepath, 'w', encoding=encoding) as f:
            f.write(final_text)
        logging.info(f"✅ Đã tạo file dịch hoàn chỉnh: '{final_filepath}'")
    except Exception as e:
        logging.error(f"❌ Lỗi khi ghi file tổng hợp: {e}")
        return

    # Di chuyển các file chunk đã xử lý vào thư mục 'parts'
    try:
        parts_dir = output_path / 'parts'
        parts_dir.mkdir(exist_ok=True)
        
        moved_count = 0
        for f in chunk_files:
            shutil.move(str(f), str(parts_dir))
            moved_count += 1
        
        logging.info(f"🗄️ Đã di chuyển {moved_count} file chunk đã dịch vào thư mục '{parts_dir}'.")
    except Exception as e:
        logging.error(f"❌ Lỗi khi di chuyển các file chunk đã dịch: {e}")