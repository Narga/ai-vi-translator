# parser.py

import re
import html
from typing import Tuple, List, Dict

# Phụ thuộc tùy chọn, chỉ cần thiết khi người dùng kích hoạt chế độ Markdown
try:
    import markdown as mdlib
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

# ==============================================================================
# == LOGIC CHO CHẾ ĐỘ VĂN BẢN THUẦN TÚY (MẶC ĐỊNH) ===============================
# ==============================================================================

# <<< THAY ĐỔI: Biểu thức chính quy được cập nhật và chia thành hai loại để tăng độ chính xác >>>
# Loại 1: Các từ khóa thường đi kèm số (Chương 1, Quyển 2, v.v.)
TITLE_PATTERNS_NUMERIC = re.compile(
    r'^\s*((chương|hồi|quyển|cuốn|phần)\s+\d+.*)', 
    re.IGNORECASE
)
# Loại 2: Các từ khóa đứng một mình (Ngoại truyện, Vĩ thanh, v.v.)
# <<< SỬA LỖI: Loại bỏ ký tự '$' cuối để cho phép có thêm nội dung sau từ khóa, ví dụ "Ngoại truyện 1" >>>
TITLE_PATTERNS_STANDALONE = re.compile(
    r'^\s*(mở\s+đầu|giới\s+thiệu|ngoại\s+truyện|vĩ\s+thanh|kết\s+thúc|phi|lộ).*', 
    re.IGNORECASE
)

def _get_clean_text_for_matching(line: str) -> str:
    """
    Hàm nội bộ: "Làm sạch" một dòng văn bản khỏi các định dạng Markdown phổ biến
    để có thể đối chiếu chính xác với các biểu thức chính quy.
    """
    return re.sub(r'^[#\s*_-]+|[#\s*_-]+$', '', line).strip()

def parse_text_into_chapters(text_content: str) -> List[Dict[str, str]]:
    """
    [Plain Text Mode] Phân tích văn bản thô thành một danh sách các chương.
    Mỗi chương là một dictionary chứa 'title' và 'content'.
    """
    chapters: List[Dict[str, str]] = []
    lines = text_content.splitlines()
    
    current_chapter_lines: List[str] = []

    for line in lines:
        stripped_line = line.strip()
        
        # Bỏ qua các dòng trống giữa các chương
        if not stripped_line and not current_chapter_lines:
            continue

        clean_line = _get_clean_text_for_matching(stripped_line)
        is_chapter_marker = bool(TITLE_PATTERNS_NUMERIC.match(clean_line) or TITLE_PATTERNS_STANDALONE.match(clean_line)) if clean_line else False
        
        if is_chapter_marker:
            # Khi gặp một mốc chương mới, chương cũ (nếu có) sẽ kết thúc.
            if current_chapter_lines:
                title = current_chapter_lines[0]
                content = "\n".join(current_chapter_lines[1:])
                chapters.append({"title": title, "content": content})
            
            # Bắt đầu một chương mới với dòng tiêu đề vừa tìm thấy
            current_chapter_lines = [stripped_line]
        else:
            # Nếu không phải mốc chương, thêm dòng vào nội dung của chương hiện tại
            current_chapter_lines.append(line)
            
    # Xử lý khối cuối cùng sau khi vòng lặp kết thúc
    if current_chapter_lines:
        title = current_chapter_lines[0]
        content = "\n".join(current_chapter_lines[1:])
        chapters.append({"title": title, "content": content})
        
    # <<< SỬA LỖI: Loại bỏ hoàn toàn logic post-processing gây ra lỗi gán nhãn "Phần mở đầu" >>>
    # Logic mới giờ đây sẽ xử lý chính xác ngay trong vòng lặp.
    # Nếu có nội dung trước chương đầu tiên, nó sẽ được gom lại và lấy dòng đầu tiên làm tiêu đề,
    # người dùng có thể đặt tên là "Phi lộ", "Giới thiệu", v.v. và script sẽ tôn trọng điều đó.
            
    return chapters

def convert_plaintext_to_html_body(chapter_content: str) -> str:
    """
    [Plain Text Mode] Chuyển đổi NỘI DUNG của một chương sang các thẻ HTML <p>.
    """
    cleaned_content = chapter_content.replace('——', '-')
    if not cleaned_content.strip():
        return ""

    html_body_parts = []
    paragraphs = re.split(r'\n\s*\n', cleaned_content.strip())
    for p_text in paragraphs:
        stripped_p = p_text.strip()
        if stripped_p:
            p_html = html.escape(stripped_p)
            p_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', p_html)
            p_html = re.sub(r'_(.*?)_', r'<em>\1</em>', p_html)
            html_body_parts.append(f'<p>{p_html}</p>')
    
    return '\n'.join(html_body_parts)

# ==============================================================================
# == LOGIC CHO CHẾ ĐỘ MARKDOWN (GIỮ NGUYÊN) =====================================
# ==============================================================================

def extract_title_from_markdown(text_content: str) -> str:
    match = re.search(r'^\s*#\s+(.*)', text_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Chương không có tiêu đề"

def convert_markdown_to_html_body(text_content: str) -> str:
    if not HAS_MARKDOWN:
        raise ImportError("Thư viện 'markdown' là bắt buộc cho chế độ này.")
    return mdlib.markdown(text_content, extensions=["extra", "sane_lists", "tables"])

# ==============================================================================
# == HÀM DÙNG CHUNG: XÂY DỰNG FILE XHTML (GIỮ NGUYÊN) ===========================
# ==============================================================================

def build_xhtml(chapter_title: str, body_html: str, book_lang: str, css_href: str) -> str:
    """
    Xây dựng một tài liệu XHTML hoàn chỉnh.
    """
    clean_title = _get_clean_text_for_matching(chapter_title)
    
    return "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!DOCTYPE html>',
        f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{book_lang}" lang="{book_lang}">',
        "<head>",
        '  <meta charset="utf-8"/>',
        f'  <title>{html.escape(clean_title)}</title>',
        f'  <link rel="stylesheet" type="text/css" href="{css_href}" />',
        "</head>",
        "<body>",
        f"  <h1>{html.escape(clean_title)}</h1>",
        body_html,
        "</body>",
        "</html>",
    ])