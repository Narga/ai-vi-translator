# 🚀 Kế Hoạch Tiếp Tục Phát Triển (Continuation Plan)
Tài liệu này hợp nhất các công việc chưa hoàn thành từ các báo cáo rà soát và kế hoạch cải tiến trước đó.

---

## 1. Tái cấu trúc & Hạ tầng (Backend Refactoring)
Tiếp tục hiện đại hóa mã nguồn để tăng tính bảo trì và độ tin cậy.

### 🏗️ Phân rã Monolith
- [ ] **Task 3.3: Tách `webui/static/js/main.js`**:
    - File hiện tại ~3,000 dòng. Cần tách thành các ES modules chuyên biệt (ví dụ: `projects.js`, `settings.js`, `editor.js`, `api.js`).
    - Sử dụng `type="module"` trong thẻ script.
    - Giữ `main.js` làm orchestrator trung tâm.

### 🛡️ Độ tin cậy & Kiểm thử
- [ ] **Xây dựng bộ khung Unit Test**:
    - Sử dụng `pytest` để kiểm thử các logic lõi: `Chunker`, `CacheService`, `CheckpointService`, `RateLimiter`.
- [ ] **Quản lý cấu hình**:
    - Triển khai schema validation cho `config/app.ini` để tránh lỗi do nhập sai thông số kỹ thuật.
- [ ] **Wiring Unused Infrastructure**:
    - Tích hợp `CircuitBreaker` (ngắt mạch khi lỗi API liên tục) và `HealthMonitor` (giám sát tình trạng ứng dụng) vào luồng dịch chính.

### 📝 Type Safety & Logging
- [ ] **Hoàn thiện Type Annotations**: Bổ sung return type cho tất cả các hàm public (đặc biệt là trong `webui/helpers.py`).
- [ ] **Structured Logging**: Chuyển đổi toàn bộ `print()` sang `logging` và cấu hình định dạng JSON cho log để dễ dàng phân tích bằng công cụ.

---

## 2. Cải tiến Giao diện (UI/UX Improvements)
Dựa trên kế hoạch cải tiến desktop-first.

### 🛡️ Bảo vệ Dữ liệu & Bảo mật
- [ ] **Fix XSS**: Escape HTML trong quá trình render tên file trên UI.
- [ ] **Unsaved Changes Protection**: Cảnh báo người dùng khi chuyển file hoặc đóng trình duyệt mà chưa lưu nội dung đã sửa.

### 🎨 Trải nghiệm Người dùng (UX)
- [ ] **ModalManager**: Chuẩn hóa hệ thống modal để hỗ trợ đóng bằng phím Escape hoặc click overlay.
- [ ] **Custom Dialogs**: Thay thế `confirm()` và `prompt()` của trình duyệt bằng giao diện modal đồng nhất với dự án.
- [ ] **Resizable Tables**: Cho phép người dùng điều chỉnh độ cao của bảng danh sách file nguồn/dịch.
- [ ] **Progress Modal UX**: Bỏ cơ chế tự động đóng modal tiến trình sau 10 giây; thay bằng nút "Hoàn thành" thủ công.

### ✨ Tính năng mới trên UI
- [ ] **Diff View**: Thêm tính năng so sánh trực quan (line-by-line) giữa văn bản gốc và văn bản dịch trong modal.
- [ ] **Editor Toolbar**: Bổ sung thanh công cụ đơn giản (Tìm kiếm/Thay thế, Bật/Tắt ngắt dòng) cho trình soạn thảo.

---

## 3. Tính năng AI Nâng cao (Future Features)
Lộ trình dài hạn cho các tính năng thông minh.

### ⚙️ Tối ưu hóa Dịch thuật
- [ ] **Progressive Batch Translation**: Hỗ trợ hàng đợi dịch nhiều file với thanh tiến độ tổng thể.
- [ ] **Prompt Versioning**: Lưu lịch sử các phiên bản prompt của dự án để khôi phục khi cần.
- [ ] **HTML/Markdown Preservation**: Thuật toán bảo toàn thẻ tag khi dịch nội dung phức tạp.

### 🤖 Trí tuệ nhân tạo chuyên sâu
- [ ] **Advanced OCR Engines**: Tích hợp các engine OCR mạnh mẽ hơn hoặc kết nối Cloud OCR (Google Cloud Vision).
- [ ] **Local LLM Integration**: Hỗ trợ kết nối Ollama hoặc LocalAI cho nhu cầu dịch thuật offline.
- [ ] **Agentic Post-Editing**: 
    - AI tự động rà soát bản dịch sau khi hoàn tất để fix các lỗi xưng hô.
    - **Character Memory**: AI ghi nhớ sâu bối cảnh nhân vật để nhất quán xưng hô theo giới tính/địa vị.

---
*Tài liệu này được hợp nhất từ CODE_REVIEW_REPORT, UI_IMPROVEMENTS và REMEDIATION_PLAN vào ngày 06/05/2026.*
