# Roadmap - Novel Translator

## Hoàn thành

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

### v8.3.0 (2026-07-12) — Dọn dẹp over-engineering
- [x] Xóa 7 file services chết (async_genai_client, health_monitor, circuit_breaker, statistics_service, monitoring_service, file_service, io_service)
- [x] Xóa dead code trong file sống (AsyncOpenAIClient, SmartRateLimiter, TokenBudgetLimiter, wait_for_emergency_clear, emergency_check, ChunkTranslationMemory)
- [x] Xóa 4 thư mục backend rỗng + `requirements.txt` + deps `psutil`/`aiohttp`
- [x] Migrate `main.py` → `AppConfigService`, xóa `config_service.py` (duplicate)
- [x] Dọn `services/__init__.py` barrel export
- [ ] (tùy chọn) Gom `_get_client()` trùng lặp → shared helper
- [ ] (tùy chọn) Inline `file_utils.py` vào call site
- [ ] (tùy chọn) Dùng `model_catalog_service` thay hardcoded model list

### v7.9.0 (2026-07-10)
- [x] Tiền xử lý HTML/XHTML → Markdown offline
- [x] Cải tiến UI workspace (batch convert, deselect, status bar)

### v7.8.0 (2026-06-16)
- [x] Tái cấu trúc Plugin Navigation
- [x] Quản lý Plugin tập trung

---

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

## Đang phát triển / Sắp tới

### v9.0.0 (planned)
- [ ] Export dự án sang EPUB/PDF
- [ ] Dọn JS chết trong `ui-helpers.js` (`runEpubToText()`, `runTextToEpub()` cũ)
- [ ] Frontend bundle optimization (tree-shaking, code splitting)
- [ ] Gom `_get_client()` trùng lặp → shared helper
- [ ] Inline `file_utils.py` vào call site
- [ ] Dùng `model_catalog_service` thay hardcoded model list

### Tối ưu hóa
- [ ] Backend caching layer
- [ ] WebSocket thay thế SSE cho real-time progress

---

## Đã hoãn (YAGNI)
- Per-project model override (quyết định sau khi có nhu cầu thực tế)
- Migration script từ genre sang library (không cần - dự án chưa có dữ liệu cũ)
- Collaboration features (multi-user) — quá sớm
