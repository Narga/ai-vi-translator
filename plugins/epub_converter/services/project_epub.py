from __future__ import annotations

import html
import os
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
from bs4 import Comment
from bs4 import NavigableString
from bs4 import Tag

# ponytail: cấu trúc EPUB theo chuẩn Sigil/OEBPS — chỉ đóng gói nội dung text.
# Ảnh/font/style người dùng tự đưa vào OEBPS/Images|Styles|Fonts khi biên tập;
# mở rộng asset resolver khi có nhu cầu đóng gói hoàn chỉnh tự động.
CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
MIMETYPE = "application/epub+zip"
SUPPORTED_SOURCE_SUFFIXES = {".html", ".htm", ".xhtml"}
DEFAULT_LANGUAGE = "vi"
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
    """Đóng gói EPUB 3 tối thiểu (layout OEBPS) từ các chapter HTML/XHTML.

    - Chapter vào ``OEBPS/Text/`` giữ nguyên cấu trúc thư mục con của section.
    - ``src``/``href`` giữ nguyên verbatim (biên tập thủ công bằng Sigil sau).
    - Không tạo nav.xhtml/titlepage/cover — phần mềm biên tập tự sinh.
    - Ghi atomic: zip vào file tạm, self-check rồi ``os.replace`` (ghi đè bản cũ).
    """
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
        oebps_dir = build_dir / "OEBPS"
        text_dir = oebps_dir / "Text"
        (build_dir / "META-INF").mkdir(parents=True, exist_ok=True)
        text_dir.mkdir(parents=True, exist_ok=True)
        # Thư mục rỗng theo chuẩn OEBPS để người dùng đưa asset vào khi biên tập
        (oebps_dir / "Images").mkdir(parents=True, exist_ok=True)
        (oebps_dir / "Styles").mkdir(parents=True, exist_ok=True)
        (oebps_dir / "Fonts").mkdir(parents=True, exist_ok=True)

        (build_dir / "mimetype").write_text(MIMETYPE, encoding="utf-8")
        (build_dir / "META-INF" / "container.xml").write_text(CONTAINER_XML, encoding="utf-8")

        manifest_items: list[_ManifestItem] = []
        spine_ids: list[str] = []
        used_ids: set[str] = set()

        for source_path in source_paths:
            relative_name = str(source_path.resolve().relative_to(project_dir.resolve()))
            if source_path.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
                skipped_files.append(relative_name)
                continue

            # ponytail: href giữ cấu trúc tương đối của section dưới OEBPS/Text/;
            # chỉ đổi suffix sang .xhtml, không rewrite link/ảnh.
            chapter_rel = _chapter_href(project_dir, section, source_path)
            oebps_rel = Path("OEBPS") / chapter_rel
            chapter_path = build_dir / oebps_rel
            chapter_path.parent.mkdir(parents=True, exist_ok=True)

            depth = len(chapter_rel.parent.parts)
            css_href = "../" * depth + "Styles/styles.css"
            chapter_title, chapter_xhtml = _build_xhtml_document(
                source_path, language, css_href
            )
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
            included_files.append(relative_name)

        if not included_files:
            raise ValueError("Không có tập tin HTML/XHTML hợp lệ nào để tạo EPUB 3")

        content_opf = _build_content_opf(
            title=title,
            creator=creator,
            description=description,
            identifier=identifier,
            language=language,
            manifest_items=manifest_items,
            spine_ids=spine_ids,
        )
        (oebps_dir / "content.opf").write_text(content_opf, encoding="utf-8")

        result = ProjectEpubBuildResult(
            output_path=output_path,
            included_files=included_files,
            skipped_files=skipped_files,
        )
        _write_epub_zip_atomic(build_dir, output_dir, output_path)

    return result


def _project_title(project_meta: dict, slug: str) -> str:
    return (
        (project_meta.get("book_title") or "").strip()
        or (project_meta.get("name") or "").strip()
        or slug
    )


def _chapter_href(project_dir: Path, section: str, source_path: Path) -> Path:
    section_root = (project_dir / section).resolve()
    relative = source_path.resolve().relative_to(section_root)
    return Path("Text") / relative.with_suffix(".xhtml")


def _build_xhtml_document(source_path: Path, language: str, css_href: str) -> tuple[str, str]:
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
            # ponytail: link stylesheet theo quy ước OEBPS/Styles/styles.css; file
            # sẽ do người dùng thêm khi biên tập. Bỏ link nếu không muốn quy ước này.
            f'  <link rel="stylesheet" type="text/css" href="{html.escape(css_href)}"/>',
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
        f"    <meta property=\"dcterms:modified\">{modified}</meta>",
    ]
    if description:
        metadata_lines.append(f"    <dc:description>{html.escape(description)}</dc:description>")

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


def _write_epub_zip_atomic(build_dir: Path, output_dir: Path, output_path: Path) -> None:
    """Zip build tree vào file tạm, self-check rồi os.replace vào đích.

    Lỗi ở bất kỳ bước nào → xóa temp, file EPUB cũ (nếu có) còn nguyên.
    """
    fd, tmp_name = tempfile.mkstemp(
        prefix=output_path.stem + ".", suffix=".epub.tmp", dir=output_dir
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp_path, "w") as epub_zip:
            # mimetype bắt buộc là entry đầu tiên và không nén
            epub_zip.writestr("mimetype", MIMETYPE, compress_type=zipfile.ZIP_STORED)
            for file_path in sorted(build_dir.rglob("*")):
                rel = file_path.relative_to(build_dir).as_posix()
                if file_path.is_dir():
                    # giữ thư mục rỗng (Images/Styles/Fonts) trong zip
                    epub_zip.writestr(rel + "/", "")
                elif file_path.name == "mimetype":
                    continue
                else:
                    epub_zip.write(file_path, rel, compress_type=zipfile.ZIP_DEFLATED)
        _validate_epub_archive(tmp_path)
        os.replace(tmp_path, output_path)
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _validate_epub_archive(path: Path) -> None:
    """Self-check tối thiểu bằng stdlib (không dùng epubcheck).

    Kiểm tra: mimetype entry đầu + không nén, container/content.opf parse được,
    mọi href trong manifest tồn tại, mọi XHTML parse XML được.
    """
    opf_ns = "{http://www.idpf.org/2007/opf}"
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        infos = zf.infolist()
        if not infos or names[0] != "mimetype":
            raise ValueError("EPUB thiếu entry mimetype đầu tiên")
        if infos[0].compress_type != zipfile.ZIP_STORED:
            raise ValueError("Entry mimetype phải lưu uncompressed (ZIP_STORED)")
        if zf.read("mimetype") != MIMETYPE.encode("utf-8"):
            raise ValueError("Nội dung mimetype không đúng application/epub+zip")

        container = ET.fromstring(zf.read("META-INF/container.xml"))
        ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
        rootfile = container.find(".//c:rootfile", ns)
        if rootfile is None:
            raise ValueError("container.xml thiếu <rootfile>")
        opf_path = rootfile.attrib["full-path"]

        opf = ET.fromstring(zf.read(opf_path))
        name_set = set(names)
        for item in opf.findall(f".//{opf_ns}item"):
            href = item.attrib.get("href", "")
            resolved = (Path(opf_path).parent / href).as_posix()
            if resolved not in name_set:
                raise ValueError(f"Manifest tham chiếu tài nguyên không có: {href}")

        for name in names:
            if name.endswith(".xhtml"):
                chapter = zf.read(name).decode("utf-8")
                ET.fromstring(chapter.replace("<!DOCTYPE html>", ""))


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
