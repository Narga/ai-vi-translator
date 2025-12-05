# file_utils.py

import os
from pathlib import Path
from typing import List

def read_text_file(file_path: Path) -> str:
    """
    Đọc toàn bộ nội dung của một tệp văn bản với mã hóa UTF-8.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Lỗi khi đọc tệp '{file_path}': {e}")
        return ""

def write_html_file(file_path: Path, content: str):
    """
    Ghi nội dung vào một tệp với mã hóa UTF-8.
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"Lỗi khi ghi tệp '{file_path}': {e}")

def find_text_files(directory: Path) -> List[Path]:
    """
    Tìm tất cả các tệp chunk_*.txt và chunk_*.md trong một thư mục và sắp xếp chúng.
    """
    # Tìm cả hai loại tệp và gộp lại thành một danh sách duy nhất
    txt_files = sorted(directory.glob('chunk_*.txt'))
    md_files = sorted(directory.glob('chunk_*.md'))
    
    all_files = sorted(txt_files + md_files)
    return all_files