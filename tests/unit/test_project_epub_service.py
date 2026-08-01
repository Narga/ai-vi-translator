from zipfile import ZipFile
import zipfile

from plugins.epub_converter.services.project_epub import create_project_epub


def _make_project(tmp_path):
    project_dir = tmp_path / "demo-project"
    for d in ("sources", "translated", "output"):
        (project_dir / d).mkdir(parents=True, exist_ok=True)
    return project_dir


def test_create_project_epub_builds_oebps_package(tmp_path):
    project_dir = _make_project(tmp_path)
    sources = project_dir / "sources"

    chapter_one = sources / "chapter01.html"
    chapter_one.write_text(
        "<html><head><title>Chapter 01</title></head><body><h1>Chương 1</h1><p>Nội dung một.</p></body></html>",
        encoding="utf-8",
    )
    chapter_two = sources / "chapter02.xhtml"
    chapter_two.write_text(
        "<html><body><h1>Chương 2</h1><p>Nội dung hai.</p></body></html>",
        encoding="utf-8",
    )

    result = create_project_epub(
        project_dir=project_dir,
        slug="demo-project",
        section="sources",
        source_paths=[chapter_one, chapter_two],
        project_meta={
            "book_title": "Example Book Title",
            "author": "Jane Doe",
            "description": '<p class="description">Mo ta</p>',
        },
    )

    assert result.output_path == project_dir / "output" / "demo-project.epub"
    assert result.chapter_count == 2
    assert result.skipped_files == []

    with ZipFile(result.output_path) as epub_file:
        names = epub_file.namelist()

        # Cấu trúc OEBPS chuẩn Sigil
        assert names[0] == "mimetype"
        assert "META-INF/container.xml" in names
        assert "OEBPS/content.opf" in names
        assert "OEBPS/Text/chapter01.xhtml" in names
        assert "OEBPS/Text/chapter02.xhtml" in names
        # Thư mục asset rỗng sẵn sàng cho biên tập
        assert "OEBPS/Images/" in names
        assert "OEBPS/Styles/" in names
        assert "OEBPS/Fonts/" in names
        # Không tạo nav/titlepage — phần mềm biên tập tự sinh
        assert not any("nav.xhtml" in n for n in names)
        assert not any("titlepage" in n for n in names)

        # mimetype phải uncompressed
        infos = epub_file.infolist()
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert epub_file.read("mimetype") == b"application/epub+zip"

        # container trỏ tới OEBPS/content.opf
        container = epub_file.read("META-INF/container.xml").decode("utf-8")
        assert 'full-path="OEBPS/content.opf"' in container

        # metadata tối thiểu
        content_opf = epub_file.read("OEBPS/content.opf").decode("utf-8")
        assert '<dc:title id="title">Example Book Title</dc:title>' in content_opf
        assert '<dc:creator id="creator">Jane Doe</dc:creator>' in content_opf
        assert "&lt;p class=&quot;description&quot;&gt;Mo ta&lt;/p&gt;" in content_opf
        assert 'href="Text/chapter01.xhtml"' in content_opf
        assert '<itemref idref=' in content_opf  # spine tồn tại

        # Chapter có stylesheet link theo quy ước ../Styles/styles.css
        chap1 = epub_file.read("OEBPS/Text/chapter01.xhtml").decode("utf-8")
        assert 'href="../Styles/styles.css"' in chap1


def test_create_project_epub_keeps_subdirectory_structure(tmp_path):
    """Chapter trong thư mục con của section giữ nguyên đường dẫn tương đối."""
    project_dir = _make_project(tmp_path)
    subdir = project_dir / "translated" / "vol2"
    subdir.mkdir(parents=True, exist_ok=True)
    chapter = subdir / "chuong-01.html"
    chapter.write_text("<body><p>Nội dung</p></body>", encoding="utf-8")

    result = create_project_epub(
        project_dir=project_dir,
        slug="demo-project",
        section="translated",
        source_paths=[chapter],
        project_meta={},
    )

    with ZipFile(result.output_path) as epub_file:
        assert "OEBPS/Text/vol2/chuong-01.xhtml" in epub_file.namelist()
        chap = epub_file.read("OEBPS/Text/vol2/chuong-01.xhtml").decode("utf-8")
        # Chapter ở sâu 2 cấp dưới OEBPS → stylesheet cần ../../Styles/styles.css
        assert 'href="../../Styles/styles.css"' in chap


def test_create_project_epub_atomic_keeps_old_file_on_failure(tmp_path):
    """Conversion lỗi giữa chừng không được phá file EPUB cũ."""
    project_dir = _make_project(tmp_path)
    sources = project_dir / "sources"
    existing = project_dir / "output" / "demo-project.epub"
    existing.write_bytes(b"OLD_VALID_EPUB")

    bad = sources / "bad.html"
    bad.write_text("<p>x</p>", encoding="utf-8")
    unsupported = sources / "readme.txt"
    unsupported.write_text("not html", encoding="utf-8")

    # Tất cả file đều unsupported → raise trước khi zip; file cũ còn nguyên
    try:
        create_project_epub(
            project_dir=project_dir,
            slug="demo-project",
            section="sources",
            source_paths=[unsupported],
            project_meta={},
        )
    except ValueError as e:
        assert "Không có tập tin" in str(e)

    assert existing.read_bytes() == b"OLD_VALID_EPUB"


def test_convert_markdown_to_html_preserves_footnote(tmp_path):
    """Footnote [^id] được render với forward/backlink (footnotes extension)."""
    from plugins.epub_converter.services.text_converter import markdown_body_to_html

    out = markdown_body_to_html("Nội dung.[^ck1]\n\n[^ck1]: Chú giải")
    assert 'href="#fn:ck1"' in out  # marker
    assert 'id="fn:ck1"' in out  # note body
    assert "href=\"#fnref:ck1\"" in out  # backlink
