# 20. PHASE 5 — PLUGIN CÔNG CỤ: CHUYỂN ĐỔI ĐỊNH DẠNG + EPUB CƠ BẢN

> **Phạm vi (user chốt "mức cơ bản"):** chuyển đổi 2 chiều txt/md/html + đóng gói EPUB 2.0
> từ `results/`. Spec gốc: `docs/05_*` §1 (`SimpleEpubPacker` + `TextFormatConverter`
> + quy ước plugin "thêm file là chạy, không framework").
> Backend stdlib + UI vanilla như mọi phase. Không checkpoint, không queue.

---

## 0. PHẠM VI & NON-GOALS

**Làm:**
1. `core/convert.py`: 6 hàm thuần `md→txt, txt→md, html→md, md→html, html→txt, txt→html`.
2. `tools/epub_tool.py`: CLI độc lập `python tools/epub_tool.py --project S --out name.epub`
   (+ `--title/--author` override, mặc định lấy meta project).
3. Backend mỏng: `POST /api/projects/{slug}/convert`, `POST /api/projects/{slug}/epub`,
   `GET /api/projects/{slug}/epub?file=` (tải về).
4. UI: 1 dialog "Công cụ" (convert scope file đã chọn + build EPUB) + nút tải về.

**KHÔNG làm:** bìa ảnh (cover = trang tiêu đề chữ), footnote/endnote, EPUB 3,
CSS trong sách, split/join file (gộp đã có ở merge-translate), OCR,
glossary/entity (hoãn dài hạn).

---

## 1. TASK A — `core/convert.py` (hàm thuần, có unit test)

```python
"""Chuyển đổi txt/md/html 2 chiều. Thuần string in/out, không chạm đĩa hay API."""
import re
from html.parser import HTMLParser

class _Stripper(HTMLParser):
    """Bóc thẻ HTML giữ text (đúng hơn regex với thẻ lồng nhau)."""
    def __init__(self):
        super().__init__()
        self.out = []
    def handle_data(self, d):
        self.out.append(d)

def html_to_text(content: str) -> str: ...
def md_to_txt(content: str) -> str: ...   # strip cú pháp, giữ chữ (theo docs/05 §1)
def txt_to_md(content: str) -> str: ...   # dòng đầu ngắn → `# heading`
def html_to_md(content: str) -> str: ...  # h1/h2/p/br + strip còn lại
def md_to_html(content: str) -> str: ...  # đoạn → <p>, `#` → <h1>/<h2> (dùng chung cho EPUB)
def txt_to_html(content: str) -> str: ... # đoạn cách nhau \n\n → <p>
CONVERTERS = {("md","txt"): md_to_txt, ("txt","md"): txt_to_md, ...}  # đủ 6 chiều
```

- Escape XML dùng `xml.sax.saxutils.escape` (stdlib), không tự replace tay.
- Unit test: round-trip `txt→md→txt` giữ nội dung (normalize whitespace),
  `html_to_text` với thẻ lồng, heading đầu dòng, file rỗng.

## 2. TASK B — `tools/epub_tool.py` (CLI độc lập, đúng quy ước plugin)

- `SimpleEpubPacker(title, author)`: mimetype STORED **đầu tiên**, `container.xml`,
  `content.opf` (EPUB 2.0 + manifest/spine), `toc.ncx`, `title-page.xhtml` (cover chữ),
  `chapter_NNN.xhtml` (tiêu đề = heading `#` đầu tiên, fallback tên file).
- Nội dung chương tái dùng `md_to_html/txt_to_html` từ `core/convert.py`
  (không duplicate logic strip); file `.html` nguồn → bóc `<body>` rồi nhúng lại.
- CLI: `python tools/epub_tool.py --project Truyen [--side results] [--title ..] [--author ..] [--out sach.epub]`
  → ghi `workspace/projects/{slug}/assets/{out}` (assets: sản phẩm phái sinh, không lẫn `results/`).
- Test: mở lại bằng `zipfile`, assert mimetype đầu + STORED, parse OPF XML được,
  số spine = số file + cover, đọc được bằng Calibre/preview (checklist tay 1 lần).

## 3. TASK C — BACKEND MỎNG (3 endpoint, tái dùng helper hiện có)

| Endpoint | In | Out / lỗi |
|---|---|---|
| `POST /api/projects/{slug}/convert` | `{files[], side, target: "txt"\|"md"\|"html"}` | `{converted:[{old,new}], skipped:[...], errors:{}}` — file mới cùng thư mục/side, đổi ext; va chạm → `unique_name` `_conflict` (đúng policy không đè); binary → `skipped` (tái dùng `read_text_strict`); regex/ext lạ → 400 |
| `POST /api/projects/{slug}/epub` | `{files[]?, title?, author?}` (trống = cả `results/`) | `{path:"assets/x.epub", chapters:n}` — title/author mặc định từ `GET .../info` |
| `GET /api/projects/{slug}/epub?file=` | — | bytes `application/epub+zip` + `Content-Disposition: attachment`; traversal → 400 (tái dùng `guard_name` + `relative_to`) |

- Convert cùng định dạng (`md→md`) → 400. Không convert file `.epub` (không nằm whitelist vào).
- Lỗi giữ shape `{"error"}` như mọi endpoint (`Handler._err`).

## 4. TASK D — UI (1 dialog "Công cụ", không thêm tab)

- Nút `🧰 Công cụ` trong `#wActions` (sau Xóa trắng) → `dialog#toolDlg`:
  - Khối 1 Convert: `Áp dụng cho N file đã chọn (tab hiện tại) → sang [txt|md|html] [Chuyển đổi]`.
  - Khối 2 EPUB: `Tiêu đề [prefill info] Tác giả [prefill] [Đóng sách từ results/] → link Tải .epub`.
- `web/js/tools.js` (mới, ~60 dòng): mở dialog (prefill meta), gọi 2 endpoint, toast + `listFiles()`.
- Không đụng luồng dịch; khóa nút khi `setRunning`? Convert/EPUB không chiếm `_translate_lock`
  (không gọi AI) → vẫn cho chạy song song, nhưng chặn khi file đang dịch (`_job_blocks` → 409).

## 5. TEST + DOCS

- `tests/test_convert.py`: 6 chiều + round-trip + rỗng/whitespace/Unicode.
- `tests/test_epub.py`: build từ tmp files → zip hợp lệ (mimetype đầu+STORED, OPF parse được, đủ spine); CLI `--help` chạy.
- `tests/test_server.py`: convert đổi ext + va chạm `_conflict` + binary skip + 400 cùng-định-dạng; epub build + download 200 + traversal 400.
- Cập nhật `docs/04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md` (endpoint 41–43), CHANGELOG `[Unreleased]`
  (không bump version), `docs/16_*` tick.

## 6. THỨ TỰ + ACCEPTANCE

1. Commit A (`core/convert.py` + unit). 2. Commit B (`tools/epub_tool.py` + CLI test).
3. Commit C (3 endpoint + test). 4. Commit D (dialog + `tools.js`).
5. Commit E (docs + CHANGELOG).

**DoD:** convert 6 chiều đúng trên file thật; `.epub` mở được trong Calibre/librera;
`pytest` + node xanh; không file nhị phân nào lọt vào convert; va chạm không đè.
