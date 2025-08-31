# main.py

import argparse
from pathlib import Path
import sys
import shutil

from file_utils import find_text_files, read_text_file, write_html_file
from metadata_parser import parse_metadata
# Thay đổi import để reflect sự tái cấu trúc của parser.py
from parser import (
    extract_full_chapter_title, convert_plaintext_to_html_body,
    extract_title_from_markdown, convert_markdown_to_html_body,
    build_xhtml, HAS_MARKDOWN
)
from epub_creator import create_epub

def process_book_directory(directory: Path, use_markdown: bool):
    """
    Hàm chính để xử lý toàn bộ thư mục sách, với tùy chọn chế độ xử lý.
    
    Args:
        directory: Đường dẫn đến thư mục sách.
        use_markdown: True nếu xử lý bằng Markdown, False nếu xử lý văn bản thuần túy.
    """
    print(f"=============================================")
    print(f"Bắt đầu xử lý thư mục sách: '{directory}'")
    print(f"Chế độ xử lý: {'Markdown' if use_markdown else 'Văn bản thuần túy (Mặc định)'}")
    print(f"=============================================")

    # 1. Kiểm tra và đọc metadata
    assets_dir = directory / 'assets'
    metadata_path = assets_dir / 'metadata.xml'
    
    print(f"\n[1/4] Đang kiểm tra và đọc metadata...")
    if not metadata_path.is_file():
        print(f" LỖI: Không tìm thấy tệp 'metadata.xml' tại '{metadata_path}'.", file=sys.stderr)
        sys.exit(1)
    
    metadata = parse_metadata(metadata_path)
    print(f" -> Phân tích thành công: Tiêu đề '{metadata.get('title')}'")

    # 2. Tìm tệp nội dung
    print(f"\n[2/4] Đang tìm các tệp nội dung (.txt, .md)...")
    txt_files = find_text_files(directory)
    if not txt_files:
        print(" CẢNH BÁO: Không tìm thấy tệp 'chunk_*.txt' hoặc 'chunk_*.md' nào để xử lý.")
        return
    print(f" -> Tìm thấy {len(txt_files)} tệp nội dung.")

    # 3. Chuyển đổi sang HTML
    print(f"\n[3/4] Đang chuyển đổi nội dung sang HTML...")
    xhtml_files = []
    chapter_titles = []
    output_dir_temp = directory / "temp_html"
    if not output_dir_temp.exists():
        output_dir_temp.mkdir()

    for txt_path in txt_files:
        print(f"  - Đang xử lý: '{txt_path.name}'")
        content = read_text_file(txt_path)
        if not content:
            continue
        
        # TÁI CẤU TRÚC: Lựa chọn luồng xử lý dựa trên tham số
        if use_markdown:
            # --- LUỒNG XỬ LÝ MARKDOWN ---
            chapter_title = extract_title_from_markdown(content)
            body_html = convert_markdown_to_html_body(content)
        else:
            # --- LUỒNG XỬ LÝ VĂN BẢN THUẦN TÚY (MẶC ĐỊNH) ---
            chapter_title, title_lines_count = extract_full_chapter_title(content)
            body_html = convert_plaintext_to_html_body(content, title_lines_count)

        chapter_titles.append(chapter_title)
        print(f"    -> Nhận dạng tiêu đề: '{chapter_title}'")
        
        # Dùng hàm xây dựng XHTML chung
        xhtml_path = output_dir_temp / txt_path.with_suffix('.xhtml').name
        final_xhtml = build_xhtml(
            chapter_title, 
            body_html, 
            metadata.get('language'), 
            "../Styles/styles.css" # Đường dẫn CSS cố định cho cấu trúc EPUB
        )
        
        write_html_file(xhtml_path, final_xhtml)
        print(f"    -> Đã tạo tệp HTML tạm tại: '{xhtml_path}'")
        xhtml_files.append(xhtml_path)
    
    print(f" -> Hoàn tất chuyển đổi {len(xhtml_files)} tệp sang HTML.")

    # 4. Đóng gói EPUB
    print(f"\n[4/4] Đang đóng gói thành tệp EPUB...")
    create_epub(directory, metadata, xhtml_files, chapter_titles)
    
    shutil.rmtree(output_dir_temp)
    print(f"\n -> Đã dọn dẹp thư mục tạm: '{output_dir_temp}'")
    
    print(f"\n=============================================")
    print(f" TẤT CẢ HOÀN TẤT!")
    print(f"=============================================")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Chuyển đổi các tệp văn bản (.txt, .md) và đóng gói thành tệp EPUB3 hoàn chỉnh.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "directory",
        type=str,
        help="Đường dẫn đến thư mục chứa các tệp nguồn (chunk_*.txt, assets/)."
    )
    # THÊM THAM SỐ MỚI
    parser.add_argument(
        "--src-md",
        action="store_true",
        help="Xử lý các tệp nguồn dưới dạng Markdown. Yêu cầu thư viện 'python-markdown'."
    )
    args = parser.parse_args()
    
    # Kiểm tra phụ thuộc nếu cần
    if args.src_md and not HAS_MARKDOWN:
        print("\nLỖI: Chế độ --src-md yêu cầu thư viện 'python-markdown'.", file=sys.stderr)
        print("Vui lòng cài đặt bằng lệnh: pip install markdown", file=sys.stderr)
        sys.exit(1)

    book_dir = Path(args.directory).resolve()
    if not book_dir.is_dir():
        print(f"Lỗi: Thư mục '{book_dir}' không tồn tại.", file=sys.stderr)
        sys.exit(1)
        
    process_book_directory(book_dir, use_markdown=args.src_md)