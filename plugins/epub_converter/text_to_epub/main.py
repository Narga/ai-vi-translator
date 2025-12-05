# main.py

import argparse
from pathlib import Path
import sys
import shutil
import re
import html

from file_utils import find_text_files, read_text_file, write_html_file
from metadata_parser import parse_metadata
from parser import (
    parse_text_into_chapters, convert_plaintext_to_html_body,
    extract_title_from_markdown, convert_markdown_to_html_body,
    build_xhtml, HAS_MARKDOWN
)
from epub_creator import create_epub

def process_book_directory(directory: Path, use_markdown: bool, split_chapters: bool):
    """
    Hàm chính để xử lý toàn bộ thư mục sách, với các tùy chọn chế độ.
    """
    print(f"=============================================")
    print(f"Bắt đầu xử lý thư mục sách: '{directory}'")
    mode = "Markdown" if use_markdown else "Văn bản thuần túy"
    if split_chapters and not use_markdown:
        mode += " (Tách chương)"
    print(f"Chế độ xử lý: {mode}")
    print(f"=============================================")

    # 1. Đọc metadata
    assets_dir = directory / 'assets'
    metadata_path = assets_dir / 'metadata.xml'
    print(f"\n[1/4] Đang kiểm tra và đọc metadata...")
    if not metadata_path.is_file():
        print(f" LỖI: Không tìm thấy tệp 'metadata.xml' tại '{metadata_path}'.", file=sys.stderr)
        sys.exit(1)
    metadata = parse_metadata(metadata_path)
    print(f" -> Phân tích thành công: Tiêu đề '{metadata.get('title')}'")

    # 2. Tìm tệp nguồn
    print(f"\n[2/4] Đang tìm các tệp nội dung (.txt, .md)...")
    txt_files = find_text_files(directory)
    if not txt_files:
        print(" CẢNH BÁO: Không tìm thấy tệp 'chunk_*.txt' hoặc 'chunk_*.md' nào để xử lý.")
        return
    print(f" -> Tìm thấy {len(txt_files)} tệp nội dung.")

    # 3. Chuẩn bị và chuyển đổi sang HTML
    print(f"\n[3/4] Đang chuyển đổi nội dung sang HTML...")
    all_xhtml_files = []
    all_chapter_titles = []
    output_dir_temp = directory / "temp_html"
    if output_dir_temp.exists():
        shutil.rmtree(output_dir_temp)
    output_dir_temp.mkdir()

    for txt_path in txt_files:
        print(f"  - Đang xử lý: '{txt_path.name}'")
        content = read_text_file(txt_path)
        if not content:
            continue
        
        if use_markdown:
            # --- LUỒNG MARKDOWN (1 tệp nguồn -> 1 tệp đích) ---
            chapter_title = extract_title_from_markdown(content)
            body_html = convert_markdown_to_html_body(content)
            
            all_chapter_titles.append(chapter_title)
            xhtml_path = output_dir_temp / txt_path.with_suffix('.xhtml').name
            
            final_xhtml = build_xhtml(
                chapter_title, body_html, metadata.get('language'), "../Styles/styles.css"
            )
            write_html_file(xhtml_path, final_xhtml)
            print(f"    -> Đã tạo tệp HTML tạm tại: '{xhtml_path}'")
            all_xhtml_files.append(xhtml_path)
        else:
            # --- LUỒNG VĂN BẢN THUẦN TÚY ---
            chapters = parse_text_into_chapters(content)
            if not chapters:
                print(f"    -> Cảnh báo: Không tìm thấy nội dung hợp lệ trong {txt_path.name}")
                continue
            
            if split_chapters and len(chapters) > 1:
                # Tách thành nhiều file XHTML
                print(f"    -> Phát hiện {len(chapters)} chương, đang tách tệp...")
                for i, chapter in enumerate(chapters):
                    chapter_title = chapter.get('title', f"Chương không tên {i+1}")
                    body_html = convert_plaintext_to_html_body(chapter.get('content', ''))
                    
                    all_chapter_titles.append(chapter_title)
                    safe_title = re.sub(r'[^\w-]', '', chapter_title.replace(' ', '_'))[:30]
                    xhtml_name = f"{txt_path.stem}_{i+1:03d}_{safe_title}.xhtml"
                    xhtml_path = output_dir_temp / xhtml_name
                    
                    final_xhtml = build_xhtml(
                        chapter_title, body_html, metadata.get('language'), "../Styles/styles.css"
                    )
                    write_html_file(xhtml_path, final_xhtml)
                    print(f"      -> Đã tạo tệp chương: '{xhtml_path.name}'")
                    all_xhtml_files.append(xhtml_path)
            else:
                # <<< THAY ĐỔI: Logic gộp chương được viết lại để tránh lặp lại tiêu đề >>>
                # Gộp tất cả các chương trong một file thành một file XHTML duy nhất
                full_body_html_parts = []
                # Tiêu đề của file là tiêu đề của chương đầu tiên
                doc_title = chapters[0].get('title', metadata.get('title', 'Untitled')) if chapters else metadata.get('title', 'Untitled')
                all_chapter_titles.append(doc_title)
                
                # Hàm build_xhtml sẽ tạo H1 cho doc_title, nên chúng ta sẽ tạo H2 cho các chương con bên trong
                for i, chapter in enumerate(chapters):
                    # Nếu là chương đầu tiên, tiêu đề của nó đã được dùng làm H1, nên chỉ cần in nội dung
                    if i == 0:
                        full_body_html_parts.append(convert_plaintext_to_html_body(chapter.get('content', '')))
                    else: # Với các chương tiếp theo, in tiêu đề dưới dạng H2
                        chapter_title = chapter.get('title', 'Chương không xác định')
                        full_body_html_parts.append(f"<h2>{html.escape(chapter_title)}</h2>")
                        full_body_html_parts.append(convert_plaintext_to_html_body(chapter.get('content', '')))
                
                xhtml_path = output_dir_temp / txt_path.with_suffix('.xhtml').name
                final_xhtml = build_xhtml(
                    doc_title, "\n".join(full_body_html_parts), metadata.get('language'), "../Styles/styles.css"
                )
                write_html_file(xhtml_path, final_xhtml)
                print(f"    -> Đã tạo tệp HTML tạm tại: '{xhtml_path}'")
                all_xhtml_files.append(xhtml_path)

    print(f" -> Hoàn tất chuyển đổi. Tổng cộng {len(all_xhtml_files)} tệp XHTML được tạo.")

    # 4. Đóng gói EPUB
    print(f"\n[4/4] Đang đóng gói thành tệp EPUB...")
    create_epub(directory, metadata, all_xhtml_files, all_chapter_titles)
    
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
    parser.add_argument("directory", type=str, help="Đường dẫn đến thư mục chứa các tệp nguồn (chunk_*.txt, assets/).")
    parser.add_argument(
        "--src-md", action="store_true",
        help="Xử lý các tệp nguồn dưới dạng Markdown. Yêu cầu thư viện 'python-markdown'."
    )
    parser.add_argument(
        "--split-chapters", action="store_true",
        help="[Chế độ Plain Text] Tách một tệp .txt chứa nhiều chương thành nhiều tệp .xhtml riêng biệt."
    )
    args = parser.parse_args()
    
    if args.src_md and not HAS_MARKDOWN:
        print("\nLỖI: Chế độ --src-md yêu cầu thư viện 'python-markdown'.", file=sys.stderr)
        print("Vui lòng cài đặt bằng lệnh: pip install markdown", file=sys.stderr)
        sys.exit(1)

    book_dir = Path(args.directory).resolve()
    if not book_dir.is_dir():
        print(f"Lỗi: Thư mục '{book_dir}' không tồn tại.", file=sys.stderr)
        sys.exit(1)
        
    process_book_directory(book_dir, use_markdown=args.src_md, split_chapters=args.split_chapters)