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

### v8.4.0 (2026-07-12)
- [x] 📄 Tích hợp Tab Tài liệu dự án (trình duyệt đọc đệ quy, cache dữ liệu)
- [x] 🔒 Bảo mật chống Path Traversal cho file reader API
- [x] 🔌 Tự động lưu trữ offline toàn bộ các thư viện CSS/JS (Tachyons, Marked.js)
- [x] 💡 Phục hồi & Tinh chỉnh trợ giúp Chỉ dẫn AI (Placeholders cleanup)

## Đang phát triển / Sắp tới

### v8.5.0 (planned)
- [ ] Batch translate (dịch nhiều file cùng lúc với progress riêng)
- [ ] Translation Memory improvements (fuzzy match threshold tuning)
- [ ] Advanced search & filter trong danh sách file

### v8.6.0 (planned)
- [ ] Export dự án sang EPUB/PDF
- [ ] Frontend bundle optimization (tree-shaking, code splitting)

### Tối ưu hóa
- [ ] Backend caching layer
- [ ] WebSocket thay thế SSE cho real-time progress

---

## Đã hoãn (YAGNI)
- Per-project model override (quyết định sau khi có nhu cầu thực tế)
- Migration script từ genre sang library (không cần - dự án chưa có dữ liệu cũ)
- Collaboration features (multi-user) — quá sớm
