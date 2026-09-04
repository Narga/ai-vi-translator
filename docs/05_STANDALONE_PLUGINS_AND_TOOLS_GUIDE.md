# 05. CHỈ DẪN CHI TIẾT CÁC CÔNG CỤ & PLUGINS ĐỘC LẬP
> **Tài liệu**: Hướng dẫn kỹ thuật và mã nguồn chi tiết cho các công cụ chuyên biệt, đảm bảo tính tách biệt, không làm phình to lõi ứng dụng chính.
> **Phiên bản**: v2.3 (04/09/2026) — bỏ OCR, chốt glossary path + quy ước mở rộng không framework.

---

## 1. CÔNG CỤ 1: CÔNG CỤ EPUB & CHUYỂN ĐỔI ĐỊNH DẠNG VĂN BẢN (EPUB TOOL)

### 1.1. Yêu Cầu & Phạm Vi
* **Đầu vào (Input)**:
  * **CHỈ nhận các file text**, bao gồm: Text thuần (`.txt`), Markdown (`.md`), HTML (`.html`).
  * Mặc định xử lý tất cả như là các text file thuần túy, không quan tâm cấu trúc phức tạp bên trong vì người dùng tự chủ được nguồn nội dung của mình.
* **Đầu ra & Chức năng (Output & Features)**:
  1. **Đóng gói thành sách `.epub`**: Gom các file text/md/html được chọn thành 1 file sách điện tử tiêu chuẩn, tự động tạo trang bìa và mục lục TOC dựa theo tên file hoặc heading đầu tiên.
  2. **Chuyển đổi qua lại định dạng (Bidirectional Converter)**:
     * Chuyển đổi giữa `Markdown (.md)` $\longleftrightarrow$ `Text thuần (.txt)`
     * Chuyển đổi giữa `HTML (.html)` $\longleftrightarrow$ `Markdown (.md)`
     * Chuyển đổi giữa `HTML (.html)` $\longleftrightarrow$ `Text thuần (.txt)`
  3. **Hỗ trợ toàn diện 2 chiều**: Áp dụng được cho **CẢ** thư mục nguồn (`sources/`) lẫn thư mục bản dịch (`translated/`).

### 1.2. Thiết Kế Mã Nguồn Độc Lập (`tools/epub_tool.py`)
Công cụ được viết độc lập bằng thư viện chuẩn, không can thiệp vào lõi dịch thuật:

```python
# tools/epub_tool.py
import os
import zipfile
import re
from pathlib import Path
from typing import List, Dict, Optional

class SimpleEpubPacker:
    """Đóng gói các tệp text/markdown/html thành EPUB 2.0 tối giản (OPF 2.0 + NCX)."""

    def __init__(self, title: str, author: str = "AI Translator"):
        self.title = title
        self.author = author

    def build_epub(self, input_files: List[Path], output_epub_path: Path):
        output_epub_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Mở file zip để tạo cấu trúc EPUB
        with zipfile.ZipFile(output_epub_path, "w", zipfile.ZIP_DEFLATED) as z:
            # 1. mimetype (bắt buộc lưu không nén)
            z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

            # 2. container.xml
            z.writestr("META-INF/container.xml", """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""")

            manifest_items = []
            spine_items = []
            toc_entries = []

            # 3. Đọc từng file text/md/html và chuyển thành trang XHTML
            for idx, file_path in enumerate(input_files, 1):
                raw_content = file_path.read_text(encoding="utf-8", errors="replace")
                
                # Chuyển đổi các đoạn text thành các thẻ <p>...</p> HTML cơ bản
                paragraphs = raw_content.split("\n\n")
                body_html = ""
                for p in paragraphs:
                    p_clean = p.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    if p_clean:
                        # Nếu là tiêu đề Markdown
                        if p_clean.startswith("# "):
                            body_html += f"<h1>{p_clean[2:]}</h1>\n"
                        elif p_clean.startswith("## "):
                            body_html += f"<h2>{p_clean[3:]}</h2>\n"
                        else:
                            body_html += f"<p>{p_clean.replace('\n', '<br/>')}</p>\n"

                chapter_filename = f"chapter_{idx:03d}.xhtml"
                chapter_content = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{file_path.stem}</title></head>
<body>
{body_html}
</body>
</html>"""
                z.writestr(f"OEBPS/{chapter_filename}", chapter_content)
                
                item_id = f"chap_{idx}"
                manifest_items.append(f'<item id="{item_id}" href="{chapter_filename}" media-type="application/xhtml+xml"/>')
                spine_items.append(f'<itemref idref="{item_id}"/>')
                toc_entries.append(f'<navPoint id="nav_{idx}" playOrder="{idx}"><navLabel><text>{file_path.stem}</text></navLabel><content src="{chapter_filename}"/></navPoint>')

            # 4. content.opf
            opf_content = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookID" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{self.title}</dc:title>
    <dc:creator>{self.author}</dc:creator>
    <dc:language>vi</dc:language>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    {"".join(manifest_items)}
  </manifest>
  <spine toc="ncx">
    {"".join(spine_items)}
  </spine>
</package>"""
            z.writestr("OEBPS/content.opf", opf_content)

            # 5. toc.ncx
            ncx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:uuid:12345"/></head>
  <docTitle><text>{self.title}</text></docTitle>
  <navMap>
    {"".join(toc_entries)}
  </navMap>
</ncx>"""
            z.writestr("OEBPS/toc.ncx", ncx_content)

class TextFormatConverter:
    """Chuyển đổi qua lại giữa TXT, MD và HTML thuần túy."""

    @staticmethod
    def md_to_txt(content: str) -> str:
        # Xóa các cú pháp Markdown cơ bản giữ lại chữ
        text = re.sub(r'#+\s*', '', content)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        return text

    @staticmethod
    def html_to_md(content: str) -> str:
        # Chuyển đổi các thẻ đoạn văn và break line thành Markdown
        text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', content, flags=re.IGNORECASE)
        text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', content, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', content, flags=re.IGNORECASE)
        text = re.sub(r'<br\s*/?>', r'\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)  # Strip các thẻ còn lại
        return text.strip()

    @staticmethod
    def txt_to_md(content: str) -> str:
        # Tự động nhận diện dòng đầu tiên làm heading nếu ngắn
        lines = content.splitlines()
        if lines and len(lines[0]) < 60 and not lines[0].startswith("#"):
            lines[0] = f"# {lines[0]}"
        return "\n".join(lines)
```

---

## 2. CÔNG CỤ 2: OCR — TẠM HOÃN, CHUYỂN VÀO ROADMAP (CHỐT v2.3)
* **Quyết định**: **Không làm trong Phase 1–4. Chi tiết hoãn xem `ROADMAP.md` §6.**
* **Lý do**: Tesseract/Poppler nặng, chất lượng tiếng Việt + layout thua xa công cụ ngoài (Preview, Google Lens/Docs, NAPS2, Calibre). Giữ lõi Lean.
* **Tạm thời**: Người dùng OCR bằng tool ngoài rồi nạp txt/md/html vào `sources/` như bình thường.

---

## 3. CÔNG CỤ 3: TRAU CHUỐT VĂN PHONG & SOÁT LỖI (HỢP NHẤT VÀO LÕI)

Theo yêu cầu, tính năng này được **tinh giản và tích hợp trực tiếp thành tính năng cốt lõi** thông qua cơ chế chọn Prompt Bổ Sung.

### Các File Prompt Bổ Sung Cung Cấp Sẵn (`prompts/`):

#### 1. File `prompts/qa_polish_tien_hiep.txt`:
```text
[CHỈ THỊ TRAU CHUỐT VĂN PHONG TIÊN HIỆP / KIẾM HIỆP]
1. Chuẩn hóa các danh xưng Hán-Việt phù hợp: sư tôn, đệ tử, đạo hữu, các hạ, tiền bối, vãn bối.
2. Các chiêu thức võ công, đan dược, pháp bảo dịch theo phong cách kiếm hiệp kinh điển (ví dụ: Bạt Kiếm Thuật, Hỗn Nguyên Đan).
3. Đảm bảo câu văn hùng hồn, nhịp điệu dứt khoát trong các đoạn miêu tả chiến đấu.
```

#### 2. File `prompts/qa_proofread.txt`:
```text
[CHỈ THỊ SOÁT LỖI CHÍNH TẢ & DẤU CÂU]
1. Rà soát và sửa triệt để các lỗi chính tả tiếng Việt (dấu hỏi/ngã, s/x, tr/ch, d/gi/r).
2. Xử lý các câu bị lặp từ hoặc dịch gượng gạo theo cấu trúc ngữ pháp ngoại ngữ.
3. Giữ nguyên 100% tất cả các thẻ Markdown và khoảng cách dòng trống.
```

* **Cách dùng**: Khi người dùng dịch file hoặc muốn chạy lại một file đã dịch để trau chuốt, chỉ cần tick chọn file đó trên màn hình Workspace $\to$ Chọn thêm prompt `qa_polish_tien_hiep.txt` hoặc `qa_proofread.txt` $\to$ Bấm Chạy!

---

## 4. CÔNG CỤ 4: TRÍCH XUẤT THỰC THỂ, NHÂN VẬT & THUẬT NGỮ (ENTITY EXTRACTOR)

### 4.1. Cơ Chế Sinh Nội Dung Trực Tiếp Tại Thư Mục Dự Án
* Công cụ chạy quét các file nguồn trong dự án và tự động tạo ra tệp (đường dẫn chuẩn duy nhất, chốt v2.3):
  `workspace/projects/{slug}/assets/glossary.txt`
* **Định dạng chuẩn của file `glossary.txt`**:
  ```text
  # BẢNG THUẬT NGỮ & NHÂN VẬT DỰ ÁN
  # Cú pháp: [Tên gốc] = [Tên dịch tiếng Việt] (Vai trò/Ghi chú)

  Kim Dokja = Kim Độc Hành (Nhân vật chính)
  Yoo Joonghyuk = Du Trọng Hách (Hồi quy giả)
  Han Sooyoung = Hàn Tú Ánh (Tác giả tiểu thuyết)
  Star Stream = Tinh Lưu Trực Tiếp (Hệ thống phát sóng)
  Black Flame Dragon = Hắc Diễm Ma Long (Tinh tọa vực thẳm)
  ```

### 4.2. Cơ Chế Đính Kèm Khi Gửi Chunk Để Có Tác Dụng
* **Nguyên lý bắt buộc**: File `assets/glossary.txt` chỉ phát huy tác dụng khi nội dung của nó được **đính kèm vào Prompt gửi cùng từng Chunk**.
* **Luồng xử lý (Phase 1 dùng `run.py`, Phase 3+ tách `core/pipeline.py` nếu cần)**:
  1. Khi bắt đầu dịch chunk $K$, hệ thống đọc nội dung file `workspace/projects/{slug}/assets/glossary.txt`.
  2. Quét nhanh: Chỉ lấy ra những dòng thuật ngữ có từ gốc xuất hiện thực tế trong văn bản của chunk $K$ (để không làm loãng prompt).
  3. Nhúng danh sách thuật ngữ này vào biến `{{glossary_terms}}` trong template prompt chính:
     ```text
     # BẢNG THUẬT NGỮ BẮT BUỘC SỬ DỤNG CHO ĐOẠN NÀY:
     - Kim Dokja -> Kim Độc Hành
     - Star Stream -> Tinh Lưu Trực Tiếp
     
     *Quy tắc: Khi gặp các từ gốc trên trong văn bản, bạn BẮT BUỘC phải dịch chính xác thành từ dịch tương ứng.*
     ```
   4. Gửi toàn bộ gói chỉ thị này cùng chunk lên AI. Nhờ đó, AI luôn dịch chuẩn xác và nhất quán 100% tên riêng của nhân vật qua hàng trăm chương truyện.

---

## 5. ĐÁNH GIÁ HỖ TRỢ PLUGIN (CHỐT v2.3: QUY ƯỚC, KHÔNG FRAMEWORK)

**Kết luận**: Không xây hệ thống plugin động (entry-points/sandbox/marketplace) ở Phase 1/2 — quá nặng cho tool single-user. Mở rộng bằng 3 quy ước có sẵn, ai biết Python cơ bản cũng thêm được:

| Loại mở rộng | Quy ước | Ví dụ |
|---|---|---|
| Prompt mới | Thêm file `prompts/<ten>.txt` chứa `{{source_text}}` (+ `{{glossary_terms}}` nếu cần) | `qa_polish_tien_hiep.txt` |
| Tool độc lập | Thêm file `tools/<ten>_tool.py` chạy `python tools/<ten>_tool.py ...`, chỉ dùng stdlib | `epub_tool.py` |
| Provider AI mới | Thêm file `core/<ten>_client.py` implement `AIClient.translate_chunk(prompt)`, tái dùng `KeyRotator` | `openai_client.py` |

Khi nào mới cần framework thật: có ≥5 providers hoặc tool cần UI riêng → khi đó thêm `tools/manifest.json` + loader `importlib` ~20 dòng (Phase 5, chưa làm).
