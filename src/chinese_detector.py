# src/chinese_detector.py - v2.6.1
# Tác giả: Narga
# Chức năng: Module chuyên phát hiện và đếm ký tự tiếng Trung trong văn bản.
#            Hỗ trợ tìm kiếm nhanh các file chứa ký tự Hán.

import re
from pathlib import Path
from typing import List, Tuple


# Biểu thức chính quy để phát hiện ký tự Hán (CJK Unified Ideographs)
CHINESE_CHAR_PATTERN = re.compile(r'[\u4e00-\u9fff]')


def has_chinese_characters(text: str) -> bool:
    """
    Kiểm tra xem văn bản có chứa ký tự tiếng Trung (Hán tự) hay không.
    
    Args:
        text (str): Văn bản cần kiểm tra
        
    Returns:
        bool: True nếu có ít nhất 1 ký tự tiếng Trung, False nếu không
        
    Examples:
        >>> has_chinese_characters("Hello World")
        False
        >>> has_chinese_characters("你好 World")
        True
    """
    if not text:
        return False
    
    return bool(CHINESE_CHAR_PATTERN.search(text))


def count_chinese_characters(text: str) -> int:
    """
    Đếm số lượng ký tự tiếng Trung trong văn bản.
    
    Args:
        text (str): Văn bản cần đếm
        
    Returns:
        int: Số lượng ký tự tiếng Trung
        
    Examples:
        >>> count_chinese_characters("你好世界")
        4
        >>> count_chinese_characters("你好 Hello 世界")
        4
    """
    if not text:
        return 0
    
    return len(CHINESE_CHAR_PATTERN.findall(text))


def find_chinese_files(directory: Path, pattern: str = "*.txt") -> List[Tuple[Path, int]]:
    """
    Tìm tất cả các file chứa ký tự tiếng Trung trong thư mục.
    
    Hàm này quét tất cả các file khớp pattern trong thư mục, đọc nội dung
    và kiểm tra xem có chứa ký tự Hán hay không.
    
    Args:
        directory (Path): Đường dẫn đến thư mục cần quét
        pattern (str): Pattern để lọc file (mặc định: "*.txt")
        
    Returns:
        List[Tuple[Path, int]]: Danh sách các file có lỗi.
            Mỗi tuple gồm: (file_path, số_lượng_ký_tự_Trung)
            
    Examples:
        >>> find_chinese_files(Path("output/my_novel/parts"))
        [(Path("output/my_novel/parts/chapter_05.txt"), 12),
         (Path("output/my_novel/parts/chapter_18.txt"), 3)]
    """
    if not directory.exists():
        return []
    
    failed_files = []
    files = sorted(directory.glob(pattern))
    
    for file_path in files:
        try:
            # Đọc nội dung file
            content = file_path.read_text(encoding='utf-8')
            
            # Đếm số ký tự tiếng Trung
            chinese_count = count_chinese_characters(content)
            
            if chinese_count > 0:
                failed_files.append((file_path, chinese_count))
        
        except Exception as e:
            # Bỏ qua các file bị lỗi khi đọc
            continue
    
    return failed_files


def find_chinese_chunks(progress_dir: Path) -> List[Tuple[int, Path, int]]:
    """
    Tìm tất cả các chunks chứa ký tự tiếng Trung trong thư mục progress.
    
    [DEPRECATED in v2.6.1 - Giữ lại để tương thích ngược]
    Sử dụng find_chinese_files() thay thế.
    
    Args:
        progress_dir (Path): Đường dẫn đến thư mục chứa các chunks
        
    Returns:
        List[Tuple[int, Path, int]]: Danh sách các chunks có lỗi.
            Mỗi tuple gồm: (chunk_index, file_path, số_lượng_ký_tự_Trung)
    """
    if not progress_dir.exists():
        return []
    
    failed_chunks = []
    chunk_files = sorted(progress_dir.glob("chunk_*.txt"))
    
    for chunk_file in chunk_files:
        try:
            # Đọc nội dung chunk
            content = chunk_file.read_text(encoding='utf-8')
            
            # Đếm số ký tự tiếng Trung
            chinese_count = count_chinese_characters(content)
            
            if chinese_count > 0:
                # Trích xuất index từ tên file (chunk_5.txt -> 5)
                chunk_index = int(chunk_file.stem.split('_')[1])
                failed_chunks.append((chunk_index, chunk_file, chinese_count))
        
        except Exception as e:
            # Bỏ qua các file bị lỗi khi đọc
            continue
    
    return failed_chunks


def extract_chinese_snippets(text: str, context_chars: int = 20) -> List[str]:
    """
    Trích xuất các đoạn văn bản chứa ký tự tiếng Trung kèm ngữ cảnh xung quanh.
    
    Hữu ích để debug và hiển thị vị trí cụ thể của ký tự tiếng Trung còn sót.
    
    Args:
        text (str): Văn bản cần trích xuất
        context_chars (int): Số ký tự ngữ cảnh trước và sau mỗi ký tự Trung
        
    Returns:
        List[str]: Danh sách các snippet chứa ký tự tiếng Trung với ngữ cảnh
        
    Examples:
        >>> extract_chinese_snippets("Hello 你好 World", context_chars=5)
        ['Hello 你好 World']
    """
    snippets = []
    
    for match in CHINESE_CHAR_PATTERN.finditer(text):
        start = max(0, match.start() - context_chars)
        end = min(len(text), match.end() + context_chars)
        snippet = text[start:end]
        
        # Thêm ... nếu đã cắt
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        
        snippets.append(snippet)
    
    return snippets
