# main.py

import argparse
from pathlib import Path
import sys
import shutil

from file_utils import find_text_files, read_text_file, write_html_file
from metadata_parser import parse_metadata
from parser import extract_full_chapter_title, convert_text_to_html
from epub_creator import create_epub

def process_book_directory(directory: Path):
    # ... (phần đầu hàm giữ nguyên) ...
    print(f"=============================================")
    print(f"Bắt đầu xử lý thư mục sách: '{directory}'")
    print(f"=============================================")

    # 1. Kiểm tra và phân tích metadata từ thư mục 'assets'
    assets_dir = directory / 'assets'
    metadata_path = assets_dir / 'metadata.xml'
    
    print(f"\n[1/4] Đang kiểm tra và đọc metadata...")
    if not metadata_path.is_file():
        print(f" LỖI: Không tìm thấy tệp 'metadata.xml' tại '{metadata_path}'.")
        print(f" Vui lòng đảm bảo tệp metadata.xml nằm trong thư mục con 'assets'.")
        sys.exit(1)
    
    print(f" -> Tìm thấy metadata tại: '{metadata_path}'")
    metadata = parse_metadata(metadata_path)
    print(f" -> Phân tích thành công: Tiêu đề '{metadata.get('title')}'")

    # 2. Tìm tệp văn bản nguồn (.txt hoặc .md)
    print(f"\n[2/4] Đang tìm các tệp nội dung (.txt, .md)...")
    txt_files = find_text_files(directory)
    if not txt_files:
        print(" CẢNH BÁO: Không tìm thấy tệp 'chunk_*.txt' hoặc 'chunk_*.md' nào để xử lý.")
        return

    print(f" -> Tìm thấy {len(txt_files)} tệp nội dung.")

    # 3. Chuyển đổi sang HTML
    print(f"\n[3/4] Đang chuyển đổi nội dung sang HTML...")
    xhtml_files = []
    chapter_titles = [] # << MỚI: Danh sách để lưu các tiêu đề chương
    output_dir_temp = directory / "temp_html"
    if not output_dir_temp.exists():
        output_dir_temp.mkdir()

    for txt_path in txt_files:
        print(f"  - Đang xử lý: '{txt_path.name}'")
        content = read_text_file(txt_path)
        if not content:
            continue
        
        # << MỚI: Trích xuất tiêu đề đầy đủ từ nội dung
        full_title, title_lines_count = extract_full_chapter_title(content)
        chapter_titles.append(full_title)
        print(f"    -> Nhận dạng tiêu đề: '{full_title}'")
        
        # << THAY ĐỔI: Truyền tiêu đề và số dòng đã dùng vào hàm convert
        html_content = convert_text_to_html(
            content, 
            metadata.get('title'), 
            full_title, 
            metadata.get('language'), 
            title_lines_count
        )
        
        xhtml_path = output_dir_temp / txt_path.with_suffix('.xhtml').name
        write_html_file(xhtml_path, html_content)
        print(f"    -> Đã tạo tệp HTML tạm tại: '{xhtml_path}'")
        xhtml_files.append(xhtml_path)
    
    print(f" -> Hoàn tất chuyển đổi {len(xhtml_files)} tệp sang HTML.")

    # 4. Gọi module đóng gói EPUB
    print(f"\n[4/4] Đang đóng gói thành tệp EPUB...")
    # << THAY ĐỔI: Truyền danh sách tiêu đề vào hàm create_epub
    create_epub(directory, metadata, xhtml_files, chapter_titles)
    
    # Dọn dẹp thư mục HTML tạm
    shutil.rmtree(output_dir_temp)
    print(f"\n -> Đã dọn dẹp thư mục tạm: '{output_dir_temp}'")
    
    print(f"\n=============================================")
    print(f" TẤT CẢ HOÀN TẤT!")
    print(f"=============================================")


if __name__ == '__main__':
    # ... (phần argparse giữ nguyên) ...
    parser = argparse.ArgumentParser(
        description="Chuyển đổi các tệp văn bản (.txt, .md) và đóng gói thành tệp EPUB3 hoàn chỉnh.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "directory",
        type=str,
        help="Đường dẫn đến thư mục chứa các tệp nguồn (chunk_*.txt, assets/)."
    )
    args = parser.parse_args()
    book_dir = Path(args.directory).resolve()

    if not book_dir.is_dir():
        print(f"Lỗi: Thư mục '{book_dir}' không tồn tại.")
        sys.exit(1)
        
    process_book_directory(book_dir)