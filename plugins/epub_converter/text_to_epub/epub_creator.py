# epub_creator.py

import os
import shutil
import zipfile
import html
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timezone

# (Các hằng số MIMETYPE và CONTAINER_XML giữ nguyên)
MIMETYPE = "application/epub+zip"
CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

def create_epub(source_dir: Path, book_info: Dict, xhtml_files: List[Path], chapter_titles: List[str]):
    # ... (Phần đầu hàm giữ nguyên) ...
    epub_build_dir = source_dir / "epub_build"
    oebps_dir = epub_build_dir / "OEBPS"
    assets_dir = source_dir / "assets"
    
    if epub_build_dir.exists():
        shutil.rmtree(epub_build_dir)
    oebps_dir.mkdir(parents=True, exist_ok=True)
    
    text_dir = oebps_dir / "Text"; text_dir.mkdir()
    styles_dir = oebps_dir / "Styles"; styles_dir.mkdir()
    images_dir = oebps_dir / "Images"; images_dir.mkdir()
    fonts_dir = oebps_dir / "Fonts"; fonts_dir.mkdir()
    (epub_build_dir / "META-INF").mkdir()
    
    print(f" -> Đã tạo cấu trúc thư mục tạm tại: '{epub_build_dir}'")
    print(" -> Đang sao chép các tệp cần thiết...")
    for file in xhtml_files:
        shutil.move(str(file), str(text_dir / file.name))
        
    shutil.copy(assets_dir / "styles.css", styles_dir / "styles.css")
    
    cover_exists = (assets_dir / "cover.jpg").is_file()
    if cover_exists:
        shutil.copy(assets_dir / "cover.jpg", images_dir / "cover.jpg")
    else:
        print(f"  - Cảnh báo: Không tìm thấy 'cover.jpg', sẽ tạo EPUB không có ảnh bìa.")

    if (assets_dir / "Fonts").is_dir():
        shutil.copytree(assets_dir / "Fonts", fonts_dir, dirs_exist_ok=True)

    print(" -> Đang tạo các tệp metadata theo chuẩn EPUB 3...")
    (epub_build_dir / "mimetype").write_text(MIMETYPE)
    (epub_build_dir / "META-INF" / "container.xml").write_text(CONTAINER_XML, encoding='utf-8')

    font_files = list(fonts_dir.glob("*"))
    
    _create_content_opf(oebps_dir, book_info, xhtml_files, font_files, cover_exists)
    _create_toc_xhtml(oebps_dir, book_info, xhtml_files, chapter_titles)
    _create_toc_ncx(oebps_dir, book_info, xhtml_files, chapter_titles)
    print(f"  - Đã tạo: 'content.opf', 'toc.xhtml' (EPUB 3 Nav Doc), 'toc.ncx' (Tương thích EPUB 2)")

    epub_filename = source_dir.parent / f"{source_dir.name}.epub"
    print(f" -> Đang nén thành tệp EPUB tại: '{epub_filename}'")
    with zipfile.ZipFile(epub_filename, 'w') as epub_zip:
        epub_zip.write(epub_build_dir / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        
        for root, _, files in os.walk(epub_build_dir):
            for file in files:
                if file == "mimetype": continue
                file_path = Path(root) / file
                arcname = file_path.relative_to(epub_build_dir)
                epub_zip.write(file_path, arcname, compress_type=zipfile.ZIP_DEFLATED)
    
    print(f" -> Đóng gói thành công!")
    shutil.rmtree(epub_build_dir)


def _create_content_opf(oebps_dir: Path, book_info: Dict, xhtml_files: List[Path], font_files: List[Path], cover_exists: bool):
    """
    Tạo tệp Package Document (content.opf), bao gồm cả metadata cho Calibre.
    """
    modified_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    metadata_xml = f"""
    <dc:identifier id="bookid">{book_info['identifier']}</dc:identifier>
    <dc:title>{book_info['title']}</dc:title>
    <dc:creator id="creator">{book_info['creator']}</dc:creator>
    <dc:language>{book_info['language']}</dc:language>
    <meta property="dcterms:modified">{modified_date}</meta>"""
    
    if cover_exists:
        metadata_xml += '\n    <meta name="cover" content="cover-image"/>'
    if book_info.get('date'):
        metadata_xml += f"\n    <dc:date>{book_info['date']}</dc:date>"
        
    # <<< THÊM TÍNH NĂNG MỚI TẠI ĐÂY >>>
    # Ghi metadata của Calibre vào file .opf nếu chúng tồn tại.
    if book_info.get('series'):
        # html.escape để đảm bảo các ký tự đặc biệt như '&' hay '<' trong tên series không làm hỏng file XML.
        safe_series_name = html.escape(book_info['series'])
        metadata_xml += f'\n    <meta name="calibre:series" content="{safe_series_name}"/>'
    if book_info.get('series_index'):
        metadata_xml += f'\n    <meta name="calibre:series_index" content="{book_info["series_index"]}"/>'

    manifest_items = [
        '<item id="toc" href="toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="Styles/styles.css" media-type="text/css"/>'
    ]
    if cover_exists:
        manifest_items.insert(1, '<item id="cover-image" href="Images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>')
    
    for i, file in enumerate(xhtml_files):
        manifest_items.append(f'<item id="chapter-{i}" href="Text/{Path(file).name}" media-type="application/xhtml+xml"/>')
    for i, font in enumerate(font_files):
        media_type = "application/vnd.ms-opentype" if font.suffix.lower() == '.otf' else "application/font-sfnt"
        manifest_items.append(f'<item id="font-{i}" href="Fonts/{font.name}" media-type="{media_type}"/>')
    
    spine_items = [f'<itemref idref="chapter-{i}"/>' for i in range(len(xhtml_files))]

    opf_content = f"""<?xml version="1.0" encoding="utf-8"?>
<package version="3.0" unique-identifier="bookid" xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <metadata>
    {metadata_xml}
  </metadata>
  <manifest>
    {"\n    ".join(manifest_items)}
  </manifest>
  <spine toc="ncx">
    {"\n    ".join(spine_items)}
  </spine>
</package>
"""
    (oebps_dir / "content.opf").write_text(opf_content, encoding='utf-8')


def _create_toc_xhtml(oebps_dir: Path, book_info: Dict, xhtml_files: List[Path], chapter_titles: List[str]):
    # ... (Hàm này giữ nguyên) ...
    toc_items = []
    for xhtml_file, title in zip(xhtml_files, chapter_titles):
        toc_items.append(f'<li><a href="Text/{Path(xhtml_file).name}">{html.escape(title)}</a></li>')

    toc_content = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>Mục lục - {html.escape(book_info['title'])}</title>
  <link rel="stylesheet" type="text/css" href="Styles/styles.css"/>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>Mục lục</h1>
    <ol>
      {"\n      ".join(toc_items)}
    </ol>
  </nav>
</body>
</html>
"""
    (oebps_dir / "toc.xhtml").write_text(toc_content, encoding='utf-8')


def _create_toc_ncx(oebps_dir: Path, book_info: Dict, xhtml_files: List[Path], chapter_titles: List[str]):
    # ... (Hàm này giữ nguyên) ...
    nav_points = []
    for i, (xhtml_file, title) in enumerate(zip(xhtml_files, chapter_titles)):
        nav_points.append(f"""
    <navPoint id="navpoint-{i+1}" playOrder="{i+1}">
      <navLabel><text>{html.escape(title)}</text></navLabel>
      <content src="Text/{Path(xhtml_file).name}"/>
    </navPoint>""")

    ncx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{book_info['identifier']}"/>
  </head>
  <docTitle><text>{html.escape(book_info['title'])}</text></docTitle>
  <navMap>
    {''.join(nav_points)}
  </navMap>
</ncx>
"""
    (oebps_dir / "toc.ncx").write_text(ncx_content, encoding='utf-8')