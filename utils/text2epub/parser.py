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

# Biểu thức chính quy để nhận dạng dòng bắt đầu một chương.
TITLE_PATTERNS = [
    re.compile(r'^\s*((chương|hồi|quyển|cuốn|phần)\s+\d+.*)', re.IGNORECASE),
    re.compile(r'^\s*((chapter|part|section)\s+\d+.*)', re.IGNORECASE),
    re.compile(r'^\s*(mở\s+đầu|giới\s+thiệu|ngoại\s+truyện|vĩ\s+thanh)', re.IGNORECASE),
    re.compile(r'^\s*(prologue|epilogue|introduction)', re.IGNORECASE),
]

def _cleanup_markdown_title(line: str) -> str:
    """Hàm nội bộ: Loại bỏ các ký tự Markdown khỏi một dòng tiêu đề."""
    # Loại bỏ các dấu # ở đầu, các dấu * hoặc _ ở hai bên
    cleaned = re.sub(r'^[#\s]+', '', line) # Bỏ dấu heading
    cleaned = re.sub(r'^(\*\*|__)(.*?)(\1)$', r'\2', cleaned) # Bỏ dấu bold
    cleaned = re.sub(r'^(\*|_)(.*?)(\1)$', r'\2', cleaned) # Bỏ dấu italic
    return cleaned.strip()

def parse_text_into_chapters(text_content: str) -> List[Dict[str, str]]:
    """
    [Plain Text Mode] Phân tích văn bản thô thành một danh sách các chương.
    Mỗi chương là một dictionary chứa 'title' và 'content'.
    - Dòng khớp với TITLE_PATTERNS được coi là mốc bắt đầu chương.
    - Dòng ngay sau đó có định dạng Markdown (heading, bold, italic) được coi là tiêu đề phụ.
    """
    chapters: List[Dict[str, str]] = []
    lines = text_content.splitlines()
    
    current_content_lines: List[str] = []
    current_title = "Phần mở đầu" # Tiêu đề mặc định cho nội dung trước chương đầu tiên

    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Kiểm tra xem dòng hiện tại có phải là một mốc chương mới không
        is_chapter_marker = any(pat.match(line) for pat in TITLE_PATTERNS)
        
        if is_chapter_marker:
            # 1. Lưu lại chương trước đó (nếu có nội dung)
            if current_content_lines:
                chapters.append({
                    "title": current_title,
                    "content": "\n".join(current_content_lines).strip()
                })
            
            # 2. Bắt đầu xử lý chương mới
            main_title = line.strip()
            current_content_lines = []
            
            # 3. Kiểm tra dòng tiếp theo xem có phải tiêu đề phụ không
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                # Biểu thức regex để kiểm tra định dạng heading, bold, hoặc italic
                is_subtitle_format = re.match(r'^\s*(#+\s*.*|(\*\*|__|\*|_).*\2\s*)$', next_line)
                if next_line and is_subtitle_format:
                    subtitle = _cleanup_markdown_title(next_line)
                    current_title = f"{main_title}: {subtitle}"
                    i += 1 # Bỏ qua dòng tiêu đề phụ này
                else:
                    current_title = main_title
            else:
                current_title = main_title
        else:
            # Nếu không phải mốc chương, thêm dòng vào nội dung của chương hiện tại
            current_content_lines.append(line)
        
        i += 1
        
    # Lưu lại chương cuối cùng trong tệp
    if current_content_lines:
        chapters.append({
            "title": current_title,
            "content": "\n".join(current_content_lines).strip()
        })
        
    return chapters

def convert_plaintext_to_html_body(chapter_content: str) -> str:
    """
    [Plain Text Mode] Chuyển đổi nội dung của MỘT chương (văn bản thuần túy) sang các thẻ HTML <p>.
    """
    cleaned_content = chapter_content.replace('——', '-')
    if not cleaned_content.strip():
        return ""

    html_body_parts = []
    # Chia nội dung thành các đoạn dựa trên các dòng trống
    paragraphs = re.split(r'\n\s*\n', cleaned_content)
    for p_text in paragraphs:
        stripped_p = p_text.strip()
        if stripped_p:
            html_body_parts.append(f'<p>{html.escape(stripped_p)}</p>')
    
    return '\n'.join(html_body_parts)

# ==============================================================================
# == LOGIC CHO CHẾ ĐỘ MARKDOWN (KÍCH HOẠT BỞI --src-md) =========================
# ==============================================================================

def extract_title_from_markdown(text_content: str) -> str:
    """
    [Markdown Mode] Trích xuất tiêu đề từ thẻ H1 đầu tiên trong văn bản Markdown.
    """
    match = re.search(r'^\s*#\s+(.*)', text_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Chương không có tiêu đề"

def convert_markdown_to_html_body(text_content: str) -> str:
    """
    [Markdown Mode] Chuyển đổi toàn bộ văn bản Markdown sang HTML.
    """
    if not HAS_MARKDOWN:
        raise ImportError("Thư viện 'markdown' là bắt buộc cho chế độ này.")
    return mdlib.markdown(text_content, extensions=["extra", "sane_lists", "tables"])

# ==============================================================================
# == HÀM DÙNG CHUNG: XÂY DỰNG FILE XHTML HOÀN CHỈNH =============================
# ==============================================================================

def build_xhtml(chapter_title: str, body_html: str, book_lang: str, css_href: str) -> str:
    """
    Xây dựng một tài liệu XHTML hoàn chỉnh từ tiêu đề và phần thân HTML đã được xử lý.
    Hàm này tuân thủ các đặc tả của EPUB 3.
    """
    return "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<!DOCTYPE html>',
        # Khai báo namespace XHTML là bắt buộc cho EPUB 3.
        # xml:lang và lang đảm bảo khả năng tương thích tối đa.
        f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{book_lang}" lang="{book_lang}">',
        "<head>",
        '  <meta charset="utf-8"/>',
        f'  <title>{html.escape(chapter_title)}</title>',
        f'  <link rel="stylesheet" type="text/css" href="{css_href}" />',
        "</head>",
        "<body>",
        f"  <h1>{html.escape(chapter_title)}</h1>",
        body_html,
        "</body>",
        "</html>",
    ])