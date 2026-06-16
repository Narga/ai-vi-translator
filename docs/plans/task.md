| Task | Status | Details |
|---|---|---|
| Phase 1: Sửa thứ tự load script | [x] | Đưa `ui-helpers.js` và `plugin-manager.js` lên trước Alpine trong `footer.html` |
| Phase 2: Guard lỗi trong `x-init` | [x] | Thêm xử lý lỗi ở khối plugin management UI |
| Phase 3: Check HTTP status | [x] | Kiểm tra `res.ok` trong `PluginManager.ensureLoaded()` |
| Phase 4: Kiểm tra backend API | [x] | Đảm bảo `/api/plugins/list` trả metadata đúng chuẩn |
