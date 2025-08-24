# file_writer.py - v1.2
import os
import re
import glob
import logging
from typing import List

def save_progress_chunk(
    chunk_content: str, chunk_index: int, progress_dir: str, encoding: str
) -> None:
    os.makedirs(progress_dir, exist_ok=True)
    file_path = os.path.join(progress_dir, f"chunk_{chunk_index:05d}.txt")
    with open(file_path, 'w', encoding=encoding) as f:
        f.write(chunk_content)

def _create_chapter_files(
    full_content: str, output_dir: str, base_filename: str,
    encoding: str, create_combined: bool
) -> None:
    logging.info(f"📑 Bắt đầu phân tích và tạo file chương tại '{output_dir}'...")
    os.makedirs(output_dir, exist_ok=True)
    chapter_pattern = re.compile(r'\*{2}(.*?)\*{2}')
    split_content = chapter_pattern.split(full_content)
    intro_content = split_content[0].strip()
    if intro_content:
        intro_path = os.path.join(output_dir, f"{base_filename}_gioi_thieu.txt")
        with open(intro_path, 'w', encoding=encoding) as f: f.write(intro_content)
        logging.info(f"  - Đã ghi: {os.path.basename(intro_path)}")
    chapter_index = 1
    for i in range(1, len(split_content), 2):
        title = split_content[i].strip()
        content = split_content[i+1].strip()
        safe_title_part = re.sub(r'[^\w\s-]', '', title).replace(' ', '_')
        if len(safe_title_part) > 50: safe_title_part = safe_title_part[:50]
        chapter_filename = f"{base_filename}_chuong_{chapter_index:03d}_{safe_title_part}.txt"
        chapter_path = os.path.join(output_dir, chapter_filename)
        with open(chapter_path, 'w', encoding=encoding) as f:
            f.write(f"**{title}**\n\n{content}")
        logging.info(f"  - Đã ghi: {chapter_filename}")
        chapter_index += 1
    if create_combined:
        combined_path = os.path.join(output_dir, f"{base_filename}_full.txt")
        with open(combined_path, 'w', encoding=encoding) as f: f.write(full_content)
        logging.info(f"  - Đã ghi file tổng hợp: {os.path.basename(combined_path)}")

def assemble_final_files(
    progress_dir: str, output_dir: str, base_filename: str,
    encoding: str, create_combined: bool
) -> None:
    logging.info("\n✅ Tất cả các chunk đã được dịch xong. Bắt đầu ghép file cuối cùng...")
    chunk_files = sorted(glob.glob(os.path.join(progress_dir, "chunk_*.txt")))
    if not chunk_files:
        logging.warning("⚠️ Không tìm thấy file chunk nào để ghép. Bỏ qua bước này.")
        return
    full_translated_content = []
    for f in chunk_files:
        with open(f, 'r', encoding=encoding) as chunk_file:
            full_translated_content.append(chunk_file.read())
    final_text = "\n\n".join(full_translated_content)
    _create_chapter_files(
        full_content=final_text, output_dir=output_dir, base_filename=base_filename,
        encoding=encoding, create_combined=create_combined
    )