# Roadmap - Novel Translator

## Hoàn thành

### v8.23.0 (2026-08-11)
- [x] 💾 **Lưu trữ Tác vụ Nền SQLite TaskStore (`tasks.db`)**: Nâng cấp `TaskRegistry` từ RAM sang SQLite store (`TaskStore`), tự động lưu trạng thái tác vụ, tiến trình chunk và lịch sử event SSE xuống đĩa.
- [x] 🔄 **Tự động Quét & Khôi phục Tác vụ khi Server Restart (`scan_and_recover`)**: Phát hiện các checkpoint SQLite và tác vụ chưa hoàn tất khi máy khởi động lại hoặc sau khi OS sleep/crash, tự động chuyển về trạng thái `resumable` hoặc `paused`.
- [x] 🏷️ **Checkpoint Identity & Project Slug Mapping**: Lưu `project_slug` trực tiếp vào checkpoint identity để tự động liên kết checkpoint về đúng dự án gốc.
- [x] 🐛 **Vá lỗi UI Tiến trình Modal (TDZ) & Stream Event SSE**: Sửa lỗi `ReferenceError: Cannot access 'btnResume' before initialization` trong `translation-worker.js`, bổ sung `jsonify` bị thiếu và cập nhật ngắt kết nối SSE khi task chuyển về trạng thái `resumable`/`paused`.
- [x] 🧪 **Bộ Kiểm thử Unit Test cho SQLite TaskStore**: Thêm unit test suite `test_task_store.py` và `test_task_registry_persistence.py` kiểm thử toàn diện luồng lưu trữ và quét khôi phục tác vụ.

### v8.22.0 (2026-08-08)
- [x] 📦 **Di chuyển hoàn toàn Chia/Ghép tập tin vào Converter Tool**: Di chuyển logic Chia (`split_files`) và Ghép (`merge_files`) từ `projects.py` vào service `plugins/epub_converter/services/file_operations.py`.
- [x] 📄 **Hỗ trợ 7 định dạng mở rộng**: Cho phép chia/ghép trên `.md`, `.txt`, `.html`, `.htm`, `.xhtml`, `.json`, `.csv`.
- [x] 🧩 **Ghép HTML nâng cao với BeautifulSoup**: Trích xuất nội dung `<body>` ghép vào file HTML gốc, bảo toàn Doctype, HTML, Head & Style wrapper (`_merge_html_bodies`).
- [x] ✂️ **Chunker Boundary Policy**: Mở rộng `process_text_for_chunking` với parameter `boundary_mode` (`document`, `line`, `legacy`) giúp phân chia văn bản theo chương/heading và paragraph hoàn chỉnh.
- [x] 🛡️ **Chuẩn hóa Path Traversal Guard**: Cập nhật `_safe_project_file` trong `webui/routes/plugins.py` trả về `Path | None` độc lập với kiểm tra sự tồn tại file.
- [x] 🎨 **Cải tiến UX Tab Converter**: Phân nhóm 6 nút thao tác (4 dồn trái, 2 dồn phải với separator `|`), đổi màu phân biệt, cấu hình ô nhập `max_chars` lấy mặc định hệ thống từ `/api/config` và ẩn nút spinner.
- [x] 🐛 **Khắc phục lỗi `UnboundLocalError` scope**: Khắc phục triệt để lỗi biến `delete_source`, `section`, `filenames` do bị gán trùng lặp trong closure function `_run()`.
- [x] 🛡️ **Frontend Guard JSON.parse**: Bổ sung `if (!r.ok) throw ...` cho 46 vị trí `fetch()` trên 8 module JavaScript chính (`api-client.js`, `editor-component.js`, `provider-manager.js`, `translation-worker.js`, `prompt-manager.js`, `converter-tool-plugin.js`, `project-manager.js`, `doc-manager.js`, `ui-helpers.js`) và backend Flask error handlers trong `webui/__init__.py`.
- [x] 🧪 **Unit Test Suite**: Bổ sung `tests/unit/test_file_operations.py` phủ 100% test case cho 7 suffixes, HTML body merge, path traversal guard và safe atomic write.

### v8.21.0 (2026-08-05)
- [x] 🤖 **Tác vụ AI Thông tin dự án chạy nền**: Chuyển `/api/projects/<slug>/summarize` từ sync sang task-based, trả `202 Accepted` + `job_id` ngay, worker chạy thread nền.
- [x] 📊 **SSE Progress realtime**: Worker phát lifecycle events `started` → `loading_source` → `loading_prompt` → `planning` → `extracting` → `merging` → `synthesizing` → `validating` → `saving` → `complete`.
- [x] 📈 **Phân tích file lớn tự động (map-reduce)**: Tự động chọn `single_request` hoặc `map_reduce` dựa trên context budget; chia theo boundary `chapter/heading > paragraph > sentence`.
- [x] 🔄 **Retry & Cancel tối thiểu**: Tối đa 2 retry cho lỗi tạm thời; hủy an toàn qua `/api/tasks/<job_id>/cancel` kiểm tra trước mỗi phần.
- [x] 💾 **Ghi asset an toàn**: Áp dụng `_atomic_write_text` (`os.replace` từ tmp) cho asset output.
- [x] 🛡️ **Đọc nguồn an toàn**: Thay `errors="ignore"` bằng xử lý tường minh `UnicodeDecodeError`; file lỗi encoding tạo task `failed` rõ ràng.
- [x] 🎨 **UI Tab Thông tin cập nhật**: `aiGenerateFromInfoTab()` và `aiGenerateContent()` kết nối SSE, hiển thị phase/percent/log realtime, chống double-submit, tải kết quả từ asset sau complete.
- [x] 📝 **Prompt mặc định cải tiến**: Cập nhật 4 prompt (`summary`, `relationship`, `glossary`, `style_guide`) với `PART_ID`, `evidence`, yêu cầu coverage toàn văn.

### v8.20.0 (2026-08-02)
- [x] 🔍 **Chuẩn hóa Portable Markdown Regex v1**: Thống nhất cú pháp Regex (ECMAScript/Python) ở cả Frontend (WebUI Editor) và Backend (Python `re` helper), tự động chuẩn hóa ngắt dòng `CRLF -> LF`.
- [x] 🔄 **Adapter Cú pháp Replacement `$1`**: Chuyển đổi tự động cú pháp back-reference từ `$1`, `$2` ở UI sang `\g<1>`, `\g<2>` của Python `re.sub()`.
- [x] 👁️ **API Dry-Run Preview (`replace-preview`)**: Bổ sung endpoint `POST /api/projects/<slug>/replace-preview` xem trước số lượng kết quả và file bị ảnh hưởng toàn bộ dự án mà không thực hiện ghi đĩa.
- [x] 🛡️ **Nút Chạy thử & Guard UI Modal**: Đưa nút **Chạy thử** vào modal Search & Replace, bắt buộc người dùng Chạy thử thành công trước khi Thay tất cả cho phạm vi "Tất cả tập tin". Tự động invalidate preview khi đổi từ khóa, cờ, phạm vi hoặc khi file bị sửa.
- [x] 📚 **Hướng dẫn Regex & Quy trình Chạy thử trong Document**: Cập nhật `docs/MANUAL.md` hướng dẫn cú pháp portable regex và quy trình 3 bước Chạy thử an toàn.
- [x] 🧪 **Bộ Unit Tests Regex**: Bổ sung `tests/unit/test_batch_regex.py` kiểm thử toàn diện compile, adapter `$1` -> `\g<1>`, đếm group, replacement, và zero-width match.

### v8.19.0 (2026-08-02)
- [x] 📦 **Tái cấu trúc EPUB sang OEBPS chuẩn Sigil**: `mimetype` → `META-INF/container.xml` → `OEBPS/Text/`, `OEBPS/Images/` rỗng, `OEBPS/Styles/` rỗng, `OEBPS/Fonts/` rỗng, `OEBPS/content.opf` tối thiểu. Bỏ `nav.xhtml` và `titlepage.xhtml` — phần mềm biên tập (Sigil/Calibre) tự tạo.
- [x] 💾 **Ghi EPUB atomic**: `zipfile` ra temp file rồi `os.replace`, self-check mimetype trước khi commit. Bản EPUB cũ được thay thế chỉ khi bản mới hoàn chỉnh.
- [x] 🔗 **Link stylesheet tự động đúng độ sâu**: thư mục con của section được giữ nguyên trong `Text/`, href `../Styles/styles.css` tính theo depth.
- [x] ⚠️ **Frontend nhận biết status `partial`**: `converter-tool-plugin.js` hiển thị đúng số file thành công/lỗi khi batch có partial failure (trước đây chờ vô hạn).
- [x] 🧪 **Mở rộng test suite EPUB**: bao phủ cấu trúc OEBPS, subdirectory preservation, thư mục ảnh rỗng, metadata escaping.

### v8.18.0 (2026-08-01)
- [x] 🌐 **Tích hợp EndpointPolicy**: Hỗ trợ chuẩn hóa Cloudflare/Vercel Gateway và Direct API (Google/OpenAI) qua policy.
- [x] 🛡️ **Refactor API Consumers**: Mọi entry point nay dùng chung `ProviderService` thay vì gọi key trực tiếp, bảo vệ config.
- [x] 💾 **Checkpoint Identity Cứng**: Yêu cầu trùng khớp `provider_kind`, model, chunk_size, hash file để resume, tránh sai lệch.
- [x] 📚 **Translation Memory theo Hệ Sinh Thái**: Cách ly cache TM dựa trên `provider_kind`, ngăn lẫn lộn Google và OpenAI.
- [x] ⏱️ **Rate Limiter Động**: `AdaptiveRateLimiter` hỗ trợ limit tùy biến dựa vào config provider (VD: Gemini 15 RPM, OpenAI 20 RPM).
- [x] ☁️ **Giao diện & Bộ lọc Model Cloudflare Workers AI**: Thêm thanh lọc model 1 hàng ngang với từ khóa, chế độ Bao gồm/Loại trừ, icon 🔖, 🔄 và link tài liệu Cloudflare Models.

### v8.17.0 (2026-07-31)
- [x] 🖼️ **Bảo toàn Alt Text Ảnh**: Sửa `post_clean()` trong `source_normalizer.py` giữ nguyên thuộc tính `![alt](url)` của ảnh khi chuyển đổi sang Markdown.
- [x] 📦 **Tích hợp Standard `markdown` Package**: Chuyển đổi Markdown → HTML dùng gói `markdown` chuẩn Python hỗ trợ đầy đủ các extension (`tables`, `fenced_code`, ...).
- [x] 💾 **Ghi đĩa Nguyên tử & Safe Overwrite**: Áp dụng `_atomic_write` (ghi ra tmpfile rồi `os.replace`) và `_reject_in_place_overwrite` chống hỏng file và ghi đè trùng nguồn.
- [x] 📊 **Báo cáo Trạng thái Batch Converter**: Cập nhật route backend phân loại chính xác trạng thái `done`, `partial`, và `error` kèm `failed_files`.
- [x] 🧪 **Bộ Kiểm thử Tự động Chuyển đổi**: Bổ sung 2 test suite `test_html_to_markdown.py` và `test_markdown_to_html.py` nghiệm thu toàn diện luồng converter.

### v8.16.0 (2026-07-31)
- [x] 🎯 **Hoàn thiện Sync Scroll & Reset Editor View**: Triển khai `_resetEditorView(elementId)` reset cuộn/con trỏ về đầu dòng và `setupSyncScroll` dùng `requestAnimationFrame` + re-entry guard cho cả 2 workspace Dịch thuật và Soát lỗi.
- [x] 🔌 **Nối tùy chọn `delete_source` Converter UI**: Đọc `#converter-tool-delete-source` checkbox và gửi trường `delete_source` trong payload request tới backend API.
- [x] 🔍 **Khắc phục Race Condition Search & Replace**: `replaceAll()` chờ thao tác `saveActiveFile()` hoàn tất trước khi gọi API `replace-all`.
- [x] 🔄 **Đồng bộ File Lifecycle khi Refresh Dự án**: Kiểm tra sự tồn tại của file đang mở trong `openProject()` / `refreshProjectFiles()`, tự động dọn sạch editor nếu file bị xóa.
- [x] 🧪 **Cập nhật Unit Test Suite cho Spellcheck Migration**: Migrate test suite `test_helpers.py` và `test_spellcheck_provider.py` theo canonical engine `TranslationExecutor.spellcheck_text`.
- [x] 🧹 **Dọn dẹp & Tổng hợp tài liệu `docs/wip/`**: Đổi tên các file kế hoạch audit hoàn thành sang `del_`, cập nhật `del_DONE_TASKS.md` và `del_PENDING_TASKS.md`.

### v8.15.0 (2026-07-31)
- [x] ⚡ Hợp nhất luồng Soát lỗi AI vào `TranslationExecutor` (`core/executor.py`), tái sử dụng 100% cơ sở hạ tầng dịch thuật và dọn dẹp 2 module thừa (`spellcheck_executor.py`, `spellchecker.py`)
- [x] 🔌 Bổ sung tùy chọn xóa file nguồn sau khi chuyển đổi `MD ↔ HTML` và tự động dọn dẹp các tệp HTML trung gian khi xuất `MD → EPUB 3`
- [x] 🔍 Nâng cấp API Search & Replace đệ quy toàn bộ dự án (`search-all`, `replace-all` qua `rglob("*")`), tương thích xuống dòng Windows CRLF (`\r\n`)
- [x] 🎯 Tối ưu hóa UI Editor: Tự động cuộn/đặt con trỏ về đầu dòng khi mở file, sync scroll 2 bên không kẹt focus, nút Retranslate force retranslate
- [x] 🧹 Dọn dẹp tài liệu `docs/wip/`: Hợp nhất kế hoạch vào `del_plan_2026-07-31_merged_technical_report.md`, tổng hợp `del_DONE_TASKS.md` & `del_PENDING_TASKS.md`
- [x] 🛡️ Cập nhật `.gitignore` bổ sung các thư mục tạm `.kiro/` phát sinh từ IDE

### v8.14.0 (2026-07-29)
- [x] 🎯 Reset con trỏ và vị trí cuộn về dòng đầu tiên (`scrollTop = 0`, `setSelectionRange(0, 0)`) mỗi khi nạp file mới vào Editor
- [x] 🔄 Đồng bộ cuộn 2 bên (Sync Scroll) dùng cờ reentry guard kết hợp `requestAnimationFrame` cho tab Dịch thuật và Soát lỗi
- [x] ⚡ Hợp nhất luồng Soát lỗi AI vào `TranslationExecutor` (`core/executor.py`), tái sử dụng 100% cơ sở hạ tầng dịch thuật
- [x] 🗑️ Xóa bỏ triệt để 2 module thừa `core/spellcheck_executor.py` và `plugins/spellcheck/spellchecker.py`
- [x] 🧹 Tự động xóa các file `.html` trung gian và thư mục tạm `temp_html` sau khi đóng gói `MD → EPUB 3`
- [x] 🔄 Đồng bộ làm mới dự án và dọn dẹp nội dung editor khi xóa file đang mở trong `ProjectManager`

### v8.13.0 (2026-07-29)
- [x] 🐛 Sửa lỗi Spellcheck Worker (`NameError` và thiếu `folder_type` khi soát lỗi file dịch)
- [x] ⬆️ Di chuyển thông tin tập tin (ký tự, từ, token) lên phía bên phải Header Workspace
- [x] 🗑️ Loại bỏ hoàn toàn khối chân trang (Bottom Bar) và checkbox "Dịch lại từ đầu", tăng chiều cao khu vực làm việc
- [x] 🔄 Thêm nút Icon "Dịch lại từ đầu" (`#btn-retranslate-file`) force retranslate cho 1 file đang mở
- [x] 🎨 Chuẩn hóa Row Highlight: gán ngay class `.active` khi click file, giữ nguyên màu khi rê chuột hover
- [x] 🔍 Nâng cấp Tìm kiếm & Thay thế: quét đệ quy mọi định dạng văn bản (`.md`, `.html`, `.xhtml`, `.txt`), xử lý xuống dòng Windows CRLF
- [x] 📊 Bổ sung API `search-all` thống kê số kết quả và số file khớp trước khi thay thế toàn bộ

### v8.12.0 (2026-07-28)
- [x] 🔌 Tích hợp tính năng chuyển đổi trực tiếp `MD -> EPUB 3` vào plugin Converter Tool
- [x] ➕ Nút bấm `MD → EPUB 3` mới trên UI tab Converter, tự động chạy liên hoàn MD -> HTML -> EPUB 3
- [x] 🛡️ Lọc file không phải `.md` một cách thông minh, chỉ ghi log cảnh báo và không làm lỗi cả tiến trình
- [x] 📦 Bảo vệ tính nguyên vẹn của Service Layer, thực hiện lắp ghép luồng (orchestration) tại routing layer

### v8.11.0 (2026-07-28)
- [x] 🔄 Đồng bộ Modal tiến trình dịch và bộ đếm Tasks counter
- [x] 💾 Lưu trữ trạng thái tác vụ local (`_activeJobId`, `_lastViewedJobId`, `_taskStateByJob`) không mất log và phần trăm khi ẩn modal
- [x] 🚪 Cho phép ẩn modal tiến trình ngầm (click overlay/Escape) thay vì tắt hẳn tác vụ đang chạy
- [x] ⚡ Optimistic update: tăng/giảm counter Tasks ngay lập tức trên header khi bấm dịch
- [x] 👆 Pill Tasks trên Header luôn clickable để khôi phục modal tiến trình hoặc xem lại log tác vụ gần nhất
- [x] 📊 Nâng cấp Backend TaskRegistry bổ sung các trường thông tin phong phú phục vụ rehydrate trạng thái

### v8.10.0 (2026-07-28)
- [x] 🎨 Tái cấu trúc giao diện Trang Dự án thành Grid Card co giãn linh động (3 cột desktop)
- [x] 📦 Chuyển form Tạo dự án mới thành Modalbox giữa màn hình, tự động đóng sau khi khởi tạo thành công
- [x] ➕ Card nét đứt "+ Tạo dự án mới" ở cuối Grid làm shortcut mở nhanh modalbox
- [x] 📊 Cải tiến Project Card: Thống kê tỉ lệ `[đã dịch]/[nguồn]`, SVG icon màu riêng biệt cho từng hành động, Progress Bar động và chấm trạng thái đổi màu linh hoạt
- [x] 🐛 Sửa lỗi sập/vỡ layout grid co về hàng dọc (thêm `w-100` và `display: grid !important` trên container)
- [x] 🔄 Sửa lỗi nút Refresh bị đổi thành chữ "Làm mới" sau khi click bằng cách giữ nguyên SVG icon trong JS loading callback

### v8.9.0 (2026-07-27)
- [x] 🧠 Sửa thuật toán Smart Batching (loại bỏ prompt instruction overhead khỏi content size limit check)
- [x] 🐛 Sửa lỗi Bug A & C: Delimiter overhead cho file đầu tiên (index 0) của mỗi batch được tính chính xác
- [x] 📋 Bổ sung log tổng quan batch plan trước khi bắt đầu dịch (`📦 Batch plan [N/M]`)
- [x] 📚 Chuẩn hóa quy định viết Kế hoạch thực thi AI Model (AI-Executable Plan) dạng diff chuẩn vào `DEVELOPMENT.md`

### v8.8.0 (2026-07-27)
- [x] 🔄 Nâng cấp hệ thống tiến trình dịch song song/ngầm dùng Task Registry & Job ID
- [x] 🐛 Sửa lỗi dịch 1 file nhỏ bị bỏ qua trong Smart Batching
- [x] 🗑️ Tự động dọn dẹp các tập tin batch tạm thời sau khi hoàn tất
- [x] 🔀 Đảm bảo sắp xếp danh sách tập tin theo thứ tự tự nhiên
- [x] 👆 Thêm tính năng chọn nhiều file bằng Shift + Click checkbox
- [x] 🎨 Thiết kế lại giao diện nút Làm mới & Đặt lại bộ nhớ dịch ở Workspace Header (2 nút trên dưới, nowrap, w-100)

### v8.7.0 (2026-07-15)
- [x] 🧹 Dọn dẹp JS chết trong `ui-helpers.js`
- [x] 🧠 Triển khai Smart Batching tối ưu số lượng request lên AI model
- [x] 🧪 Bổ sung bộ kiểm thử Unit Tests cho cơ chế Smart Batching

### v8.6.0 (2026-07-13)
- [x] 🔄 Rebuild plugin: EPUB Converter → "Công cụ chuyển đổi" (Converter Tool)
- [x] 📝 2 tác vụ: HTML→Markdown, Markdown→HTML (self-contained, không phụ thuộc thư viện markdown)
- [x] 🗑️ Xoá route cũ `/api/projects/<slug>/convert-markdown` + JS dead code
- [x] 🐛 Sửa lỗi 1: import sai `services.text_converter` → relative import
- [x] 🐛 Sửa lỗi 2: trùng giao diện editor (wrapper x-show cho editor panels)
- [x] 🐛 Sửa lỗi 3: `relative_to` path không đồng nhất (resolve cả 2 vế)
- [x] 🐛 Sửa lỗi 4: auto-switch tab sau convert (isSameProject guard + refreshProjectFiles)
- [x] 🛡️ `_safe_project_file()` chống path traversal trong task converter
- [x] 🎯 Đồng bộ UI dùng `switchPmFileTab` thay render riêng lẻ
- [x] 🔗 Tác vụ `create_epub` + endpoint `GET .../download/<path>` tải EPUB
- [x] 🔄 Link tải EPUB ngay trên thông báo hoàn tất canh phải
- [x] 🔤 Đổi tên nút tác vụ: `.MD → HTML` / `HTML → .MD`

### v8.5.0 (2026-07-13)
- [x] 🔍 Bộ lọc File List: sort theo tên/định dạng, tăng/giảm, lọc keyword real-time
- [x] ⚙️ Cấu hình đường dẫn quét tài liệu (config panel trong sidebar Tab Tài liệu)
- [x] 🔎 Tìm kiếm nhanh danh sách tài liệu
- [x] 🔒 Phân quyền truy cập tài liệu theo cấu hình đường dẫn

### v8.4.0 (2026-07-12)
- [x] 📄 Tích hợp Tab Tài liệu dự án (trình duyệt đọc đệ quy, cache dữ liệu)
- [x] 🔒 Bảo mật chống Path Traversal cho file reader API
- [x] 🔌 Tự động lưu trữ offline toàn bộ các thư viện CSS/JS (Tachyons, Marked.js)
- [x] 💡 Phục hồi & Tinh chỉnh trợ giúp Chỉ dẫn AI (Placeholders cleanup)

### v8.3.0 (2026-07-12) — Dọn dẹp over-engineering
- [x] Xóa 7 file services chết (async_genai_client, health_monitor, circuit_breaker, statistics_service, monitoring_service, file_service, io_service)
- [x] Xóa dead code trong file sống (AsyncOpenAIClient, SmartRateLimiter, TokenBudgetLimiter, wait_for_emergency_clear, emergency_check, ChunkTranslationMemory)
- [x] Xóa 4 thư mục backend rỗng + `requirements.txt` + deps `psutil`/`aiohttp`
- [x] Migrate `main.py` → `AppConfigService`, xóa `config_service.py` (duplicate)
- [x] Dọn `services/__init__.py` barrel export

### v8.2.0 (2026-07-11)
- [x] 🔍 Tìm kiếm & Thay thế nâng cao (3 chế độ: normal, case-sensitive, regex)
- [x] 💾 Nút Lưu file nguồn (PUT `/api/projects/.../file/sources/...`)
- [x] 🔄 Làm mới Workspace (nút toolbar duy nhất, reload toàn bộ)
- [x] ✏️ Đổi tên dự án (rename slug + thư mục trên đĩa)
- [x] Sửa AutoSave sai editor ID (`result-text` → `pm-result-text`)
- [x] Sửa `saveChunkTranslation` lấy đúng textarea
- [x] Sửa Tải về 404 (thay route backend bằng Blob download)

### v8.1.0 (2026-07-11)
- [x] Prompt UI đại tu: editor 2 cột + tab-style + import per-tab
- [x] Hợp nhất path thư viện prompt: `workspace/prompts/library/` → `workspace/prompts/`
- [x] Xoá route reset prompt + `PromptService.reset_project_prompts()`
- [x] Dọn route prompt trùng trong `projects.py` (chuyển hết sang `prompts.py`)
- [x] Modal tạo/sửa thông tin bộ prompt (Tên + Mô tả)
- [x] Batch rename hoạt động trên cả 3 mini-tab (Nguồn, Dịch, Soát lỗi)
- [x] Xoá badge trạng thái prompt, bỏ nút "Xóa riêng" (reset)

### v8.0.0 (2026-07-10)
- [x] Issue 1: Sửa thông tin dự án không cập nhật danh sách (priority `name > book_title`)
- [x] Issue 8: Thống nhất nút Info (chỉ giữ ở danh sách dự án)
- [x] Issue 5+6: Xóa Genre + Viết lại Prompt Subsystem (Library + Project copy)
- [x] Issue 3: Nút dừng tiến trình dịch (cancel state, endpoint, frontend)
- [x] Issue 4: Config model validation (validate thuộc provider type)
- [x] Issue 2: Toolbar refactor (nút Đổi tên hàng loạt)
- [x] Issue 7: Đổi tên hàng loạt (pattern `{N}`, zero-pad, batch endpoint)

### v7.9.0 (2026-07-10)
- [x] Tiền xử lý HTML/XHTML → Markdown offline
- [x] Cải tiến UI workspace (batch convert, deselect, status bar)

### v7.8.0 (2026-06-16)
- [x] Tái cấu trúc Plugin Navigation
- [x] Quản lý Plugin tập trung

---


## Đang phát triển / Sắp tới (Kế hoạch dọn dẹp & Tối ưu hóa)

### Việc cần làm ngay (Mức độ ưu tiên cao)
- [ ] ⏳ **Kiểm soát `empty_response` & Request Budget**: Giới hạn retry budget cho streak response rỗng trong `translator.py`, gán status/cooldown phù hợp cho key thay vì xoay key `keys * 3`.
- [ ] ⏳ **Đảm bảo tính toàn vẹn trạng thái Terminal của Batch Job**: Đồng bộ trạng thái kết thúc `completed`, `partial_failed`, `failed` giữa `TranslateProjectFilesUseCase` và `TaskRegistry` worker.
- [ ] ⏳ **Chuẩn hóa Chunking 2 tầng & Fallback Batch Parse**: Tối ưu hóa Virtual Chunk size và ngăn chặn fallback dịch lại toàn bộ file.

### Việc cần làm tiếp theo (Mức độ ưu tiên trung bình)
- [ ] 🗑️ Gỡ bỏ các dependencies thừa (`python-dotenv`, `flask-sock`, `ebooklib`, `lxml`) trong `pyproject.toml`
- [ ] ⚙️ Dọn sạch các key cấu hình chết (`THINKING_LEVEL`, `REQUEST_DELAY`, `ARCHIVE_DIR_NAME`, `CACHE_DIR`, `ENABLE_CACHE`) và loại bỏ `config/API.txt.example` đã lỗi thời
- [ ] 🔗 Inline các hàm trong `file_utils.py` trực tiếp vào call site (thay thế bằng `Path` API chuẩn của Python)
- [ ] 📂 Tích hợp `ModelCatalogService` thay thế danh sách model hardcoded trong `webui/helpers.py`
- [ ] 🧹 Thu gọn mã nguồn (Shrink) bằng cách xóa bỏ các hàm/phương thức chết trong `checkpoint_service.py`, `emergency_stop.py`, `translation_memory.py` và `webui_progress_bridge.py`
- [ ] 🧠 Gom logic `_get_client()` trùng lặp trong hệ thống thành một OpenAI-compatible shared helper chung

### Kế hoạch dài hạn
- [ ] 📦 Tối ưu hóa frontend bundle (tree-shaking, code splitting)
- [ ] 🔄 Tải xuất dự án trực tiếp sang EPUB/PDF
- [ ] ⚡ Cấu trúc cache layer cho backend
- [ ] 🔌 Chuyển SSE sang WebSocket cho đồng bộ real-time progress

---

## Đã hoãn (YAGNI)
- Per-project model override (quyết định sau khi có nhu cầu thực tế)
- Migration script từ genre sang library (không cần - dự án chưa có dữ liệu cũ)
- Collaboration features (multi-user) — quá sớm

### Đã hoãn từ audit HTML→Markdown→EPUB (2026-08-01)
- [ ] 🖼️ **Asset resolver cho ảnh nội dung trong EPUB** (`Images/`/`Fonts/`): hiện tại chỉ tạo thư mục rỗng. Chỉ làm khi cần đóng gói EPUB hoàn chỉnh không cần biên tập manual.
- [ ] 🔗 **Link resolver (rewrite `href` nội bộ + `#fragment`)**: hiện tại chỉ đổi suffix `.html`→`.xhtml`, không rewrite base path. Chỉ làm khi chấp nhận auto-rewrite link.
- [ ] 📝 **Nav doc (`nav.xhtml`) và titlepage**: bỏ hoàn toàn, phần mềm biên tập tự tạo khi import. Chỉ làm khi cần EPUB tự khép kín không cần Sigil.
- [ ] 🖼️ **Cover image**: hiện không tự copy cover vào ảnh; người dùng đặt trong `assets/cover.*`. Chỉ làm khi cần cover tự động.
- [ ] 🔤 **Footnote semantic nâng cao** (`epub:type="noteref"`, ID unique cross-chapter): hiện tại `footnotes` extension render thành chapter-end list, ID có thể trùng giữa chương. Chỉ làm khi cần footnote EPUB-native.
- [ ] 🔍 **epubcheck/xmllint validation**: self-check đã đủ cho dùng-cá-nhân (mimetype, XML parse, manifest refs). Chỉ thêm khi cần xác thực chuẩn strict trước khi phát hành ra ngoài.
- [ ] 🚫 **Strikethrough `~~text~~`**: hiếm dùng. Khi cần, thêm extension `pymdownx.tilde` hoặc ánh xạ sang `<del>`.

