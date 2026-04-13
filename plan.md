# 📚 Novel Translator - Implementation Plan (v6.2.0+)

Đây là kế hoạch chi tiết để khôi phục và nâng cấp hệ thống sau đợt tái cấu trúc giao diện v6.2.0. Kế hoạch được chia thành 4 giai đoạn thực hiện dứt điểm.

---

## 🎯 Trạng thái Hiện tại
- **Phiên bản**: v6.2.0 (Đã nạp thành công từ CHANGELOG.md).
- **Vấn đề tồn đọng**: 
  - Thanh cuộn (scroll) bị khóa ở tab Prompt và Profile.
  - Khu vực Nhật ký quá cao, cần giới hạn `680px`.
  - Thiếu hệ thống 6-prompts (hiện chỉ có 3).
  - Chưa có cơ chế chọn nhiều file để chạy AI analysis trong Profile.

---

## 🚀 Kế hoạch thực hiện (4 Phases)

### Phase 1: Sửa lỗi Hiển thị & Cuộn trang (Ưu tiên 1)
- **Mục tiêu**: Khôi phục trải nghiệm cuộn và giới hạn chiều cao Log.
- **Công việc**:
  - `templates/partials/tab_logs.html`: Thay `min-height: 600px` bằng `max-height: 680px` (kèm `overflow-y: auto`).
  - `templates/partials/tab_workspace.html` & `tab_prompts.html`: Gỡ bỏ các lớp `h-100` gây bó cứng layout. Cấu hình `.nt-tab-content` sử dụng flex-column với `min-height: 100%` để trang có thể cuộn tự nhiên.

### Phase 2: Xây dựng bố cục 6 Prompts dạng Tab (Giao diện)
- **Mục tiêu**: Chuẩn bị giao diện cho hệ thống Prompt nâng cao.
- **Công việc**:
  - Cập nhật Editor trong `tab_prompts.html` và tab con Prompts trong Workspace.
  - Hiển thị 6 thẻ Tab:
    1. **Dịch thô (Main)**
    2. **Dịch kỹ (Retranslate)**
    3. **Sửa lỗi (Correction)**
    4. **Tóm tắt nội dung (Summary)** - [Mới]
    5. **Bảng quan hệ (Relationships)** - [Mới]
    6. **Bảng thuật ngữ (Glossary)** - [Mới]
  - *Lưu ý*: Chỉ xây dựng phần khung HTML/CSS, chưa xử lý logic lưu trữ ở giai đoạn này.

### Phase 3: Cơ chế lựa chọn tập tin trong Profile (UI & Logic)
- **Mục tiêu**: Cho phép chọn tệp cụ thể để AI phân tích.
- **Công việc**:
  - Tái sử dụng `Sidebar Sources` (danh sách tệp) từ tab Workspace đưa vào tab Profile.
  - Thêm Checkbox cho từng tệp để hỗ trợ chọn một, nhiều hoặc tất cả.
  - Cập nhật `main.js` để thu thập danh sách tệp đã chọn khi nhấn các nút AI.

### Phase 4: Cải tiến Mã nguồn & Đồng bộ 6 Prompts (Backend)
- **Mục tiêu**: Đưa hệ thống vào hoạt động hoàn chỉnh.
- **Công việc**:
  - Cập nhật `webui/routes/prompts.py` và `projects.py` để hỗ trợ lưu trữ 6 tệp tin prompt (thêm: `04-summarize.txt`, `05-relationships.txt`, `06-glossary.txt`).
  - Triển khai 2 API mới: `/api/projects/<slug>/extract-characters` và `/api/projects/<slug>/extract-glossary`.
  - Kết nối dữ liệu từ các Tab ở Phase 2 vào bộ máy AI.

---

## 📝 Chỉ dẫn kỹ thuật cho AI Session sau
1. **Khởi đầu**: Chạy ngay **Phase 1** bằng cách điều chỉnh CSS flexbox.
2. **Kiểm soát**: Luôn chạy `npx eslint static/js/main.js` sau mỗi lần sửa JS để tránh lỗi cú pháp làm treo app.
3. **Đồng bộ**: Đảm bảo các ID nút AI trong `tab_workspace.html` khớp với logic trong `main.js`.

---
*Kế hoạch này được lập vào ngày 12/04/2026. Hãy bắt đầu từ Phase 1.*
