# Kế hoạch dịch EPUB/HTML giữ nguyên vị trí ảnh theo kiến trúc plugin

Ngày: 2026-05-07

## 1. Mục tiêu

Xây dựng một luồng xử lý có thể:

- Dịch một file `.epub` gồm một hoặc nhiều file HTML/XHTML.
- Dịch trực tiếp một file `.html` hoặc một thư mục HTML.
- Giữ nguyên vị trí hình ảnh, cấu trúc chương, thứ tự spine, metadata, và khả năng đóng gói lại EPUB.
- Ưu tiên phát triển thành các plugin/stage tách biệt để dễ bảo trì và mở rộng.
- Cho phép kết nối plugin OCR và plugin EPUB hiện có như các công đoạn tùy chọn, không bắt buộc.

## 2. Kết quả rà soát codebase bằng GitNexus

### 2.1. Chức năng hiện có

- `plugins/epub_converter/epub_to_text/epub2text.py:convert_epub`
  - Dùng để đọc EPUB, tìm OPF, lấy spine, trích metadata, rồi chuyển HTML sang `txt` hoặc `md` qua `html2text`.
  - Direct callers theo GitNexus:
    - `webui/routes/plugins.py:_run`
    - `plugins/epub_converter/plugin.py:Plugin._epub_to_text`
    - `plugins/epub_converter/epub_to_text/epub2text.py:main`
- `plugins/epub_converter/text_to_epub/main.py:process_book_directory`
  - Dùng để đọc `chunk_*.txt|md` + `assets/metadata.xml`, sinh XHTML rồi đóng gói EPUB.
  - Direct callers theo GitNexus:
    - `webui/routes/plugins.py:_run`
    - `plugins/epub_converter/plugin.py:Plugin._text_to_epub`
    - CLI nội bộ của chính module
- `plugins/ocr/ocr_engine.py:ocr_file`
  - Dùng để OCR PDF/ảnh, có cleanup và spell-check tùy chọn.
  - Direct callers theo GitNexus:
    - `webui/routes/plugins.py:_run`
    - `plugins/ocr/plugin.py:Plugin.convert`
- `core/executor.py:TranslationExecutor`
  - Là lõi dịch hiện tại cho CLI/WebUI.
  - Incoming callers theo GitNexus:
    - `main.py:main`
    - `webui/routes/translation.py:translate_worker`
    - `webui/routes/projects.py:_project_translate_worker`

### 2.2. Blast radius của các symbol chính

- `TranslationExecutor`
  - `gitnexus impact --repo Novel-Translator TranslationExecutor`
  - Risk: `MEDIUM`
  - Direct dependents: `main.py`, `webui/routes/translation.py`, `webui/routes/projects.py`
  - Kết luận: không nên nhúng logic EPUB/HTML phức tạp trực tiếp vào đây.
- `process_book_directory`
  - `gitnexus impact --repo Novel-Translator process_book_directory`
  - Risk: `LOW`
  - Direct dependents: route plugin EPUB và `plugins/epub_converter/plugin.py`
  - Kết luận: có thể mở rộng hoặc song song hóa bằng module mới mà rủi ro thấp.
- `ocr_file`
  - `gitnexus impact --repo Novel-Translator ocr_file`
  - Risk: `LOW`
  - Direct dependents: route plugin OCR và `plugins/ocr/plugin.py`
  - Kết luận: phù hợp làm optional stage.

### 2.3. Nhận xét kiến trúc hiện tại

- Tài liệu cũ vẫn nhắc `PluginManager/ServiceBus/EventBus`, nhưng `CHANGELOG` cho biết lõi dịch đã được hợp nhất qua `TranslationExecutor`.
- WebUI hiện gọi plugin EPUB/OCR trực tiếp trong `webui/routes/plugins.py`, tức là kiến trúc plugin đang thiên về "module độc lập được gọi trực tiếp", chưa phải một pipeline chuẩn hóa nhiều stage.
- Điều này phù hợp để phát triển tiếp theo hướng:
  - giữ `TranslationExecutor` làm lõi dịch text,
  - thêm một orchestration layer riêng cho book/html pipeline,
  - không hồi sinh lại toàn bộ hạ tầng plugin cũ.

## 3. Hạn chế của luồng EPUB hiện tại

### 3.1. Ở chiều EPUB -> text/markdown

`convert_epub()` hiện:

- lấy danh sách file HTML/XHTML theo spine,
- chuyển mỗi file HTML sang Markdown/TXT bằng `html2text`,
- trích `metadata.xml`,
- không duy trì một manifest chuẩn cho ảnh nội dung,
- không copy toàn bộ ảnh nội dung sang một workspace có mapping ổn định.

### 3.2. Ở chiều text/markdown -> EPUB

`process_book_directory()` + `create_epub()` hiện:

- mong chờ đầu vào là `chunk_*.txt` hoặc `chunk_*.md`,
- dùng `assets/metadata.xml`, `assets/styles.css`, `assets/cover.jpg`, `assets/Fonts`,
- chỉ đóng gói chắc chắn `cover.jpg`, stylesheet và fonts,
- chưa có luồng chuẩn để giữ nguyên các ảnh nằm trong thân chương ở đúng vị trí cũ.

### 3.3. Kết luận kỹ thuật

Nếu mục tiêu là "dịch rồi đóng gói lại EPUB mà vẫn giữ nguyên vị trí ảnh", thì **Markdown thuần không nên là canonical representation**.

## 4. Có nên chuyển sang thuần Markdown để gửi đi dịch không?

### 4.1. Câu trả lời ngắn

Không nên dùng Markdown thuần làm định dạng nguồn chính nếu cần:

- giữ vị trí ảnh,
- giữ anchor/link nội bộ,
- giữ cấu trúc HTML phức tạp,
- giữ semantic inline formatting,
- repack EPUB với độ trung thực cao.

### 4.2. Vì sao không nên

Markdown thuần làm mất hoặc làm yếu:

- cấu trúc DOM chi tiết,
- thuộc tính của thẻ,
- đường dẫn tài nguyên tương đối,
- vị trí chính xác của ảnh trong cây HTML,
- chú thích hoặc wrapper HTML tùy biến.

Khi đó bước dựng ngược `Markdown -> XHTML -> EPUB` sẽ chỉ là tái tạo gần đúng, không còn là round-trip đáng tin cậy.

### 4.3. Phương án khuyến nghị

Dùng mô hình **dual representation**:

- `Canonical`: bundle HTML/XHTML chuẩn hóa + manifest + assets
- `Derived`: text/markdown view để phục vụ chunking hoặc biên tập khi cần

Nói cách khác:

- dịch trên các text segment được trích ra từ DOM,
- nhưng nguồn chân lý vẫn là cây HTML/XHTML và manifest tài nguyên.

## 5. Thuật toán đề xuất

## 5.1. Intermediate Representation

Tạo một định dạng trung gian gọi tắt là `BookBundle`:

```text
job/
  manifest.json
  metadata.xml
  source/
    chapters/
      0001.xhtml
      0002.xhtml
    assets/
      images/
      fonts/
      styles/
  working/
    normalized/
    segments.jsonl
    translated_segments.jsonl
    rebuilt/
  output/
    translated.epub
    translated_html/
```

`manifest.json` nên chứa:

- loại input: `epub`, `html`, `html_dir`
- spine/order
- mapping chapter id -> file path
- mapping asset id -> original path -> normalized path
- metadata sách
- các rule đóng gói lại

## 5.2. Bước 1: Ingest

### Input EPUB

1. Giải nén EPUB vào workspace job.
2. Tìm `container.xml`, `content.opf`, manifest, spine.
3. Copy toàn bộ XHTML/HTML thuộc spine.
4. Copy toàn bộ asset liên quan:
   - ảnh nội dung,
   - cover,
   - CSS,
   - font,
   - file tham chiếu khác.
5. Rewrite đường dẫn về dạng chuẩn nội bộ nếu cần.

### Input HTML

1. Nếu là một file HTML:
   - tạo `manifest.json` với một chapter duy nhất.
2. Nếu là thư mục HTML:
   - xác định thứ tự file theo rule cấu hình hoặc theo tên.
3. Copy asset kèm theo vào bundle.

## 5.3. Bước 2: Normalize DOM

Với mỗi chapter HTML/XHTML:

1. Parse DOM bằng parser HTML/XHTML ổn định.
2. Chuẩn hóa encoding, namespace, line ending.
3. Gắn `data-segment-id` cho các node có text cần dịch.
4. Giữ nguyên các node không dịch:
   - `img`
   - `svg`
   - `code`
   - `pre`
   - footnote/backlink
   - anchor id/name
5. Chuẩn hóa `src` ảnh về asset id ổn định để không mất vị trí khi rebuild.

## 5.4. Bước 3: Trích segment để dịch

Thay vì chuyển cả file sang Markdown, chỉ trích text từ các node dịch được:

- heading
- paragraph
- list item
- table cell nếu được bật
- figcaption/caption nếu có

Mỗi segment nên mang metadata:

- `segment_id`
- `chapter_id`
- `xpath` hoặc DOM path
- text gốc
- ngữ cảnh trước/sau
- flags: `is_title`, `is_caption`, `preserve_whitespace`, `allow_ocr_enrichment`

## 5.5. Bước 4: Gom segment thành chunk gửi dịch

Tạo `TranslationChunk` thay vì gửi nguyên file:

1. Gom các segment liên tiếp cùng chapter.
2. Chặn vượt ngưỡng ký tự tương tự `TranslationExecutor`.
3. Chèn delimiter rõ ràng giữa các segment.
4. Giữ mapping chunk -> segment list.

Ví dụ:

```text
[[SEGMENT:ch01.s001]]
...
[[/SEGMENT]]

[[SEGMENT:ch01.s002]]
...
[[/SEGMENT]]
```

Sau khi nhận kết quả, tách lại theo delimiter để gán ngược vào từng segment.

## 5.6. Bước 5: OCR stage tùy chọn

OCR không phải bắt buộc cho mọi EPUB/HTML. Chỉ bật khi:

- chapter thực chất là ảnh scan,
- có ảnh chứa text cần dịch,
- có vùng text thay thế (`alt`, chú thích ảnh) cần làm giàu dữ liệu.

Luồng OCR đề xuất:

1. Dò các chapter có text quá ít nhưng nhiều ảnh.
2. Dò ảnh lớn nghi là page scan.
3. Nếu plugin OCR có sẵn:
   - OCR ảnh hoặc PDF trung gian,
   - sinh segment bổ sung hoặc gợi ý thay thế.
4. Nếu plugin OCR không có:
   - bỏ qua stage,
   - pipeline vẫn tiếp tục bình thường.

## 5.7. Bước 6: Dịch

Tận dụng `TranslationExecutor` hoặc một adapter quanh `robust_translate()`:

- chunk text theo giới hạn hiện tại,
- dùng cache/checkpoint hiện có,
- hỗ trợ resume,
- hỗ trợ glossary/prompt hiện hữu.

Khuyến nghị:

- không sửa mạnh `TranslationExecutor`,
- tạo `BookTranslationAdapter` để bọc các `TranslationChunk` thành text gửi đi,
- sau đó map ngược về `segment_id`.

## 5.8. Bước 7: Rehydrate DOM

1. Mở DOM chapter đã normalize.
2. Với mỗi `data-segment-id`, thay text gốc bằng text dịch.
3. Giữ nguyên:
   - `img src`
   - thứ tự node
   - wrapper HTML
   - anchor/id/class quan trọng
4. Chạy post-process:
   - escape hợp lệ,
   - giữ whitespace cần thiết,
   - validate XHTML nếu đích là EPUB.

## 5.9. Bước 8: Xuất bản

### Output HTML

- ghi ra `output/translated_html/`
- giữ nguyên cấu trúc thư mục và tài nguyên

### Output EPUB

- build OPF/manifest/spine từ `BookBundle`
- copy lại toàn bộ assets đã chuẩn hóa
- đóng gói EPUB

Lưu ý:

- nếu muốn round-trip trung thực cao, cần một EPUB packager mới dựa trên manifest thật của bundle,
- không nên phụ thuộc hoàn toàn vào `text_to_epub` hiện tại vì module đó đang tối ưu cho `chunk_*.txt|md`.

## 6. Thiết kế plugin/stage đề xuất

## 6.1. Mục tiêu kiến trúc

- Mỗi công đoạn là một plugin/stage độc lập.
- Có thể chạy cả pipeline hoặc từng phần riêng lẻ.
- Plugin nào thiếu thì stage đó bị skip hoặc thay bằng fallback, không làm hỏng toàn hệ thống.

## 6.2. Stage đề xuất

### A. `book_ingest`

Trách nhiệm:

- nhận `epub/html/html_dir`
- tạo `BookBundle`
- extract metadata, chapters, assets, spine

Output:

- `manifest.json`
- `source/chapters/*`
- `source/assets/*`

### B. `dom_segmenter`

Trách nhiệm:

- parse DOM
- đánh dấu node cần dịch
- sinh `segments.jsonl`

### C. `ocr_enricher` (optional)

Trách nhiệm:

- dùng plugin OCR hiện có để OCR các asset/chapter cần thiết
- bổ sung segment hoặc text hint

Fallback:

- nếu không có OCR plugin, đánh dấu `SKIPPED`

### D. `translation_adapter`

Trách nhiệm:

- gom segment thành chunk
- gọi lõi dịch hiện có
- map kết quả về `translated_segments.jsonl`

### E. `dom_rebuilder`

Trách nhiệm:

- ghép text dịch trở lại DOM
- tạo chapter HTML/XHTML đã dịch

### F. `epub_packager` (optional nếu input là EPUB hoặc người dùng muốn EPUB)

Trách nhiệm:

- build lại EPUB từ bundle đã dịch

Fallback:

- nếu packager không có, vẫn trả ra thư mục HTML đã dịch

## 6.3. Cơ chế kết nối stage

Thay vì hồi sinh `PluginManager` cũ, đề xuất một `PipelineRegistry` nhẹ:

- mỗi stage khai báo:
  - `name`
  - `capabilities`
  - `requires`
  - `optional`
  - `run(context) -> context`
- orchestration layer sẽ:
  - nạp stage nếu import được,
  - skip stage optional nếu không có,
  - fail sớm nếu stage bắt buộc bị thiếu.

Ví dụ thứ tự:

1. `book_ingest`
2. `dom_segmenter`
3. `ocr_enricher` optional
4. `translation_adapter`
5. `dom_rebuilder`
6. `epub_packager` optional

## 6.4. Kết nối với plugin hiện có

### Plugin EPUB hiện có

Nên tái sử dụng:

- logic đọc OPF/spine/metadata từ `epub2text.py`
- một phần logic đóng gói từ `epub_creator.py`

Không nên dùng nguyên xi cho fidelity mode:

- `epub2text.py` hiện chuyển HTML -> Markdown/TXT quá sớm
- `text_to_epub` hiện giả định input là `chunk_*.txt|md`

### Plugin OCR hiện có

Nên tái sử dụng trực tiếp như stage optional:

- `ocr_file`
- các cấu hình cleanup/spell-check nếu người dùng bật

### Translation core hiện có

Nên giữ nguyên:

- `TranslationExecutor`
- `robust_translate`
- cache/checkpoint/glossary

Chỉ cần adapter mới để dịch theo `segment/chunk mapping`.

## 7. Quyết định kiến trúc khuyến nghị

## 7.1. Khuyến nghị chính

Phát triển một pipeline mới theo hướng:

- **HTML-preserving translation**
- **asset-aware repackaging**
- **optional OCR enrichment**
- **plugin stage orchestration**

Thay vì:

- ép toàn bộ EPUB sang Markdown thuần,
- dịch Markdown,
- rồi cố dựng lại EPUB từ đầu.

## 7.2. Quyết định về Markdown

Markdown chỉ nên dùng cho:

- preview/edit phụ,
- export trung gian cho người dùng muốn biên tập tay,
- fallback mode khi không cần giữ ảnh/cấu trúc cao.

Markdown không nên là source of truth cho pipeline EPUB fidelity.

## 8. Kế hoạch triển khai theo phase

## Phase 1: Bundle + HTML fidelity foundation

Mục tiêu:

- ingest EPUB/HTML vào `BookBundle`
- extract assets đầy đủ
- normalize HTML/XHTML
- segment text trong DOM

Deliverables:

- module `book_ingest`
- module `dom_segmenter`
- `manifest.json` schema

## Phase 2: Translation adapter

Mục tiêu:

- nối `BookBundle` với `TranslationExecutor`
- hỗ trợ checkpoint/cache cho segment chunks

Deliverables:

- `translation_adapter`
- `segments.jsonl` / `translated_segments.jsonl`

## Phase 3: Rebuild + output

Mục tiêu:

- rebuild HTML đã dịch
- pack lại EPUB từ bundle

Deliverables:

- `dom_rebuilder`
- `epub_packager`
- validation round-trip cơ bản

## Phase 4: OCR enrichment + fallback policies

Mục tiêu:

- dùng plugin OCR như stage tùy chọn
- auto-detect khi nào nên OCR
- graceful skip nếu plugin OCR không có

Deliverables:

- `ocr_enricher`
- pipeline policy `required/optional/skipped`

## 9. Rủi ro và lưu ý

- GitNexus index hiện stale so với commit hiện tại, nên mọi kết luận đã được đối chiếu lại bằng source code thực tế.
- `TranslationExecutor` có blast radius `MEDIUM`, nên tránh nhúng logic book pipeline trực tiếp vào class này.
- `process_book_directory` và `ocr_file` có blast radius `LOW`, phù hợp để tái sử dụng theo kiểu adapter/stage.
- Dự án hiện có một số tài liệu cũ chưa khớp hoàn toàn với source; khi triển khai cần bám source trước, docs sau.

## 10. Kết luận

Phương án phù hợp nhất cho dự án này là:

1. Không dùng Markdown thuần làm lõi cho EPUB/HTML fidelity mode.
2. Dùng một `BookBundle` dựa trên HTML/XHTML + manifest + assets làm canonical representation.
3. Tái sử dụng plugin OCR và EPUB hiện có theo mô hình stage/adapters.
4. Giữ cho OCR và EPUB packager là các công đoạn tùy chọn, để thiếu plugin vẫn không làm vỡ pipeline chính.
5. Giữ `TranslationExecutor` làm lõi dịch text, nhưng bọc bằng adapter riêng cho segment-based translation.

## 11. Đề xuất file/module khi bắt đầu hiện thực

Nếu triển khai, nên thêm theo hướng sau:

- `plugins/book_pipeline/ingest.py`
- `plugins/book_pipeline/segmenter.py`
- `plugins/book_pipeline/translation_adapter.py`
- `plugins/book_pipeline/rebuilder.py`
- `plugins/book_pipeline/packager.py`
- `plugins/book_pipeline/pipeline.py`
- `plugins/book_pipeline/models.py`

Plugin OCR và EPUB hiện có sẽ được gọi thông qua adapter, không cần ép sửa sâu ngay từ đầu.
