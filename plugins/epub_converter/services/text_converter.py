from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Optional

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


def _md_inline(text: str) -> str:
    """Apply inline markdown formatting to already HTML-escaped text."""
    # Images: ![alt](url)
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)\)",
        lambda m: f'<img src="{_attr(m.group(2))}" alt="{m.group(1)}"/>',
        text,
    )
    # Links: [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: f'<a href="{_attr(m.group(2))}">{m.group(1)}</a>',
        text,
    )
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _md_block_to_xhtml(md: str) -> str:
    """Convert a markdown document into an XHTML body (self-contained, no deps)."""
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)

    def is_hr(line: str) -> bool:
        s = line.strip()
        return bool(s) and len(set(s)) == 1 and s[0] in "-*_" and len(s) >= 3

    def is_ul(line: str) -> bool:
        return bool(re.match(r"^\s*[-*+]\s+", line))

    def is_ol(line: str) -> bool:
        return bool(re.match(r"^\s*\d+\.\s+", line))

    def is_block_start(s: str) -> bool:
        return (
            s.startswith("```")
            or re.match(r"^#{1,6}\s", s)
            or is_hr(s)
            or s.startswith(">")
            or is_ul(s)
            or is_ol(s)
        )

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            i += 1
            buf: list[str] = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            code = html.escape("\n".join(buf))
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{code}</code></pre>")
            continue

        # Heading
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            content = _md_inline(html.escape(m.group(2).strip()))
            out.append(f"<h{level}>{content}</h{level}>")
            i += 1
            continue

        # Horizontal rule
        if is_hr(line):
            out.append("<hr/>")
            i += 1
            continue

        # Blockquote (recursive)
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{_md_block_to_xhtml(chr(10).join(buf))}</blockquote>")
            continue

        # Unordered list
        if is_ul(line):
            items: list[str] = []
            while i < n and is_ul(lines[i]):
                item = re.sub(r"^\s*[-*+]\s+", "", lines[i])
                items.append(f"<li>{_md_inline(html.escape(item.strip()))}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        # Ordered list
        if is_ol(line):
            items = []
            while i < n and is_ol(lines[i]):
                item = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                items.append(f"<li>{_md_inline(html.escape(item.strip()))}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # Paragraph
        para: list[str] = []
        while i < n and lines[i].strip() and not is_block_start(lines[i].strip()):
            para.append(lines[i])
            i += 1
        para_text = _md_inline(html.escape("\n".join(para)))
        para_text = para_text.replace("\n", "<br/>")
        out.append(f"<p>{para_text}</p>")

    return "\n".join(out)


def markdown_text_to_html_document(text: str, title: str) -> str:
    body_html = _md_block_to_xhtml(text)
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


def convert_markdown_file(
    input_path: Path,
    output_path: Optional[Path] = None,
) -> Path:
    text = _read_text(input_path)
    title = _extract_title(text, input_path.stem)
    destination = output_path or _derive_output_path(input_path, ".html")
    destination.write_text(
        markdown_text_to_html_document(text, title),
        encoding="utf-8",
    )
    return destination


def convert_html_file(
    input_path: Path,
    output_path: Optional[Path] = None,
) -> Path:
    from core.source_normalizer import normalize_html_file

    destination = output_path or _derive_output_path(input_path, ".md")
    generated = Path(normalize_html_file(str(input_path)))
    if generated.resolve() == destination.resolve():
        return generated
    destination.write_text(generated.read_text(encoding="utf-8"), encoding="utf-8")
    if generated.exists():
        generated.unlink()
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

---

Final paragraph.
"""
    doc = markdown_text_to_html_document(sample, "Chapter One")
    for needle in [
        "<h1>Chapter One</h1>",
        "<h2>2. IT DID NOT SEEM PRUDENT</h2>",
        "<strong>bold</strong>",
        '<a href="https://example.com">link</a>',
        "<ul><li>item one</li><li>item two</li></ul>",
        "<ol><li>first</li><li>second</li></ol>",
        "<blockquote>",
        '<img src="img/cover.png" alt="alt text"/>',
        "<hr/>",
        'xmlns:epub="http://www.idpf.org/2007/ops"',
    ]:
        assert needle in doc, f"MISSING: {needle}"
    print("markdown->xhtml self-check OK")
