# parser.py

import re
from typing import Tuple

# (Các mẫu TITLE_PATTERNS giữ nguyên như trước)
TITLE_PATTERNS = [
    re.compile(r'^\s*((quyển|cuốn|phần)\s+\d+.*)', re.IGNORECASE),
    re.compile(r'^\s*((part)\s+\d+.*)', re.IGNORECASE),
    re.compile(r'^\s*((chương|hồi)\s+\d+.*)', re.IGNORECASE),
    re.compile(r'^\s*((chapter|section)\s+\d+.*)', re.IGNORECASE),
    re.compile(r'^\s*(mở\s+đầu|giới\s+thiệu|ngoại\s+truyện|vĩ\s+thanh|lời\s+tựa)', re.IGNORECASE),
    re.compile(r'^\s*(prologue|epilogue|introduction)', re.IGNORECASE),
]


def _cleanup_markdown_title(line: str) -> str:
    """Loại bỏ các ký tự Markdown khỏi một dòng tiêu đề."""
    return re.sub(r'^[#\s]+|\*\*|#+$', '', line).strip()

def extract_full_chapter_title(text_content: str) -> Tuple[str, int]:
    """
    Trích xuất tiêu đề đầy đủ từ 1-2 dòng đầu tiên và số dòng đã sử dụng.
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


def convert_text_to_html(text_content: str, book_title: str, chapter_title: str, book_lang: str, title_line_count: int) -> str:
    """
    Chuyển đổi nội dung văn bản sang HTML, sử dụng tiêu đề đã được trích xuất.
    """
    cleaned_content = text_content.replace('——', '-')
    lines = cleaned_content.split('\n')
    
    html_body_parts = []
    content_lines = lines[title_line_count:]

    for line in content_lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue

        if stripped_line == '***':
            html_body_parts.append('<hr class="separator" />')
            continue
        
        match_heading = re.match(r'^(#+)\s*(.*)', stripped_line)
        match_bold = re.match(r'^\*\*(.*)\*\*$', stripped_line)

        if match_heading:
            level = len(match_heading.group(1))
            text = match_heading.group(2).strip()
            html_body_parts.append(f'<h{level}>{text}</h{level}>')
        elif match_bold:
            text = match_bold.group(1).strip()
            html_body_parts.append(f'<h3>{text}</h3>')
        else:
            html_body_parts.append(f'<p>{stripped_line}</p>')

    body_content = '\n'.join(html_body_parts)

    html_template = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{book_lang}">
<head>
  <meta charset="UTF-8" />
  <title>{chapter_title}</title>
  <link rel="stylesheet" type="text/css" href="../Styles/styles.css" />
</head>
<body>
  <h1>{chapter_title}</h1>
{body_content}
</body>
</html>
"""
    return html_template