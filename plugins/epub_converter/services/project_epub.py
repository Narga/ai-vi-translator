from __future__ import annotations

import html
import mimetypes
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable

from bs4 import BeautifulSoup
from bs4 import Comment
from bs4 import NavigableString
from bs4 import Tag

CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
MIMETYPE = "application/epub+zip"
SUPPORTED_SOURCE_SUFFIXES = {".html", ".htm", ".xhtml"}
DEFAULT_LANGUAGE = "vi"
DEFAULT_STYLESHEET = """
body { font-family: serif; line-height: 1.65; margin: 5%; }
h1, h2, h3 { line-height: 1.2; }
img { display: block; height: auto; margin: 1.5em auto; max-width: 100%; }
.titlepage { text-align: center; margin-top: 12vh; }
.titlepage .byline { color: #555; font-size: 1.05em; }
.titlepage .description { margin: 2em auto 0; max-width: 32em; text-align: left; }
nav ol { padding-left: 1.5em; }
""".strip()
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
BOOLEAN_ATTRIBUTES = {
    "allowfullscreen",
    "async",
    "autofocus",
    "autoplay",
    "checked",
    "controls",
    "default",
    "defer",
    "disabled",
    "hidden",
    "ismap",
    "loop",
    "multiple",
    "muted",
    "novalidate",
    "open",
    "readonly",
    "required",
    "reversed",
    "selected",
}


@dataclass(frozen=True)
class ProjectEpubBuildResult:
    output_path: Path
    included_files: list[str]
    skipped_files: list[str]

    @property
    def chapter_count(self) -> int:
        return len(self.included_files)


@dataclass
class _ManifestItem:
    item_id: str
    href: str
    media_type: str
    properties: str = ""


def create_project_epub(
    project_dir: Path,
    slug: str,
    section: str,
    source_paths: Iterable[Path],
    project_meta: dict,
) -> ProjectEpubBuildResult:
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{slug}.epub"

    included_files: list[str] = []
    skipped_files: list[str] = []
    language = (project_meta.get("language") or DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE
    title = _project_title(project_meta, slug)
    creator = (project_meta.get("author") or "").strip() or "Không rõ tác giả"
    description = (project_meta.get("description") or "").strip()
    identifier = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'novel-translator:{slug}')}"

    with TemporaryDirectory(prefix=f"{slug}-epub-", dir=output_dir) as temp_dir_name:
        build_dir = Path(temp_dir_name)
        (build_dir / "META-INF").mkdir(parents=True, exist_ok=True)
        text_dir = build_dir / "text"
        css_dir = build_dir / "css"
        images_dir = build_dir / "images"
        text_dir.mkdir(parents=True, exist_ok=True)
        css_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

        (build_dir / "mimetype").write_text(MIMETYPE, encoding="utf-8")
        (build_dir / "META-INF" / "container.xml").write_text(CONTAINER_XML, encoding="utf-8")
        (css_dir / "style.css").write_text(DEFAULT_STYLESHEET, encoding="utf-8")

        manifest_items: list[_ManifestItem] = [
            _ManifestItem("nav", "nav.xhtml", "application/xhtml+xml", "nav"),
            _ManifestItem("stylesheet", "css/style.css", "text/css"),
            _ManifestItem("titlepage", "text/titlepage.xhtml", "application/xhtml+xml"),
        ]
        spine_ids = ["titlepage", "nav"]
        used_ids = {"nav", "stylesheet", "titlepage"}

        cover_item = _copy_cover_image(project_dir, images_dir, used_ids)
        if cover_item:
            manifest_items.append(cover_item)

        chapter_links: list[tuple[str, str]] = []
        for source_path in source_paths:
            relative_name = str(source_path.resolve().relative_to(project_dir.resolve()))
            if source_path.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
                skipped_files.append(relative_name)
                continue

            chapter_rel = _chapter_href(project_dir, section, source_path)
            chapter_path = build_dir / chapter_rel
            chapter_path.parent.mkdir(parents=True, exist_ok=True)

            chapter_title, chapter_xhtml = _build_xhtml_document(source_path, language)
            chapter_path.write_text(chapter_xhtml, encoding="utf-8")

            chapter_id = _unique_id(chapter_rel.stem, used_ids)
            manifest_items.append(
                _ManifestItem(
                    chapter_id,
                    chapter_rel.as_posix(),
                    "application/xhtml+xml",
                )
            )
            spine_ids.append(chapter_id)
            chapter_links.append((chapter_title, chapter_rel.as_posix()))
            included_files.append(relative_name)

        if not included_files:
            raise ValueError("Không có tập tin HTML/XHTML hợp lệ nào để tạo EPUB 3")

        titlepage = _build_titlepage(title, creator, description, cover_item.href if cover_item else None, language)
        (text_dir / "titlepage.xhtml").write_text(titlepage, encoding="utf-8")

        nav_doc = _build_nav_document(title, chapter_links, language)
        (build_dir / "nav.xhtml").write_text(nav_doc, encoding="utf-8")

        content_opf = _build_content_opf(
            title=title,
            creator=creator,
            description=description,
            identifier=identifier,
            language=language,
            manifest_items=manifest_items,
            spine_ids=spine_ids,
        )
        (build_dir / "content.opf").write_text(content_opf, encoding="utf-8")

        with zipfile.ZipFile(output_path, "w") as epub_zip:
            epub_zip.write(build_dir / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
            for file_path in sorted(build_dir.rglob("*")):
                if not file_path.is_file() or file_path.name == "mimetype":
                    continue
                epub_zip.write(
                    file_path,
                    file_path.relative_to(build_dir).as_posix(),
                    compress_type=zipfile.ZIP_DEFLATED,
                )

    return ProjectEpubBuildResult(
        output_path=output_path,
        included_files=included_files,
        skipped_files=skipped_files,
    )


def _project_title(project_meta: dict, slug: str) -> str:
    return (
        (project_meta.get("book_title") or "").strip()
        or (project_meta.get("name") or "").strip()
        or slug
    )


def _copy_cover_image(project_dir: Path, images_dir: Path, used_ids: set[str]) -> _ManifestItem | None:
    for candidate in ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp"):
        cover_path = project_dir / "assets" / candidate
        if not cover_path.is_file():
            continue
        target_path = images_dir / cover_path.name
        target_path.write_bytes(cover_path.read_bytes())
        media_type = mimetypes.guess_type(target_path.name)[0] or "application/octet-stream"
        return _ManifestItem(
            _unique_id("cover-image", used_ids),
            f"images/{target_path.name}",
            media_type,
            "cover-image",
        )
    return None


def _chapter_href(project_dir: Path, section: str, source_path: Path) -> Path:
    section_root = (project_dir / section).resolve()
    relative = source_path.resolve().relative_to(section_root)
    return Path("text") / relative.with_suffix(".xhtml")


def _build_xhtml_document(source_path: Path, language: str) -> tuple[str, str]:
    content = source_path.read_text(encoding="utf-8", errors="replace")
    document = BeautifulSoup(content or "<html><body></body></html>", "html.parser")
    for node in document.find_all(["script", "style"]):
        node.decompose()

    body = document.body or document
    body_markup = "".join(_render_node(child) for child in body.contents).strip()

    if not body_markup:
        text_content = " ".join(document.get_text(" ", strip=True).split())
        body_markup = f"<p>{html.escape(text_content or source_path.stem)}</p>"

    title = _extract_document_title(document, source_path.stem)
    xhtml = "\n".join(
        [
            '<?xml version="1.0" encoding="utf-8"?>',
            "<!DOCTYPE html>",
            f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{html.escape(language)}" lang="{html.escape(language)}">',
            "<head>",
            '  <meta charset="utf-8"/>',
            f"  <title>{html.escape(title)}</title>",
            '  <link rel="stylesheet" type="text/css" href="../css/style.css"/>',
            "</head>",
            "<body>",
            body_markup,
            "</body>",
            "</html>",
        ]
    )
    return title, xhtml


def _extract_document_title(document: BeautifulSoup, fallback: str) -> str:
    title_tag = document.title
    if title_tag:
        text = " ".join(title_tag.get_text(" ", strip=True).split())
        if text:
            return text
    for name in ("h1", "h2"):
        node = document.find(name)
        if node:
            text = " ".join(node.get_text(" ", strip=True).split())
            if text:
                return text
    return fallback


def _build_titlepage(title: str, creator: str, description: str, cover_href: str | None, language: str) -> str:
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<!DOCTYPE html>",
        f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{html.escape(language)}" lang="{html.escape(language)}">',
        "<head>",
        '  <meta charset="utf-8"/>',
        f"  <title>{html.escape(title)}</title>",
        '  <link rel="stylesheet" type="text/css" href="../css/style.css"/>',
        "</head>",
        '<body epub:type="frontmatter titlepage">',
        '  <section class="titlepage">',
    ]
    if cover_href:
        parts.append(f'    <img src="../{html.escape(cover_href)}" alt="{html.escape(title)}"/>')
    parts.append(f"    <h1>{html.escape(title)}</h1>")
    parts.append(f'    <p class="byline">{html.escape(creator)}</p>')
    if description:
        parts.append(f'    <p class="description">{html.escape(description)}</p>')
    parts.extend(["  </section>", "</body>", "</html>"])
    return "\n".join(parts)


def _build_nav_document(title: str, chapter_links: list[tuple[str, str]], language: str) -> str:
    items = "\n".join(
        f'      <li><a href="{html.escape(href)}">{html.escape(chapter_title)}</a></li>'
        for chapter_title, href in chapter_links
    )
    return "\n".join(
        [
            '<?xml version="1.0" encoding="utf-8"?>',
            "<!DOCTYPE html>",
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{html.escape(language)}" lang="{html.escape(language)}">',
            "<head>",
            '  <meta charset="utf-8"/>',
            f"  <title>Mục lục - {html.escape(title)}</title>",
            '  <link rel="stylesheet" type="text/css" href="css/style.css"/>',
            "</head>",
            "<body>",
            '  <nav epub:type="toc" id="toc">',
            f"    <h1>{html.escape(title)}</h1>",
            "    <ol>",
            items,
            "    </ol>",
            "  </nav>",
            "</body>",
            "</html>",
        ]
    )


def _build_content_opf(
    *,
    title: str,
    creator: str,
    description: str,
    identifier: str,
    language: str,
    manifest_items: list[_ManifestItem],
    spine_ids: list[str],
) -> str:
    modified = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    metadata_lines = [
        f'    <dc:identifier id="pub-id">{html.escape(identifier)}</dc:identifier>',
        f'    <dc:title id="title">{html.escape(title)}</dc:title>',
        f'    <dc:creator id="creator">{html.escape(creator)}</dc:creator>',
        f'    <dc:language>{html.escape(language)}</dc:language>',
        f'    <dc:description>{html.escape(description)}</dc:description>',
        f"    <meta property=\"dcterms:modified\">{modified}</meta>",
    ]
    cover_item = next((item for item in manifest_items if "cover-image" in item.properties), None)
    if cover_item:
        metadata_lines.append(f'    <meta name="cover" content="{cover_item.item_id}" />')

    manifest_lines = []
    for item in manifest_items:
        attrs = [
            f'id="{html.escape(item.item_id)}"',
            f'href="{html.escape(item.href)}"',
            f'media-type="{html.escape(item.media_type)}"',
        ]
        if item.properties:
            attrs.append(f'properties="{html.escape(item.properties)}"')
        manifest_lines.append(f"    <item {' '.join(attrs)} />")

    spine_lines = [f'    <itemref idref="{html.escape(item_id)}" />' for item_id in spine_ids]
    return "\n".join(
        [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id">',
            '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">',
            *metadata_lines,
            "  </metadata>",
            "  <manifest>",
            *manifest_lines,
            "  </manifest>",
            "  <spine>",
            *spine_lines,
            "  </spine>",
            "</package>",
        ]
    )


def _unique_id(seed: str, used_ids: set[str]) -> str:
    clean = "".join(ch if ch.isalnum() else "-" for ch in seed).strip("-").lower() or "item"
    if not clean[0].isalpha():
        clean = f"item-{clean}"
    candidate = clean
    index = 2
    while candidate in used_ids:
        candidate = f"{clean}-{index}"
        index += 1
    used_ids.add(candidate)
    return candidate


def _render_node(node: Tag | NavigableString) -> str:
    if isinstance(node, Comment):
        return ""
    if isinstance(node, NavigableString):
        return html.escape(str(node))
    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()
    if name in {"script", "style"}:
        return ""

    attrs = []
    for key, value in node.attrs.items():
        if value is None:
            continue
        attr_name = html.escape(str(key), quote=True)
        if isinstance(value, list):
            attr_value = " ".join(str(part) for part in value if part is not None)
        elif value is True and key.lower() in BOOLEAN_ATTRIBUTES:
            attr_value = key
        else:
            attr_value = str(value)
        attrs.append(f' {attr_name}="{html.escape(attr_value, quote=True)}"')

    children = "".join(_render_node(child) for child in node.contents)
    if name in VOID_ELEMENTS:
        return f"<{name}{''.join(attrs)} />"
    return f"<{name}{''.join(attrs)}>{children}</{name}>"
