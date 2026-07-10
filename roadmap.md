# Roadmap - Novel Translator

## Hoàn thành

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

## Đang phát triển / Sắp tới

### v8.1.0 (planned)
- [ ] Per-project model override (cho phép mỗi dự án dùng model khác nhau)
- [ ] Batch translate (dịch nhiều file cùng lúc với progress riêng)
- [ ] Translation Memory improvements (fuzzy match threshold tuning)

### v8.2.0 (planned)
- [ ] Advanced search & filter trong danh sách file
- [ ] Export dự án sang EPUB/PDF
- [ ] Collaboration features (multi-user)

### Tối ưu hóa
- [ ] Frontend bundle optimization (tree-shaking, code splitting)
- [ ] Backend caching layer (Redis/Memcached cho prompt cache)
- [ ] WebSocket thay thế SSE cho real-time progress

---

## Đã hoãn (YAGNI)
- Per-project model override (v8.1.0)
- Migration script từ genre sang library (không cần - dự án chưa chạy thực tế)
