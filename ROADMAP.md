# Roadmap - Novel Translator

## Hoàn thành

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
- [ ] 🗑️ Gỡ bỏ các dependencies thừa (`python-dotenv`, `flask-sock`, `ebooklib`, `lxml`) trong `pyproject.toml`
- [ ] ⚙️ Dọn sạch các key cấu hình chết (`THINKING_LEVEL`, `REQUEST_DELAY`, `ARCHIVE_DIR_NAME`, `CACHE_DIR`, `ENABLE_CACHE`) và loại bỏ `config/API.txt.example` đã lỗi thời

### Việc cần làm tiếp theo (Mức độ ưu tiên trung bình)
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

