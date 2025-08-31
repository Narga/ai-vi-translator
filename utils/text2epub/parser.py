# parser.py

import re
import html
from typing import Tuple, List

# Phụ thuộc tùy chọn, chỉ cần thiết khi người dùng kích hoạt chế độ Markdown
try:
    import markdown as mdlib
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

# ==============================================================================
# == LOGIC CHO CHẾ ĐỘ VĂN BẢN THUẦN TÚY (MẶC ĐỊNH) ===============================
# ==============================================================================

def _cleanup_markdown_title(line: str) -> str:
    """Hàm nội bộ: Loại bỏ các ký tự Markdown khỏi một dòng tiêu đề."""
    # Loại bỏ các dấu # ở đầu, các dấu * hoặc _ ở hai bên
    return re.sub(r'^[#\s]+|(\*\*|__)(.*?)\1|#+$', r'\2', line).strip()

def extract_full_chapter_title(text_content: str) -> Tuple[str, int]:
    """
    [Plain Text Mode] Trích xuất tiêu đề đầy đủ từ 1-2 dòng đầu tiên của văn bản
    thuần túy và trả về số dòng đã được sử dụng cho tiêu đề.

    Returns:
        Một tuple chứa (chuỗi tiêu đề đầy đủ, số dòng đã dùng).
    """
    cleaned_content = text_content.replace('——', '-')
    lines = [line.strip() for line in cleaned_content.split('\n') if line.strip()]
    
    if not lines:
        return "Chương không có tiêu đề", 0

    main_title = _cleanup_markdown_title(lines[0])
    full_title = main_title
    title_line_count = 1

    if len(lines) > 1:
        subtitle_candidate = lines[1]
        if len(subtitle_candidate.split()) <= 10:
            subtitle = _cleanup_markdown_title(subtitle_candidate)
            full_title = f"{main_title}: {subtitle}"
            title_line_count = 2
            
    return full_title, title_line_count

def convert_plaintext_to_html_body(text_content: str, title_line_count: int) -> str:
    """
    [Plain Text Mode] Chuyển đổi phần thân của văn bản thuần túy sang HTML,
    bỏ qua các dòng đã được xác định là tiêu đề.
    """
    cleaned_content = text_content.replace('——', '-')
    lines = cleaned_content.split('\n')
    
    html_body_parts = []
    # Chỉ xử lý các dòng sau phần tiêu đề
    content_lines = lines[title_line_count:]

    for line in content_lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue

        if stripped_line == '***':
            html_body_parts.append('<hr class="separator" />')
            continue
        
        # Nhận dạng các định dạng đơn giản còn lại
        match_heading = re.match(r'^(#+)\s*(.*)', stripped_line)
        match_bold = re.match(r'^\*\*(.*)\*\*$', stripped_line)

        if match_heading:
            level = len(match_heading.group(1))
            text = match_heading.group(2).strip()
            html_body_parts.append(f'<h{level}>{html.escape(text)}</h{level}>')
        elif match_bold:
            text = match_bold.group(1).strip()
            html_body_parts.append(f'<h3>{html.escape(text)}</h3>')
        else:
            html_body_parts.append(f'<p>{html.escape(stripped_line)}</p>')

    return '\n'.join(html_body_parts)

# ==============================================================================
# == LOGIC CHO CHẾ ĐỘ MARKDOWN (KÍCH HOẠT BỞI --src-md) =========================
# ==============================================================================

def extract_title_from_markdown(text_content: str) -> str:
    """
    [Markdown Mode] Trích xuất tiêu đề từ thẻ H1 đầu tiên trong văn bản Markdown.
    """
    # Tìm dòng đầu tiên bắt đầu bằng '# ' (H1)
    match = re.search(r'^\s*#\s+(.*)', text_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Chương không có tiêu đề"

def convert_markdown_to_html_body(text_content: str) -> str:
    """
    [Markdown Mode] Chuyển đổi toàn bộ văn bản Markdown sang HTML
    sử dụng thư viện python-markdown.
    """
    if not HAS_MARKDOWN:
        # Trường hợp này sẽ được kiểm tra ở main.py, nhưng thêm vào để đảm bảo an toàn
        raise ImportError("Thư viện 'markdown' là bắt buộc cho chế độ này.")
        
    # Sử dụng các extension phổ biến để hỗ trợ bảng, danh sách, v.v.
    return mdlib.markdown(text_content, extensions=["extra", "sane_lists", "tables"])

# ==============================================================================
# == HÀM DÙNG CHUNG: XÂY DỰNG FILE XHTML HOÀN CHỈNH =============================
# ==============================================================================

def build_xhtml(chapter_title: str, body_html: str, book_lang: str, css_href: str) -> str:
    """
    Xây dựng một tài liệu XHTML hoàn chỉnh từ tiêu đề và phần thân HTML đã được xử lý.
    Hàm này được cả hai chế độ (plain text và markdown) sử dụng.
    """
    # Mẫu HTML5 tuân thủ chuẩn EPUB3
    html_template = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{book_lang}">
<head>
  <meta charset="UTF-8" />
  <title>{html.escape(chapter_title)}</title>
  <link rel="stylesheet" type="text/css" href="{css_href}" />
</head>
<body>
  <h1>{html.escape(chapter_title)}</h1>
{body_html}
</body>
</html>
"""
    return html_template