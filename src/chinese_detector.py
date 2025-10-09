# src/chinese_detector.py - v2.6.3
# Tác giả: Narga
# Chức năng: Module chuyên phát hiện và đếm ký tự tiếng Trung/CJK trong văn bản.
# Nâng cấp v2.6.3:
# - Mở rộng phạm vi phát hiện từ chỉ "CJK Unified Ideographs" sang bao gồm:
#   + CJK Symbols and Punctuation: U+3000..U+303F
#   + Halfwidth and Fullwidth Forms: U+FF00..U+FFEF
#   Nhằm phát hiện triệt để dấu câu/ký tự fullwidth như ，。、《》【】（）— … và khoảng trắng toàn chiều rộng (U+3000).
# - Chuẩn hóa tất cả hàm kiểm tra/đếm/tìm kiếm đều dùng chung một pattern mở rộng để kết quả nhất quán.

import re
from pathlib import Path
from typing import List, Tuple

# --------------------------------------------------------------------------------------
# DẢI UNICODE CẦN PHÁT HIỆN
# --------------------------------------------------------------------------------------
# - CJK Unified Ideographs:        U+4E00..U+9FFF  (chữ Hán cơ bản)
# - CJK Symbols and Punctuation:   U+3000..U+303F  (dấu câu CJK, khoảng trắng fullwidth)
# - Halfwidth and Fullwidth Forms: U+FF00..U+FFEF  (kí tự fullwidth/halfwidth, bao gồm dạng fullwidth của ASCII)
#
# Lưu ý:
# - Không bổ sung Hiragana/Katakana/Bopomofo trong phạm vi này vì yêu cầu hiện tại tập trung vào "ký tự Trung và dấu câu CJK".
# - Có thể mở rộng trong tương lai nếu dự án cần (ví dụ: U+3400..U+4DBF CJK Unified Ideographs Extension A).
#
# Regex dạng character class gộp các dải trên để đạt hiệu năng quét nhanh và dễ bảo trì.
CHINESE_OR_CJK_PATTERN = re.compile(
    r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]'
)

def has_chinese_characters(text: str) -> bool:
    """
    Kiểm tra văn bản có chứa ký tự Trung/CJK không.

    Args:
        text (str): Chuỗi văn bản cần kiểm tra.

    Returns:
        bool: True nếu có ít nhất một ký tự thuộc các dải đã định nghĩa, False nếu không.

    Ghi chú:
        - Hàm dùng pattern mở rộng CHINESE_OR_CJK_PATTERN để bao phủ cả dấu câu/khoảng trắng fullwidth.
        - Đầu vào rỗng/None trả về False để an toàn.
    """
    if not text:
        return False
    return bool(CHINESE_OR_CJK_PATTERN.search(text))

def count_chinese_characters(text: str) -> int:
    """
    Đếm số lượng ký tự Trung/CJK trong văn bản.

    Args:
        text (str): Chuỗi văn bản cần đếm.

    Returns:
        int: Số lượng ký tự thuộc các dải Unicode đã định nghĩa.

    Ví dụ:
        "你好，世界！" → Bao gồm chữ Hán + dấu phẩy/dấu chấm than fullwidth → được tính đầy đủ.
    """
    if not text:
        return 0
    return len(CHINESE_OR_CJK_PATTERN.findall(text))

def find_chinese_files(directory: Path) -> List[Tuple[Path, int]]:
    """
    Quét thư mục (không đệ quy) và trả về danh sách file .txt có chứa ký tự Trung/CJK.

    Args:
        directory (Path): Đường dẫn thư mục cần quét.

    Returns:
        List[Tuple[Path, int]]: Danh sách (đường_dẫn_file, số_ký_tự_CJK) cho các file có chứa ký tự cần phát hiện.

    Thiết kế:
        - Chỉ quét các file .txt để phù hợp pipeline hiện tại (parts/chunk đều là .txt).
        - Đọc với utf-8 và errors='replace' để an toàn trước dữ liệu không chuẩn.
        - Không đệ quy nhằm đảm bảo hiệu năng và tính dự đoán được của pipeline.
    """
    results: List[Tuple[Path, int]] = []
    if not directory.exists() or not directory.is_dir():
        return results

    for file_path in sorted(directory.glob("*.txt")):
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            cnt = count_chinese_characters(text)
            if cnt > 0:
                results.append((file_path, cnt))
        except Exception:
            # Bỏ qua file lỗi đọc để không chặn toàn bộ quy trình
            continue
    return results

def _parse_chunk_index_from_name(name: str) -> int:
    """
    Cố gắng trích xuất chỉ số chunk từ tên file dạng 'chunk_{index}.txt'.

    Args:
        name (str): Tên file.

    Returns:
        int: Chỉ số chunk nếu trích xuất được, ngược lại trả về -1.

    Ghi chú:
        - Không raise exception để không làm vỡ pipeline khi gặp tên file không chuẩn.
    """
    # Mẫu đơn giản: chunk_00012.txt → index = 12
    m = re.match(r'^chunk_(\d+)\.txt$', name, flags=re.IGNORECASE)
    if not m:
        return -1
    try:
        return int(m.group(1))
    except Exception:
        return -1

def find_chinese_chunks(progress_dir: Path) -> List[Tuple[int, Path, int]]:
    """
    Quét thư mục progress và trả về danh sách các chunk còn ký tự Trung/CJK.

    Args:
        progress_dir (Path): Đường dẫn thư mục chứa các file chunk_*.txt.

    Returns:
        List[Tuple[int, Path, int]]: Danh sách (chunk_index, đường_dẫn_file, số_ký_tự_CJK)
                                     sắp xếp theo chunk_index tăng dần (nếu trích xuất được).

    Thiết kế:
        - Chỉ xem xét file bắt đầu bằng 'chunk_' để phù hợp workflow file đơn.
        - Đọc file an toàn bằng utf-8, errors='replace'.
        - Sử dụng pattern mở rộng để phát hiện triệt để cả dấu câu/khoảng trắng fullwidth.
    """
    results: List[Tuple[int, Path, int]] = []
    if not progress_dir.exists() or not progress_dir.is_dir():
        return results

    for file_path in sorted(progress_dir.glob("chunk_*.txt")):
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            cnt = count_chinese_characters(text)
            if cnt > 0:
                idx = _parse_chunk_index_from_name(file_path.name)
                results.append((idx, file_path, cnt))
        except Exception:
            continue

    # Sắp xếp theo index nếu có, đặt các mục không có index (=-1) ở cuối
    results.sort(key=lambda x: (x[0] < 0, x[0]))
    return results
