# src/file_writer.py - v2.8.2
# Tác giả: Narga
# Chức năng: Module chứa các hàm liên quan đến ghi file.
# Hỗ trợ lưu file với tên gốc và ghép nối linh hoạt.
#
# Nâng cấp v2.8.2:
# - Thêm tham số base_filename vào assemble_final_files() để tạo <base_filename>_full.txt
#   thay vì chỉ full.txt, giúp nhận diện dự án dễ hơn.

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
    file_path.write_text(translated_text, encoding=encoding)
    logging.info(f"Đã lưu file: {filename}")


def save_progress_chunk(
    chunk_text: str,
    chunk_index: int,
    progress_dir: str,
    encoding: str = 'utf-8'
) -> None:
    """
    Lưu chunk đã dịch vào thư mục tiến trình (progress/cache).
    
    Tên file có dạng chunk_XXXXX.txt (5 chữ số với padding 0).
    
    Args:
        chunk_text (str): Nội dung chunk đã dịch
        chunk_index (int): Chỉ số chunk (bắt đầu từ 0)
        progress_dir (str): Đường dẫn thư mục tiến trình
        encoding (str): Encoding để ghi file
    
    Example:
        >>> save_progress_chunk("Đoạn dịch...", 0, "workspace/cache/progress")
        # Lưu vào: workspace/cache/progress/chunk_00000.txt
    """
    progress_path = Path(progress_dir)
    progress_path.mkdir(parents=True, exist_ok=True)
    
    chunk_filename = f"chunk_{chunk_index:05d}.txt"
    chunk_file_path = progress_path / chunk_filename
    chunk_file_path.write_text(chunk_text, encoding=encoding)


def assemble_final_files(
    parts_dir: str,
    output_dir: str,
    encoding: str = 'utf-8',
    source_is_parts: bool = False,
    base_filename: Optional[str] = None
) -> None:
    """
    Ghép nối các chunks/parts đã dịch thành file hoàn chỉnh.
    
    Hàm này tạo hai file trong output_dir:
    1. <base_filename>_full.txt: File ghép nối từ tất cả chunks/parts
    2. parts/ (bản sao): Thư mục chứa các chunks/parts riêng lẻ (nếu source_is_parts=False)
    
    Args:
        parts_dir (str): Thư mục chứa các chunks/parts đã dịch
        output_dir (str): Thư mục output chính
        encoding (str): Encoding để đọc/ghi file
        source_is_parts (bool): Nếu True, parts_dir đã là thư mục output/parts,
                                không cần copy; nếu False, copy từ progress_dir.
        base_filename (Optional[str]): Tên dự án (ví dụ: "my_novel"). Nếu không cung cấp,
                                       dùng tên thư mục output.
    
    Example:
        >>> assemble_final_files(
        ...     "workspace/cache/progress",
        ...     "workspace/output/my_novel",
        ...     base_filename="my_novel"
        ... )
        # Tạo:
        # - workspace/output/my_novel/my_novel_full.txt (ghép nối)
        # - workspace/output/my_novel/parts/ (copy các chunks)
    """
    parts_path = Path(parts_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Xác định tên file output
    if base_filename:
        full_filename = f"{base_filename}_full.txt"
    else:
        # Fallback: dùng tên thư mục output
        full_filename = f"{output_path.name}_full.txt"
    
    full_file_path = output_path / full_filename
    
    # Tìm tất cả chunks/parts (sắp xếp theo tên)
    chunk_files = sorted(parts_path.glob('*.txt'))
    
    if not chunk_files:
        logging.warning(f"⚠️ Không tìm thấy file nào trong '{parts_dir}' để ghép nối.")
        return
    
    # Ghép nối các chunks
    logging.info(f"📝 Đang ghép nối {len(chunk_files)} chunks thành {full_filename}...")
    with open(full_file_path, 'w', encoding=encoding) as full_file:
        for chunk_file in chunk_files:
            try:
                chunk_content = chunk_file.read_text(encoding=encoding)
                full_file.write(chunk_content)
                # Không thêm newline giữa các chunks để giữ nguyên format gốc
            except Exception as e:
                logging.error(f"⚠️ Lỗi khi đọc {chunk_file.name}: {e}")
    
    logging.info(f"✅ Đã tạo file ghép nối: {full_filename}")
    
    # Copy chunks vào output/parts nếu cần (chỉ khi source_is_parts=False)
    if not source_is_parts:
        output_parts_dir = output_path / 'parts'
        output_parts_dir.mkdir(exist_ok=True)
        
        logging.info(f"📂 Sao chép {len(chunk_files)} chunks vào output/parts/...")
        for chunk_file in chunk_files:
            try:
                import shutil
                dest_file = output_parts_dir / chunk_file.name
                shutil.copy2(chunk_file, dest_file)
            except Exception as e:
                logging.error(f"⚠️ Lỗi khi copy {chunk_file.name}: {e}")
        
        logging.info("✅ Đã sao chép chunks vào output/parts/")
