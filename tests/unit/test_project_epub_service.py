from zipfile import ZipFile

from plugins.epub_converter.services.project_epub import create_project_epub


def test_create_project_epub_builds_epub3_package(tmp_path):
    project_dir = tmp_path / "demo-project"
    sources_dir = project_dir / "sources"
    assets_dir = project_dir / "assets"
    output_dir = project_dir / "output"
    sources_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    chapter_one = sources_dir / "chapter01.html"
    chapter_one.write_text(
        "<html><head><title>Chapter 01</title></head><body><h1>Chương 1</h1><p>Nội dung một.</p></body></html>",
        encoding="utf-8",
    )
    chapter_two = sources_dir / "chapter02.xhtml"
    chapter_two.write_text(
        "<html><body><h1>Chương 2</h1><p>Nội dung hai.</p></body></html>",
        encoding="utf-8",
    )
    (assets_dir / "cover.jpg").write_bytes(b"fake-cover")

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

    assert result.output_path == output_dir / "demo-project.epub"
    assert result.chapter_count == 2
    assert result.skipped_files == []

    with ZipFile(result.output_path) as epub_file:
        names = epub_file.namelist()
        assert names[0] == "mimetype"
        assert "META-INF/container.xml" in names
        assert "content.opf" in names
        assert "nav.xhtml" in names
        assert "css/style.css" in names
        assert "images/cover.jpg" in names
        assert "text/titlepage.xhtml" in names
        assert "text/chapter01.xhtml" in names
        assert "text/chapter02.xhtml" in names

        content_opf = epub_file.read("content.opf").decode("utf-8")
        assert '<dc:title id="title">Example Book Title</dc:title>' in content_opf
        assert '<dc:creator id="creator">Jane Doe</dc:creator>' in content_opf
        assert "&lt;p class=&quot;description&quot;&gt;Mo ta&lt;/p&gt;" in content_opf
        assert 'href="text/chapter02.xhtml"' in content_opf
        assert 'properties="cover-image"' in content_opf

        nav_doc = epub_file.read("nav.xhtml").decode("utf-8")
        assert "Chapter 01" in nav_doc
        assert "Chương 2" in nav_doc
