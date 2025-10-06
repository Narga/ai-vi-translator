# src/file_writer.py - v2.4.1
# Tác giả: Gemini & Narga
# Chức năng: Quản lý việc lưu trữ và ghép nối các chunk đã dịch.
#            Hỗ trợ đặt tên file chunk theo nguồn gốc để dễ dàng so sánh.

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
    """
    Lưu nội dung của một chunk đã dịch vào thư mục tạm `progress`.
    
    Tên file chunk có định dạng: chunk_<index>_translated.txt
    để dễ dàng liên kết với chunk gốc (nếu cần).
    
    Args:
        chunk_content (str): Nội dung đã dịch của chunk
        chunk_index (int): Chỉ số của chunk trong danh sách
        progress_dir (str): Đường dẫn đến thư mục progress
        encoding (str): Encoding để ghi file (thường là 'utf-8')
    """
    os.makedirs(progress_dir, exist_ok=True)
    
    # Đặt tên file với suffix _translated để phân biệt
    # Format: chunk_00001_translated.txt
    file_path = os.path.join(progress_dir, f"chunk_{chunk_index:05d}_translated.txt")
    
    with open(file_path, 'w', encoding=encoding) as f:
        f.write(chunk_content)
    
    logging.debug(f"Đã lưu chunk {chunk_index} vào {file_path}")


def assemble_final_files(
    progress_dir: str,
    output_dir: str,
    encoding: str
) -> None:
    """
    Đọc tất cả các chunk, ghép chúng lại thành một file duy nhất,
    và sau đó di chuyển các chunk vào thư mục `parts`.
    
    Args:
        progress_dir (str): Đường dẫn đến thư mục chứa các chunk đã dịch
        output_dir (str): Đường dẫn đến thư mục output chính
        encoding (str): Encoding để đọc/ghi file
    """
    logging.info("\n✅ Bắt đầu ghép file cuối cùng và lưu trữ các chunk...")
    
    progress_path = Path(progress_dir)
    output_path = Path(output_dir)
    
    # Tạo thư mục output nếu chưa có
    output_path.mkdir(parents=True, exist_ok=True)
    
    base_filename = output_path.name
    
    # Tìm tất cả các file chunk đã dịch (có suffix _translated)
    chunk_files = sorted(progress_path.glob("chunk_*_translated.txt"))
    
    if not chunk_files:
        logging.warning("⚠️  Không tìm thấy file chunk nào để ghép.")
        return
    
    # Đọc và ghép nối nội dung từ tất cả các chunk
    full_translated_content = []
    
    for f in chunk_files:
        with open(f, 'r', encoding=encoding) as chunk_file:
            content = chunk_file.read()
            full_translated_content.append(content)
    
    # Ghép nối với 2 dòng trống giữa các chunk
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
            destination = parts_dir / f.name
            shutil.move(str(f), str(destination))
            moved_count += 1
        
        logging.info(f"🗄️  Đã di chuyển {moved_count} file chunk đã dịch vào thư mục '{parts_dir}'.")
    
    except Exception as e:
        logging.error(f"❌ Lỗi khi di chuyển các file chunk đã dịch: {e}")
