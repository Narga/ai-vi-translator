import re
from pathlib import Path
from bs4 import BeautifulSoup
from plugins.epub_converter.epub_to_text.epub2text import convert_html_to_markdown

def _extract_body(html: str) -> str:
    """Trích xuất phần nội dung nằm giữa thẻ <body>...</body>"""
    if not html:
        return ""
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.find('body')
    if body:
        # Lấy HTML nội bộ trong body mà không lấy bản thân thẻ <body>
        return body.decode_contents()
    return html

def _preprocess_ruby(html: str) -> str:
    """Chuyển đổi thẻ <ruby> thành cấu trúc 漢字《かな》"""
    if not html:
        return ""
    # Thay thế ruby: <ruby>漢字<rt>かな</rt></ruby> -> 漢字《かな》
    pattern = re.compile(r'<ruby[^>]*>(.*?)<rt[^>]*>(.*?)</rt></ruby>', re.DOTALL | re.IGNORECASE)
    return pattern.sub(r'\1《\2》', html)

def post_clean(md: str) -> str:
    """Làm sạch Markdown đầu ra (dòng trống thừa, comment, thực thể html, inlining reference links).

    Invariants: hậu xử lý chỉ chuẩn hóa whitespace/format, không làm mất
    nội dung ngữ nghĩa như alt ảnh, URL hay text hiển thị.
    """
    if not md:
        return ""

    # 1. Xóa comments HTML
    md = re.sub(r'<!--.*?-->', '', md, flags=re.DOTALL)

    # 2. Xóa các thẻ style và script nếu còn sót
    md = re.sub(r'<style[\s\S]*?</style>', '', md, flags=re.IGNORECASE)
    md = re.sub(r'<script[\s\S]*?</script>', '', md, flags=re.IGNORECASE)

    # 3. Gom reference-style links thành inline links
    defs = {}
    def_pattern = re.compile(r'^\[(\d+)\]:\s*(\S+)', re.MULTILINE)
    for match in def_pattern.finditer(md):
        defs[match.group(1)] = match.group(2)

    def replace_link(match):
        text = match.group(1)
        num = match.group(2)
        if num in defs:
            return f"[{text}]({defs[num]})"
        return match.group(0)

    md = re.sub(r'\[([^\]]+)\]\s*\[(\d+)\]', replace_link, md)
    md = def_pattern.sub('', md)

    # 4. Gom nhiều dòng trống liên tiếp thành tối đa 2 dòng trống
    md = re.sub(r'\n{3,}', '\n\n', md)

    # 5. Chuẩn hóa &nbsp; thành khoảng trắng
    md = md.replace('&nbsp;', ' ')

    return md.strip()

def normalize_html_content(html_content: str) -> str:
    """Tiền xử lý nội dung HTML thành Markdown (không ghi file).

    Raises:
        ImportError: nếu thiếu html2text.
        ValueError: nếu chuyển đổi thất bại.
    """
    # 1. Trích xuất body
    body_content = _extract_body(html_content)

    # 2. Xử lý ruby
    body_content = _preprocess_ruby(body_content)

    # 3. Chuẩn hóa thẻ gạch chân <u>
    body_content = re.sub(r'<u[^>]*>', '<u>', body_content, flags=re.IGNORECASE)
    body_content = re.sub(r'</u>', '</u>', body_content, flags=re.IGNORECASE)

    # 4. Chuyển đổi HTML -> Markdown qua convert_html_to_markdown (bảo toàn thẻ <u>)
    md_content = convert_html_to_markdown(body_content, preserve_underline=True)

    # 5. Làm sạch Markdown sau khi convert
    return post_clean(md_content)


def normalize_html_file(input_path: str) -> str:
    """
    Tiền xử lý file HTML thành Markdown offline, lưu file .md tại cùng vị trí.
    Trả về đường dẫn file .md được tạo.
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {input_path}")

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        html_content = f.read()

    cleaned_md = normalize_html_content(html_content)

    output_path = path.with_suffix('.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_md)

    return str(output_path)
