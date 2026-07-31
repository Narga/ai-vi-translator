# Kế hoạch / báo cáo đánh giá HTML → Markdown

Ngày: 2026-07-31  
Phạm vi: tính năng chuyển HTML/XHTML/HTM sang Markdown phục vụ nội dung sách điện tử.  
Ràng buộc: chỉ phân tích và lập kế hoạch; không thay đổi mã nguồn.

## 1. Kết luận điều hành

Tính năng hiện có đường chạy đầy đủ từ UI đến converter, nhưng **chưa đủ cơ sở để xem là bảo toàn định dạng sách điện tử một cách đáng tin cậy**.

Có một blocker triển khai trực tiếp:

- `html2text` được khai báo trong optional extra `epub`, nhưng `core/source_normalizer.py` import `convert_html_to_markdown`, và module đó import `html2text` ngay khi nạp. Trong môi trường Python hệ thống và `.venv` hiện tại, import thất bại với `ModuleNotFoundError: No module named 'html2text'`.

Có các lỗi/điểm mất dữ liệu đã xác nhận qua đọc mã:

- `post_clean()` xóa toàn bộ alt text của ảnh: `![alt](url)` thành `![](url)`.
- `<u>` được giữ lại dưới dạng HTML thô, không phải cú pháp Markdown chuẩn; khả năng hiển thị phụ thuộc renderer.
- Ngoại lệ converter bị biến thành chuỗi `[Lỗi chuyển đổi nội dung]`, sau đó vẫn có thể được ghi thành file đầu ra như một conversion thành công.
- Chưa có test riêng cho HTML → Markdown; vì vậy các tuyên bố hỗ trợ bảng, XHTML thực tế, ảnh, liên kết tương đối, ruby và các thẻ định dạng chưa được nghiệm thu.

Đánh giá hiện tại: **P1 — cần xử lý trước khi dùng làm pipeline tiền xử lý sách điện tử đáng tin cậy**. Nếu môi trường triển khai chưa cài extra `epub`, mức độ thực tế là **P0 vận hành: tính năng không chạy**.

## 2. Tuân thủ kiến trúc

Luồng phù hợp với `ARCHITECTURE.md`: WebUI/route gọi plugin converter thuộc vùng Plugins & Text Processing; xử lý chuẩn hóa nằm ở `core/source_normalizer.py`, còn adapter file nằm ở service converter.

Luồng thực tế:

```text
converter-tool-plugin.js
  → webui/routes/plugins.py:run_epub_converter
  → plugins/epub_converter/plugin.py:Plugin._html_to_markdown
  → services/text_converter.py:convert_html_file
  → core/source_normalizer.py:normalize_html_file
  → epub_to_text/epub2text.py:convert_html_to_markdown
  → html2text
  → post_clean
  → .md
```

GitNexus context xác nhận:

- `normalize_html_file` gọi `_extract_body`, `_preprocess_ruby`, `convert_html_to_markdown`, `post_clean`.
- `convert_html_file` là adapter được `Plugin._html_to_markdown` gọi.
- `Plugin._html_to_markdown` có caller từ `Plugin.convert`; route worker gọi plugin qua `run_epub_converter`.
- Impact upstream của `_html_to_markdown`: LOW theo chỉ mục, ảnh hưởng trực tiếp vùng `Epub_converter` và gián tiếp `Routes`; tuy nhiên route thực thi trong closure nên đồ thị không phản ánh hết mọi runtime consumer.

Không có HIGH/CRITICAL risk trong kết quả impact cho các symbol khảo sát. Báo cáo này không sửa symbol nào.

## 3. Bằng chứng và phát hiện

### 3.1. Dependency / khả năng chạy

Nguồn khai báo: `pyproject.toml:29-40` đặt `beautifulsoup4`, `html2text` trong `[project.optional-dependencies].epub`, không nằm trong dependencies lõi.

Nguồn import: `plugins/epub_converter/epub_to_text/epub2text.py:21` import `html2text` ở module level; `core/source_normalizer.py:4` import converter ở module level.

Kiểm tra runtime:

```text
python3: ModuleNotFoundError: No module named 'html2text'
.venv/bin/python: ModuleNotFoundError: No module named 'html2text'
```

Hệ quả: không thể chạy conversion thực tế trong môi trường hiện tại; mọi kết luận về output của `html2text` (đặc biệt bảng và nested list) cần được xác nhận sau khi chuẩn hóa dependency.

### 3.2. Ma trận định dạng

| Thành phần sách điện tử | Mã hiện tại | Đánh giá |
|---|---|---|
| Heading | Giao cho `html2text` | Có ý định hỗ trợ; chưa có runtime test |
| Bold / italic | Giao cho `html2text` | Có ý định hỗ trợ; chưa test nested/emphasis biên |
| Danh sách UL/OL | Giao cho `html2text` | Chưa test nested list, continuation paragraph |
| Blockquote | Giao cho `html2text` | Chưa test nested quote |
| Link | `html2text`, sau đó `post_clean` inline numeric references | Có nguy cơ sai link tương đối/anchor; chưa test |
| Ảnh | `html2text`, sau đó `post_clean:59-60` xóa alt | **Mất metadata alt đã xác nhận** |
| Code inline / fenced code | `h.mark_code = True` | Cần test ký tự backtick, whitespace và ngôn ngữ |
| Bảng | README tuyên bố hỗ trợ | Không có cấu hình/test chứng minh; **chưa nghiệm thu** |
| Underline | placeholder rồi khôi phục `<u>` | Giữ được nội dung nhưng không portable Markdown |
| Strikethrough | Phụ thuộc `html2text` | Chưa có contract hoặc test |
| Ruby | `_preprocess_ruby:17-23` đổi sang `漢字《かな》` | Mang tính đặc thù; regex chỉ bao phủ dạng đơn giản |
| Style/script/comment | `post_clean` dọn sau conversion | Cần test để bảo đảm không lọt text script/style |
| Charset | đọc file với UTF-8 `errors='replace'` | Có thể thay thế ký tự sai, không báo lỗi |

### 3.3. Các vấn đề về tính đúng đắn

1. `post_clean()` không chỉ làm sạch cấu trúc mà còn thay đổi nội dung hiển thị: xóa alt ảnh. Đây là nguyên nhân gốc của mất thông tin ảnh, không phải lỗi renderer.
2. `convert_html_to_markdown()` bắt mọi exception và trả về chuỗi lỗi. Boundary phía trên không phân biệt kết quả lỗi với Markdown hợp lệ; do đó có nguy cơ tạo file “thành công giả”.
3. Chưa có hợp đồng rõ ràng về Markdown flavor. Việc giữ `<u>` cho thấy output là Markdown pha HTML, nhưng UI/README đang mô tả là Markdown sạch.
4. `normalize_html_file()` luôn tạo file `.md` cạnh input trước khi `convert_html_file()` xử lý output path. Với file trùng stem đã tồn tại, cần policy collision/atomic write rõ ràng để tránh ghi đè ngoài ý muốn.
5. Batch route đánh dấu `done` nếu có ít nhất một output; lỗi từng file được log nhưng không biểu diễn trạng thái partial failure rõ ràng.
6. UI hiện đã gửi `delete_source` trong payload (`converter-tool-plugin.js:104-112`) và template ghi rõ cờ chỉ áp dụng cho MD ↔ HTML. Cần nghiệm thu rằng backend tiếp tục bỏ qua cờ này cho cả hai luồng EPUB.

## 4. Nguyên nhân cốt lõi

### Cốt lõi A — Dependency contract không khớp runtime

Converter được coi là plugin/extra nhưng lại được import từ đường xử lý core. Vì vậy việc không cài `epub` extra làm hỏng toàn bộ đường HTML → Markdown tại thời điểm import, trước cả khi đọc input.

### Cốt lõi B — Trộn conversion với hậu xử lý phá dữ liệu

`post_clean()` đang mang trách nhiệm “làm sạch” nhưng có biến đổi semantics (xóa alt ảnh, inline reference links). Không có invariant rằng hậu xử lý phải bảo toàn nội dung và định dạng.

### Cốt lõi C — Error contract không phân biệt lỗi và output

Converter trả chuỗi sentinel thay vì raise/kiểu kết quả lỗi. Các tầng adapter/route tiếp tục ghi file và báo thành công, làm mất khả năng phát hiện sớm và có thể đưa dữ liệu lỗi vào bước dịch tiếp theo.

### Cốt lõi D — Thiếu test contract theo định dạng sách

Không tìm thấy test riêng cho `convert_html_to_markdown`, `normalize_html_file` hoặc `convert_html_file`. README/CHANGELOG nêu hỗ trợ bảng và định dạng cơ bản nhưng không có fixture/round-trip assertion tương ứng.

## 5. Phương án xử lý triệt để

### P0 — Làm cho môi trường chạy đúng

1. Chốt ownership dependency: hoặc đưa `html2text` và `beautifulsoup4` vào dependency bắt buộc của application, hoặc bảo đảm mọi deployment chạy converter cài `[epub]` và thêm preflight/error UI rõ ràng.
2. Thêm kiểm tra khởi động/tác vụ để báo thiếu dependency với hướng dẫn cài đặt, thay vì traceback trong worker.
3. Xác định một phiên bản `html2text` được hỗ trợ và chạy fixture trên cùng phiên bản đó.

### P1 — Khôi phục tính toàn vẹn nội dung

1. Bỏ biến đổi xóa alt ảnh; hậu xử lý chỉ được chuẩn hóa whitespace/format không làm đổi semantics.
2. Chọn contract underline: Markdown mở rộng được hỗ trợ rõ ràng, hoặc giữ HTML inline và công bố đó là Markdown pha HTML. Không để hành vi phụ thuộc ngầm vào renderer.
3. Chuyển lỗi conversion thành exception/result lỗi có cấu trúc; không ghi output khi conversion thất bại hoặc output chứa sentinel lỗi.
4. Ghi output theo cách atomic và kiểm tra collision; chỉ thay thế file đích sau khi conversion hoàn tất.
5. Định nghĩa trạng thái batch: `done`, `partial`, `error`, kèm danh sách file thất bại.

### P1 — Kiểm thử định dạng sách điện tử

Tạo fixture HTML/XHTML tối thiểu gồm: heading 1–6, bold/italic lồng nhau, underline, strikethrough, UL/OL lồng nhau, blockquote lồng nhau, link tương đối + anchor, ảnh có alt + title, inline/fenced code, bảng có thead/tbody, ruby, entity Unicode, comment/style/script và HTML lỗi nhẹ.

Mỗi fixture cần assertion cho:

- không mất text;
- heading/list/quote/code giữ cấu trúc;
- URL và fragment không đổi;
- alt ảnh không đổi;
- bảng có output theo Markdown flavor đã chốt hoặc được đánh dấu unsupported rõ ràng;
- lỗi dependency và lỗi parser không tạo file output giả;
- conversion lặp lại không làm thay đổi nội dung thêm lần nữa.

### P2 — Nghiệm thu tích hợp

1. Test service trực tiếp với file tạm.
2. Test plugin `Plugin.convert()` cho HTML/HTM/XHTML.
3. Test route batch: thành công toàn bộ, một file lỗi, tất cả lỗi, output collision, file không tồn tại.
4. Browser smoke test: chọn file, chạy HTML → MD, xem log, tải output, refresh sidebar.
5. Chỉ cập nhật README/CHANGELOG sau khi fixture và smoke test pass.

## 6. Tiêu chí đạt

- Môi trường cài đặt chuẩn chạy được HTML → Markdown mà không import error.
- Không mất text, alt ảnh, link, heading, emphasis, list, quote hoặc code trong fixture đã chốt.
- Bảng và underline có contract/documentation rõ ràng; không tuyên bố hỗ trợ nếu chưa kiểm chứng.
- Conversion lỗi không tạo file Markdown hợp lệ giả và không báo `done`.
- Batch partial failure được báo đúng.
- Có test tự động cho service/plugin/route và ít nhất một browser/manual smoke test được ghi nhận.
- `git diff --check` sạch; không sửa mã nguồn trong báo cáo này.

## 7. Thứ tự triển khai đề xuất

1. P0 dependency/preflight.
2. P1 error contract + hậu xử lý bảo toàn dữ liệu.
3. P1 fixture/unit tests cho converter.
4. P1 batch/output safety.
5. P2 route/browser nghiệm thu.
6. Cập nhật tài liệu tính năng và chỉ đánh dấu hoàn thành sau khi có bằng chứng runtime.

## 8. Trạng thái thay đổi của phiên này

- Đã đọc `ARCHITECTURE.md` và `docs/wip/del_SKILL.md`.
- Đã cập nhật GitNexus index do index cũ chậm 1 commit.
- Đã truy vết bằng GitNexus context/impact và kiểm tra mã nguồn liên quan.
- Đã chạy import smoke check; phát hiện thiếu `html2text`.
- **Không thay đổi mã nguồn.** Các thay đổi có sẵn trong worktree (`config/app.ini`, `webui/static/js/editor-component.js`, `webui/static/js/main.js`) được giữ nguyên.

---

# Phần tiếp theo — Rà soát Markdown → HTML/XHTML

## 9. Kết luận Markdown → HTML

Tính năng Markdown → HTML hiện **chỉ đạt mức prototype cho Markdown đơn giản**, chưa đạt yêu cầu của pipeline sách điện tử có style, hình ảnh, liên kết, footnote/note, quote và pre/code.

Nguyên nhân kiến trúc lớn nhất là hệ thống có **hai implementation khác nhau**:

1. `plugins/epub_converter/services/text_converter.py` dùng cho task UI `.MD → HTML`, tự viết `_md_inline()` và `_md_block_to_xhtml()`.
2. `plugins/epub_converter/text_to_epub/parser.py` dùng khi tạo EPUB với `python-markdown`, bật `extra`, `sane_lists`, `tables`.

Hai đường chạy không có cùng dialect, cùng extension hoặc cùng test contract. Một file Markdown có thể hiển thị khác nhau tùy người dùng bấm `.MD → HTML` hay xuất `MD → EPUB 3`.

Đánh giá: **P1 — cần chuẩn hóa engine và contract trước khi gọi là hoàn thiện**. Nếu mục tiêu là sách điện tử production, footnote/note và asset path phải được xem là P0/P1 bắt buộc, không phải cải tiến tùy chọn.

## 10. Bằng chứng runtime của custom Markdown → HTML

Đã chạy self-check có sẵn:

```text
./.venv/bin/python plugins/epub_converter/services/text_converter.py
markdown->xhtml self-check OK
```

Self-check này chỉ kiểm tra heading, bold, link, list phẳng, quote, image đơn giản và hr; không kiểm tra các yêu cầu sách điện tử quan trọng.

Smoke input mở rộng cho kết quả:

```markdown
Đoạn **đậm _lồng_**, ~~gạch~~, <u>gạch chân</u>,
[link](chap.xhtml#n), ![ảnh](img/a.png "title").

[^1]: Chú thích cuối trang

- mục
  - mục con

| A | B |
|---|---|
| 1 | 2 |
```

Kết quả thực tế của custom engine:

- `~~gạch~~` giữ nguyên Markdown, không thành `<del>`.
- `<u>gạch chân</u>` bị escape thành `&lt;u&gt;...`, nên không còn là style underline.
- Image có title không được nhận dạng; toàn bộ cú pháp giữ nguyên như text.
- Footnote definition trở thành một đoạn văn thường.
- Nested list bị làm phẳng thành các `<li>` cùng cấp.
- Bảng bị coi là paragraph và xuống dòng bằng `<br/>`.
- Fenced code cơ bản chạy được và escape nội dung `<`, `>` đúng.

## 11. Ma trận định dạng Markdown → XHTML

| Định dạng | Custom UI engine | Engine `python-markdown` hiện tại | Quyết định cần chốt |
|---|---|---|---|
| Heading ATX | Có H1–H6 | Có | Giữ; thêm setext nếu contract cần |
| Heading setext | Không | Có khả năng hỗ trợ | Chọn một dialect chung |
| Bold / italic | Có nhưng regex dễ lỗi khi lồng/code | Có | Test nested và code boundary |
| Underline | Raw HTML bị escape | Raw HTML thường được giữ | Dùng extension/HTML contract rõ ràng |
| Strikethrough | Không | `extra` không đủ đảm bảo | Bật extension hoặc quy ước `<del>` |
| Highlight / small caps / ruby | Không | Không có contract | Dùng HTML inline an toàn hoặc extension riêng |
| Inline code | Có cơ bản | Có | Không áp dụng bold/link bên trong code |
| Fenced code / `pre` | Có code fence cơ bản | Có qua extension | Giữ language class hợp lệ, escape attr |
| Indented code | Không | Có khả năng hỗ trợ | Test hoặc tuyên bố unsupported |
| UL/OL phẳng | Có | Có | Giữ |
| Nested list / continuation | Làm phẳng | Tốt hơn nhưng chưa có test | Bắt buộc fixture |
| Task list | Không | Chưa có contract | Quyết định có/không hỗ trợ |
| Blockquote nhiều đoạn | Có cơ bản | Có | Test nested quote/list/code |
| Link đơn giản | Có | Có | Giữ URL + fragment |
| Link title / parentheses / reference | Không đầy đủ | Tùy extension | Bắt buộc test URL thực tế |
| Image alt + URL đơn giản | Có | Có | Alt là dữ liệu bắt buộc |
| Image title / query URL | Không | Tùy parser | Bắt buộc test |
| Bảng | Không | Có `tables` | Hai đường chạy phải đồng nhất |
| Footnote | Không | Chưa bật `footnotes` | Phải định nghĩa EPUB footnote contract |
| Notes/endnotes | Không | Không có contract | Phân biệt note chú giải với footnote |
| Raw HTML | Escape toàn bộ | Có thể giữ nguyên | Chốt policy an toàn và semantic |
| HTML entities/Unicode | Có escape đầu ra | Parser xử lý khác | Test Unicode, entity, XML validity |
| Hard break | Mọi newline trong paragraph thành `<br/>` | Theo Markdown parser | Cần thống nhất để tránh thay đổi dàn trang |

## 12. Lỗi cốt lõi của Markdown → HTML

### 12.1. Parser tự viết bằng regex không đủ cho Markdown

`_md_inline()` chạy một chuỗi regex tuần tự trên text đã escape. Cách này không có lexer/AST, nên không biết vùng code, link, image, raw HTML hay nested emphasis. Hệ quả:

- Có thể biến đổi cú pháp bên trong inline code.
- Không xử lý delimiter escaping, nested structures và URL phức tạp.
- Không phân biệt image có title với text thường.
- Không thể mở rộng an toàn cho footnote, attributes hoặc inline style.

`_md_block_to_xhtml()` cũng xử lý từng dòng và chỉ nhận các block đơn giản. Nó không xây dựng cây list, không parse table, không parse footnote và không giữ metadata block.

### 12.2. Hai engine tạo output không nhất quán

`Plugin._markdown_to_html()` gọi `convert_markdown_file()` trong `services/text_converter.py`; còn `process_book_directory(..., use_markdown=True)` gọi `convert_markdown_to_html_body()` trong `text_to_epub/parser.py`. Việc sửa một engine không sửa engine còn lại sẽ tạo hồi quy theo đường chạy.

### 12.3. Footnote/note chưa có semantic EPUB

Markdown footnote không chỉ là text. Với EPUB/XHTML cần ít nhất:

- marker trong nội dung có liên kết tới note;
- note có `id` ổn định và không trùng;
- backlink từ note về marker;
- phân biệt footnote/endnote/author note nếu sản phẩm cần;
- `epub:type="noteref"` cho marker và `epub:type="footnote"` hoặc semantic tương ứng cho phần note;
- xử lý nhiều chương, ID scope và link khi đóng gói EPUB.

Hiện không có bước nào thực hiện contract này.

### 12.4. Asset path và HTML validity chưa được chốt

Image hiện chỉ hỗ trợ dạng URL đơn giản. Chưa có policy cho:

- đường dẫn có khoảng trắng, query string hoặc dấu ngoặc;
- URL tuyệt đối so với asset nội bộ EPUB;
- copy/resolve asset vào thư mục `Images`;
- alt/title và kích thước;
- path traversal (`../`) khi đóng gói;
- kiểm tra XML/XHTML sau khi sinh.

Ngoài ra `build_xhtml()` escape title nhưng không escape `book_lang` và `css_href`; metadata bất thường có thể tạo XHTML không hợp lệ.

## 13. Contract đích phải chốt trước khi sửa

Model thực hiện task phải ghi rõ các quyết định sau trong test hoặc tài liệu, không tự suy đoán:

1. **Dialect:** CommonMark cơ bản + GFM tables/strikethrough/task list, hay một dialect khác.
2. **Raw HTML:** giữ các tag inline được whitelist (`u`, `mark`, `ruby`, `small`, `sub`, `sup`) hay escape toàn bộ.
3. **Style:** mapping tối thiểu `strong`, `em`, `del`, `u`, `mark`, `sub`, `sup`, `code`; không dùng CSS inline từ input tùy ý.
4. **Links:** giữ nguyên URL, fragment, title; chặn scheme nguy hiểm nếu nội dung đến từ nguồn không tin cậy.
5. **Images:** giữ alt/title; URL nội bộ phải resolve/copy đúng vào EPUB; không cho path thoát khỏi thư mục asset.
6. **Footnote:** quy ước cú pháp input, numbering, placement, backlink và EPUB semantics.
7. **Notes:** phân biệt footnote, endnote, sidenote và author note; nếu chưa hỗ trợ phải báo unsupported, không âm thầm biến thành paragraph.
8. **Quote:** hỗ trợ quote lồng, nhiều paragraph, list và code trong quote hay không.
9. **Pre/code:** giữ whitespace tuyệt đối, escape text, language class whitelist/escape, xử lý fence không đóng.
10. **Output:** XHTML hợp lệ, UTF-8, self-closing tags phù hợp, title/lang/css được escape, không tạo file khi validation thất bại.

## 14. Chỉ dẫn triển khai bắt buộc cho model tiếp theo

### Giai đoạn A — Chuẩn bị và kiểm soát phạm vi

1. Đọc `ARCHITECTURE.md`, file kế hoạch này và `docs/wip/del_SKILL.md` nếu còn áp dụng cho task.
2. Chạy `git status --short`; không ghi đè thay đổi có sẵn.
3. Chạy GitNexus context cho các symbol: `_md_inline`, `_md_block_to_xhtml`, `convert_markdown_file`, `convert_markdown_to_html_body`, `build_xhtml`, `process_book_directory`.
4. Trước khi sửa từng function/class/method, chạy `gitnexus_impact` upstream đúng symbol. Nếu risk HIGH/CRITICAL, dừng và báo người dùng trước khi sửa.
5. Không sửa song song hai engine mà không có quyết định engine canonical.

### Giai đoạn B — Chọn engine canonical

1. Ưu tiên dùng parser Markdown chuẩn đã có trong dependency (`python-markdown`) thay vì tiếp tục mở rộng regex parser.
2. Nếu cần GFM/footnotes/attributes, chốt extension cụ thể và pin dependency; không giả định `extra` tự hỗ trợ mọi tính năng.
3. Để UI `.MD → HTML` và MD → EPUB gọi cùng một service/parser và cùng options.
4. Nếu phải giữ custom engine vì lý do dependency, giới hạn nó ở dialect nhỏ được tài liệu hóa; không tuyên bố hỗ trợ bảng/footnote/nested list khi chưa có parser/fixture.

### Giai đoạn C — Thiết kế semantic model

1. Parse Markdown thành AST/token hoặc dùng renderer chuẩn.
2. Render block nodes: heading, paragraph, thematic break, blockquote, list (có nesting), table, code/pre, footnote definition.
3. Render inline nodes: text, strong, em, del, underline/whitelist HTML, code, link, image, footnote reference.
4. Tách `render_inline`, `render_block`, `render_footnotes` và `validate_xhtml`; mỗi phần có test contract riêng.
5. Không dùng regex hậu xử lý trên HTML đã sinh để “sửa nhanh” cấu trúc.

### Giai đoạn D — Quy tắc bảo toàn định dạng

- Text: escape text node đúng một lần; không double-escape entity hợp lệ.
- Strong/emphasis: không áp dụng formatting bên trong code span/pre.
- Underline/highlight/sub/sup/ruby: chỉ cho phép theo whitelist và validate nesting.
- Link: escape attribute, giữ fragment/query/title; reject scheme nguy hiểm theo policy.
- Image: escape alt/title/src; resolve asset nội bộ; giữ alt rỗng có chủ ý; reject traversal.
- List: giữ nesting, ordered-list start và continuation paragraph nếu dialect hỗ trợ.
- Quote: giữ cấu trúc nhiều paragraph và block con.
- Pre/code: giữ nguyên whitespace/newline, escape nội dung, validate `language-*` class.
- Table: giữ header/body, cell alignment nếu contract có; escape cell content.
- Footnote/note: tạo ID ổn định, marker/backlink, semantic EPUB attributes và không trùng ID giữa chương.
- HTML document: escape `title`, `lang`, `css_href`; validate XML/XHTML trước khi ghi.

### Giai đoạn E — Test bắt buộc

Tạo fixture và assertion cho từng nhóm sau:

1. Style: bold, italic, nested, underline, strike, highlight, sub/sup, escaped delimiters.
2. Image: alt, title, relative path, query/fragment, Unicode filename, path traversal bị từ chối.
3. Link: absolute, relative, fragment, title, parentheses, reference link, unsafe scheme.
4. Footnote/note: một note, nhiều note, note trước marker, duplicate labels, nhiều chương, backlink.
5. Quote: nhiều paragraph, nested quote, list/code trong quote.
6. Pre/code: inline backtick, fenced code có language, fence không đóng, ký tự `<>&`, whitespace.
7. Lists: nested UL/OL, ordered start, mixed nesting, task list nếu hỗ trợ.
8. Tables: header, body, escaped pipe, alignment nếu hỗ trợ.
9. XHTML: parse bằng XML parser; kiểm tra không có unescaped `&`, attribute malformed hoặc duplicate ID.
10. Integration: UI task và MD → EPUB phải cho cùng body semantics với cùng input.

### Giai đoạn F — Nghiệm thu và bàn giao

1. Chạy unit/service tests tối thiểu.
2. Chạy test route/plugin batch, gồm partial failure và output collision.
3. Chạy browser/manual smoke cho `.MD → HTML`.
4. Kiểm tra EPUB bằng validator/reader thực tế nếu có; ít nhất mở XHTML và kiểm tra footnote/image/link.
5. Chạy `git diff --check`.
6. Trước commit chạy `gitnexus_detect_changes()` và xác nhận chỉ các symbol/flow dự kiến bị ảnh hưởng.
7. Không đánh dấu hoàn tất nếu chỉ self-check cũ `markdown->xhtml self-check OK` pass.

## 15. Tiêu chí hoàn thành mới

- Hai đường Markdown → HTML và Markdown → EPUB dùng cùng dialect/semantic contract.
- Style cơ bản, ảnh, link, quote, pre/code được test và giữ đúng.
- Footnote/note hoặc được render đúng semantic EPUB, hoặc bị từ chối rõ ràng; không biến thành paragraph im lặng.
- Nested list và table không bị làm phẳng/mất cấu trúc.
- Output XHTML parse được và không có duplicate ID/path traversal.
- Không có regex post-processing làm biến đổi semantics sau khi render.
- Có fixture regression cho mọi lỗi đã nêu trong phần 10.
- Báo cáo/changelog chỉ cập nhật sau khi test runtime và EPUB smoke pass.

---

# Phần tiếp theo — Xóa nguồn và hai luồng EPUB 3

## 16. Phạm vi runtime chính xác

Có ba đường liên quan, cần phân biệt khi sửa:

| Tác vụ UI/API | Đường chạy hiện tại | Có xóa nguồn không? |
|---|---|---|
| HTML → Markdown | `run_epub_converter` → `Plugin.convert` → `convert_html_file` | Có thể, qua `delete_source` |
| Markdown → HTML | `run_epub_converter` → `Plugin.convert` → `convert_markdown_file` | Có thể, qua `delete_source` |
| Markdown → EPUB 3 | route đổi MD thành HTML tạm → `create_project_epub` → dọn HTML tạm | **Không được xóa MD nguồn** |
| HTML → EPUB 3 | route truyền HTML trực tiếp → `create_project_epub` | **Không được xóa HTML nguồn** |
| Legacy text/MD → EPUB | `run_epub_converter(direction=text_to_epub)` → `process_book_directory` → `text_to_epub` | Không nằm trong checkbox converter hiện tại; không mở rộng phạm vi nếu không có yêu cầu riêng |

`create_project_epub()` là service canonical cho hai task EPUB của workspace hiện tại. `text_to_epub/main.py` là đường legacy/khác contract; không được sửa nó để “tiện tay” khi task chỉ yêu cầu hai nút EPUB 3 hiện tại.

## 17. Đánh giá xóa file nguồn sau chuyển đổi

### Đã đúng

- Checkbox có mặt trong `workspace_ebook_kit.html` và ghi rõ chỉ áp dụng cho MD ↔ HTML.
- `converter-tool-plugin.js` đọc checkbox; thiếu element được coi là `false`.
- Route chỉ truyền `delete_flag` khi task là `html_to_markdown` hoặc `markdown_to_html` (`webui/routes/plugins.py:223`). Vì vậy hai task EPUB hiện không nhận cờ xóa nguồn.
- Service chỉ gọi `_do_delete()` sau khi `write_text()` đầu ra hoàn tất.
- `_do_delete()` không xóa nếu input và destination resolve thành cùng một path.

### Vấn đề cần xử lý

1. **Collision cùng path vẫn nguy hiểm:** `convert_markdown_file()` ghi thẳng `destination`; nếu caller truyền output trùng input, nguồn bị ghi đè trước khi `_do_delete()` có cơ hội chặn. HTML → MD cũng có rủi ro qua flow tạm/copy.
2. **Không có validation trước khi xóa:** “ghi được file” chưa đồng nghĩa output là HTML/XHTML/Markdown hợp lệ. Xóa nguồn chỉ được phép sau parse/validation thành công và output tồn tại, khác path, nằm trong vùng được phép.
3. **Batch partial success không rõ:** route thu thập `outputs`; chỉ cần một file thành công là status `done`, dù file khác lỗi. Với delete source, cần log/trạng thái từng file để không làm người dùng tưởng tất cả nguồn đã được xử lý.
4. **Không có test filesystem:** chưa thấy test riêng cho checkbox off/on, output collision, permission error, conversion lỗi, input symlink, file không tồn tại và batch partial.
5. **Không được mở rộng cờ sang EPUB:** nếu sau này frontend gửi cờ cho mọi task, backend phải vẫn ép `False` cho `create_epub` và `markdown_to_epub`. EPUB build không phải conversion tại chỗ; xóa nguồn có thể làm mất dữ liệu khi đóng gói lỗi hoặc asset thiếu.

### Contract an toàn tối thiểu

Chỉ xóa nguồn khi đồng thời đúng tất cả điều kiện:

```text
task ∈ {html_to_markdown, markdown_to_html}
AND delete_source == true
AND input tồn tại và là file thường trong project/section
AND output resolve khác input resolve
AND output tồn tại, đọc được, đúng suffix và qua validation
AND conversion không trả partial/error
```

Không cần trash system, backup manager hay transaction framework mới: theo Ponytail, dùng output tạm cùng thư mục, `os.replace`/rename nguyên tử và guard path là đủ cho contract hiện tại. Chỉ thêm backup/undo nếu sản phẩm yêu cầu khôi phục nguồn.

## 18. Đánh giá Markdown → EPUB 3

### Luồng hiện tại

```text
filenames (.md)
  → convert_markdown_file()
  → HTML tạm cạnh file nguồn
  → create_project_epub()
  → EPUB tại project/output/{slug}.epub
  → finally xóa HTML tạm
```

### Vấn đề

1. **Markdown engine không đầy đủ:** route dùng `convert_markdown_file()` với custom regex engine; các lỗi đã xác nhận ở phần 10 (table, footnote, nested list, underline, image title, strikethrough) đi thẳng vào EPUB.
2. **Có hai lớp XHTML khác nhau:** custom engine sinh XHTML; `create_project_epub()` lại parse bằng BeautifulSoup `html.parser`, render lại node và thay đổi cấu trúc/attribute. Không có round-trip assertion.
3. **Không có manifest cho ảnh nội dung:** `create_project_epub()` chỉ copy cover từ `project/assets`; ảnh trong chương được giữ nguyên `src` nhưng không được resolve/copy vào `images/` và không được thêm vào OPF manifest. EPUB có thể chứa link ảnh hỏng.
4. **Relative URL bị đổi base:** chapter được đặt vào `text/...`; `src`/`href` tương đối theo file Markdown/HTML nguồn có thể không còn đúng sau khi đóng gói. Chưa có rewrite policy cho ảnh, link nội bộ và fragment.
5. **Footnote/note không được tạo semantic EPUB:** custom Markdown không parse footnote; route không có bước tạo `noteref`, `footnote`, backlink hoặc ID scope.
6. **Output EPUB không atomic:** `zipfile.ZipFile(output_path, "w")` ghi trực tiếp vào `{slug}.epub`. Lỗi giữa chừng có thể để lại file EPUB hỏng hoặc thay thế bản cũ bằng artifact dở dang.
7. **Partial input chưa có contract:** route bỏ qua MD lỗi trong vòng lặp; nếu còn một file hợp lệ, vẫn build và báo `done`. `create_project_epub()` cũng có `skipped_files`, nhưng route chưa chuyển nó thành trạng thái `partial`.
8. **Kiểm tra EPUB còn mỏng:** test hiện có chỉ kiểm tra tên file, metadata cơ bản, cover và hai chapter; chưa kiểm tra XML validity, OPF references, image chapter, link, footnote, mimetype compression, spine/nav hoặc mở được bằng reader.
9. **Xóa HTML tạm cần ownership rõ:** `finally` dọn các HTML được tạo trong lần chạy, đây là đúng hướng; nhưng model không được thay bằng `rmtree` thư mục nguồn hoặc xóa file có trước khi job bắt đầu.

### Mức độ

- P0 nếu output EPUB được phân phối như sách thật: ảnh nội dung có thể hỏng và output hỏng có thể được báo thành công.
- P1 cho metadata/partial status/atomic replace.
- P2 cho tối ưu CSS/reader compatibility sau khi semantic và asset contract đã pass.

## 19. Đánh giá HTML → EPUB 3

### Luồng hiện tại

```text
filenames (.html/.htm/.xhtml)
  → _safe_project_file()
  → create_project_epub()
  → _build_xhtml_document()
  → BeautifulSoup + _render_node()
  → text/{relative}.xhtml + OPF/nav/titlepage
  → output/{slug}.epub
```

### Vấn đề

1. **Ảnh nội dung không được đóng gói:** `_render_node()` giữ nguyên mọi `src`; chỉ cover được copy. Đây là lỗi chức năng trực tiếp với sách có illustration.
2. **Link nội bộ chưa được rewrite:** href tương đối vẫn dựa trên vị trí nguồn, trong khi chapter đổi sang `build_dir/text`; link sang chapter/asset dễ hỏng.
3. **Không có allowlist HTML/attribute:** `_render_node()` render gần như toàn bộ tag/attribute còn lại. Script/style được bỏ, nhưng các tag/attribute không cần thiết hoặc namespace lạ vẫn có thể làm XHTML không portable.
4. **Không parse/validate như XML:** BeautifulSoup dùng `html.parser`, phù hợp HTML lỗi nhẹ nhưng không chứng minh XHTML đầu ra hợp lệ. Cần XML parse/EPUB validation sau render.
5. **Input ngoài project chỉ an toàn nhờ caller:** `create_project_epub()` tự tính `relative_to(project_dir)` nhưng không tự chốt ownership/path policy; service trực tiếp cần reject source ngoài project/section, không dựa riêng vào route.
6. **Unsupported format bị skip:** service có `skipped_files`; nếu còn file hợp lệ thì vẫn tạo EPUB. Cần trả `partial` rõ ràng hoặc fail-fast theo policy đã chốt.
7. **Metadata và chapter contract cần test:** title lấy từ `<title>`, rồi `<h1>/<h2>`, rồi filename; cần xác nhận đây là hành vi mong muốn và không tạo title trùng/blank.

## 20. Kế hoạch xử lý tối giản theo Ponytail

Không tạo thêm pipeline thứ ba, không thêm abstraction/factory/backup system khi chưa cần. Thứ tự tối thiểu:

1. Giữ `create_project_epub()` làm owner của đóng gói EPUB 3.
2. Dùng **một Markdown renderer canonical** cho UI MD → HTML và MD → EPUB; tái sử dụng output/XHTML contract.
3. Thêm đúng một bước asset resolver trong owner EPUB: resolve ảnh nội bộ, copy vào `images/`, tạo manifest item, rewrite `src`; không quét toàn project.
4. Thêm một bước link resolver nhỏ: giữ external URL, rewrite link nội bộ theo map chapter/asset, giữ fragment.
5. Dùng temporary EPUB trong `output/` rồi `os.replace` sau khi zip và validation thành công.
6. Dùng một helper delete-source chung cho MD ↔ HTML; EPUB task luôn truyền/ép `False`.
7. Chỉ thêm semantic footnote renderer khi dialect/contract đã được chốt; không tự đoán từ các paragraph có số.
8. Thêm test contract nhỏ nhưng đủ: filesystem deletion, one Markdown EPUB with image/link/footnote, one HTML EPUB with image/internal link, invalid/partial/atomic failure.

Các simplification có chủ ý cần ghi chú trong code nếu áp dụng:

- `ponytail:` chỉ hỗ trợ asset path tương đối trong cùng project/section; mở rộng URL resolver khi có yêu cầu remote asset.
- `ponytail:` fail-fast khi một asset nội bộ thiếu; không phát EPUB “gần đúng” có link hỏng.
- `ponytail:` không xóa nguồn trong EPUB workflow; thêm tùy chọn riêng chỉ khi có transaction/restore contract.

## 21. Chỉ dẫn triển khai chi tiết cho model khác

### Bước 1 — Chuẩn bị

1. Đọc `ARCHITECTURE.md`, `docs/wip/del_SKILL.md` và toàn bộ phần 16–24 của kế hoạch này.
2. Chạy `git status --short`; bảo toàn mọi thay đổi không thuộc task.
3. Chạy GitNexus context/impact trước khi sửa các symbol sau: `convert_markdown_file`, `convert_html_file`, `_do_delete`, `create_project_epub`, `_build_xhtml_document`, `_render_node`, `run_epub_converter`, `process_book_directory` nếu chạm legacy path.
4. Nếu impact trả HIGH/CRITICAL, dừng và báo blast radius; không tự ý tiếp tục.
5. Không sửa legacy `text_to_epub` trừ khi test chứng minh task đang dùng nó hoặc người dùng mở rộng phạm vi.

### Bước 2 — Sửa delete-source trước

1. Tách conversion thành: đọc → render → validate → ghi output tạm → commit output → tùy chọn xóa input.
2. Reject nếu output resolve bằng input resolve; tuyệt đối không ghi đè nguồn.
3. Kiểm tra input/output nằm trong project/section theo boundary của route/service.
4. Chỉ xóa sau khi output tồn tại, đọc được, đúng format và conversion hoàn tất.
5. Với batch, thu thập `succeeded`, `failed`, `deleted`, `not_deleted`; status là `done` chỉ khi tất cả hợp lệ, `partial` khi có cả success/failure, `error` khi không có output.
6. Khi delete lỗi, không rollback output đã thành công; báo rõ `output_created=true, source_deleted=false`.
7. Test delete off/on, output collision, conversion exception, write permission, unlink permission, missing input, symlink và batch partial.

### Bước 3 — Chuẩn hóa Markdown → HTML/EPUB

1. Chọn renderer canonical; ưu tiên parser dependency hiện có thay vì mở rộng `_md_inline`/`_md_block_to_xhtml` bằng regex.
2. Bật/chốt extension cho tables, strikethrough, footnotes và attributes nếu sản phẩm cần; pin dependency.
3. Cả `convert_markdown_file()` và MD → EPUB phải gọi cùng renderer/options.
4. Renderer phải trả body XHTML cùng asset references/footnote references, không chỉ string không metadata.
5. Validate XHTML trước khi chuyển sang bước đóng gói.
6. Test parity: cùng input, body của MD → HTML và chapter trong MD → EPUB phải tương đương về heading/style/list/table/link/image/footnote.

### Bước 4 — Hoàn thiện HTML → EPUB

1. Validate mỗi source là file trong đúng project/section và suffix được hỗ trợ.
2. Parse HTML, bỏ script/style theo policy, render allowlist tag/attribute cần cho ebook.
3. Với mỗi `img`, resolve từ thư mục source; reject path traversal/missing file; copy vào `build_dir/images` với tên collision-safe; thêm manifest item; rewrite href tương đối từ chapter.
4. Với mỗi link nội bộ, map source path → chapter output path; giữ `#fragment`; external URL giữ nguyên theo policy.
5. Preserve semantic tags cần thiết: headings, paragraphs, strong/em, del/u/mark, lists, blockquote, pre/code, table, figure/figcaption, sup/sub và footnote markup nếu input đã có.
6. Escape metadata/attributes và parse lại từng XHTML bằng XML parser.

### Bước 5 — Đóng gói EPUB 3 an toàn

1. Tạo build tree trong `TemporaryDirectory` dưới `output/`.
2. Manifest phải chứa nav, CSS, titlepage, chapters, cover và mọi asset được tham chiếu.
3. Spine chỉ chứa content document theo EPUB contract; nav phải có `properties="nav"` và được kiểm tra theo validator.
4. Tạo `content.opf`, nav và titlepage sau khi có đủ chapter/assets.
5. Zip vào file tạm cùng thư mục output; đảm bảo `mimetype` là entry đầu tiên, uncompressed, đúng bytes.
6. Đọc lại ZIP, kiểm tra mọi href trong manifest tồn tại, XML parse được, không duplicate ID, không có path traversal.
7. Chỉ `os.replace(temp_epub, final_epub)` sau validation; lỗi không được để lại bản EPUB nửa chừng.
8. Route chỉ báo `done` sau khi service trả result hợp lệ; hiển thị `included_files`, `skipped_files`, `failed_files`.

### Bước 6 — Dọn HTML tạm MD → EPUB

1. Ghi snapshot chính xác các HTML path do job này tạo.
2. `finally` chỉ xóa các path snapshot đó, không xóa mọi file `.html` hoặc cả thư mục nguồn.
3. Nếu conversion một file lỗi, file HTML của file lỗi không được đưa vào source_paths; cleanup vẫn phải chạy.
4. Nếu EPUB build lỗi, cleanup HTML tạm vẫn chạy nhưng MD nguồn không được xóa.
5. Test exception ở conversion, exception ở asset copy, exception ở zip và cleanup permission error.

### Bước 7 — Nghiệm thu

1. Unit: delete helper, Markdown renderer, asset resolver, link resolver, XHTML/OPF validation.
2. Service: `create_project_epub()` cho HTML có ảnh/link/table/footnote và MD đã render canonical.
3. Route: task đúng, checkbox đúng, partial status, download path đúng.
4. ZIP inspection: mimetype, container, OPF, nav, spine, chapter, CSS, cover, inline image, all asset manifest refs.
5. Mở EPUB bằng ít nhất một reader hoặc validator có sẵn; ghi rõ nếu chưa có `epubcheck`.
6. Chạy `git diff --check`.
7. Trước commit chạy `gitnexus_detect_changes()`; chỉ commit nếu scope đúng các symbol/flow dự kiến.

## 22. Ma trận nghiệm thu bắt buộc

| Case | Kết quả bắt buộc |
|---|---|
| MD → HTML, delete off | Output đúng; MD còn nguyên |
| MD → HTML, delete on | Output hợp lệ trước; MD bị xóa sau commit output |
| HTML → MD, delete on | MD hợp lệ trước; HTML bị xóa sau commit output |
| Output path = input path | Reject; input không bị ghi đè |
| Conversion/parser lỗi | Không xóa nguồn; không báo done |
| Delete permission lỗi | Output giữ lại; báo source chưa xóa |
| MD → EPUB, delete checkbox on | MD không bị xóa; HTML tạm được dọn |
| HTML → EPUB, delete checkbox on | HTML không bị xóa |
| MD có ảnh nội bộ | Ảnh có trong ZIP, manifest và href đúng |
| HTML có ảnh nội bộ | Ảnh có trong ZIP, manifest và href đúng |
| Link chapter nội bộ | Mở được sau khi chapter đổi thư mục |
| External link/fragment | Giữ URL/fragment theo policy |
| Footnote/note | Semantic + backlink đúng, hoặc fail rõ nếu unsupported |
| Một file lỗi trong batch | Status partial; file thành công và thất bại được liệt kê |
| Zip/validation lỗi | Không thay bản EPUB cũ bằng file hỏng |
| Rerun cùng input | Không tích lũy temp/asset rác; output deterministic theo policy |

## 23. Blast radius dự kiến khi triển khai

Theo GitNexus context:

- `convert_markdown_file` có caller từ `Plugin._markdown_to_html` và route worker.
- `create_project_epub` có caller từ route worker và test service; ảnh hưởng trực tiếp vùng `Epub_converter` và route.
- `_build_xhtml_document` và `_render_node` nằm trong chuỗi `create_project_epub`; thay đổi semantics có thể ảnh hưởng toàn bộ HTML → EPUB.
- `run_epub_converter` bao phủ cả bốn task converter; thay đổi trạng thái/delete/partial cần test cả MD↔HTML và hai EPUB task.

Không được coi impact LOW là bằng chứng an toàn cho file deletion hoặc EPUB data loss; phải có test filesystem/ZIP và validation thực tế.

## 24. Trạng thái rà soát bổ sung

- GitNexus index đã được cập nhật trong phiên rà soát bằng `npx gitnexus analyze`; trước khi implementation, model phải kiểm tra lại staleness.
- GitNexus query trong phiên có cảnh báo FTS thiếu, nên phần kết luận dựa trên context chính xác và đọc source trực tiếp, không dựa vào ranking query; nếu query tiếp tục cảnh báo thì chạy `npx gitnexus analyze --repair-fts`.
- Test hiện có cho `create_project_epub()` mới kiểm tra package cơ bản, cover, metadata và chapter; chưa kiểm tra asset nội dung, link, footnote, atomic failure hoặc partial.
- Self-check Markdown → XHTML hiện pass nhưng không bao phủ các case đã nêu.
- Phần này chỉ cập nhật kế hoạch; chưa sửa mã nguồn và không xóa dữ liệu nào.
