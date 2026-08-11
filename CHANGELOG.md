# Changelog - Lịch sử thay đổi

Tất cả các thay đổi quan trọng của dự án Content Translator sẽ được ghi nhận tại đây.

## [8.23.0] - 2026-08-11
### Khôi phục Tác vụ Nền SQLite TaskStore, Tự động Khôi phục Checkpoint & Vá lỗi UI Modal Progress

**Kiên cố hóa Trạng thái Tác vụ Nền qua SQLite TaskStore (`services/task_store.py`, `backend/infrastructure/progress/task_registry.py`):**
- **Lưu trữ Tác vụ Nền xuống Đĩa (`workspace/tasks.db`)**: Nâng cấp `TaskRegistry` từ bộ nhớ tạm RAM thành SQLite-backed store (`TaskStore`), tự động lưu lại thông tin tác vụ, lịch sử event SSE, tiến trình chunk và trạng thái lifecycle.
- **Tự động Quét & Khôi phục Tác vụ khi Server Restart (`scan_and_recover`)**: Tự động phát hiện các checkpoint SQLite và task chưa hoàn tất khi máy khởi động lại hoặc sau khi OS sleep/crash; tự động khôi phục tác vụ về trạng thái `resumable` hoặc `paused`.
- **Identity & Project Mapping**: Lưu `project_slug` trực tiếp vào checkpoint identity để tự động liên kết checkpoint về đúng dự án gốc khi thực hiện quét hệ thống.

**Vá lỗi UI Tiến trình & Khắc phục Crash Server (`webui/static/js/translation-worker.js`, `webui/__init__.py`):**
- **Sửa lỗi Temporal Dead Zone (TDZ)**: Sửa lỗi `ReferenceError: Cannot access 'btnResume' before initialization` trong `translation-worker.js` giúp modal tiến trình hiển thị chính xác khi người dùng bấm Dịch hoặc bấm xem chi tiết tác vụ.
- **Sửa lỗi Import & Stream Event SSE**: Bổ sung `jsonify` bị thiếu trong `webui/__init__.py`, bổ sung import `TranslateProjectFilesUseCase` cho worker, và cập nhật kết thúc stream SSE cho các trạng thái kết thúc/tạm dừng (`resumable`, `paused`).

**Bộ Kiểm thử Unit Test (`tests/unit/test_task_store.py`, `tests/unit/test_task_registry_persistence.py`):**
- **Bổ sung Suite Kiểm thử SQLite TaskStore & Persistence**: Đảm bảo 100% độ tin cậy cho luồng tạo tác vụ, ghi nhận sự kiện, lọc trạng thái và tự động quét khôi phục checkpoint mồ côi.

---

## [8.20.0] - 2026-08-02
### Chuẩn hóa Portable Markdown Regex, API Replace Preview & Nút Chạy thử Bảo vệ Thao tác

**Chuẩn hóa Engine Portable Markdown Regex v1:**
- **Định nghĩa ECMAScript/Python Portable Regex Profile**:
  - Chuẩn hóa bộ cú pháp regex thống nhất giữa JavaScript (`RegExp`) ở frontend và Python (`re`) ở backend trong `webui/routes/projects.py`.
  - Tự động chuẩn hóa ký tự xuống dòng từ Windows CRLF (`\r\n`) về LF (`\n`) trước khi thực hiện khớp pattern.
  - Tích hợp `_portable_replacement_adapter()` chuyển đổi tự động cú pháp back-reference từ `$1`, `$2` ở UI sang `\g<1>`, `\g<2>` cho Python `re.sub()`.
  - Đếm chính xác số lượt xuất hiện match với `finditer()` ngay cả khi pattern chứa capture groups.

**API Dry-Run Preview & Bảo vệ Thao tác Thay tất cả:**
- **Endpoint `/api/projects/<slug>/replace-preview`**:
  - Bổ sung API preview hỗ trợ quét và đếm kết quả thay thế trên toàn bộ dự án mà không thực hiện ghi file (`scanned_files`, `matched_files`, `total_occurrences`).
- **Nút "Chạy thử" & UI Guard Modal (`tab_projects.html`, `footer.html`)**:
  - Thêm nút **Chạy thử** trực tiếp trên modal Tìm kiếm & Thay thế cho phạm vi "Tất cả tập tin".
  - Ép buộc người dùng thực hiện **Chạy thử** để xác nhận trước khi cho phép bấm **Thay tất cả** toàn dự án.
  - Tự động vô hiệu hóa trạng thái preview nếu người dùng thay đổi từ khóa, chế độ tìm kiếm, phạm vi áp dụng hoặc khi file đang mở bị chỉnh sửa.
  - Tự động kích hoạt lưu file (save active file) trước khi thực hiện preview.

**Tài liệu & Unit Tests:**
- **Hướng dẫn sử dụng Regex (`docs/MANUAL.md`)**: Bổ sung mục hướng dẫn cú pháp Regex chuẩn portable v1 và quy trình 3 bước Chạy thử an toàn cho người dùng.
- **Bộ Kiểm thử Unit Test (`tests/unit/test_batch_regex.py`)**: Thêm unit test kiểm tra toàn diện các hàm compile, adapter replacement, đếm capture groups, và zero-width match.

## [8.22.0] - 2026-08-08
### Di chuyển hoàn toàn Chia/Ghép tập tin vào Converter Tool, Hỗ trợ 7 Định dạng, BeautifulSoup Merge & Guard Frontend CRUD

**Converter Tool & Service Layer (`plugins/epub_converter/services/file_operations.py`, `webui/routes/plugins.py`):**
- **Di chuyển hoàn toàn Chia & Ghép tập tin**: Chuyển logic `split_files` và `merge_files` từ `projects.py` vào service `file_operations.py` thuộc plugin `epub_converter`.
- **Hỗ trợ 7 định dạng mở rộng**: Cho phép chia/ghép trên `.md`, `.txt`, `.html`, `.htm`, `.xhtml`, `.json`, `.csv`.
- **Ghép HTML nâng cao với BeautifulSoup**: Trích xuất nội dung `<body>` ghép vào file HTML gốc, bảo toàn Doctype, HTML, Head & Style wrapper (`_merge_html_bodies`).
- **Boundary Policy cho Chunker**: Bổ sung parameter `boundary_mode` (`document`, `line`, `legacy`) vào `process_text_for_chunking()`, bảo đảm phân chia theo chương/heading và đoạn văn hoàn chỉnh mà không cắt đứt markup HTML hay JSON/CSV record.
- **Chuẩn hóa Path Traversal Guard**: Cập nhật `_safe_project_file()` trả về `Path | None` độc lập với kiểm tra sự tồn tại của file.
- **Sửa lỗi scope Python `UnboundLocalError`**: Khắc phục triệt để lỗi `delete_source`, `section`, `filenames` do bị gán trùng lặp trong closure function `_run()`.

**Giao diện WebUI Tab Converter (`workspace_ebook_kit.html`, `converter-tool-plugin.js`):**
- **Tái cấu trúc 6 nút thao tác**: Dồn 4 nút sang trái, 2 nút EPUB 3 dồn sang phải có đường phân cách `|` phân biệt rõ nhóm chức năng.
- **Tự động cấu hình `max_chars`**: Tải giá trị mặc định từ `/api/config` qua `initDefaultChunkSize()`, ẩn các nút tăng/giảm spinner trên ô nhập tay `max_chars`.

**An toàn Frontend CRUD & Error Guarding (`webui/static/js/`, `webui/__init__.py`):**
- **Thêm Guard `if (!r.ok)`**: Bổ sung kiểm tra HTTP status trên 46 vị trí `fetch()` thuộc 8 module JavaScript chính (`api-client.js`, `editor-component.js`, `provider-manager.js`, `translation-worker.js`, `prompt-manager.js`, `converter-tool-plugin.js`, `project-manager.js`, `doc-manager.js`, `ui-helpers.js`).
- **Flask Error Handlers**: Bổ sung generic JSON handlers cho lỗi HTTP 404/405/500 trong backend Flask.

**Bộ Kiểm thử Unit Test (`tests/unit/test_file_operations.py`):**
- **Unit Test Suite mới**: Bổ sung test suite nghiệm thu toàn diện 7 định dạng suffix, BeautifulSoup HTML merge, safe atomic write và path traversal guard.

---

## [8.21.0] - 2026-08-05
### Tác vụ Tạo Thông tin AI bằng Task System, SSE Progress & Phân tích File Lớn Map-Reduce

**Backend - Tác vụ AI Thông tin dự án (`webui/routes/projects.py`):**
- **Task hóa endpoint `/api/projects/<slug>/summarize`**: Chuyển từ xử lý đồng bộ sang tạo `TaskRegistry` task + worker nền, trả `202 Accepted` + `job_id` ngay lập tức.
- **SSE Progress realtime**: Worker phát lifecycle events `started` → `loading_source` → `loading_prompt` → `planning` → `extracting` → `merging` → `synthesizing` → `validating` → `saving` → `complete`.
- **Hỗ trợ phân tích file lớn (map-reduce)**: Tự động chọn `single_request` cho file nhỏ, `map_reduce` cho file lớn dựa trên context budget; chia theo boundary `chapter/heading > paragraph > sentence`.
- **Retry tối thiểu**: Tối đa 2 retry cho timeout, rate-limit, connection error, empty response; không retry lỗi model/key/prompt.
- **Hủy an toàn**: Tái sử dụng `/api/tasks/<job_id>/cancel`; worker kiểm tra trạng thái trước mỗi phần và trước khi ghi asset.
- **Ghi file an toàn**: Áp dụng `_atomic_write_text` (`os.replace` từ tmp) cho asset output.
- **Đọc nguồn an toàn**: Thay `errors="ignore"` bằng xử lý tường minh `UnicodeDecodeError`; file lỗi encoding tạo task `failed` rõ ràng.

**Frontend - UI Tab Thông tin (`webui/static/js/prompt-manager.js`, `translation-worker.js`):**
- **SSE Progress cho AI Generate**: Cả `aiGenerateFromInfoTab()` và `aiGenerateContent()` nay kết nối SSE qua `TranslationWorker.connectToProgress()`, hiển thị phase/percent/log realtime.
- **Chống double-submit**: Thêm guard `_infoTabGenerating` / `_contentTabGenerating` chống bấm Generate nhiều lần cùng lúc.
- **Tải kết quả từ asset**: Sau khi complete, fetch `/api/projects/<slug>/file/assets/<file>` và cập nhật textarea + toast thông báo.

**Prompt mặc định cải tiến (`workspace/prompts/default/`):**
- Cập nhật 4 prompt: `summary_prompt.txt`, `relationship_prompt.txt`, `glossary_prompt.txt`, `style_guide_prompt.txt`.
- Thêm yêu cầu `PART_ID`, `evidence`, `coverage` toàn văn; loại bỏ yêu cầu "3-5 câu" cố định; bổ sung extraction/synthesis schema.

**Tài liệu:**
- Bổ sung mục kiến trúc task-based AI generation vào `docs/DEVELOPMENT.md`.

---

## [8.20.0] - 2026-08-02
### Tích hợp EndpointPolicy (Cloudflare/Vercel Gateway), Refactor Checkpoint & Bộ lọc Model Cloudflare

**Kiến trúc Provider & Endpoint Policy:**
- **Triển khai `EndpointPolicy` (`infrastructure/providers/endpoint_policy.py`)**: 
  - Phân tách logic xử lý URL, API Key, Validation Model và phân loại lỗi HTTP dựa trên loại Gateway (Cloudflare AI Gateway, Vercel AI Gateway) hoặc Direct (OpenAI/Google).
  - Cung cấp `classify_endpoint(base_url)` tự động nhận diện và gán policy phù hợp cho từng provider.
- **Tái cấu trúc API Consumers**:
  - Loại bỏ hoàn toàn việc load trực tiếp cấu hình qua `webui.helpers` (`load_api_keys`, `get_active_provider`).
  - Mọi luồng dịch thuật (`translate_text`, `translate_project_file`), soát lỗi (`spellcheck_project_file`), tóm tắt (`summarize_project`) và `/api/models` nay đều lấy cấu hình thống nhất qua `ProviderService` và `EndpointPolicy`.

**Giao diện & Bộ lọc Model Cloudflare Workers AI:**
- **Thanh công cụ Lọc Model 1 Hàng Ngang (`webui/templates/partials/tab_config.html`, `webui/static/js/api-client.js`)**:
  - Bố trí trên 1 hàng duy nhất: Dropdown chọn model, icon 🔖 (đánh dấu), icon 🔄 (lấy danh sách), Input từ khóa lọc, Dropdown phương thức (Bao gồm / Loại trừ).
  - Hỗ trợ lọc danh sách model linh hoạt theo từ khóa tìm kiếm và chế độ include/exclude.
  - Tự động nhận diện và hiển thị link "Thông tin Cloudflare Models" (dẫn tới `https://developers.cloudflare.com/ai/models/`) và tooltip hướng dẫn `ⓘ` khi active gateway là Cloudflare.

**Cải tiến Checkpoint & Translation Memory (TM):**
- **Checkpoint Identity Cứng (Hard Identity)**:
  - Cập nhật `services/checkpoint_service.py` và `core/executor.py` để lưu trữ `identity` (bao gồm `provider_kind`, `model`, `chunk_size`, mã băm nội dung và prompt).
  - Khởi tạo session mới hoàn toàn nếu phát hiện mismatch identity khi resume, tránh lỗi "râu ông nọ cắm cằm bà kia" khi thay đổi cấu hình giữa chừng.
- **Cách ly Cache TM theo Ecosystem**:
  - Gắn tag `provider_kind` vào các bản ghi trong Translation Memory.
  - Phân luồng kết quả match tránh cache chéo sai ngữ nghĩa giữa các hệ sinh thái API khác nhau.

**Cải tiến ApiManager & Rate Limiting:**
- **Dynamic Rate Limit**:
  - `AdaptiveRateLimiter` nay tự động nhận diện RPM/RPD từ cấu hình provider thay vì giả định cứng (Ví dụ: 15 RPM / 1500 RPD cho Gemini, 20 RPM / 1M RPD cho OpenAI/Custom).

## [8.17.0] - 2026-07-31
### Tối ưu hóa Converter HTML ↔ Markdown, Bảo toàn Alt Text Ảnh & Cải tiến Ghi đĩa Nguyên tử

**Bảo toàn Dữ liệu & Chuẩn hóa Error Contract:**
- **Bảo toàn Alt Text Ảnh (`core/source_normalizer.py`)**:
  - Sửa `post_clean()` giữ nguyên thuộc tính alt text của ảnh (`![alt text](url)`) thay vì xóa trắng.
  - Bổ sung `normalize_html_content()` cho phép chuẩn hóa HTML trực tiếp trong bộ nhớ.
  - Loại bỏ sentinel string lỗi `[Lỗi chuyển đổi nội dung]`, ném exception có cấu trúc để tránh sinh file output hợp lệ giả khi conversion thất bại.
- **Tích hợp Thư viện Standard `markdown` (`services/text_converter.py`)**:
  - Chuyển đổi luồng Markdown → HTML sang dùng thư viện `markdown` chính thức với các extension chuẩn (`tables`, `fenced_code`, `codehilite`, ...).
  - Thêm `ImportError` cảnh báo rõ ràng khi thiếu thư viện `markdown` hoặc `html2text` kèm câu lệnh hướng dẫn `pip install '.[epub]'`.
- **Ghi đĩa Nguyên tử & Chống Ghi đè Nguồn (`_atomic_write`)**:
  - Áp dụng `_atomic_write` (ghi ra tmpfile cùng thư mục rồi `os.replace`) đảm bảo file đầu ra không bị vỡ/hỏng nếu tiến trình bị gián đoạn.
  - Chặn ghi đè trực tiếp lên file nguồn với `_reject_in_place_overwrite()`.
- **Báo cáo Trạng thái Batch Converter (`routes/plugins.py`)**:
  - Cập nhật route xử lý batch converter báo cáo chính xác trạng thái `done`, `partial`, và `error` kèm danh sách `failed_files` và số lượng `failed_count`.

**Bổ sung Kiểm thử Tự động:**
- Thêm 2 bộ unit test mới `tests/unit/test_html_to_markdown.py` và `tests/unit/test_markdown_to_html.py` nghiệm thu toàn diện luồng chuyển đổi HTML ↔ Markdown.

---

## [8.16.0] - 2026-07-31
### Hoàn thiện Sync Scroll, Reset Editor View, Nối Converter Option & Khắc phục Race Search/Replace

**Cải tiến Editor UI & Đồng bộ Workspace:**
- **Đồng bộ cuộn Editor (Sync Scroll)**:
  - Khôi phục và nâng cấp `EditorComponent.setupSyncScroll` sử dụng cờ reentry guard kết hợp `requestAnimationFrame`, gỡ bỏ hoàn toàn kiểm tra `activeElement`.
  - Khởi tạo đồng bộ cuộn 2 bên cho cả Workspace Dịch thuật (`pm-source-text` ↔ `pm-result-text`) và Workspace Soát lỗi (`pm-spell-source-text` ↔ `pm-spell-result-text`) trong `main.js`.
- **Reset Editor View (`_resetEditorView`)**:
  - Triển khai `EditorComponent._resetEditorView(elementId)` tự động đưa vị trí cuộn `scrollTop = 0`, `scrollLeft = 0` và con trỏ về đầu dòng `setSelectionRange(0, 0)` mỗi khi nạp file mới.
- **Đồng bộ Lifecycle File & Refresh Dự án**:
  - Cập nhật `ProjectManager.openProject()` và `refreshProjectFiles()` kiểm tra tính tồn tại của file đang mở khi bấm Làm mới (🔄): reload nội dung từ đĩa nếu còn, hoặc dọn sạch editor/spellcheck nếu file đã bị xóa.

**Sửa lỗi Backend & Test Migration:**
- **Khắc phục Race Condition Search & Replace**:
  - Bổ sung `await window.EditorComponent.saveActiveFile()` trong `replaceAll()` (`footer.html`) trước khi gọi API `replace-all`, đảm bảo nội dung chưa lưu được ghi đĩa trước khi thay thế hàng loạt.
- **Nối tùy chọn `delete_source` Converter UI**:
  - Đọc trạng thái checkbox `#converter-tool-delete-source` và gửi trường `delete_source` trong payload request của `ConverterToolPlugin.runTask`.
- **Cập nhật Unit Test Suite cho Spellcheck Migration**:
  - Cập nhật `tests/unit/test_helpers.py` và `tests/unit/test_spellcheck_provider.py` tương thích với canonical engine `TranslationExecutor.spellcheck_text`.
  - Loại bỏ hoàn toàn các import tham chiếu tới 2 module đã bị xóa (`spellcheck_executor`, `spellchecker`).

**Dọn dẹp Tài liệu & WIP Plans**:
- Đổi tên tệp kế hoạch hoàn thành `plan_2026-07-31_feature-audit.md` và `plan_2026-07-31_html-to-markdown-audit.md` sang prefix `del_`.
- Tổng hợp đầy đủ nhật ký tác vụ hoàn thành (`del_DONE_TASKS.md`) và tác vụ chờ làm (`del_PENDING_TASKS.md`).

---

## [8.15.0] - 2026-07-31
### Release Review, Hợp nhất Engine Soát lỗi AI, Nâng cấp Converter & Tối ưu Giao diện Editor

**Cải tiến Mã nguồn Backend & Engine AI:**
- **Hợp nhất luồng Soát lỗi AI vào `TranslationExecutor` (`core/executor.py`)**:
  - Thêm phương thức `spellcheck_text` và `@staticmethod _parse_spellcheck_chunk` trực tiếp vào `TranslationExecutor`.
  - Tái sử dụng 100% cơ chế chunking, SQLite checkpointing (`spell:{filename}`), xoay vòng API key pool và event log của engine dịch.
  - Xóa bỏ triệt để 2 module cũ `core/spellcheck_executor.py` và `plugins/spellcheck/spellchecker.py`.
  - Sửa `SpellcheckProjectFilesUseCase` truyền chính xác `folder_type` (`sources` hoặc `translated`), loại bỏ lỗi duplicate event log (`double-emit`).
- **Nâng cấp Công cụ chuyển đổi (Converter Tool)**:
  - Thêm tùy chọn `delete_source` (Xóa file nguồn sau khi chuyển đổi MD ↔ HTML) trên giao diện `workspace_ebook_kit.html` và truyền xuống `webui/routes/plugins.py`.
  - Tự động xóa sạch các file `.html` trung gian và thư mục tạm `temp_html` sau khi xuất `MD → EPUB 3`.
- **Nâng cấp Tìm kiếm & Thay thế toàn bộ dự án (Search & Replace)**:
  - Thêm 2 API mới `POST /api/projects/<slug>/search-all` và `POST /api/projects/<slug>/replace-all` hỗ trợ quét đệ quy `rglob("*")` mọi loại tập tin văn bản.
  - Xử lý tương thích dòng xuống Windows CRLF (`\r\n`) và bỏ qua lỗi mã hóa file non-UTF8.
- **Cải tiến WebUI & Editor Component**:
  - **Reset Editor View**: Tự động đưa vị trí cuộn `scrollTop = 0`, `scrollLeft = 0` và con trỏ về đầu dòng `setSelectionRange(0, 0)` khi nạp file mới.
  - **Sync Scroll**: Cải tiến cuộn đồng bộ 2 bên bằng cờ reentry guard kết hợp `requestAnimationFrame`, gỡ bỏ kiểm tra `activeElement`.
  - **Retranslate Icon Button**: Thêm nút Dịch lại từ đầu `#btn-retranslate-file` trên toolbar kết quả dịch, tự động ép `force_retranslate: true`.
  - **Row Highlight**: Gán ngay class `.active` khi click chọn file, bảo toàn màu highlight khi rê chuột (hover).
- **Vệ sinh Hệ thống & Dọn dẹp Tài liệu**:
  - Bổ sung `.kiro/` vào `.gitignore`.
  - Chuyển tệp kế hoạch `plan_2026-07-31_merged_technical_report.md` sang `del_plan_2026-07-31_merged_technical_report.md`.
  - Tổng hợp đầy đủ nhật ký tác vụ hoàn thành (`del_DONE_TASKS.md`) và tác vụ chờ làm (`del_PENDING_TASKS.md`).

---

## [8.14.0] - 2026-07-29
### Tối ưu Editor, Hợp nhất Luồng Soát lỗi AI & Quản lý File Dự án

**Nâng cấp Editor UI & Hợp nhất Core AI Engine:**
- **Tối ưu Editor & Reset View (`_resetEditorView`)**:
  - Tự động đặt vị trí cuộn (`scrollTop = 0`, `scrollLeft = 0`) và đưa con trỏ về dòng đầu tiên (`setSelectionRange(0, 0)`) mỗi khi nạp file mới vào editor.
  - Sửa lỗi DirtyState key `spell-result-text` thiếu prefix `pm-`.
- **Đồng bộ cuộn Editor (Sync Scroll)**:
  - Cải tiến hàm `setupSyncScroll` sử dụng cờ reentry guard kết hợp `requestAnimationFrame`, bỏ kiểm tra `activeElement` giúp cuộn mượt và chính xác khi dùng chuột lăn mà chưa click focus.
  - Khởi tạo đồng bộ cuộn 2 bên cho cả Workspace Dịch thuật và Workspace Soát lỗi trong `main.js`.
- **Hợp nhất luồng Soát lỗi AI vào `TranslationExecutor`**:
  - Thêm phương thức `spellcheck_text` và `@staticmethod _parse_spellcheck_chunk` vào `TranslationExecutor` (`core/executor.py`), tái sử dụng 100% cơ chế chunking, SQLite checkpoint, API key rotation và event logging từ luồng dịch.
  - Xóa bỏ hoàn toàn 2 tệp thừa `core/spellcheck_executor.py` và `plugins/spellcheck/spellchecker.py`.
  - Viết lại `SpellcheckProjectFilesUseCase` thành wrapper mỏng, loại bỏ lỗi duplicate log (`double-emit`).
- **Dọn dẹp File HTML Trung gian khi Tạo EPUB 3**:
  - Bổ sung `try...finally` trong `webui/routes/plugins.py` và `plugins/epub_converter/text_to_epub/main.py` để tự động xóa sạch các tệp `.html` trung gian và thư mục tạm sau khi đóng gói `MD → EPUB 3`.
- **Đồng bộ Làm mới Dự án & Dọn dẹp Editor khi Xóa File**:
  - Tự động xóa sạch nội dung trong các khung editor (`pm-source-text`, `pm-result-text`, ...) và reset `window.currentProjectFile` khi xóa file đang mở.
  - Cập nhật `ProjectManager.openProject()` kiểm tra sự tồn tại của file đang mở khi bấm Làm mới (🔄) để reload nội dung mới nhất từ đĩa hoặc dọn editor nếu file không còn tồn tại.
  - Xóa kèm tệp `_info.txt` tương ứng khi xóa file trong thư mục `spelling/`.

---

## [8.13.0] - 2026-07-29
### Sửa lỗi Spellcheck Worker, Tái cấu trúc Header/Bottom Bar & Nâng cấp Search/Replace

**Nâng cấp Giao diện Workspace & Sửa lỗi Soát chính tả:**
- **Sửa lỗi Spellcheck Worker**: Khắc phục lỗi `NameError` và truyền thiếu `folder_type` trong `SpellcheckProjectFilesUseCase.execute()`, route `webui/routes/projects.py` và frontend `translation-worker.js`.
- **Tái cấu trúc Header Workspace & Loại bỏ Bottom Bar**:
  - Di chuyển thông tin tập tin (ký tự, số từ, ước lượng token) từ chân trang lên phía bên phải Header (`#pm-header-file-info`).
  - Loại bỏ hoàn toàn khối Bottom Bar (`#pm-translation-bottom-bar`, `#pm-spellcheck-bottom-bar`) và checkbox `"Dịch lại từ đầu"`, mở rộng tối đa chiều cao vùng làm việc.
  - Tự động ẩn/hiện thông tin phù hợp khi chuyển giữa tab Biên tập dịch và Soát chính tả.
- **Icon Button Dịch lại từ đầu (`#btn-retranslate-file`)**:
  - Bổ sung nút biểu tượng Dịch lại vào thanh công cụ `pm-result-editor`, mặc định luôn ép AI dịch lại từ đầu (`force_retranslate: true`, xóa checkpoint/cache/TM cũ của 1 file hiện tại).
  - Cập nhật icon SVG uốn vòng lặp kèm ngôi sao AI lấp lánh khớp chuẩn với yêu cầu thiết kế.
- **Chuẩn hóa Row Highlight**:
  - Khắc phục lỗi so sánh object `window.currentProjectFile` khiến class `.active` không được gán khi render.
  - Thêm phương thức `ProjectManager.highlightActiveFile()` gán ngay class `.active` khi click chọn file trong danh sách.
  - Chuẩn hóa CSS highlight cho `.active` và `.selected`, giữ nguyên màu nổi bật khi rê chuột (hover).
- **Nâng cấp Tìm kiếm & Thay thế (Search & Replace)**:
  - Chuyển đổi backend `batch_replace_in_project` từ `glob("*.txt")` sang `rglob("*")` hỗ trợ tất cả định dạng văn bản (`.txt`, `.md`, `.html`, `.xhtml`, `.xml`, `.json`, ...).
  - Tương thích ký tự xuống dòng Windows CRLF (`\r\n`) và bỏ qua lỗi mã hóa file non-UTF8.
  - Bổ sung API `POST /api/projects/<slug>/search-all` giúp thống kê chính xác số kết quả tìm thấy và số file khớp trước khi thay thế.
  - Tự động lưu file đang làm việc nếu có chỉnh sửa chưa lưu trước khi thay thế hàng loạt.

---

## [8.12.0] - 2026-07-28
### Tích hợp chuyển đổi trực tiếp MD -> EPUB 3 cho plugin Converter

**Cải tiến Công cụ chuyển đổi (Converter Tool):**
- Thêm nút mới `MD → EPUB 3` vào bên trái nút `HTML → EPUB 3` trên giao diện tab Công cụ chuyển đổi (`workspace_ebook_kit.html`).
- Triển khai task `markdown_to_epub` trong `routes/plugins.py`, phối hợp chạy luồng sinh HTML trung gian từ MD bằng `convert_markdown_file()` và đóng gói trực tiếp thành EPUB 3 bằng `create_project_epub()`.
- Hỗ trợ cơ chế lọc và bỏ qua các file không phải Markdown kèm log cảnh báo chi tiết, giúp tránh lỗi/vỡ luồng khi chọn lẫn lộn nhiều định dạng.
- Giữ nguyên cấu trúc Service Layer (`project_epub.py`, `text_converter.py`, `plugin.py`), tăng tính bảo mật và giảm thiểu tối đa rủi ro gây lỗi hồi quy.

---

## [8.11.0] - 2026-07-28
### Đồng bộ Modal tiến trình và Tasks counter cho dự án

**Nâng cấp Quản lý Tác vụ (Task Tracking & Resiliency):**
- Tích hợp lưu trạng thái tác vụ local (`_activeJobId`, `_lastViewedJobId`, `_taskStateByJob`) ở frontend (`translation-worker.js`) giúp bảo toàn và hiển thị lại toàn bộ nhật ký log, tiến độ phần trăm khi mở lại modal.
- Thay đổi chính sách ẩn/hiện modal tiến trình: click ra ngoài modal hoặc nhấn `Escape` chỉ ẩn modal đi ngầm, không làm gián đoạn hay xóa mất dữ liệu của tác vụ đang chạy.
- Tối ưu hóa UI: Cập nhật chỉ số Tasks tức thì ngay sau khi người dùng kích hoạt dịch mà không cần chờ poll API (5 giây).
- Biến cụm `Tasks` trên Header thành button pill luôn hiển thị. Khi click vào cụm Tasks này sẽ kích hoạt mở lại modal tiến trình của tác vụ đang chạy hoặc hiển thị lại log của tác vụ vừa kết thúc gần nhất.
- Nâng cấp Backend: Cập nhật các trường thông tin tiến trình phong phú (`percent`, `last_message`, `current`, `total`, `completed_files`, `error_count`, `finished_at`) cho `Task` và `TaskRegistry` để frontend có dữ liệu rehydrate trạng thái tác vụ.

---

## [8.10.0] - 2026-07-28
### Tái cấu trúc Trang Quản lý Dự án dạng Grid Card & Sửa lỗi hiển thị

**Tái thiết kế giao diện Trang Dự án (Project Page Redesign):**
- Thay đổi bố cục dạng 2 cột (Tạo dự án 40% / Danh sách 60%) sang dạng Grid Card hiển thị 3 cột co giãn linh hoạt full-width.
- Đưa form "Tạo dự án mới" vào trong Modalbox giữa màn hình, tự động đóng sau khi khởi tạo thành công và chuyển hướng về Workspace.
- Thêm Card nét đứt `+ Tạo dự án mới` ở cuối danh sách dự án như một shortcut mở nhanh modalbox.
- Sắp xếp lại thứ tự nút hành động trên Header: `+ Tạo dự án mới` (trái), `Nhập dự án` (phải).
- Cập nhật thông tin trên Project Card:
  - Hiển thị tỷ lệ tập tin dịch hoàn thành dưới dạng `[số file đã dịch]/[số file nguồn] tập tin`.
  - Thay thế các nút hành động dạng text/emoji thô sơ bằng 4 nút Icon SVG gọn gàng với màu sắc riêng biệt (Thông tin: Indigo, Tải về: Teal, Lưu trữ: Brown, Xóa: Red).
  - Tích hợp thanh tiến độ (Progress Bar) trực quan thay đổi màu sắc và phần trăm theo tỉ lệ hoàn thành thực tế.
  - Sử dụng dấu chấm trạng thái (Status Dot) linh động theo tiến độ (Xám: 0%, Nâu/Amber: Đang dịch, Teal: Hoàn thành 100%).

**Sửa lỗi UI/UX:**
- Sửa lỗi sập/vỡ layout grid co card về một hàng dọc bằng cách ép thuộc tính `w-100` và `display: grid !important` trên container.
- Sửa lỗi nút Refresh (Làm mới) tự ý đổi thành text "↻ Làm mới" thô thiển sau khi click bằng cách giữ nguyên SVG icon trong JS loading callback.

---

## [8.9.0] - 2026-07-27
### Cân chỉnh thuật toán Smart Batching & Chuẩn hóa Kế hoạch AI

**Cải tiến thuật toán Smart Batching:**
- Loại bỏ hằng số `batch_instruction_overhead` cố định ra khỏi việc tính toán kích thước content chunk (do prompt instruction nằm ở system prompt, không thuộc nội dung).
- Sửa lỗi Bug A & C: Luôn tính toán chính xác delimiter overhead cho mọi file (kể cả file đầu tiên ở index 0 của batch) trong cả hai trường hợp khởi tạo batch hoặc tạo batch mới ở nhánh fallback/else.
- Bổ sung log tổng quan batch plan (`📦 Batch plan [N/M]`) giúp kiểm soát số lượng file và ước lượng ký tự trước khi bắt đầu dịch.

**Chuẩn hóa Quy trình Phát triển (AI-Executable Plan):**
- Bổ sung hướng dẫn chi tiết về cấu trúc 5 phần bắt buộc cho Kế hoạch thực thi AI model vào [DEVELOPMENT.md](file:///Users/narga/Briefcase/Projects/Novel-Translator/docs/DEVELOPMENT.md).
- Quy định bắt buộc sử dụng định dạng diff chuẩn cho mọi thay đổi mã nguồn trong kế hoạch để đảm bảo model thực thi chính xác.

---

## [8.8.0] - 2026-07-27
### Task Registry & Quản lý tiến trình dịch thông minh

**Nâng cấp Hệ thống Tiến trình (Task Registry):**
- Thay thế progress queue toàn cục bằng `TaskRegistry` quản lý các tác vụ dịch theo `job_id`.
- Tách luồng SSE theo `job_id` thông qua API `/api/tasks/progress/<job_id>`.
- Cho phép người dùng đóng modal tiến trình mà không làm mất hoặc gián đoạn tác vụ đang chạy ngầm.
- Thêm thanh trạng thái tác vụ ngầm ở góc dưới màn hình ("Tác vụ: N") để mở lại modal chi tiết hoặc hủy tác vụ bất kỳ lúc nào.

**Sửa lỗi dịch thuật & Smart Batching:**
- Sửa lỗi nghiêm trọng bỏ qua các tập tin đơn lẻ nhỏ hơn `chunk_size` khiến dịch 1 file không sinh kết quả.
- Sửa lỗi logic callback và biến tham chiếu `{fallback}` chưa định nghĩa gây lỗi khi dịch fallback.
- Tự động xóa các file văn bản tạm `batch_*.txt` sau khi dịch xong để giữ sạch thư mục đầu ra.
- Đảm bảo danh sách file luôn được sắp xếp theo thứ tự bảng chữ cái tự nhiên trước khi xử lý.

**Cải tiến UI/UX Biên tập:**
- Thiết kế lại các nút thao tác nhanh ở Workspace Header thành 2 nút trên dưới, co giãn rộng bằng nhau (`w-100`), giữ nguyên chữ trên một dòng (`ws-nowrap`), giúp phần mô tả dự án rộng rãi và cân đối hơn.
- Thêm tính năng chọn nhiều file bằng **Shift + Click** checkbox trong sidebar.

---

## [8.7.0] - 2026-07-15
### Smart Batching — Tối ưu dịch nhiều file đồng thời

**Smart Batching (TranslateProjectFilesUseCase):**
- Gom nhóm file nhỏ thành Virtual Chunks — giảm số request (RPD/RPM) tới API AI
- Session token ngẫu nhiên + delimiter `<<<token:N>>>` — tránh AI dịch nhầm tên file
- Regex parse + index sequence validation — phát hiện lỗi cấu trúc response
- Fallback tự động: rã nhóm → dịch tuần tự nếu parse thất bại
- Batch Instruction inject vào `prompts["main"]` — không sửa `executor.py`
- 5 helpers mới: `_delimiter_overhead`, `_build_batches`, `_wrap_batch`, `_make_batch_config`, `_parse_batch_response`
- Unit tests: `tests/unit/test_smart_batching.py` (276 dòng)

**Dọn dẹp:**
- Xóa JS dead code: `runEpubToText()`, `runTextToEpub()` trong `ui-helpers.js`

**Sửa lỗi:**
- Sửa thiếu thẻ đóng `</div>` trong `tab_projects.html`

---

## [8.6.0] - 2026-07-13
### Công cụ chuyển đổi (Converter Tool) — thay thế eBook Kit

**Rebuild plugin EPUB Converter → Công cụ chuyển đổi:**
- Workspace `eBook Kit` cũ (form path thủ công) được thay bằng workspace "Công cụ chuyển đổi" tái dùng file list sidebar của dự án với 2 nút tác vụ: HTML→Markdown và Markdown→HTML.
- Plugin `plugins/epub_converter/plugin.py` v4.0.0: thêm 2 task `html_to_markdown`, `markdown_to_html`; contract trả về `Union[bool, Path]`.
- Plugin self-contained: `plugins/epub_converter/services/text_converter.py` với bộ chuyển Markdown→XHTML tự viết (không phụ thuộc thư viện `markdown`), xử lý heading, bold/italic, link, image, code, blockquote, list, fenced code, hr, paragraph.
- Xoá route cũ `POST /api/projects/<slug>/convert-markdown` và các hàm convert JS dead (`convertSelectedToMarkdown`, `convertSingleFileToMarkdown`).
- Xoá nút "Chuyển Markdown" khỏi row actions của file list sources.
- Xoá `convert_project_files_to_markdown()` khỏi `webui/routes/projects.py`.

**Sửa lỗi nghiêm trọng:**
- **Lỗi 1 — Import sai**: `from services.text_converter` → `from .services.text_converter` (relative import) tránh xung đột với gói `services/` gốc.
- **Lỗi 2 — Trùng giao diện editor khi tải project**: Bọc các panel biên tập (`pm-translation-workspace`, `pm-spellcheck-workspace`) và bottom bar vào wrapper chung với `x-show="$store.workspace.wsTab === 'editor'"`.
- **Lỗi 3 — Đường dẫn `relative_to`**: `output_path.resolve().relative_to(project_dir.resolve())` đảm bảo đồng nhất path tuyệt đối.
- **Lỗi 4 — Auto-switch tab sau convert**: `openProject(slug)` không còn ép `wsTab = 'editor'` nếu đang mở cùng project (`isSameProject` guard). Thêm `refreshProjectFiles()` để refresh sidebar nhẹ mà không đổi tab.

**Cải tiến `project-manager.js`:**
- `openProject`: `isSameProject` guard giữ nguyên wsTab, không clear editor, không show toast.
- Đồng bộ UI dùng `switchPmFileTab` thay vì gọi `renderPmFileList`/`renderPmTranslatedList` riêng lẻ.
- `converter-tool-plugin.js`: dùng `refreshProjectFiles()` thay `openProject(slug)` + 100ms `setWorkspaceTab` (fix race condition).

### `_safe_project_file()` trong `plugins.py`:
- Helper mới chống path traversal: resolve path + kiểm tra `startswith(base_dir)`.
- Task routing: `html_to_markdown` / `markdown_to_html` xử lý section (sources/translated/spelling), filenames, output dạng relative path.

**Cải tiến thêm:**
- Nút tác vụ đổi tên: `.MD → HTML` và `HTML → .MD` cho gọn, dễ đọc.
- Thêm tác vụ `create_epub` (đóng gói EPUB 3 từ file đã chọn) với progress log real-time và lọc định dạng không hỗ trợ.
- Thêm endpoint `GET /api/projects/<slug>/download/<path>` để tải file nhị phân (epub, zip) trực tiếp từ thư mục dự án, chống path traversal.
- Frontend: thông báo hoàn tất kèm link tải EPUB canh phải — click tên file là tải về.

## [8.5.0] - 2026-07-13
### Bộ lọc File List & Nâng cấp Tab Tài liệu

**Bộ lọc File List (Filter Toolbar):**
- **Nút bộ lọc mới** trong mini toolbar cột danh sách tập tin, nằm giữa nút "Tải lên" và "Chuyển Markdown".
- **Mini context menu** với 3 nhóm điều khiển:
  - Sắp xếp theo: Tên file / Định dạng
  - Thứ tự: Tăng dần / Giảm dần
  - Lọc theo tên: nhập keyword lọc real-time
- Áp dụng đồng bộ cho cả 3 tab: Nguồn, Bản dịch, Soát lỗi.
- Checkbox "chọn tất cả" hoạt động đúng trên danh sách đã lọc (không chọn nhầm file bị ẩn).
- Click-outside và phím Escape để đóng menu. Giữ nguyên filter khi chuyển tab, reset khi mở project mới.

**Nâng cấp Tab Tài liệu:**
- **Cấu hình đường dẫn quét**: Panel cấu hình mới trong sidebar cho phép tùy chỉnh thư mục quét (mặc định: `docs, .agent, .agents, .cloud`) và chọn có quét file ở thư mục gốc hay không.
- **API cấu hình**: `GET/POST /api/docs/config` để đọc/ghi cấu hình đường dẫn.
- **Tìm kiếm nhanh**: Ô tìm kiếm filter danh sách tài liệu real-time, hiển thị nút xóa nhanh khi có keyword.
- **Phân quyền truy cập**: Kiểm tra tệp tin thuộc vùng tài liệu được cấp quyền trước khi hiển thị.

---

## [8.4.0] - 2026-07-12
### Tích hợp Tab Tài liệu dự án & Tối ưu hóa Offline hoàn toàn

**Tab "Tài liệu" mới (Project Docs Reader):**
- **Trình đọc tài liệu dự án trực tiếp**: Cho phép duyệt và đọc toàn bộ tệp tin `.txt`, `.md`, `.html` trong thư mục `docs/` đệ quy ngay trên WebUI.
  - Sidebar bên trái hiển thị danh mục tệp tin được phân nhóm theo thư mục con đệ quy.
  - Reader bên phải hiển thị nội dung tệp tin đã chọn.
  - Cache danh sách tài liệu trong session JS giúp chuyển tab nhanh không cần gọi lại API.
- **Bảo mật tuyệt đối**: Ngăn chặn Path Traversal bằng resolve đường dẫn và kiểm tra `startswith(docs_root)`.

**Lưu trữ tài nguyên Offline hoàn toàn (Tự host local):**
- **Chuyển đổi CDN sang Offline**:
  - Tải CSS Tachyons về [tachyons.min.css](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/static/css/tachyons.min.css).
  - Tải JS Marked.js (v12.0.0) về [marked.min.js](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/static/js/marked.min.js) để render Markdown phía client.
  - Cập nhật các thẻ stylesheet và script trong [header.html](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/header.html) và [footer.html](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/footer.html) để tải offline, không sử dụng mạng.

**Phục hồi & Tinh chỉnh trợ giúp Chỉ dẫn AI:**
- **Phục hồi khối trợ giúp**: Đưa phần trợ giúp về placeholders và chỉ dẫn biên soạn trở lại bên dưới Prompt editor.
- **Tinh chỉnh Placeholders**: Xóa các placeholders tĩnh không hoạt động trực tiếp (`{glossary}` và `{relationships}`) khỏi phần mô tả để tránh gây nhầm lẫn cho người dùng.
- **Tài liệu hóa cơ chế**: Cập nhật chi tiết tệp cấu hình Assets trong `workspace/projects/<slug>/assets/` và AI summarize API trong [MANUAL.md](file:///Users/narga/Briefcase/Projects/Novel-Translator/docs/MANUAL.md).

---

## [8.3.0] - 2026-07-12
### Dọn dẹp over-engineering (Ponytail Audit) — không đổi behavior người dùng

**Xóa mã chết (zero caller, verified bằng GitNexus + grep):**
- **Phase 1 — 7 file services chết**: `async_genai_client.py`, `health_monitor.py`, `circuit_breaker.py`, `statistics_service.py`, `monitoring_service.py`, `file_service.py`, `io_service.py` (tổng ~1.225 dòng). Dọn `services/__init__.py` barrel (bỏ 7 export + alias `SmartRateLimiter`).
- **Phase 2 — dead code trong file đang dùng**: xóa class `AsyncOpenAIClient`, alias `SmartRateLimiter`, class `TokenBudgetLimiter` + field `_token_limiter` + methods `acquire_token_budget`/`get_token_stats`, hàm `wait_for_emergency_clear`/`emergency_check`, class `ChunkTranslationMemory`.
- **Phase 3 — dirs rỗng + deps**: xóa 4 thư mục backend rỗng (`project_archive`, `project_files`, `project_prompts`, `project_tm`), xóa `requirements.txt` (trùng `pyproject.toml`), xóa 2 dependencies thừa `psutil` + `aiohttp`.
- **Phase 4.1 — gom config trùng lặp**: migrate `main.py` sang `AppConfigService` (drop-in, cùng signature `.get()`), xóa `services/config_service.py` (duplicate của `AppConfigService`).

**Kết quả:**
- **~−2.300 dòng** (bao gồm `uv.lock` −697) + **−2 dependencies**, **0 regression**.
- Test baseline giữ nguyên: 158 passed / 26 failed (26 failure đều là lỗi môi trường — thiếu `flask` trong runner `rtk pytest` + 2 test `PromptService` attribute mismatch có từ trước, không liên quan đợt cắt này).
- `python webui.py` không bị ảnh hưởng (không import `config_service`/`main.py`).

**Files changed:** `main.py`, `services/__init__.py`, `services/config_service.py` (xóa), `pyproject.toml`, `uv.lock`, + 11 file services/backend đã dọn.

---

## [8.2.0] - 2026-07-11
### Sửa lỗi Biên tập & Tìm kiếm/Thay thế nâng cao

**Sửa lỗi Biên tập:**
- **Sửa AutoSave sai editor ID**: `result-text` → `pm-result-text` — AutoSave giờ lưu đúng nội dung textarea đang hiển thị thay vì lưu rỗng.
- **Sửa Lưu phiên dịch (`saveChunkTranslation`)**: lấy `pm-result-text` thay vì `result-text` cũ, đảm bảo lưu đúng nội dung hiện tại.
- **Sửa Tải về 404**: Xoá route `/api/download/<filename>` không tồn tại — dùng Blob download thuần front-end, không cần gọi backend.

**Tính năng mới:**
- **🔍 Tìm kiếm & Thay thế (Search & Replace)**: Modal Alpine.js với 3 chế độ — Bình thường, Phân biệt chữ hoa/thường, Biểu thức chính quy (Regex). Tìm tiến/lùi, thay thế 1 hoặc tất cả. Tích hợp trên cả 4 textarea (Nguồn, Dịch, Soát nguồn, Soát kết quả).
- **💾 Lưu file nguồn (`saveSourceFile`)**: Nút "Lưu" mới ở cột Nguồn — PUT `/api/projects/<slug>/file/sources/<filename>`.
- **🔄 Làm mới Workspace**: Nút "Làm mới trang" duy nhất trên toolbar (thay vì nút 🔄 cục bộ trong tab Chỉ dẫn) — reload toàn bộ project data, file lists, prompts.
- **✏️ Đổi tên dự án (Rename slug)**: Sửa tên dự án tự động đổi tên thư mục + slug. Kiểm tra trùng tên, báo lỗi 409 nếu slug mới đã tồn tại.

**Cải tiến khác:**
- Toolbar workspace: sắp xếp lại thứ tự nút (Chia nhỏ chuyển xuống cuối).
- Tích hợp `Alpine.data('searchReplace')` trong `footer.html` thay vì inline script.

**Files changed (5 files, +350/-29):**
- Backend: `projects.py`
- Frontend: `editor-component.js`, `project-manager.js`, `tab_projects.html`, `footer.html`

---

## [8.1.0] - 2026-07-11
### Cải tiến Prompt UI & Dọn mã Prompt trùng

**Thay đổi chính:**
- **Hợp nhất path lưu thư viện prompt**: `workspace/prompts/library/` → `workspace/prompts/` (xóa bỏ folder `library/` trung gian). Bỏ qua folder `library` cũ nếu còn tồn tại để tránh dữ liệu rác.
- **Xoá route `/api/projects/<slug>/prompts/reset`** — cơ chế reset prompt cũ (xóa toàn bộ folder prompt) được loại bỏ. Thay vào đó, dự án chỉ cần lưu prompt rỗng cho từng key để fallback về mặc định.
- **Xoá `PromptService.reset_project_prompts()`** khỏi backend.
- **Dọn route trùng trong `projects.py`**: Xoá toàn bộ khối project prompt APIs cũ (GET/PUT/DELETE `/api/projects/<slug>/prompts`) đã được chuyển sang `prompts.py` từ v8.0.0.
- **Migration dữ liệu**: Không cần migration — dự án chưa chạy thực tế.

**Cải thiện Prompt Library (Thư viện Chỉ dẫn AI):**
- UI Library mới: modal tạo bộ prompt (Tên + Mô tả), modal sửa thông tin bộ prompt, nút Xóa bộ (ẩn nếu là `default`).
- Editor thư viện: giao diện 2 cột (danh sách bên trái, editor bên phải) với tab-switching giống workspace.
- Hiển thị tên/mô tả bộ prompt ở header editor.
- Nút Lưu hoạt động trực tiếp trên editor thư viện (không cần mở modal riêng).
- Xóa bộ prompt: lọc qua modal xác nhận, clear editor, load lại danh sách.

**Cải thiện Prompt dự án (Workspace):**
- Tab-style cho prompt tabs (Dịch thuật, Tóm tắt, Quan hệ, Thuật ngữ, Chính tả) — giao diện đồng bộ với Info tabs.
- Import từ thư viện theo từng tab riêng biệt: chọn bộ prompt nguồn → nhập nội dung vào textarea đang mở (có dirty flag chờ lưu).
- Bỏ nút "Xóa riêng" (reset) — thay bằng cơ chế lưu trống cho từng key.
- Bỏ badge trạng thái "Mặc định/Tùy chỉnh" — không còn cần thiết vì dự án không có prompt riêng sẽ tự dùng default.

**Sửa Batch Rename:**
- `getSelectedFilesForCurrentTab()`: batch rename giờ hoạt động đúng trên cả 3 mini-tab (Nội dung nguồn, Bản dịch, Soát chính tả) thay vì chỉ tab Nguồn.
- `clearSelectionForCurrentTab()`: dọn selection đúng tab sau khi rename.

**Backend cleanup:**
- `PromptService`: bỏ `reset_project_prompts()`, thêm fallback name/description cho bộ `default`, thêm filter bỏ folder `library` cũ.
- `prompts.py`: sửa `update_library()` load metadata cũ khi không gửi đủ field, API project prompts trả về `load_project_prompts()` (riêng dự án, không merged).

**Frontend cleanup:**
- Xoá các wrapper tương thích ngược (`loadProjectPrompts`, `saveProjectPrompts`, `importFromLibrary`) — giờ gọi thẳng `loadProjectPromptsFromWorkspace`, `saveProjectPromptsFromWorkspace`, `importFromLibraryToWorkspace`.
- Xoá `_updatePromptStatusBadge()` — badge không còn dùng.
- Xoá `resetProjectPrompts()` frontend.
- Xoá event listener `btn-reset-project-prompts`.

**Files changed (11 files, +490/-325):**
- Backend: `prompt_service.py`, `prompts.py`, `projects.py`
- Frontend: `tab_prompts.html`, `prompt-manager.js`, `main.js`, `project-manager.js`, `tab_projects.html`, `modals.html`, `style.css`
- Docs: `MANUAL.md`

---

## [8.0.0] - 2026-07-10
### Cải tiến lớn: Xóa Genre, Viết lại Prompt Subsystem, Nút Dừng Dịch, Batch Rename

**Issue 1: Sửa thông tin dự án không cập nhật danh sách**
- Đổi priority hiển thị tên dự án từ `book_title || name` sang `name || book_title` trong `project-manager.js`.

**Issue 8: Thống nhất nút Info**
- Xóa nút "Thông tin" ở workspace header (tab_projects.html), chỉ giữ nút Info ở danh sách dự án.

**Issue 5+6: XÓA TRIỆT ĐỂ GENRE + VIẾT LẠI PROMPT SUBSYSTEM**
- **Xóa hoàn toàn concept "Genre"** khỏi toàn bộ codebase (17+ điểm dính genre).
- **Kiến trúc mới:** `default/` (gốc hệ thống) → `library/<slug>/` (thư viện bộ prompt mẫu) → `projects/<slug>/prompt/` (copy tùy chỉnh).
- **Backend:** Viết lại `PromptService` với library CRUD, merge logic default + project override. Viết lại `webui/routes/prompts.py` với API mới: `/api/prompts/library/*` và `/api/projects/<slug>/prompts/*`.
- **Frontend:** Viết lại `tab_prompts.html` với UI Library + Project editors. Viết lại `prompt-manager.js` với `loadLibrary()`, `selectLibrarySet()`, `importFromLibrary()`, `saveProjectPrompts()`, `resetProjectPrompts()`.
- **Dọn genre:** Xóa genre modal, genre form, genre badge, genre listeners khỏi `modals.html`, `tab_projects.html`, `main.js`, `ui-helpers.js`, `project-manager.js`.
- **Clear logic:** File rỗng → unlink (quay về default). Project mới KHÔNG auto-copy default.
- Cập nhật `MANUAL.md`, `DEVELOPMENT.md`.

**Issue 3: Nút dừng tiến trình dịch**
- Thêm `cancel state` (`_cancel`, `request_cancel()`, `is_cancelled()`, `reset_cancel()`) trong `RuntimeState`.
- Thêm endpoint `POST /api/translate/cancel` trong `translation.py`.
- Check cancel trong `executor.py` sau mỗi chunk.
- Thêm nút "Dừng" trong progress modal, `stopTranslation()` trong `translation-worker.js`.
- Double-click guard: disable nút Dịch 3s sau khi bấm.

**Issue 4: Config model sai (Gemini → chạy OpenAI)**
- Validate `default_model` thuộc danh sách model của `provider_type` trong `projects.py` (translate + spellcheck). Sai → fallback model đúng + log warning.
- Fix `settings_facade.get_provider_info` trả provider **active** thay vì provider openai đầu tiên khi Gemini đang active.

**Issue 2+7: Toolbar refactor + Đổi tên hàng loạt**
- Thêm nút "Đổi tên hàng loạt" vào `icon-toolbar` trong `tab_projects.html`.
- Thêm modal `batch-rename-modal` trong `modals.html` với pattern `{N}`, start, zero-pad.
- Thêm backend endpoint `POST /api/projects/<slug>/rename-batch` trong `projects.py`.
- Thêm `showBatchRenameModal()` và `executeBatchRename()` trong `project-manager.js`.

**Files changed (20 files, -756/+717 lines):**
- Backend: `prompt_service.py`, `prompts.py`, `projects.py`, `project_service.py`, `runtime_state.py`, `executor.py`, `translation.py`, `settings_facade.py`, `helpers.py`
- Frontend: `tab_prompts.html`, `prompt-manager.js`, `main.js`, `ui-helpers.js`, `project-manager.js`, `translation-worker.js`, `modals.html`, `tab_projects.html`
- Docs: `MANUAL.md`, `DEVELOPMENT.md`, `test_webui_app_factory.py`

---

## [7.9.0] - 2026-07-10
### Tiền xử lý HTML/XHTML sang Markdown offline & Cải tiến UI Workspace

**Tính năng Tiền xử lý Offline (HTML/XHTML → Markdown):**
- Thêm module tiền xử lý `core/source_normalizer.py` hỗ trợ bóc tách nội dung trong thẻ `<body>`, chuyển đổi thẻ `<ruby>` sang định dạng `漢字《かな》`, giữ nguyên thẻ gạch chân `<u>` qua placeholder, và dọn dẹp các dòng trống/comment/CSS rác.
- Tích hợp API route `POST /api/projects/<slug>/convert-markdown` trong `webui/routes/projects.py` hỗ trợ xử lý file `.html`, `.htm` và `.xhtml` ngoại tuyến (offline).
- Cập nhật normalizer của dự án trong `plugins/translation/normalizer.py` để không loại bỏ định dạng Markdown đối với tệp `.html`, `.htm`, `.xhtml`, `.md` và `.markdown`.

**Cải tiến Giao diện (WebUI Workspace):**
- Thêm nút "Chuyển Markdown" (Batch convert) trên thanh công cụ đầu danh sách file tại `webui/templates/partials/tab_projects.html` và nút "Chuyển Markdown" riêng lẻ trên mini-toolbar dưới tên mỗi tệp.
- Sửa lỗi không deselect (bỏ chọn tất cả) khi bỏ tích checkbox "Chọn tất cả" (`chk-select-all-sidebar`) trên các danh sách file (Sources, Translated, Spelling) trong `webui/static/js/project-manager.js`.
- Cải thiện layout `.file-item-meta` trong `webui/static/css/style.css` sử dụng `justify-content: space-between` đẩy mini-toolbar sang sát lề phải, tránh xê dịch layout khi tên file quá dài.
- Hiển thị tên file đang mở cùng trạng thái/thống kê ở thanh trạng thái (status bar) dưới cùng khi tải file trong `webui/static/js/editor-component.js`.

## [7.8.0] - 2026-06-16
### Tái cấu trúc Plugin Navigation & Quản lý Plugin

**Plugin Navigation Restructuring:**
- Xoá thẻ **Công cụ** khỏi main navigation — chuyển EPUB Converter & OCR Reader thành workspace tabs (`eBook Kit`, `OCR Toolbox`)
- Thêm khối **Quản lý Plugin** dưới cùng tab Cấu hình — danh sách plugin, bật/tắt, hiển thị trạng thái
- Plugin workspace tabs tự động hiện/ẩn theo trạng thái enabled của plugin
- Core plugins (Translation, Spellcheck) mặc định bật, không tắt được
- `PluginManager` ES module mới: `webui/static/js/plugin-manager.js` (135 dòng)

**New Partial Templates:**
- `plugin_management.html` — Giao diện quản lý plugin với Alpine.js x-data
- `workspace_ebook_kit.html` — eBook Kit workspace tab (EPUB↔Text với multi-mode)
- `workspace_ocr_toolbox.html` — OCR Toolbox workspace tab (PDF/Image OCR)
- `footer.html` — Alpine store init, script loading ordering, persist plugin

**Backend Plugin Routes Overhaul (`webui/routes/plugins.py`):**
- Route mới: `POST /api/projects/<slug>/plugins/epub-converter` — project-scoped EPUB conversion
- Route mới: `POST /api/projects/<slug>/plugins/ocr` — project-scoped OCR processing
- Route mới: `POST /api/plugins/toggle` — bật/tắt plugin, lưu vào `config/plugins.json`
- Route mới: `POST /api/projects/<slug>/plugins/epub-converter/text-to-epub` — Text→EPUB
- Middleware `@require_plugin_enabled()` kiểm tra trạng thái plugin trước khi xử lý
- Plugin progress cleanup tự động (xóa progress >30 phút)
- Legacy route `POST /api/plugins/epub-converter` vẫn giữ để tương thích ngược

**Core Interfaces:**
- `core/interfaces/__init__.py` mới: `PluginBase`, `ConverterPlugin` abstract classes
- Plugin interface chuẩn hoá: `name`, `version`, `display_name`, `initialize`, `cleanup`, `get_capabilities`

**Plugin Integration Regression Fixes (Phases 1-5):**
- Phase 1: Sửa Alpine workspace store init (`footer.html` init trước Alpine core)
- Phase 2: Sửa plugin list lifecycle (`x-init` thay `@alpine:init`, guard store)
- Phase 3: Sửa workspace tab buttons (class đồng bộ `workspace-sub-tab`)
- Phase 4: Sửa frontend API URL (`encodeURIComponent(slug)`, đổi OCR Reader → OCR Toolbox)
- Phase 5: Sửa backend plugin execution (route project-scoped, validate slug)

**UI/UX Improvements:**
- Giảm font-size bottom status bar để khớp với re-translate label

---

## [7.7.0] - 2026-06-14
### Hợp nhất Giao diện Biên tập & Kiểm chính tả

**UI Merging & Workspace Redesign:**
- Hợp nhất tab "Kiểm chính tả" cấp workspace vào tab "Biên tập" — loại bỏ 1 workspace tab
- Sidebar duy nhất với 3 mini-tab: "Nội dung nguồn", "Bản dịch", "Soát chính tả"
- Xoá sidebar spellcheck riêng (`#pm-spell-file-sidebar`, `#pm-spellcheck-file-list`, v.v.)
- Selection tự động clear khi chuyển mini-tab để tránh thao tác nhầm
- Workspace translation (`#pm-translation-workspace`) và spellcheck (`#pm-spellcheck-workspace`) tách biệt, show/hide theo mini-tab

**Toolbar & Icons:**
- Thêm nút "Soát lỗi đã chọn" vào toolbar sidebar
- Thêm nút "Soát lỗi AI" trong row actions của file list (Nội dung nguồn)
- Biểu tượng soát lỗi mới (chữ A kèm dấu tích)
- CSS tooltip scoped chỉ áp dụng cho icon toolbar (`.icon-toolbar`, `.editor-icon-toolbar`)
- Convert toolbar buttons từ `title` sang `data-tooltip` + `aria-label`

**Terminology & UX:**
- Đổi "Bản gốc" → "Nội dung nguồn" (mini-tab)
- Đổi "Xóa TM dự án" → "Đặt lại bộ nhớ dịch" với confirm message mới
- Đổi "Soát lỗi đã chọn" icon từ chữ T → chữ A
- Xoá `<span class="silver">|</span>` separator trước "Bản gốc:" trong bottom bars

**Code Cleanup:**
- Xoá các hàm spellcheck sidebar không dùng: `switchPmSpellTab`, `selectAllSpellcheckFiles`, `deleteSelectedSpellSidebarFiles`, v.v.
- Xoá `COL_MAP['spell-file']` và logic `updateColumnLayout` cho spell-file
- Đơn giản hoá `uploadProjectFile()` — chỉ dùng `pm-upload-source-file`

---

## [7.6.0] - 2026-06-14

**Translation Cache Removal:**
- Xoá hoàn toàn `services/cache_service.py` (170 dòng) — không còn cache kết quả dịch
- Xoá import/logic cache trong `core/executor.py`, `plugins/translation/translator.py`, `webui/routes/translation.py`
- Xoá `use_cache` khỏi `TranslationRequest` DTO và `TranslationResult` DTO
- Xoá checkbox "Sử dụng Cache" và block "Dọn dẹp hệ thống" trong tab Cấu hình
- Xoá thống kê cache khỏi Dashboard (`webui/helpers.py`)
- Xoá `--cache` flag khỏi CLI (`cli.py`)
- Xoá test case `test_import_cache_service` trong `tests/unit/test_helpers.py`

**Force Retranslate:**
- Thêm checkbox "Dịch lại từ đầu" trong toolbar tab Biên tập
- `translation-worker.js` gửi `force_retranslate` payload trong tất cả API translate
- Backend nhận `force_retranslate` trong `/api/projects/<slug>/translate`
- Executor bỏ qua checkpoint và TM khi `force_retranslate=True`
- Đảm bảo TM vẫn được ghi lại sau khi dịch thành công (chỉ skip `find_match`)

**Clear Project TM:**
- Thêm nút "Xóa TM dự án" trong header workspace
- API endpoint `POST /api/projects/<slug>/tm/clear` xoá TM riêng của dự án

**ProjectContextService:**
- Service mới `backend/infrastructure/config/project_context_service.py` đọc `style_guide.txt` + `summary.txt` từ assets
- Thay thế hardcode asset reading trong `projects.py`
- Hỗ trợ placeholder `{translation_guidelines}`, `{project_summary}`, `{project_context}` trong prompt
- Fallback append context nếu prompt không có placeholder

**Frontend Improvements:**
- Thêm checkbox "Chọn tất cả" cho cả sidebar nguồn và sidebar soát lỗi
- Thêm nút "Xóa đã chọn" cho cả hai sidebar
- Project card redesigned: nút hành động compact (ℹ️, 💾, 📦, 🗑️)
- Tab Info: dropdown file nguồn, Generate/Lưu hoạt động đúng theo subtab đang chọn
- Tab State Preservation: giữ trạng thái mini-tab khi reload workspace
- `data-filename` attribute thay vì inline string interpolation (XSS safety)
- `escapeHtml()` cải thiện: xử lý null/undefined, dùng string replace thay vì DOM

**API & Backend:**
- Legacy shim `/api/provider` backward compatibility cho frontend cũ
- Gemini model info fallback khi API không trả metadata
- Unified model loading endpoint (`/api/models` tự detect provider)
- `ApiClient.fetchJson()` cải thiện error handling (JSON parse protection)
- `switchProvider()` / `initProvider()` dùng `/api/providers/*` thay vì `/api/provider`
- `@click.stop` trên input config防止 nhấm nhầm chuyển provider

---

## [7.5.0] - 2026-06-11
### Sửa lỗi API Key Invalid & Cải thiện Tie-break

**Phase 1 — Sửa lỗi API Key Invalid:**
- Sửa `AdaptiveRateLimiter.should_retry()` để nhận diện lỗi key vĩnh viễn (API_KEY_INVALID, permission_denied, unauthenticated)
- Thêm cooldown 24 giờ cho key bị từ chối (không retry)
- Thêm 6 unit tests cho lỗi key invalid

**Phase 2 — Cải thiện Tie-break cho Least Used Key:**
- Thêm `_round_robin_offset` vào `AdaptiveRateLimiter.__init__()`
- Sửa `get_least_used_key()` để sử dụng round-robin tie-break
- Thêm 2 unit tests cho tie-break

**Phase 3 — Unit Test Coverage:**
- Thêm `tests/unit/test_api_service.py` (13 tests)
- Tất cả test PASS (176 tổng)

**Phase 4 — Backward Compatibility:**
- Giữ nguyên interface `ApiManager.handle_api_error()`
- Không thay đổi `plugins/translation/translator.py`
- Giữ mask key trong log (chỉ hiển thị suffix 4 ký tự)

---

## [7.4.1] - 2026-06-11
### Provider Routing Hoàn thiện & Bug Fixes

**Phase 1B — Legacy Route Cleanup:**
- Xoá hẳn route `/api/translate` (cũ trong `webui/routes/translation.py`) — không dùng nữa
- Xoá hẳn route `/api/provider` (cũ trong `webui/routes/settings.py`) — đã thay thế bằng `/api/providers`

**Phase 1C — Helper Normalization:**
- `get_default_model()` ở `webui/helpers.py`, `ModelCatalogService`, `AppConfigService` giờ đọc từ `ProviderService.get_active_default_model()` thay vì `config/app.ini`
- Giữ fallback sang `app.ini` nếu `ProviderService` chưa sẵn sàng

**3C — Chunk Splitting API Integration:**
- Thêm `getChunkTargetFilename()` để xác định file nguồn cần chunk
- `showChunkConfig()` kiểm tra project/file trước khi mở modal
- `confirmChunking()` async — gọi `POST /api/projects/<slug>/chunk/<filename>` với `{ max_chars }`
- Validation: maxChars ≥ 1000, có project, có file target

**3D — Ẩn file log `_info.txt` khỏi danh sách soát lỗi:**
- Backend: `_is_spellcheck_info_file()` + `_spellcheck_info_name()` trong `projects.py`
- `get_project_spelling_files()` lọc bỏ file `_info.txt`
- Frontend defensive: `renderPmSpellcheckedList()` lọc `_info.txt` phía client
- `getSpellcheckInfoFilename()` helper + cập nhật `_loadSpellcheckFile()` dùng helper

## [7.4.0] - 2026-06-10
### Provider Routing Fix & HTML Template Refactor

**Provider Routing (Translation + Spellcheck):**
- `plugins/spellcheck/spellchecker.py`: Thêm `_get_client()` dispatch theo `provider_type`, không còn hard-code Gemini
- `plugins/translation/translator.py`: Cập nhật `_get_client()` cache key theo provider_type + base_url
- `webui/routes/projects.py`: Worker đọc `ProviderService.get_active_provider_config()` để lấy đúng key/base_url/model theo provider đang active
- Xóa import `ApiKeyService` thừa trong `spellcheck_project_file`
- Thêm test suite `tests/unit/test_spellcheck_provider.py` (7 tests cho client dispatch)

**Nút Làm mới (Refresh) cho Quản lý dự án:**
- Thêm `ProjectManager.refreshProjectCards()` async với loading state
- Thêm nút "↻ Làm mới" trong `tab_projects.html`
- Gọi `GET /api/projects` và cập nhật danh sách card

**HTML `<template>` Refactor:**
- Project cards: chuyển từ `innerHTML` + string concat → `<template id="tpl-project-card">` + DOM API
- Thêm template trong `tab_projects.html` với `js-*` class hooks
- Chống XSS: dùng `textContent` thay vì `${}` cho dữ liệu người dùng

**Archive System Enhancements:**
- API mới `GET /api/archive/<filename>/download` tải file lưu trữ (chống path traversal)
- Nút "Tải về" trong danh sách lưu trữ
- `ProjectManager.archiveProjectFromList()` với hộp thoại ghi đè (overwrite/copy)

## [7.3.0] - 2026-06-04
### Provider Management & Config Tab Refactor

**Backend — Single Source of Truth:**
- Rewrite `ProviderService`: providers.json là nguồn duy nhất cho tất cả provider configs
- Migration một chiều: `config/API.txt` + `config/app.ini` → `config/providers.json`
- Xóa `[PROVIDER]`, `[OPENAI]`, `[API]` sections khỏi `app.ini`
- Xóa `config/API.txt` sau migration
- Thêm `config/providers.json` vào `.gitignore`
- Atomic write cho providers.json (`os.replace` + `shutil.move` fallback)
- Bảo vệ `gemini-default` — không cho xóa qua UI/API

**Backend — Service Refactor:**
- `ApiKeyService` → wrapper gọi `ProviderService` (giữ nguyên interface)
- `AppConfigService` → delegate 4 provider methods sang `ProviderService`
- `ModelCatalogService` → đọc key/url/model qua `ProviderService`
- `SettingsFacade` → cập nhật response shape `get_provider_info()`
- `webui/helpers.py` → wrapper gọi `ProviderService` (giữ nguyên interface)
- `main.py` → delegate `load_api_keys()` sang `ApiKeyService`

**API — New Endpoints:**
- `GET /api/providers` — Danh sách providers (full key cho UI nội bộ)
- `POST /api/providers` — Tạo provider mới
- `PUT /api/providers/<id>` — Cập nhật provider
- `DELETE /api/providers/<id>` — Xóa provider
- `POST /api/providers/select` — Kích hoạt provider theo id

**Frontend — Config Tab:**
- Sửa UX: click vào input/textarea không trigger toast chuyển provider
- Thêm dropdown chọn OpenAI provider + nút Xóa
- Thêm input "Nhà cung cấp mẫu hình" + nút Thêm/Sửa
- Đổi "OpenAI Compatible" → "OpenAI Compatible Providers"
- Đổi "Chọn Model cho Gemini" → "Chọn model AI"
- Đổi "QA Model" → "Review Model", ẩn vào Advanced
- Đưa Chunk Size ra khỏi Advanced
- Tạo `provider-manager.js` (GeminiProvider + OpenAIProvider)
- Auto-fill Tên + API Key + Base URL khi chọn provider

### Bug Fixes

**Critical:**
- Sửa `ProjectManager.loadProjects()` → `loadProjectCards()` — nav bar stats không hiển thị
- Xóa `ProjectManager.initProjectDialog()` — function không tồn tại
- Sửa Ctrl+S targets `#result-text` → `#pm-result-text`
- Sửa AutoSave bind `#result-text` → `#pm-result-text`
- Sửa PromptManager `#proj-prompt-*` → `#pm-proj-prompt-*` (load/save project prompts)
- Sửa `deleteGenre` ref `genre-empty-state` (null) → null-safe
- Sửa `switchProvider` CSS `b--light-gray` → `b--black-10`
- Thêm 12 hàm ProjectManager bị thiếu (showProjectInfoModal, archiveProjectFromModal, createNewProject, etc.)
- Thêm `restoreProject` + `deleteArchive` cho tab Lưu trữ
- Sửa archive API: gửi `strategy: "overwrite"` thay vì mặc định `"check"`
- Syntax error `project-manager.js` — xóa code thừa sau consolidate

**Frontend Fixes:**
- Sửa `copyResult`/`copySpellcheckResult` element IDs → `#pm-result-text`/`#pm-spell-result-text`
- Sửa `copySpellcheckResult` dùng `navigator.clipboard` thay `execCommand`
- Status indicator (file-done-dot) hiển thị cạnh kích thước, không phải trong tên file
- Thêm text "Chờ" cho file chưa soát lỗi

### Frontend Optimization (-331 dòng)

**Consolidate:**
- `loadProjectFile`/`loadPmProjectFile` → generic `_loadFilePair(prefix)`
- `loadSpellcheckFile`/`loadPmSpellcheckFile` → generic `_loadSpellcheckFile(prefix)`
- `renderPmFileList`/`renderPmSpellcheckFileList` → shared `_renderFileItems` helper
- `showPmInfoTab`/`showPmPromptTab` → `_showPanel` helper
- Column toggle map → module-level `COL_MAP` constant
- Clipboard API: `execCommand` → `navigator.clipboard.writeText`

**Remove Dead Code:**
- ~130 dòng CSS dead (radio selectors, unused classes)
- 7 dead JS functions (renderFileList3Col, runRetranslate, etc.)
- 50 global wrapper functions → direct `Module.method()` trong HTML onclick
- Unused JS variables (`window.allFiles`)

**Other:**
- Inline styles → CSS classes (`.projects-list-view`, `.api-keys-textarea`, `.prompt-textarea`)
- Modal z-index → CSS variables (`--z-modal`, `--z-modal-top`)
- Button styling: xóa global `button, .btn` override, tighten color selectors
- Consolidate modals vào 1 file (`modals.html`)

---

## [7.2.0] - 2026-06-03
### 🐛 Bug Fixes & UX Improvements

**Model Loading Fix:**
- Không còn giữ danh sách models cũ khi API mới trả về danh sách rỗng
- `/api/openai/models` trả về `default` model và xử lý lỗi nhất quán với `/api/models`
- Hiển thị thông báo "Không có models" rõ ràng thay vì giữ models cũ

**Diff View Cải tiến:**
- Thêm chế độ xem Ngang (Side-by-side) bên cạnh Dọc (Unified)
- Nút chuyển đổi Dọc/Ngang trong modal so sánh

**Project Manager:**
- Khôi phục các hàm thao tác file bị thiếu (toggle, select all, rename, delete, move back)
- Khởi tạo drag-and-drop cho spellcheck sidebar
- Input upload file cho spellcheck tab

**Translation Worker:**
- Nút "Hoàn thành" hoạt động đúng (đóng modal)
- Tự động đóng modal sau 5 giây khi hoàn tất
- Dọn dẹp timer đúng cách khi đóng modal

**Backend:**
- Sửa lỗi tham số `model_name` → `model` trong spellchecker plugin
- `get_openai_models()` trả về `default` + `provider` key tương thích

**UI/UX:**
- Tự động tải danh sách models sau khi lưu cấu hình OpenAI
- Tải prompts/genres khi chuyển sang tab Chỉ dẫn AI
- Tải API keys khi chuyển sang tab Cấu hình

---

## [7.1.0] - 2026-06-02
### 🎨 Project Management UI & Workspace 3-Column Layout

**Quản lý Dự án (Tab mới):**
- Giao diện quản lý dự án độc lập với form tạo dự án (Tên tác phẩm, Tác giả, Thể loại, Mô tả)
- Danh sách dự án dạng card với thông tin: tên, tác giả, mô tả, số files, trạng thái, ngày tạo
- Nút thao tác: Mở dự án, Lưu trữ, Xóa
- Import/Export dự án qua file zip
- Tự động xác định trạng thái "Hoàn thành" khi tất cả file đã dịch xong

**Workspace 3 Cột:**
- Layout 3 cột: Danh sách tập tin | Editor Nguồn | Editor Bản dịch
- Tab Bản gốc/Bản dịch trong danh sách tập tin
- Tab Chưa soát/Đã soát trong Kiểm chính tả
- Nút ẩn/hiện từng cột với co giãn tự động
- Token estimate cập nhật real-time

**Cải tiến UI:**
- SVG icons thay thế emoji cho các nút thao tác
- Nút thao tác luôn hiển thị cùng dòng với thông tin file
- Toast notification chuyển lên góc trên bên phải
- Spell Log Panel collapsible cho Kiểm chính tả
- Auto-save cho editor Bản dịch (10 giây)
- Phím tắt Ctrl+S để lưu
- Drag-and-drop upload file

**Backend:**
- API mới: `/api/projects/import`, `/api/projects/<slug>/export`
- API mới: `/api/projects/<slug>/files/spelling`
- Cập nhật `project.json` với `book_title` và `author`
- Backward compatibility cho dự án cũ

**Frontend Modularization:**
- Tách `main.js` thành 6 ES modules: `api-client.js`, `project-manager.js`, `editor-component.js`, `prompt-manager.js`, `translation-worker.js`, `ui-helpers.js`
- Namespace pattern: `window.ProjectManager`, `window.EditorComponent`, etc.
- Alpine.js integration cho tab switching

---

## [7.0.0] - 2026-05-31
### 🏗️ Backend Separation — Hexagonal Architecture (Phase 01-15)
Tách toàn bộ xử lý nghiệp vụ vào package `backend/` dùng chung cho CLI và WebUI.

**Backend Architecture:**
- `backend/application/use_cases/`: `TranslateTextUseCase`, `TranslateProjectFilesUseCase`, `SpellcheckProjectFilesUseCase` + DTOs
- `backend/domain/`: Domain models & ports
- `backend/infrastructure/`: `AppConfigService`, `ApiKeyService`, `PromptService`, `ProviderService`, `ModelCatalogService`, `WorkspaceService`, `ProjectService`, `FileDiscoveryService`
- `backend/facade/`: `AppService` — entry point duy nhất
- `ProgressEventType` enum + `ProgressMapper`: Chuẩn hóa progress events
- `WebUIProgressBridge`: Map progress → SSE messages
- `SettingsFacade`: Gom config/models/API keys/cache/prompts/plugins
- `RuntimeState`: Singleton thay thế global variables trong `webui/__init__.py`

**CLI & WebUI Refactor:**
- `cli.py`: Loại bỏ `sys.argv` manipulation, dùng backend services + argparse
- `webui/routes/translation.py`: Dùng `TranslateTextUseCase`
- `webui/routes/projects.py`: Dùng `TranslateProjectFilesUseCase` + `SpellcheckProjectFilesUseCase` + `ProjectService`

🎨 **UI/UX Redesign — Slate & Indigo Theme**
- **Color system**: `style.css` chuyển sang tông Slate & Indigo (`--primary: #4f46e5`, `--bg-app: #f8fafc`)
- **Header**: Nền trắng (`#ffffff`) với viền Slate mảnh dưới chân
- **Emoji cleanup**: Loại bỏ emoji khỏi tabs, buttons, stats panel (giữ status indicators)
- **Segmented Control**: Cấu hình Gemini/OpenAI dạng phẳng thay vì song song
- **Stats panel**: Thay emoji bằng dấu chấm màu (Indigo/Green/Amber)

🧪 **Test Suite (158 tests, ALL PASSED)**
- Smoke: CLI help (`test_cli_help.py`), WebUI app factory (`test_webui_app_factory.py`)
- Unit: Config services (`test_config_services.py`), Provider services (`test_provider_services.py`), Workspace services (`test_workspace_services.py`), Progress event (`test_progress_event.py`), Translate use case (`test_translate_use_case.py`), Helpers (`test_helpers.py`)
- Fixtures: `conftest.py` với temp dirs, mock config, mock files

📝 **Documentation Cleanup**
- Xóa: `docs/plans/`, `docs/chunking/`, `docs/superpowers/`, `docs/separation/`, `docs/*.report*`, `docs/NON_PROJECT_FILES_REPORT.md`
- Cập nhật: README, ROADMAP phản ánh kiến trúc v7.0.0
- Version: `pyproject.toml` → 7.0.0

## [6.9.3] - 2026-05-09
### 🛠️ Khắc phục & Hoàn thiện UI Remediation (Final)
- **Cấu trúc DOM bền vững**: Sửa lỗi nghiêm trọng thiếu thẻ đóng HTML trong `tab_workspace.html` gây hiện tượng lồng thẻ và trang trắng (blank page) ở các tab phụ.
- **Duy trì trạng thái làm việc (Persistence)**:
    - Tích hợp `localStorage` để ghi nhớ chính xác Tab chính, Sub-tab dự án và Thẻ thông tin (Mô tả, Thuật ngữ...) sau khi tải lại trang.
    - Tự động tô sáng (Highlight) dự án đang làm việc trong sidebar và duy trì lựa chọn khi refresh.
- **Tối ưu trải nghiệm (UX)**:
    - Di chuyển Toast Notification sang góc dưới bên trái để tránh che khuất các phần tử giao diện chính.
    - Bổ sung Tooltip và Bảng chú giải hành động (🔤, ✏️, 🗑️) trong tab Kiểm chính tả giúp người dùng dễ dàng làm quen.
- **Smart Merge & Natural Sort**: Hoàn thiện logic ghép tập tin thông minh, hỗ trợ sắp xếp theo thứ tự tự nhiên (chunk_2 < chunk_10) và ưu tiên các file được chọn qua checkbox.
- **Version Alignment**: Đồng bộ hóa phiên bản hệ thống lên **6.9.3** trong `pyproject.toml` và toàn bộ tài liệu.

---

## [6.9.1] - 2026-05-09
### 🎨 UI/UX & Chế độ tập trung (UI Remediation - Phase 1)
- **Global Focus Mode**: Di chuyển nút "Chế độ tập trung" lên Header chính, giúp tính năng khả dụng trên toàn bộ ứng dụng.
- **CSS-Driven Layout**: Tối ưu hóa việc ẩn/hiện Sidebar và Header dự án bằng CSS classes thay vì thao tác DOM trực tiếp, tăng độ mượt mà và ổn định.
- **Persistence & Shortcuts**: Tích hợp `localStorage` để ghi nhớ trạng thái tập trung và hỗ trợ phím tắt `Escape` để thoát nhanh.
- **Standardized Labels**: Việt hóa và đồng bộ hóa các nhãn trạng thái tập tin (từ "Chưa" sang "Chờ").

### 🔧 Sửa lỗi & Chuẩn hóa (Bugfixes & Cleanup)
- **HTML Syntax Fixes**: Khắc phục lỗi sai cú pháp class attribute trong các editor textarea gây lỗi hiển thị trên một số trình duyệt.
- **Tab Reorganization**: Sắp xếp lại thứ tự các tab Project Workspace theo quy trình làm việc thực tế: Nội dung gốc | Nội dung dịch | Kiểm chính tả | Thông tin | Chỉ dẫn.

### 📝 Tài liệu (Documentation)
- **Manual Update**: Bổ sung hướng dẫn chi tiết cho các công cụ Editor (Wrap, Diff) và logic Ghép tập tin (Smart Merge).
- **Remediation Roadmap**: Cập nhật lộ trình Phase 2 & 3 để chuẩn bị cho việc đồng bộ hóa Layout và Backend Status API.

---

## [6.9.0] - 2026-05-06
### 🏗️ Tái cấu trúc & Mô-đun hóa (Architecture Refactor - Remediation Phase 3)
- **OCR Engine De-monolithization**: Phân rã file `ocr_engine.py` khổng lồ (~7,700 dòng) thành kiến trúc đa lớp (Layered Architecture) trong thư mục `plugins/ocr/modules/`.
    - `config.py`: Quản lý cấu hình, logging và dependency injection.
    - `image.py`: Xử lý hình ảnh, xoay ảnh tự động và nhận diện ngôn ngữ CJK.
    - `pdf.py`: Trích xuất text và xử lý cấu trúc PDF chuyên sâu.
    - `tables.py`: Pipeline nhận diện và trích xuất bảng biểu đa phương thức.
    - `formats.py`: Chuyển đổi định dạng đầu ra (DOCX, EPUB, HTML).
    - `ai_processor.py`: Toàn bộ logic xử lý hậu kỳ bằng AI (Cleanup, Spellcheck).
- **Facade Pattern Implementation**: `ocr_engine.py` được chuyển đổi thành một lớp Facade mỏng, đảm bảo tính tương thích ngược (Backward Compatibility) cho tất cả các consumer hiện tại mà không cần sửa đổi mã nguồn bên ngoài.
- **Global State Management**: Chuẩn hóa việc quản lý trạng thái biến toàn cục (mutable globals) thông qua cơ chế truy cập module-reference, ngăn chặn lỗi liên kết tĩnh khi nạp module lazy.

### 🧹 Hiện đại hóa Cache (Cache Modernization)
- **Legacy Support Removal**: Loại bỏ hoàn toàn mã nguồn hỗ trợ định dạng `pickle` lỗi thời trong `services/cache_service.py`. Hệ thống hiện tại chỉ sử dụng định dạng `JSON` (gzip compressed) để đảm bảo tính an toàn và minh bạch dữ liệu.

### 📝 Tài liệu & Quy trình (Documentation)
- **Technical Remediation Reports**: Bổ sung hệ thống tài liệu kỹ thuật chuyên sâu phục vụ bảo trì:
    - `docs/CODE_REVIEW_REPORT.md`: Báo cáo kiểm định mã nguồn chi tiết.
    - `docs/REMEDIATION_PLAN.md`: Kế hoạch khắc phục và lộ trình hiện đại hóa.
    - `docs/ocr_remediation_context.md`: Tài liệu hướng dẫn chi tiết về cấu trúc phân mảnh module OCR.
- **GitNexus Index Update**: Cập nhật chỉ mục thông minh của dự án, tăng độ phủ bao quát các module mới (1,237 symbols, 104 execution flows).

---

## [6.8.0] - 2026-05-06
### 🛡️ Bảo mật & Ổn định (Security & Stability - Remediation Phase 1)
- **Path Traversal Protection**: Vá lỗ hổng bảo mật nghiêm trọng tại các endpoint di chuyển file dự án (`move-done`, `move-back`) và đổi tên file trong `webui/routes/projects.py`.
- **Safe Binding**: Thay đổi địa chỉ host mặc định từ `0.0.0.0` sang `127.0.0.1` trong `webui.py` để ngăn chặn truy cập trái phép từ mạng ngoài khi chạy cục bộ.
- **Bare Except Fixes**: Khắc phục các khối `except:` không chỉ định lỗi trong `services/translation_memory.py`, giúp tránh việc nuốt các lỗi hệ thống nghiêm trọng và cải thiện khả năng debug.
- **Log Rotation**: Tích hợp `RotatingFileHandler` vào `webui/__init__.py`, giới hạn kích thước log file (10MB) và tự động xoay vòng (5 bản backup) để tránh tràn đĩa cứng.

### ⚙️ Hiện đại hóa & Hiệu suất (Modernization & Performance - Remediation Phase 2)
- **JSON Cache Engine**: Chuyển đổi cơ chế lưu trữ cache từ `pickle` sang `JSON` (kèm gzip) trong `services/cache_service.py`. Tăng tính an toàn, minh bạch và khả năng tương thích giữa các phiên bản Python. Hỗ trợ tự động nhận diện và đọc các file cache cũ (.pkl).
- **Centralized Log Handler**: Tách `ProgressLogHandler` ra module riêng (`core/log_handler.py`), loại bỏ mã nguồn trùng lặp giữa `executor.py` và `spellcheck_executor.py`.
- **Standardized Error Handling**: Triển khai decorator `@handle_route_errors` trong `webui/decorators.py` giúp quản lý lỗi tập trung và trả về response JSON thống nhất cho các API route.
- **Atomic State Documentation**: Bổ sung tài liệu về tính nguyên tử (atomicity) của global state `translation_result` dưới cơ chế GIL của CPython.

### 🧹 Dọn dẹp & Bảo trì (Cleanup)
- **Dead Code Removal**: Loại bỏ các đoạn mã thừa và logic lặp lại sau khối xử lý ngoại lệ trong `webui/routes/settings.py`.
- **Version Alignment**: Đồng bộ hóa phiên bản dự án lên **6.8.0** trong `pyproject.toml` và các tài liệu liên quan.


## [6.7.0] - 2026-04-24
### 🛡️ Hệ thống & Độ ổn định (System & Stability)
- **API Resilience Overhaul**: Tái cấu trúc toàn bộ `ApiService` để chống lỗi rate limit và quota từ API.
    - **`AdaptiveRateLimiter`**: Thêm cơ chế tự động xử lý lỗi `429 (rate limit)` với "progressive backoff" (thời gian chờ tăng dần) và đưa các key lỗi vào cooldown thông minh.
    - **`GlobalRPMRateLimiter`**: Giới hạn tổng RPM trên toàn hệ thống để tránh bị block IP khi dùng nhiều key.
    - **`TokenBudgetLimiter`**: Quản lý và giới hạn tổng số token mỗi phút (TPM).
- **"Least Used" Key Strategy**: Thay đổi chiến lược chọn key từ xoay vòng (round-robin) sang "ít được sử dụng nhất", giúp phân bổ tải đều trên tất cả các API key và tối đa hóa RPD.
- **Backend Delegation**: `translator.py` được đơn giản hóa, ủy thác toàn bộ logic retry và xử lý lỗi cho `ApiManager`.

### 🎨 Giao diện & Trải nghiệm (UI/UX)
- **Multi-Prompt Management UI**: Tái cấu trúc giao diện "Chỉ dẫn" trong Project Workspace.
    - Chuyển từ một textarea duy nhất sang giao diện dạng tab, cho phép quản lý riêng biệt 5 loại prompt: `Dịch thuật`, `Tóm tắt`, `Quan hệ`, `Thuật ngữ`, và `Chính tả`.
    - **Project Prompt Isolation**: Hiện thực hóa cơ chế biệt lập prompt cho từng dự án. Dự án có thể dùng prompt hệ thống hoặc có bộ prompt riêng.
    - **Prompt Library Tools**: Thêm nút "Áp dụng vào dự án" (Import) và "Xóa chỉ dẫn riêng" (Reset) để quản lý cấu hình mượt mà.
    - **Visual Indicators**: Thêm Badge trạng thái trực quan giúp người dùng biết mình đang dùng prompt Hệ thống hay đã tùy chỉnh riêng cho Dự án.
- **Spell-check Refactoring**: Tái cấu trúc lớn và tách biệt hoàn toàn logic soát lỗi (`SpellcheckExecutor`) khỏi dịch thuật để đảm bảo tính độc lập tuyệt đối.
- **UI Localization**: Việt hóa toàn bộ các nút bấm và nhãn trong workspace (Kích thước, Trạng thái, Dịch đã chọn, Soát đã chọn...).
- **Statistics Bar Upgrades**: Tô đậm và bổ sung bộ đếm từ (Word Count) cho tất cả các editor, giúp theo dõi dung lượng văn bản chuyên nghiệp hơn.

## [6.6.2] - 2026-04-22
### Added
- **Premium Tooltips (ⓘ)**: Thêm các biểu tượng trợ giúp cạnh các tùy chọn cấu hình trong tab Cấu hình để giải thích các thông số kỹ thuật (RPM, TPM, Temperature, v.v.).
- **Hover Information**: Logic hiển thị thông tin chi tiết khi người dùng di chuột vào các icon trợ giúp với hiệu ứng glassmorphism mượt mà.

### Changed
- **Unified Configuration**: Hợp nhất toàn bộ API Keys từ `.env` và `API.txt` cũ vào duy nhất `config/API.txt` với cấu trúc phân nhóm `[GEMINI]`, `[OPENAI]`.
- **Backend Refactoring**: Cập nhật logic load/save API keys để hỗ trợ cấu trúc phân nhóm mới, loại bỏ phụ thuộc vào file `.env`.
- **Documentation**: Cập nhật `config/API.txt.example` và xóa bỏ các file cấu hình thừa (`.env`, `.env.example`).

## [6.6.1] - 2026-04-22
### Changed
- **WebUI Consolidation**: Di chuyển toàn bộ thư mục `static/` và `templates/` vào trong package `webui/` để tăng tính module hóa.
- **Flask App Factory**: Đơn giản hóa việc khởi tạo Flask app, tự động nhận diện tài nguyên trong package.

### 🎨 Giao diện & Trải nghiệm (UI/UX)
- **Project Info Modal**: Hợp nhất việc chỉnh sửa thông tin dự án (Tên, Mô tả) và các thao tác quản trị (Lưu trữ, Xóa) vào một Modal duy nhất.
- **Improved Workspace Editor**: 
    - Khắc phục triệt để lỗi không cuộn được trong trình soạn thảo song ngữ.
    - Sửa lỗi mô tả dự án bị cắt ngắn (truncate) trong header.
    - Tối ưu hóa layout `flexbox` để thanh công cụ (Copy, Download, Dịch lại) luôn khả dụng.
- **Smart Cleanup**: Loại bỏ các nút chức năng dư thừa ở Header để làm gọn giao diện làm việc.

## [6.5.0] - 2026-04-15 - Unified 7-Tab UI & Integrated Project Assets

### 🎨 Giao diện & Trải nghiệm (UI/UX)
- **Unified 7-Tab System**: Tái cấu trúc hoàn toàn giao diện làm việc thành 7 thẻ chức năng: *Nội dung gốc, Bản dịch, Chỉ dẫn, Mối quan hệ, Thuật ngữ, Prompt, Tóm tắt*.
- **Robust Flexbox Layout**: Giải quyết triệt để lỗi chồng lấn layout, đảm bảo hiển thị ổn định trên mọi kích thước màn hình.
- **Enhanced Editors**: Khôi phục độ cao tối ưu (500px) cho các vùng nhập liệu đối chiếu, giúp thao tác thuận tiện hơn.
- **AI Integration**: Nút **✨ AI Generate** được tích hợp trực tiếp vào các thẻ Chỉ dẫn, Mối quan hệ, Thuật ngữ và Tóm tắt với khả năng chọn Model linh hoạt.

### 📂 Quản lý Dữ liệu (Dữ liệu & Assets)
- **Project-specific Assets**: Di chuyển toàn bộ dữ liệu hướng dẫn, thuật ngữ và quan hệ nhân vật vào thư mục `assets/` riêng của từng dự án.
- **Guideline Migration**: Hệ thống tự động di chuyển dữ liệu cũ sang cấu trúc mới (`style_guide.txt`, `relationship.txt`, `glossary.txt`, `summary.txt`).
- **Prompt Library Integration**: Hỗ trợ nạp bộ prompt từ thư viện chung và cho phép tùy chỉnh prompt riêng biệt cho mỗi dự án.

### ⚙️ Hệ thống & Backend
- **Safe Tab Switching**: Cơ chế chuyển thẻ mới với Error Handling, đảm bảo ứng dụng không bị treo khi gặp lỗi nạp dữ liệu cục bộ.
- **Backend Refactoring**: Cập nhật API và Helper để hỗ trợ cấu trúc lưu trữ Assets mới.

---

## [6.3.0] - 2026-04-13 - Project Workspace & Translation Modal Refinements

### 📂 Quản lý Dự án (Project Management)
- **Merged File Handling**: File ghép (`merge`) được lưu trực tiếp vào `translated/{slug}.txt` thay vì `output/`, hiển thị trong danh sách file dịch để tiếp tục chỉnh sửa.
- **Simplified Merge**: Tự động ghép tất cả file dịch, không cần chọn thủ công. Loại bỏ popup xác nhận download sau khi merge.

### 🎨 Giao diện & Trải nghiệm (UI/UX)
- **Translated Tab Action Bar**: Thêm thanh công cụ (Token info, Copy, Download, Retranslate) bên dưới editor "Bản dịch" đồng nhất với tab "Nội dung gốc".
- **Tab Renaming**: 
    - "Workspace" → "Nội dung gốc" (Source Content)
    - "Dịch nội dung" → "Dịch lại" (Retranslate)
- **Header Cleanup**: Loại bỏ nút "Upload" và "Chia Chunk" khỏi header "Nội dung gốc".

### ⚡ Translation Modal Improvements
- **Background Translation**: Modal có thể đóng giữa chừng mà tiến trình dịch vẫn tiếp tục ngầm. Cập nhật footer message để thông báo cho người dùng.
- **Auto-Close**: Modal tự động đóng sau 10 giây kể từ khi hoàn tất (áp dụng cho tất cả các loại dịch, không chỉ batch mode).
- **Clean Stats**: Loại bỏ hiển thị thời gian, số đoạn, số ký tự trong modal vì ít giá trị và không chính xác.

### 🛡️ Độ ổn định & Sửa lỗi (Stability & Fixes)
- **Retranslation Logic**: Đảm bảo "Dịch lại" ghi đè file dịch hiện có trong `translated/`.
- **Token Estimate**: Hiển thị token ước tính cho cả tab "Nội dung gốc" và "Bản dịch".

### 📦 Code Cleanup
- Removed `selectedTranslatedFiles` set (không còn cần thiết sau khi merge tự động).
- Removed các hàm không dùng: `toggleTranslatedFile`, `updateSelectAllTranslatedButton`, `selectAllTranslatedFiles`.
- Removed `result-stats` container từ HTML modal.

---

## [6.2.0] - 2026-04-12 - Stability, Logging & UI Restoration

### ✨ Hệ thống Nhật ký (Logging System)
- **Log Viewer**: Thêm tab "Nhật ký" mới cho phép duyệt và xem nội dung các tệp log hệ thống và dự án ngay trên WebUI.
- **Log Parsing**: Tự động phân tích và tô màu các cấp độ log (`[INFO]`, `[WARN]`, `[ERROR]`) để dễ theo dõi.
- **Path Security**: Sửa lỗi "Path không hợp lệ" bằng cách chuẩn hóa việc xử lý đường dẫn log trên backend.

### 🛡️ Độ ổn định & Sửa lỗi (Stability & Fixes)
- **Defensive JS**: Cập nhật `main.js` với cơ chế kiểm tra lỗi "Null Pointer", giúp ứng dụng không bị treo nếu thiếu thành phần giao diện.
- **Port Binding Retry**: Thêm cơ chế tự động thử lại khi khởi động server nếu gặp lỗi "Address already in use", hỗ trợ tốt hơn cho lệnh `uv run`.
- **Infinite Loop Fix**: Khắc phục lỗi lặp vô hạn khi nạp dự án gây treo trình duyệt.

### 🎨 Giao diện & Trải nghiệm (UI/UX)
- **Tab Isolation System**: Thiết kế lại cơ chế chuyển tab bằng class `.active`, loại bỏ hoàn toàn lỗi hiển thị chồng chéo các tab.
- **Improved Scrolling**: Định nghĩa lại layout `.nt-main-bg` giúp thanh cuộn hoạt động chính xác trên mọi thiết bị.
- **Local Assets**: Chuyển sang sử dụng logo Gemini và OpenAI trực tiếp từ thư mục `static/images/` thay vì link online.
- **OpenAI API Visibility**: Hiển thị đầy đủ API Key của OpenAI trong tab cấu hình tương tự như Gemini.
- **Cleanup**: Loại bỏ khối "Project Empty State" không cần thiết và khôi phục các nút chức năng Copy/Download bị mất.

---

## [6.1.0] - 2026-04-11 - Project Archiving & UI Performance

### 📦 Hệ thống Lưu trữ (Project Archiving System)
- **Zip-based Archiving**: Tính năng "Lưu trữ" mới cho phép nén dự án thành file `.zip`, di chuyển vào `workspace/archive` và xóa khỏi thư mục làm việc để giữ workspace gọn gàng.
- **Conflict Handling**: Xử lý xung đột khi lưu trữ (Ghi đè hoặc Tạo bản sao với suffix timestamp).
- **Archive Management**: Tab "Lưu trữ" mới trên Navigation Bar cho phép liệt kê, xóa và **Khôi phục (Restore)** dự án về workspace gốc.

### ⚡ Tối ưu hóa Dashboard Performance
- **Tachyons Card UI**: Chuyển đổi toàn bộ layout sang card-based dùng Tachyons CSS, giảm tải JS và loại bỏ các hiệu ứng gây chậm trình duyệt.
- **Header Monitoring**: 
    - Hover tooltips (title) cho tất cả các chỉ số hệ thống.
    - Thống kê song hành: Dự án (Hoạt động / Lưu trữ) và Cache (Dung lượng / Số tệp).
    - MB-first cache display: Ưu tiên hiển thị dung lượng bộ nhớ đệm.

### 🔄 Hệ thống & Độ ổn định
- **Reliable Restart**: Upgraded mechanism sử dụng `os.execv` (UNIX) kết hợp delay port-release 3s để đảm bảo khởi động lại server không bị treo port.
- **Bug Fixes**: 
    - Sửa lỗi "Method Not Allowed" khi tải file archive.
    - Khắc phục lỗi render danh sách file dự án sau khi chuyển đổi context.
    - Đồng bộ hóa trạng thái "Select All" checkbox trong Project Sources.

### 📂 Tổ chức Tài liệu (Documentation)
- Đưa `CHANGELOG.md`, `README.md`, `ROADMAP.md` ra thư mục gốc.
- Tổng hợp các báo cáo rời rạc thành `REPORTS.md`.
- Dọn dẹp thư mục `docs/`.

---

## [6.0.0-alpha] - 2026-03-17 - Multi-Provider AI & Project Workflow

### 🚀 Phase 1: Multi-Provider AI Integration
- **OpenAI-Compatible API**: Tích hợp OpenAI SDK (`openai>=1.0.0`) hỗ trợ OpenRouter, proxy và các dịch vụ tương thích.
  - `services/openai_client.py`: Sync + Async wrapper tương tự `genai_client.py`
  - `services/ai_provider.py`: Protocol adapter + Factory pattern cho multi-provider
- **Dual-Provider UI**: Tab Cấu hình chia 2 cột nằm ngang (Gemini | OpenAI), radio button chọn 1 trong 2.
- **Template Splitting**: Tách `index.html` monolithic (729 dòng) thành 6 Jinja2 partials (`templates/partials/`).
- **4 API endpoints mới**: `/api/provider` (GET/POST), `/api/openai/models`, `/api/openai/config`.
- **Provider-aware helpers**: 7 functions mới trong `webui/helpers.py`.

### ✨ Phase 2: Project Workflow Tabs Enhancement
- **Genre Field**: Thêm trường thể loại vào project metadata, liên kết với prompt sets.
- **Project Creation Modal**: Thay `prompt()` bằng modal form đẹp với genre selector.
- **Inline Chunk-Size**: Input số ký tự/chunk cạnh nút "Chia Chunk" (để trống = config mặc định).
- **File Upload**: Mở rộng hỗ trợ `.html`, `.epub` ngoài `.txt`, `.md`.

### 📝 Phase 3: Tab Guidelines
- **Guidelines API**: `GET/PUT /api/projects/<slug>/guidelines` – 5 fields (summary, characters, glossary, style_guide, additional_notes).
- **AI Summarize**: `POST /api/projects/<slug>/summarize` – Tự động tóm tắt nội dung sách bằng AI (Gemini/OpenAI).
- **Guidelines Tab UI**: 5 textarea với nút AI Tóm tắt và Lưu Tất cả.

### 📦 Phase 4: Tab Prompts Enhancement
- **Prompt Library Dropdown**: Nạp bộ prompt từ thư viện (Mặc định + các thể loại).
- **Priority Note**: Hiển thị ghi chú ưu tiên prompt dự án > prompt hệ thống.
- **Placeholders**: Thêm placeholder gợi ý cho các textarea prompt.

### 🐛 Bug Fixes & UI Improvements
- **Sidebar Toggle**: Fix lỗi ẩn danh sách dự án không mở rộng cột chính (giờ dùng `w-100-l`).
- **Translation Output**: SSE handler giờ ưu tiên hiển thị text dịch thay vì thông báo đường dẫn file trong textarea.
- **Project Translate Routing**: `startTranslation()` tự động dùng API project nếu đang mở file trong dự án.
- **Summarize Model Selector**: Thêm dropdown chọn model ngay cạnh nút AI Tóm tắt.
- **Summarize Backend**: API `POST /summarize` hỗ trợ nhận parameter `model` tùy chỉnh.

### [6.0.0-beta.1] - 2026-03-19 - Project Sources & AI Config Enhancements

### ✨ Project Sources Improvements
- **Batch Translation**: Nút "Dịch đã chọn" giờ hoạt động và có thể dịch nhiều file cùng lúc.
- **Select All Toggle**: Nút "Chọn hết" trong Project Sources giờ có thể bật/tắt chọn tất cả các file và hiển thị số lượng file đã chọn.
- **File Renaming**: Thêm chức năng đổi tên file (✏️) cho cả file nguồn và file đã dịch. Khi đổi tên file nguồn, file dịch tương ứng (nếu có) cũng sẽ được đổi tên tự động.

### ⚙️ AI Model Configuration & UX Improvements
- **JSON Parse Error Fix**: Khắc phục lỗi `JSON.parse` khi tóm tắt AI bằng cách cải thiện xử lý lỗi phía frontend.
- **Provider-Specific Model Selection**: Tách biệt rõ ràng danh sách model cho Gemini và OpenAI trong cấu hình, tránh nhầm lẫn khi chuyển đổi nhà cung cấp AI.
- **Enhanced Model Information Display**:
  - Hiển thị thông tin chi tiết về model (giới hạn input/output token, giá cả OpenRouter) cho cả Gemini và OpenAI.
  - Các model miễn phí được ưu tiên và đánh dấu bằng 🎁.
  - Các model không khả dụng hoặc cấu hình lỗi sẽ được đánh dấu màu đỏ.
- **Summarize Bug Fix**: Khắc phục lỗi `IsADirectoryError` khi tóm tắt AI nếu thư mục `sources` trống hoặc không có file cụ thể. Giờ đây, nếu không có file cụ thể được chỉ định, tất cả các file trong thư mục `sources` sẽ được gộp lại để tóm tắt.

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `webui/routes/projects.py` | Fix `summarize_project` bug, update `translate_project_file`, add `rename_project_file` |
| `webui/routes/settings.py` | Update `get_models`, `get_model_info` for multi-provider support |
| `services/openai_client.py` | Add `list_models_full` for detailed OpenAI model info |
| `templates/partials/tab_config.html` | Reorganize AI provider blocks, separate model selectors |
| `templates/partials/tab_workspace.html` | Add `id="btn-translate-selected"` |
| `static/js/main.js` | Update model loading/info, selection logic, rename func, translation triggers |

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `services/openai_client.py` | ✨ NEW – OpenAI SDK wrapper |
| `services/ai_provider.py` | ✨ NEW – Adapter pattern |
| `templates/partials/*.html` | ✨ NEW – 6 template partials |
| `templates/index.html` | Tách thành 6 includes |
| `config/app.ini` | +`[PROVIDER]`, +`[OPENAI]` |
| `.env.example` | +`OPENAI_API_KEY` |
| `requirements.txt` | +`openai>=1.0.0` |
| `webui/helpers.py` | 7 provider functions |
| `webui/routes/settings.py` | 4 API endpoints |
| `webui/routes/projects.py` | Genre create/update + Guidelines API + Summarize |
| `static/css/style.css` | Dual-provider grid CSS |
| `static/js/main.js` | Provider switching + project modal + guidelines + prompt library |

---

## [5.0.0-alpha] - 2026-03-01 - Kiến Trúc Lại & Tối Ưu Hóa Tổng Thể

### 🚀 Tái Cấu Trúc Kiến Trúc (Refactoring)
- **Core Pipeline Unification**: Xóa bỏ hoàn toàn hệ thống Plugin (PluginManager, EventBus, ServiceBus) dư thừa. Xây dựng lõi `TranslationExecutor` (`core/executor.py`) quản lý logic dịch thuật nhất quán cho cả CLI (`main.py`) và WebUI (`webui/routes/translation.py`, `projects.py`).
- **Module hóa WebUI**: Chuyển đổi `webui.py` (1820 dòng) thành package `webui/` với các Blueprints:
  - `webui/__init__.py`: Flask App Factory với global state management
  - `webui/helpers.py`: Các hàm tiện ích dùng chung (config, API keys, stats, prompts)
  - `webui/routes/translation.py`: Translation worker, SSE streaming, direct translate
  - `webui/routes/settings.py`: Models, Config, Stats, Cache, Token estimation
  - `webui/routes/prompts.py`: Genre-based prompt management CRUD
  - `webui/routes/projects.py`: Project CRUD, File management, Translation, TM APIs
  - `webui/routes/plugins.py`: EPUB Converter và OCR execution
- **Entry point**: `webui.py` giảm từ 1820 dòng xuống 35 dòng.

### ✨ Tính Năng Mới & Thuật Toán
- **Sentence Aggregation Chunker** (`chunker.py`): Thuật toán mới tách text thành danh sách câu bằng regex multi-language (Trung/Nhật/Hàn/Latin), rồi dồn câu vào chunk — đảm bảo 100% không cắt ngang câu. Giữ `intelligent_chunking()` làm fallback cho câu quá dài.
- **SQLite Checkpoint** (`checkpoint_service.py`): Thay thế JSON bằng SQLite với WAL mode và ACID transactions. Hỗ trợ per-chunk upsert, query nhanh tiến độ không cần load toàn bộ text. API tương thích v4.0 + mới (`init_session`, `save_chunk`, `get_translated_chunks`).
- **Dynamic Glossary Injection** (`glossary_service.py`): Hệ thống lọc thuật ngữ thông minh theo ngữ cảnh từng Chunk. 
  - Sử dụng `GlossaryEntry` với `__slots__` tối ưu bộ nhớ.
  - Cơ chế deduplication O(1) và sắp xếp theo độ dài giảm dần để ưu tiên match thuật ngữ dài trước.
  - Tự động nhúng vào Prompt giúp tiết kiệm Token và tăng độ chính xác của LLM. Khả dụng cho CLI, WebUI và Project-based.
- **Side-by-Side Editor** (`index.html`, `main.js`): Giao diện soát lỗi song ngữ — hiển thị bản gốc (readonly) bên trái và bản dịch (editable) bên phải. Hỗ trợ chỉnh sửa trực tiếp, lưu nhanh, sync scroll, và thống kê ký tự/tỷ lệ dịch real-time.
- **Cải thiện Trải nghiệm Người Dùng (UI/UX)**:
  - Mở rộng kích thước các Form nhập liệu, làm mới Textarea với font chữ to, border bo góc mềm mại hơn.
  - Thay thế toàn bộ hộp thoại cảnh báo `alert()` truyền thống bằng hệ thống **Toast Notifications** mượt mà.
  - Tích hợp tính năng quản lý **API Keys** trực tiếp từ tab Cấu hình (Config) trên WebUI.
- **Upload & Chunk** (`projects.py`, `main.js`): Tải file `.txt` lên dự án và chia chunk trực tiếp từ WebUI. Chunk files được liệt kê trong danh sách nguồn, cho phép sửa và lưu từng chunk riêng lẻ.
- **Robust Fallback**: Cơ chế đánh dấu `<!-- FAILED_CHUNK -->` khi gặp lỗi API thay vì dừng tiến trình.

### 📚 Tài Liệu (Documentation)
- **Roadmap 2026**: Xây dựng lộ trình phát triển chi tiết 3 giai đoạn.
- **Development & Manual**: Tách biệt tài liệu hướng dẫn cho người dùng cuối (`Manual.md`) và lập trình viên (`DEVELOPMENT.md`).

---

## [4.1.0] - Báo cáo cải tiến UI và Fixes

### 🚀 Bug Fixes & Refactoring
- **Sửa Lỗi Chunking**: Giảm `MIN_CHARS_PER_CHUNK` và `MAX_CHARS_PER_CHUNK` trong `config/app.ini` xuống `5000` và `8000` để tránh API tự động cắt ngắn output do vượt quá giới hạn token của LLM. Tối ưu lại điều kiện gom mảnh vụn cuối trong `plugins/translation/chunker.py` (hệ số `1.2` thành `1.1`).
- **Refactor Web UI (PicoCSS)**:
  - Tích hợp chuẩn **PicoCSS Classless** qua thẻ CDN. Rút gọn cấu trúc thẻ HTML sang Semantic (`<article>`, `<section>`, `<header>`).
  - Gỡ bỏ toàn bộ Inline CSS và Inline Javascript khỏi template `templates/index.html`.
  - Tách CSS ra thư mục tĩnh: `static/css/style.css` 
  - Tách logic JS ra thư mục tĩnh: `static/js/main.js`
- **Cache Busting**: Frontend script và styles hiện tại nhận biến tham số version `?v=4.0.6` truyền từ flask render_template để cập nhật cache trình duyệt ngay khi có thay đổi bản build.

Tất cả các thay đổi quan trọng của dự án Content Translator sẽ được ghi nhận tại đây.

---

## [4.0.7] - 2026-02-17 - UI Redesign & Improvements

### UI/UX Improvements
- **Clean Layout**: Thiết kế lại giao diện, gọn gàng hơn
- **Color Indicators**: Chỉ báo màu cho file đã dịch/chờ dịch
- **Two Modes**: 
  - Tab "Chờ dịch": Hiển thị form nhập text gốc + nút dịch
  - Tab "Đã dịch xong": Hiển thị text đã dịch + nút Retranslate/Correction/Both
- **Quick View**: Click vào file để load nội dung vào form
- **Removed Redundant**: Bỏ block "Đã dịch (Output)" ở sidebar
- **Simplified Stats**: Thanh header với thông tin cần thiết

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `templates/index.html` | Complete redesign |

---

## [4.0.6] - 2026-02-17 - Translation Memory & Optimizations

### ✨ Tính năng Mới

**Translation Memory (TM):**
- Dịch vụ TM với fuzzy matching
- Lưu trữ các cặp dịch (source → target)
- Tìm kiếm fuzzy với similarity threshold có thể điều chỉnh
- Tự động học từ các bản dịch đã thực hiện
- N-gram based similarity (Jaccard)
- Export/Import TM
- Thống kê TM (số entries, kích thước)

**API Optimization:**
- Chunk size có thể lên đến 100K chars (đọc từ config)
- Cache check trước khi gọi TM
- TM check cho similarity ≥ 90% trước khi gọi API

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `services/translation_memory.py` | ✨ NEW - Translation Memory service |
| `webui.py` | Thêm TM integration, APIs |

---

## [4.0.5] - 2026-02-17 - Batch Translation & Dynamic Models

### ✨ Tính năng Mới

**Batch Translation:**
- Checkbox để chọn nhiều file cùng lúc
- Nút "Dịch file đã chọn" để dịch hàng loạt
- Tab "Đã dịch xong" hiển thị file trong thư mục done

**File Management:**
- File đã dịch tự động chuyển vào thư mục `workspace/done`
- Chức năng "Dịch lại" cho file đã dịch
- Chức năng "Xem" để xem nội dung file đã dịch
- Di chuyển file từ done về input

**Dynamic Models:**
- Tự động phát hiện models khả dụng từ Google API
- Danh sách models động thay vì hard-code
- Model mặc định từ config

**Input Form:**
- Chunk size có thể nhập tay (input number) thay vì select cố định
- Giá trị mặc định được đọc từ `config/app.ini`

**Thống kê chi tiết:**
- Số từ đã dịch / đang chờ
- Số file input / output / done
- Kích thước cache

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `webui.py` | Thêm batch translate, done folder, dynamic models |
| `templates/index.html` | Checkbox, tabs, dynamic model dropdown |

---

## [4.0.4] - 2026-02-15 - WebUI Enhancements

### ✨ Tính năng WebUI

- **Input Files List**: Liệt kê files trong input, click để load nội dung
- **Cache Priority**: Kiểm tra cache trước khi gọi API, hiển thị số chunks từ cache
- **Download**: Tải file đã dịch về máy (text file)
- **Prompt Editor**: Chỉnh sửa và lưu prompts theo ngôn ngữ
- **Output Files**: Danh sách files đã dịch với link tải

### 🔧 Script Enhancements

- **Auto-merge Small Files**: Tự động gộp files nhỏ để đủ kích thước chunk tối thiểu
- Hàm `merge_small_files()` trong main.py

### 🚀 Fix

- Default port: 7860 (tránh macOS AirPlay conflict)

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `webui.py` | Complete rewrite với tất cả APIs mới |
| `templates/index.html` | UI với file list, prompt editor |
| `main.py` | Thêm merge_small_files() |

---

## [4.0.3] - 2026-02-15 - Web UI & uv Support

### ✨ Tính năng Mới

**Web UI (Flask):**
- Giao diện web đơn giản, tối giản
- Real-time progress với Server-Sent Events (SSE)
- Form cấu hình: model, ngôn ngữ, temperature, chunk size
- Text input trực tiếp (không cần upload file)
- Log console hiển thị quá trình
- Copy kết quả dễ dàng

**uv Support:**
- Thêm `pyproject.toml` cho uv package manager
- Có thể chạy với `uv run python webui.py`
- Optional dependencies: epub, ocr, async, dev

### 📁 Files Mới

| File | Mô tả |
|------|-------|
| `webui.py` | Flask web application |
| `templates/index.html` | Web UI template |
| `pyproject.toml` | uv configuration |

### 📦 Dependencies

Thêm vào `pyproject.toml`:
- `flask>=2.0.0` - Web framework
- `flask-sock` - WebSocket support (future)

---

## [4.0.2] - 2026-02-15 - LSP Fixes & Optimizations

### 🔧 LSP/Type Fixes

- **genai_client.py**: Sửa type hints cho `generation_config`
- **chunker.py**: Fix lỗi `cut_pos` possibly unbound
- **plugin.py**: Fix Optional type cho `context` parameter

### ✨ Tính năng Mới

**Progress Bar (tqdm):**
- Tích hợp `tqdm` vào main loop
- Hiển thị tiến trình dịch cho mỗi file
- Tắt log verbose, giữ lại error messages

**Multi-language Support:**
- Hỗ trợ 3 ngôn ngữ: CN (Chinese), JP (Japanese), KR (Korean)
- Tự động detect ký tự gốc còn sót dựa trên `INPUT_LANG`
- Thêm LANGUAGE_REGEX cho mỗi ngôn ngữ

### 🚀 Optimizations

**Regex Optimization:**
- Đưa `DELIMITERS` lên module-level constant
- Tránh re-create list mỗi lần gọi `_find_best_cut_position()`

**Cache Compression:**
- Thêm gzip compression cho cache files
- File extension: `.pkl.gz` (tương thích ngược với `.pkl`)
- Giảm ~60-80% kích thước cache

**Memory Optimization:**
- Thêm `chunk_text_generator()` - generator-based chunking
- Xử lý chunk-by-chunk thay vì load all vào memory
- Phù hợp cho file lớn (>10MB)

### Files Changed

| File | Thay đổi |
|------|----------|
| `main.py` | Thêm tqdm progress bar |
| `services/genai_client.py` | Fix type hints |
| `services/cache_service.py` | Thêm gzip compression |
| `plugins/translation/chunker.py` | Regex optimization, generator |
| `plugins/translation/plugin.py` | Fix Optional type |
| `plugins/translation/translator.py` | Multi-language support |

---

## [4.0.1] - 2026-02-15 - Rate Limiting & CLI Upgrades

### 🎯 Code Review & Optimizations

**Security:**
- ✅ Thêm `.env` support với `python-dotenv`
- ✅ API keys ưu tiên từ environment variables
- ✅ Fallback về `config/API.txt` (legacy)

**API Rate Limiting:**
- ✅ `GlobalRPMRateLimiter`: Sliding window 60s, giới hạn 15 RPM toàn cục
- ✅ `TokenBudgetLimiter`: Ước tính tokens (2.5 chars/token), giới hạn 1M TPM
- ✅ Fix race condition trong `get_next_available_key()`
- ✅ Fix dead code (old SDK) trong `_call_api_with_original_context`

**CLI & Automation:**
- ✅ `cli.py`: Command-line interface với argparse
- ✅ `CheckpointService`: Lưu/khôi phục tiến trình dịch
- ✅ Auto-save checkpoint sau mỗi chunk
- ✅ Resume từ checkpoint khi bị gián đoạn

**Async Support:**
- ✅ `services/async_genai_client.py`: Async wrapper với aiohttp
- ✅ `AsyncApiManager`: Concurrent requests với semaphore

### 📦 Dependencies

Thêm vào `requirements.txt`:
- `python-dotenv` - .env file support
- `aiohttp` - Async HTTP calls (optional)

### Files Changed

| File | Thay đổi |
|------|----------|
| `main.py` | Thêm .env support |
| `cli.py` | ✨ NEW - CLI với argparse |
| `services/api_service.py` | Thêm RPM + TPM limiters |
| `services/async_genai_client.py` | ✨ NEW - Async support |
| `services/checkpoint_service.py` | ✨ NEW - Checkpoint/Resume |
| `plugins/translation/translator.py` | Fix dead code |
| `requirements.txt` | Thêm python-dotenv, aiohttp |

---

## [4.0.0] - 2026-02-01 - SDK Migration & Core Upgrades

### 🎉 Thay đổi Lớn

**SDK Migration:**
- ✅ Chuyển từ `google-generativeai` sang `google-genai` SDK mới
- ✅ Model mặc định: `gemini-3-flash-preview` (1M context window)
- ✅ Hỗ trợ `thinking_level` parameter (MINIMAL/LOW/MEDIUM/HIGH)
- ✅ Giữ `google-generativeai` làm fallback SDK

**API Rate Limiting (30 keys = 600 RPD):**
- ✅ `AdaptiveRateLimiter`: Progressive backoff 30s→300s
- ✅ Daily quota tracking với auto-reset 0:00 UTC
- ✅ Tối ưu cho 20 RPD/key limit của Google API mới

### ✨ Tính năng Mới (Merge từ Book_translator)

**GenAI Client Wrapper:**
- `services/genai_client.py`: Unified API wrapper cho cả 2 SDK
- Client caching theo API key để giảm overhead
- Auto-fallback khi SDK chính không khả dụng

**Circuit Breaker:**
- `services/circuit_breaker.py`: Ngăn cascade failures
- 3 states: CLOSED → OPEN → HALF_OPEN
- Failure threshold = 10, timeout = 5 phút

**Health Monitor:**
- `services/health_monitor.py`: Giám sát runtime và stall
- Max runtime: 48 giờ
- Stall detection: 30 phút không tiến độ
- Memory usage tracking (psutil optional)

**Emergency Stop:**
- `services/emergency_stop.py`: Thread-safe global stop flag
- Signal handlers (SIGINT, SIGTERM) cho graceful shutdown
- Decorator `@emergency_check` cho functions

### ♻️ Thay đổi

**Cấu hình (`config/app.ini`):**
```ini
[SDK]
SDK = google-genai           # SDK mới (mặc định)
FALLBACK_SDK = google-generativeai

[MODEL]
MODEL = gemini-3-flash-preview
THINKING_LEVEL = MEDIUM
TEMPERATURE = 1.0            # Gemini 3 khuyến nghị

[PROCESSING]
REQUEST_DELAY = 1            # Giảm từ 2s do có nhiều keys
```

**Files đã sửa:**
| File | Thay đổi |
|------|----------|
| `main.py` | v4.0.0 + signal handlers |
| `services/api_service.py` | v4.0.0 + AdaptiveRateLimiter |
| `services/__init__.py` | Export services mới |
| `plugins/translation/translator.py` | v4.0.0 + GenAIClient |
| `requirements.txt` | v4.0.0 + google-genai SDK |

### 📦 Dependencies

Thêm vào `requirements.txt`:
- `google-genai>=1.0.0` (SDK mới, khuyến nghị)
- `psutil` (optional, cho memory monitoring)

---

## [3.0.3] - 2025-12-06 - Plugin OCR

### ✨ Tính năng Mới

**Plugin OCR:**
- Nhận dạng text từ PDF scan và ảnh (JPG, PNG, BMP, TIFF)
- Hỗ trợ đa ngôn ngữ  (Tiếng Việt, Anh, Trung)
- AI cleanup và spell check (tích hợp Gemini API)
- Table extraction với 3 tầng fallback (unstructured → pdfplumber → OpenCV)
- Xuất đa định dạng (DOCX, TXT)

**Chức năng chính:**
- OCR PDF (cả scan và text-based)
- OCR image (JPG, PNG, BMP, TIFF, etc.)
- Auto-rotate dựa trên EXIF và OSD
- Chinese variant detection (giản thể/phồn thể)
- Format preservation trong DOCX output
- Resume capability cho long processing

**Technical:**
- Lazy dependency loading (chỉ install khi cần)
- Tesseract OCR integration
- OCRmyPDF fallback cho PDF phức tạp
- Gemini API cho cleanup và spellcheck
- ServiceBus integration cho config và API management
- Kế thừa từ `ConverterPlugin` interface

**Cấu trúc:**
```
plugins/ocr/
├── __init__.py
├── plugin.py           # ConverterPlugin implementation
└── ocr_engine.py       # Core OCR logic (7659 dòng)
```

### 🗑️ Xóa

- ❌ `ocr_reader.py` (7659 dòng - đã tích hợp vào plugin)
- ❌ `orc.txt` (documentation - không còn cần thiết)

### 📦 Dependencies

Thêm vào `requirements.txt`:
- pytesseract, pdf2image, Pillow (core OCR)
- pdfplumber, PyPDF2, PyMuPDF (PDF processing)
- python-docx, ocrmypdf (output generation)
- unstructured, opencv-python (optional - advanced features)

---

## [3.0.2] - 2025-12-06 - Kiến trúc Plugin Thuần túy

### 🎉 Thay đổi Lớn

**100% Kiến trúc Plugin:**
- Loại bỏ hoàn toàn mã nguồn legacy khỏi nhánh master
- Xóa thư mục `src/` (20 files, 3,280 dòng)
- Xóa `utils/content-analysis/` (8 files, 909 dòng)
- Master giờ là hệ thống plugin thuần túy

**Bảo toàn Legacy:**
- Toàn bộ code v2.7 được lưu trong nhánh `legacy`
- Truy cập bất cứ lúc: `git checkout legacy`

### ✨ Tính năng Mới

**main.py Đơn giản:**
- Viết lại hoàn toàn (200 dòng vs 3000+)
- Quy trình dịch hoàn chỉnh qua plugins
- Không phụ thuộc vào legacy

**Quy trình:**
1. Khởi tạo services (Config, API, Cache)
2. Nạp translation plugin
3. Tìm files trong `workspace/input/`
4. Chia chunk và dịch qua plugin
5. Lưu vào `workspace/output/`

### 🔧 Cải tiến

- Giảm 95% kích thước code (xóa 4,061 dòng)
- Kiến trúc sạch: ServiceBus + EventBus + Plugins
- Dễ bảo trì và mở rộng
- Production-ready với code tối thiểu

### 📦 Cấu trúc

```
novel-translator/ (v3.0.2)
├── main.py              # Quy trình plugin (200 dòng)
├── core/               # Hạ tầng plugin
├── services/           # Services dùng chung
├── plugins/            # Tất cả tính năng
├── config/API.txt      # API keys người dùng
└── workspace/
    ├── input/          # Files nguồn
    └── output/         # Bản dịch
```

---

## [3.0.0] - 2025-12-05 - Kiến trúc Plugin - Tái thiết kế Toàn diện

### 🎉 Thay đổi Lớn (Breaking Changes)

**Kiến trúc mới hoàn toàn:**
- Chuyển từ kiến trúc monolithic sang **plugin-based architecture**
- Tách biệt hoàn toàn code v3.0 (branch master) và v2.x (branch legacy)
- Cấu trúc thư mục mới: `core/`, `services/`, `plugins/`, `config/`, `docs/`

### ✨ Tính năng mới (Features)

#### 1. Core Infrastructure (Hạ tầng Lõi)

**Plugin System:**
- `core/plugin_manager.py`: Quản lý vòng đời plugin (discovery, loading, execution, cleanup)
  - Auto-discovery: Tự động quét và nạp plugins từ thư mục `plugins/`
  - Dependency resolution: Phân tích và sắp xếp thứ tự nạp plugin theo dependencies
  - Error isolation: Lỗi của một plugin không ảnh hưởng đến plugins khác
  - Plugin reload: Hỗ trợ tải lại plugin mà không restart hệ thống

**Service Bus:**
- `core/service_bus.py`: Registry trung tâm cho shared services
  - Quản lý các service: config, api, cache, logger
  - Dependency injection: Plugins truy cập services thông qua ServiceBus
  - Thread-safe: An toàn cho đa luồng

**Event Bus:**
- `core/event_bus.py`: Hệ thống event-driven cho plugin communication
  - Subscribe/emit pattern: Plugins giao tiếp qua events
  - Error isolation: Lỗi của một listener không ảnh hưởng listeners khác
  - Event history: Lưu lịch sử events để debug
  - Wildcard listeners: Subscribe tất cả events với `'*'`

**Plugin Interfaces:**
- `core/interfaces/plugin_base.py`: Interface cơ sở cho tất cả plugins
  - `PluginStatus`: Lifecycle states (UNLOADED, READY, RUNNING, ERROR, DISABLED)
  - `PluginPriority`: Execution priorities (CRITICAL, HIGH, NORMAL, LOW, OPTIONAL)
  - Error handling hooks: `on_error()` method
  - Configuration validation: `validate_config()` method

- `core/interfaces/processor_plugin.py`: Interface cho text processing plugins
  - `process()`: Xử lý text với context support
  - `supports_format()`: Kiểm tra định dạng được hỗ trợ
  - `validate_input()`: Validate input data

- `core/interfaces/converter_plugin.py`: Interface cho format conversion plugins
  - `convert()`: Chuyển đổi định dạng file
  - `get_supported_conversions()`: Danh sách chuyển đổi được hỗ trợ
  - `detect_format()`: Tự động nhận diện định dạng

#### 2. Shared Services (Dịch vụ Dùng chung)

**Config Service:**
- `services/config_service.py`: Quản lý cấu hình tập trung
  - App-level config: `config/app.ini`
  - Plugin-level config: `config/plugins/{plugin_name}.ini`
  - Type-safe getters: Tự động convert kiểu dữ liệu (int, float, bool)
  - Hot reload: Reload config mà không restart

**API Service:**
- `services/api_service.py`: Quản lý Gemini API keys (từ v2.x)
  - `ApiManager`: Xoay vòng API keys thông minh
  - `SmartRateLimiter`: Backoff và cooldown tự động
  - Multi-key support: Hỗ trợ nhiều API keys
  - Thread-safe: An toàn cho đa luồng

**Cache Service:**
- `services/cache_service.py`: Caching kết quả dịch (từ v2.x)
  - MD5-based hashing: Cache key theo hash
  - Smart key: Bao gồm model, temperature, prompts, context, input
  - File-based cache: Lưu cache vào files `.pkl`
  - Thread-safe: An toàn cho đa luồng

#### 3. Plugins (4 plugins được triển khai)

**Translation Plugin:**
- `plugins/translation/`: Core translation engine
  - `chunker.py`: Smart text chunking (từ `smart_chunker.py`)
  - `normalizer.py`: Text normalization (từ `text_normalizer.py`)
  - `translator.py`: Translation logic (từ `translators/core.py`)
  - Hỗ trợ: Context chaining, Chinese detection, preventive translation

**EPUB Converter Plugin:**
- `plugins/epub_converter/`: Format conversion
  - `epub_to_text/`: EPUB → Text/Markdown (từ `utils/epub2md/`)
  - `text_to_epub/`: Text/Markdown → EPUB (từ `utils/text2epub/`)
  - Metadata preservation: Giữ nguyên metadata khi convert

**Consistency Check Plugin:**
- `plugins/consistency_check/`: QA checking
  - `checker.py`: Kiểm tra consistency (từ `translators/consistency.py`)
  - Terminology verification: Kiểm tra thuật ngữ
  - Character names: Kiểm tra tên nhân vật

**Chinese Detector Plugin:**
- `plugins/chinese_detector/`: Quality assurance
  - `detector.py`: Phát hiện ký tự Trung (từ `chinese_detector.py`)
  - File scanning: Quét files có ký tự Trung
  - Chunk scanning: Quét chunks có ký tự Trung

####  4. Main Entry Point

**New Main:**
- `main.py`: Entry point mới với plugin architecture
  - Service initialization: Khởi tạo tất cả services
  - ServiceBus setup: Đăng ký services
  - EventBus setup: Cấu hình event listeners
  - Plugin discovery & loading: Tự động nạp plugins
  - Error handling: Xử lý lỗi toàn diện

**Legacy Backup:**
- `main_legacy.py`: Backup entry point v2.x
  - Giữ nguyên logic cũ để rollback nếu cần

### ♻️ Thay đổi (Changes)

**Cấu trúc Thư mục:**
```
novel-translator/ (v3.0)
├── main.py              # Entry point mới
├── main_legacy.py       # Backup v2.x
├── core/               # Hạ tầng lõi (8 files)
├── services/           # Shared services (6 files)
├── plugins/            # Plugins (24 files)
├── config/            # Cấu hình
│   ├── app.ini
│   └── plugins/
├── docs/              # Tài liệu
│   ├── README.md
│   ├── CHANGELOG.md
│   └── TODO.md
└── workspace/         # Dữ liệu runtime
```

**Removed (Đã loại bỏ):**
- ❌ `src/`: Toàn bộ mã nguồn v2.x (chuyển sang branch legacy)
- ❌ `utils/`: Toàn bộ utilities v2.x (đã tích hợp vào plugins)
- ❌ `references/`: Thư mục tham khảo thừa

**Moved (Di chuyển):**
- 📁 `README.md` → `docs/README.md`
- 📁 `CHANGELOG.md` → `docs/CHANGELOG.md`
- 📁 `TODO.md` → `docs/TODO.md`

### 📊 Thống kê

**Code Statistics:**
| Category | Files | Lines |
|----------|-------|-------|
| Core Infrastructure | 8 | 1,296 |
| Shared Services | 6 | 617 |
| Plugins | 24 | 2,741 |
| Main + Config | 5 | ~500 |
| **TOTAL** | **43** | **~5,150** |

**Git Commits:**
```
b9ab127 - Phase 4: New main.py with plugin system + updated README
7aee0cd - Phase 3: All plugins created
618decd - Phase 2: Shared services
2b74ccc - Phase 1: Core infrastructure
07af835 - Pre-migration checkpoint
```

### ⚡ Cải tiến (Improvements)

**Extensibility (Khả năng mở rộng):**
- ✅ Thêm feature mới: Chỉ cần tạo plugin mới
- ✅ Không cần sửa core code
- ✅ Plugin có thể enable/disable độc lập

**Error Isolation (Cách ly lỗi):**
- ✅ Plugin crash không ảnh hưởng hệ thống
- ✅ Lỗi của listener không ảnh hưởng listeners khác
- ✅ Có thể retry hoặc disable plugin lỗi

**Maintainability (Dễ bảo trì):**
- ✅ Code modular, tách biệt rõ ràng
- ✅ 100% docstrings cho public APIs
- ✅ Type hints đầy đủ
- ✅ Comprehensive logging

**Testing (Khả năng test):**
- ✅ Test từng plugin độc lập
- ✅ Mock services dễ dàng
- ✅ Integration tests rõ ràng

**Performance (Hiệu năng):**
- ✅ Plugin load on-demand
- ✅ Hot reload support
- ✅ Cached services

### 🔧 Migration Guide

**Từ v2.x sang v3.0:**

1. **Checkout branch mới:**
   ```bash
   git checkout master  # v3.0 plugin architecture
   ```

2. **Hoặc quay lại v2.x:**
   ```bash
   git checkout legacy  # v2.x original code
   ```

3. **Run v3.0:**
   ```bash
   python main.py
   ```

4. **Run v2.x:**
   ```bash
   python main_legacy.py
   # Hoặc
   git checkout legacy && python main.py
   ```

### 📝 Lưu ý

**Backward Compatibility:**
- ✅ Code v2.x vẫn hoạt động (branch legacy, main_legacy.py)
- ✅ Config cũ tương thích (`config.ini` → `config/app.ini`)
- ✅ API.txt format không đổi

**Breaking Changes:**
- ⚠️ Import paths thay đổi (từ `src.*` sang `core.*`, `services.*`, `plugins.*`)
- ⚠️ Workflow code cần viết lại để dùng plugins
- ⚠️ Custom modifications cần port sang plugin

**Recommendations:**
- 💡 Test kỹ trước khi deploy production
- 💡 Giữ branch legacy để rollback
- 💡 Đọc `docs/README.md` để hiểu plugin architecture

### 🎯 Future Work

**Planned Enhancements:**
- [ ] Complete workflow integration using plugins
- [ ] Unit tests cho core components
- [ ] Integration tests
- [ ] Plugin development documentation
- [ ] Performance benchmarks
- [ ] Additional plugins (PDF converter, Web UI, etc.)

---

## Lịch sử v2.x

*Xem branch `legacy` hoặc file `docs/CHANGELOG.md` trong branch đó để xem lịch sử đầy đủ v2.x*

Các phiên bản chính:
- v2.8.0: Tối ưu sửa lỗi ký tự Trung (parallel correction)
- v2.7.0: Cache key nâng cấp + GeminiProjectFileManager
- v2.6.3: Mở rộng regex phát hiện ký tự Trung
- v2.6.0: Auto-retry chunks lỗi + Verification mode
- v2.5.1: Translation Guidelines system
- v2.4.1: Statistics + Text normalization
- v2.0.0: Tái cấu trúc lớn sang src/
- v1.x: Các phiên bản đầu tiên

---

**Version:** 3.0.0  
**Date:** 2025-12-05  
**Architecture:** Plugin-based with ServiceBus and EventBus  
**Author:** Narga
