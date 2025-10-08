# src/file_writer.py - v2.6.1
# Tác giả: Narga
# Chức năng: Module chứa các hàm liên quan đến ghi file.
#            Hỗ trợ lưu file với tên gốc và ghép nối linh hoạt.

import os
import logging
from pathlib import Path
from typing import Optional


def save_translated_file(
    translated_text: str,
    output_dir: str,
    filename: str,
    encoding: str = 'utf-8'
) -> None:
    """
    Lưu file đã dịch vào thư mục output/parts với tên gốc từ input.
    
    Hàm này tạo thư mục parts nếu chưa tồn tại và lưu nội dung đã dịch
    với tên file giống file gốc để dễ đối chiếu.
    
    Args:
        translated_text (str): Nội dung đã dịch
        output_dir (str): Đường dẫn đến thư mục output chính
        filename (str): Tên file gốc (ví dụ: "chapter_01.txt")
        encoding (str): Encoding để ghi file
        
    Example:
        >>> save_translated_file(
        ...     "Đã dịch...",
        ...     "workspace/output/my_novel",
        ...     "chapter_01.txt"
        ... )
        # Lưu vào: workspace/output/my_novel/parts/chapter_01.txt
    """
    output_path = Path(output_dir)
    parts_dir = output_path / 'parts'
    parts_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = parts_dir / filename
    
    try:
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(translated_text)
        
        logging.info(f"✅ Đã lưu file: {filename}")
    
    except Exception as e:
        logging.error(f"❌ Lỗi khi lưu file {filename}: {e}")


def save_progress_chunk(
    translated_text: str,
    chunk_index: int,
    progress_dir: str,
    encoding: str = 'utf-8'
) -> None:
    """
    Lưu từng chunk đã dịch vào thư mục tạm (progress).
    
    [GIỮ LẠI ĐỂ TƯƠNG THÍCH NGƯỢC]
    Trong workflow mới (v2.6.1), sử dụng save_translated_file() thay thế.
    
    Args:
        translated_text (str): Nội dung chunk đã dịch
        chunk_index (int): Chỉ số của chunk (bắt đầu từ 0)
        progress_dir (str): Đường dẫn đến thư mục progress
        encoding (str): Encoding để ghi file
    """
    progress_path = Path(progress_dir)
    progress_path.mkdir(parents=True, exist_ok=True)
    
    chunk_filename = f"chunk_{chunk_index}.txt"
    file_path = progress_path / chunk_filename
    
    try:
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(translated_text)
        
        logging.debug(f"Đã lưu chunk {chunk_index} vào {file_path}")
    
    except Exception as e:
        logging.error(f"Lỗi khi lưu chunk {chunk_index}: {e}")


def assemble_final_files(
    progress_dir: str,
    output_dir: str,
    encoding: str = 'utf-8',
    source_is_parts: bool = False
) -> None:
    """
    Ghép nối các file đã dịch thành file hoàn chỉnh.
    
    Hàm này đọc tất cả các file trong progress_dir (hoặc output/parts),
    sắp xếp và ghép nối chúng thành file full.txt. Đồng thời copy
    các file riêng lẻ vào thư mục parts.
    
    Args:
        progress_dir (str): Thư mục chứa các file đã dịch
        output_dir (str): Thư mục đích để lưu kết quả
        encoding (str): Encoding để đọc/ghi file
        source_is_parts (bool): True nếu source đã là parts (không cần copy)
        
    Note:
        - Nếu source_is_parts=False: Copy từ progress_dir vào output/parts
        - Nếu source_is_parts=True: Chỉ ghép nối, không copy (đã có sẵn trong parts)
    """
    progress_path = Path(progress_dir)
    output_path = Path(output_dir)
    
    # Tạo thư mục output nếu chưa tồn tại
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Lấy tất cả file txt
    translated_files = sorted(progress_path.glob("*.txt"))
    
    if not translated_files:
        logging.warning(f"Không tìm thấy file nào trong '{progress_dir}' để ghép nối.")
        return
    
    # Ghép nối tất cả file thành full.txt
    full_content = []
    
    for file_path in translated_files:
        try:
            content = file_path.read_text(encoding=encoding)
            full_content.append(content)
            logging.info(f"Đã đọc file: {file_path.name}")
        except Exception as e:
            logging.error(f"Lỗi khi đọc file {file_path.name}: {e}")
    
    # Lưu file full.txt
    full_file_path = output_path / 'full.txt'
    
    try:
        with open(full_file_path, 'w', encoding=encoding) as f:
            f.write('\n\n'.join(full_content))
        
        logging.info(f"✅ Đã ghép nối thành công vào: {full_file_path}")
    
    except Exception as e:
        logging.error(f"❌ Lỗi khi ghi file full.txt: {e}")
    
    # Copy các file riêng lẻ vào thư mục parts (nếu cần)
    if not source_is_parts:
        parts_dir = output_path / 'parts'
        parts_dir.mkdir(parents=True, exist_ok=True)
        
        for file_path in translated_files:
            try:
                dest_file = parts_dir / file_path.name
                dest_file.write_text(file_path.read_text(encoding=encoding), encoding=encoding)
            except Exception as e:
                logging.error(f"Lỗi khi copy file {file_path.name}: {e}")
        
        logging.info(f"✅ Đã copy {len(translated_files)} file vào '{parts_dir}'.")
    else:
        logging.info(f"ℹ️  Các file riêng lẻ đã có sẵn trong '{progress_path}'. Bỏ qua bước copy.")
