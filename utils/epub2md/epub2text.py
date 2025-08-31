#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EPUB Converter Pro v2.0.0
=========================

Công cụ dòng lệnh nâng cao để chuyển đổi tệp EPUB sang Markdown, trích xuất
metadata và cung cấp nhiều tùy chọn đầu ra linh hoạt.

Yêu cầu thư viện bên ngoài: html2text
"""

import argparse
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET
from xml.dom import minidom
import html2text

# --- Phần 1: Các hàm tiện ích ---

def safe_filename(name: str) -> str:
    """Tạo ra một tên tệp an toàn từ một chuỗi."""
    name = re.sub(r'\s+', ' ', name.strip())
    name = re.sub(r'[\\/*?:"<>|]+', '_', name)
    return name[:200]

def ensure_dir(path: str):
    """Đảm bảo một thư mục tồn tại, nếu chưa có thì tạo mới."""
    os.makedirs(path, exist_ok=True)

def read_zip_text(zf: zipfile.ZipFile, path: str) -> str:
    """
    Đọc nội dung một tệp văn bản từ bên trong tệp ZIP với khả năng thử
    nhiều bảng mã (encoding) khác nhau.
    """
    try:
        data = zf.read(path)
        for enc in ("utf-8", "utf-16"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        # Fallback an toàn, thay thế các ký tự không hợp lệ
        return data.decode("latin-1", errors="replace")
    except KeyError:
        print(f"Lỗi: Không tìm thấy tệp '{path}' trong EPUB.", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"Lỗi khi đọc tệp '{path}': {e}", file=sys.stderr)
        return ""

def convert_html_to_markdown(html_content: str, preserve_underline: bool = False) -> str:
    """
    Chuyển đổi một chuỗi HTML thành Markdown, với tùy chọn bảo toàn thẻ <u>.
    """
    if not html_content:
        return ""

    # Xử lý đặc biệt cho thẻ <u> nếu được yêu cầu
    if preserve_underline:
        # Thay thế <u> và </u> bằng các placeholder độc nhất để html2text bỏ qua
        html_content = html_content.replace("<u>", "__U_START__")
        html_content = html_content.replace("</u>", "__U_END__")

    h = html2text.HTML2Text()
    h.body_width = 0  # Vô hiệu hóa việc tự động xuống dòng
    h.mark_code = True
    
    try:
        markdown = h.handle(html_content)
    except Exception as e:
        print(f"Lỗi trong quá trình chuyển đổi HTML sang Markdown: {e}", file=sys.stderr)
        return "[Lỗi chuyển đổi nội dung]"

    # Khôi phục lại thẻ <u> nếu cần
    if preserve_underline:
        markdown = markdown.replace("__U_START__", "<u>")
        markdown = markdown.replace("__U_END__", "</u>")
        
    return markdown

# --- Phần 2: Logic phân tích và trích xuất EPUB ---

def get_opf_path(zf: zipfile.ZipFile) -> str:
    """Tìm đường dẫn của tệp .opf từ tệp container.xml."""
    container_path = "META-INF/container.xml"
    try:
        container_xml = read_zip_text(zf, container_path)
        if not container_xml:
            raise FileNotFoundError
        root = ET.fromstring(container_xml)
        ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
        rootfile_element = root.find(".//c:rootfile", ns)
        if rootfile_element is None:
            raise ValueError("Không tìm thấy thẻ <rootfile> trong container.xml")
        return rootfile_element.attrib["full-path"]
    except (FileNotFoundError, ET.ParseError, ValueError) as e:
        print(f"Lỗi nghiêm trọng: Không thể phân tích '{container_path}'. Lý do: {e}", file=sys.stderr)
        sys.exit(1)

def extract_and_save_metadata(zf: zipfile.ZipFile, opf_path: str, out_dir: str):
    """
    Trích xuất toàn bộ khối <metadata> từ tệp .opf và lưu thành tệp .xml.
    """
    print("Đang trích xuất metadata...")
    opf_xml = read_zip_text(zf, opf_path)
    if not opf_xml:
        print("Cảnh báo: Không đọc được tệp OPF để trích xuất metadata.", file=sys.stderr)
        return

    try:
        # Đăng ký namespace để tìm kiếm chính xác
        # Namespace của OPF thường là http://www.idpf.org/2007/opf
        namespaces = {'opf': 'http://www.idpf.org/2007/opf'}
        root = ET.fromstring(opf_xml)
        
        metadata_element = root.find('opf:metadata', namespaces)
        if metadata_element is None:
            # Thử tìm không cần namespace nếu cách trên thất bại
            metadata_element = root.find('.//{*}metadata')

        if metadata_element is None:
            print("Cảnh báo: Không tìm thấy khối <metadata> trong tệp OPF.", file=sys.stderr)
            return

        # Chuyển đổi element thành chuỗi XML và làm đẹp (pretty-print)
        rough_string = ET.tostring(metadata_element, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")

        # Lưu vào tệp
        metadata_path = os.path.join(out_dir, "metadata.xml")
        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write(pretty_xml)
        print("Trích xuất metadata thành công -> metadata.xml")
    except Exception as e:
        print(f"Lỗi khi trích xuất metadata: {e}", file=sys.stderr)

def parse_opf_for_content(zf: zipfile.ZipFile, opf_path: str) -> tuple:
    """Phân tích tệp .opf để lấy manifest (danh sách tệp) và spine (thứ tự đọc)."""
    opf_dir = os.path.dirname(opf_path)
    opf_xml = read_zip_text(zf, opf_path)
    if not opf_xml:
        raise RuntimeError(f"Không đọc được tệp OPF: '{opf_path}'.")

    root = ET.fromstring(opf_xml)
    
    # Hàm nội bộ để tìm thẻ bỏ qua namespace
    def findall_local(elem, tag):
        return elem.findall(f".//{{*}}{tag}")

    manifest_map = {
        item.get("id"): item.get("href")
        for item in findall_local(root, "item")
        if item.get("id") and item.get("href")
    }
    spine_ids = [
        itemref.get("idref") for itemref in findall_local(root, "itemref") if itemref.get("idref")
    ]
    return manifest_map, spine_ids, opf_dir

def get_content_files(zf: zipfile.ZipFile, opf_path: str, include_nonspine: bool) -> list:
    """Lấy danh sách các tệp HTML cần xử lý theo đúng thứ tự."""
    manifest_map, spine_ids, opf_dir = parse_opf_for_content(zf, opf_path)
    all_zip_files = zf.namelist()
    
    def norm_join(href):
        path = os.path.normpath(os.path.join(opf_dir, href))
        return path.replace("\\", "/")

    # Lấy các tệp theo thứ tự trong spine
    spine_paths = []
    spine_path_set = set()
    for idx, idref in enumerate(spine_ids, start=1):
        href = manifest_map.get(idref)
        if href:
            full_path = norm_join(href)
            if full_path in all_zip_files:
                spine_paths.append({'index': idx, 'path': full_path})
                spine_path_set.add(full_path)

    if not include_nonspine:
        return spine_paths

    # Lấy thêm các tệp HTML không nằm trong spine
    extra_paths = []
    all_html_like = {f for f in all_zip_files if f.lower().endswith(('.html', '.xhtml', '.htm'))}
    non_spine_html = sorted(list(all_html_like - spine_path_set))
    for path in non_spine_html:
        extra_paths.append({'index': 'extra', 'path': path})
        
    return spine_paths + extra_paths

# --- Phần 3: Hàm xử lý chính ---

def convert_epub(args):
    """Hàm chính điều khiển toàn bộ quá trình chuyển đổi."""
    print(f"Bắt đầu xử lý tệp: {args.epub_path}")
    ensure_dir(args.out_dir)

    try:
        with zipfile.ZipFile(args.epub_path, 'r') as zf:
            opf_path = get_opf_path(zf)
            
            # Bước 1: Trích xuất metadata
            extract_and_save_metadata(zf, opf_path, args.out_dir)
            print("-" * 20)

            # Bước 2: Lấy danh sách tệp nội dung
            content_files = get_content_files(zf, opf_path, args.include_nonspine)
            total_files = len(content_files)
            if total_files == 0:
                print("Lỗi: Không tìm thấy tệp HTML/XHTML nào hợp lệ trong EPUB.", file=sys.stderr)
                return

            # Bước 3: Chuyển đổi từng tệp và lưu trữ nội dung
            all_content_data = []
            for i, file_info in enumerate(content_files):
                internal_path = file_info['path']
                progress = (i + 1) / total_files * 100
                print(f"Chuyển đổi {i+1}/{total_files} ({progress:.0f}%) -> {internal_path}")
                
                html = read_zip_text(zf, internal_path)
                markdown = convert_html_to_markdown(html, args.underline)
                
                file_info['content'] = markdown
                all_content_data.append(file_info)

            print("-" * 20)
            # Bước 4: Ghi tệp đầu ra dựa trên chế độ
            # Ghi các tệp riêng lẻ
            if args.mode in ['multi', 'both']:
                for item in all_content_data:
                    rel_path = item['path'] if args.preserve_dirs else os.path.basename(item['path'])
                    base_name = os.path.splitext(rel_path)[0]
                    
                    if args.prefix_index and isinstance(item['index'], int):
                        out_name = f"{item['index']:04d}_{safe_filename(base_name)}.{args.ext}"
                    else:
                        out_name = f"{safe_filename(base_name)}.{args.ext}"

                    out_path = os.path.join(args.out_dir, out_name)
                    ensure_dir(os.path.dirname(out_path))
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(item['content'])
                print(f"Đã xuất {total_files} tệp riêng lẻ vào thư mục: {args.out_dir}")

            # Ghi tệp full
            if args.mode in ['single', 'both']:
                full_content = "\n\n---\n\n".join(item['content'] for item in all_content_data)
                epub_base_name = os.path.splitext(os.path.basename(args.epub_path))[0]
                full_filename = f"{safe_filename(epub_base_name)}.{args.ext}"
                full_out_path = os.path.join(args.out_dir, full_filename)
                
                with open(full_out_path, "w", encoding="utf-8") as f:
                    f.write(full_content)
                print(f"Đã tạo tệp full thành công: {full_out_path}")

    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy tệp EPUB tại '{args.epub_path}'", file=sys.stderr)
    except zipfile.BadZipFile:
        print(f"Lỗi: Tệp '{args.epub_path}' không phải là tệp ZIP/EPUB hợp lệ.", file=sys.stderr)
    except Exception as e:
        print(f"Đã xảy ra lỗi không mong muốn: {e}", file=sys.stderr)


# --- Phần 4: Giao diện dòng lệnh (CLI) ---

def main():
    """Hàm chính để chạy chương trình từ dòng lệnh."""
    parser = argparse.ArgumentParser(
        description="EPUB Converter Pro - Chuyển đổi EPUB sang Markdown và trích xuất metadata.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Ví dụ sử dụng:\n"
               "  python %(prog)s mybook.epub -o mybook_output --mode single\n"
               "  python %(prog)s another.epub -u --ext txt"
    )
    
    # Đối số bắt buộc
    parser.add_argument("epub_path", help="Đường dẫn tới tệp .epub cần chuyển đổi.")
    
    # Tùy chọn chính
    parser.add_argument(
        "-o", "--out-dir", 
        default="output",
        help="Thư mục đầu ra để lưu kết quả.\n(Mặc định: output)"
    )
    parser.add_argument(
        "--mode",
        choices=['both', 'single', 'multi'],
        default='both',
        help="Chế độ tạo tệp:\n"
             "  both   - Tạo cả tệp riêng lẻ và tệp full (mặc định).\n"
             "  single - Chỉ tạo tệp full duy nhất.\n"
             "  multi  - Chỉ tạo các tệp riêng lẻ."
    )
    parser.add_argument(
        "--ext",
        choices=['md', 'txt'],
        default='txt',
        help="Đuôi tệp đầu ra cho các tệp nội dung.\n(Mặc định: txt)"
    )
    
    # Tùy chọn định dạng và nội dung
    parser.add_argument(
        "-u", "--underline", 
        action="store_true",
        help="Giữ lại (không chuyển đổi) các cặp thẻ <u>...</u> trong nội dung."
    )
    parser.add_argument(
        "--include-nonspine", 
        action="store_true",
        help="Bao gồm cả các tệp HTML không nằm trong luồng đọc chính."
    )
    
    # Tùy chọn tên tệp và cấu trúc
    parser.add_argument(
        "--preserve-dirs", 
        action="store_true",
        help="Giữ nguyên cấu trúc thư mục của EPUB (chế độ multi/both)."
    )
    parser.add_argument(
        "--no-index-prefix", 
        action="store_false", # Mặc định là True
        dest='prefix_index',
        help="Không thêm tiền tố số thứ tự (0001_) vào tên tệp."
    )
    
    # Tùy chọn thông tin
    parser.add_argument(
        '-v', '--version', 
        action='version', 
        version='%(prog)s 2.0.0'
    )
    
    args = parser.parse_args()
    convert_epub(args)

if __name__ == "__main__":
    main()