from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path
from typing import Optional

try:
    import markdown as _mdlib

    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

# ponytail: chốt một extension set dùng chung cho UI MD → HTML và MD → EPUB;
# thêm extension mới = thêm vào đây và vào test.
MARKDOWN_EXTENSIONS = ["extra", "sane_lists"]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _derive_output_path(input_path: Path, suffix: str) -> Path:
    if input_path.suffix.lower() == suffix.lower():
        return input_path.with_name(f"{input_path.stem}.converted{suffix}")
    return input_path.with_suffix(suffix)


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
        return stripped[:120]
    return fallback


def _attr(value: str) -> str:
    """Escape a value for use inside an HTML/XHTML attribute."""
    return html.escape(value, quote=True)


def markdown_body_to_html(text: str) -> str:
    """Convert Markdown body text to an XHTML fragment using the canonical parser.

    Raises:
        ImportError: nếu thiếu package `markdown` (cần cài `pip install '.[epub]'`).
    """
    if not HAS_MARKDOWN:
        raise ImportError(
            "Thư viện 'markdown' là bắt buộc cho Markdown → HTML. "
            "Cài đặt bằng: pip install '.[epub]' hoặc pip install markdown"
        )
    return _mdlib.markdown(text, extensions=MARKDOWN_EXTENSIONS)


def markdown_text_to_html_document(text: str, title: str) -> str:
    body_html = markdown_body_to_html(text)
    return "\n".join(
        [
            '<?xml version="1.0" encoding="utf-8"?>',
            "<!DOCTYPE html>",
            "",
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="vi">',
            "<head>",
            '  <meta charset="utf-8"/>',
            f"  <title>{html.escape(title)}</title>",
            "</head>",
            "<body>",
            body_html,
            "</body>",
            "</html>",
        ]
    )


def _do_delete(input_path: Path, destination: Path) -> None:
    """
    Xóa nguồn chỉ khi output đã được commit thành công và khác đường dẫn nguồn.
    """
    if input_path.resolve() != destination.resolve() and input_path.exists():
        input_path.unlink()


def _reject_in_place_overwrite(input_path: Path, destination: Path) -> None:
    if input_path.resolve() == destination.resolve():
        raise ValueError(f"Từ chối: đường dẫn đích trùng với nguồn ({input_path})")


def _atomic_write(path: Path, content: str) -> None:
    # ponytail: ghi ra tempfile cùng thư mục rồi os.replace để commit nguyên tử
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def convert_markdown_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    delete_source: bool = False,
) -> Path:
    text = _read_text(input_path)
    title = _extract_title(text, input_path.stem)
    destination = output_path or _derive_output_path(input_path, ".html")
    _reject_in_place_overwrite(input_path, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(destination, markdown_text_to_html_document(text, title))
    if delete_source:
        _do_delete(input_path, destination)
    return destination


def convert_html_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    delete_source: bool = False,
) -> Path:
    from core.source_normalizer import normalize_html_content

    destination = output_path or _derive_output_path(input_path, ".md")
    _reject_in_place_overwrite(input_path, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    md_content = normalize_html_content(input_path.read_text(encoding="utf-8", errors="replace"))
    _atomic_write(destination, md_content)
    if delete_source:
        _do_delete(input_path, destination)
    return destination


if __name__ == "__main__":
    sample = """# Chapter One

Some **bold** and _italic_ text with a [link](https://example.com).

## 2. IT DID NOT SEEM PRUDENT

- item one
- item two

1. first
2. second

> a quote

```python
print("hi")
```

![alt text](img/cover.png)

| A | B |
|---|---|
| 1 | 2 |

Final paragraph.
"""
    doc = markdown_text_to_html_document(sample, "Chapter One")
    for needle in [
        "<h1>Chapter One</h1>",
        "<h2>2. IT DID NOT SEEM PRUDENT</h2>",
        "<strong>bold</strong>",
        '<a href="https://example.com">link</a>',
        "<ul>",
        "<li>item one</li>",
        "<ol>",
        "<li>first</li>",
        "<blockquote>",
        '<img src="img/cover.png" alt="alt text"/>'
        if False
        else 'alt="alt text"',  # markdown lib renders alt attr
        "<table>",
        'xmlns:epub="http://www.idpf.org/2007/ops"',
    ]:
        assert needle in doc, f"MISSING: {needle}"
    print("markdown->xhtml self-check OK")
