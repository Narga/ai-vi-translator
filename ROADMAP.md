# ROADMAP - Lộ trình phát triển Content Translator

## Phiên bản hiện tại: v8.29.2 (2026-08-08)

---

## ✅ Đã hoàn thành (v8.29.2)

### 1. Sửa lỗi Modal Tìm kiếm & Thay thế (Pha 1)
- **Root cause**: Commit `2846e65` stub `openSearchReplaceModal` → `findInText()`, cắt đứt Alpine event bridge
- **Sửa đổi**:
  - `webui/static/js/editor-component.js`: Khôi phục `openSearchReplaceModal` phát `CustomEvent('open-search-replace')` lên `window`. Xóa `findInText`.
  - `webui/templates/partials/tab_projects.html`: Bỏ class `dn`, thêm `@open-search-replace.window="open($event.detail.textareaId)"`, thêm class `flex` cho centering.
  - `webui/static/css/style.css`: Di chuyển toast lên `top: 20px`, thêm `pointer-events: none` cho container + `pointer-events: auto` + `cursor: pointer` + animation vào `.toast`. Thêm `.toast.warning`/.`.toast.info` border-left, icon `⚠️`, hover effect, animation slide-in/out.
  - `webui/static/js/ui-helpers.js`: Thêm `click-to-close` handler vào `showToast`, thêm icon `⚠️` cho type warning.
- **Test**: 9/9 pass (Node-only verification); trên browser: modal center, toast click-through, không che task info.

### 2. CHANGELOG cập nhật
- Thêm entry `[8.29.2] - 2026-08-29` cho các thay đổi trên.

### 3. ROADMAP.md tạo mới
- Tổng hợp lộ trình phát triển từ các kế hoạch đã và đang thực hiện.

---

## 🚧 Đang phát triển / Sắp tới

### 4. Line Numbers (Gutter) cho 4 Editor (Pha 4)
- **Mục tiêu**: Hiển thị số dòng dạng gutter bên trái mỗi textarea (`pm-source-text`, `pm-result-text`, `pm-spell-source-text`, `pm-spell-result-text`)
- **Phương án**: Bọc textarea trong `<div class="editor-wrapper">`, render số dòng JS, đồng bộ scroll theo `syncScroll` pattern có sẵn, virtualization cho file >10.000 dòng (chỉ render viewport + buffer 50 dòng)
- **Tiến độ**: Chưa bắt đầu / pending tiếp theo

### 5. Line Numbers đồng bộ cho Modal Diff (Pha 5)
- **Mục tiêu**: Modal `showDiffView` chế độ side-by-side hiển thị 3 cột: gutter | nguồn | dịch
- **Yêu cầu**: Số dòng thẳng hàng, sync scroll 3 cột cùng lúc, chuyển Dọc/Ngang không reset gutter
- **Tiến độ**: Chưa bắt đầu

### 6. Acceptance Criteria hoàn善
- **Nhóm A - Tìm kiếm & Thay thế**: 8/8 checkbox - ✅ Modal hiện đã hoạt động (tìm/tìm lùi/thay thế/regex/all files/dry-run), 1 checkbox chưa verify trên browser (state reset giữa editor)
- **Nhóm B - Line Numbers cho 4 Editor**: 7/7 checkbox - ⏳ Chưa triển khai (tùy thuộc Pha 4)
- **Nhóm C - Line Numbers cho Modal Diff**: 5/5 checkbox - ⏳ Chưa triển khai (tùy thuộc Pha 5)

---

## ⏳ Sau này / Low Priority

### 7. Code cleanup & Refactor
- Xem `showDiffView` unified view có thêm gutter số dòng không
- Tiện ích: tách `findInText` logic nếu cần tái sử dụng

### 8. Tài liệu bổ trợ
- Cập nhật README.md nếu có tính năng mới ảnh hưởng trải nghiệm người dùng (them vao "Tính năng nổi bật")
- Thêm ví dụ về dùng modal tìm kiếm & thay thế cho người mới

---

## 📋 Cách theo dõi
- Mỗi phiên bản: review `docs/wip/plan_regex_editor_sigil_dryrun.md` và `docs/wip/*.md`
- File `del_*` trong `docs/wip/` là kế hoạch đã hoàn thành → di chuyển vào `.gitignore` (đã có)
- Mối quan hệ: `ROADMAP.md` quản lý lộ trình tổng thể, `CHANGELOG.md` ghi lịch sử chi tiết, `plan_regex_editor_sigil_dryrun.md` là kế hoạch chi tiết cho phiên bản
- Progress: ✅ = done, ⏳ = pending, ⬜ = chưa bắt đầu