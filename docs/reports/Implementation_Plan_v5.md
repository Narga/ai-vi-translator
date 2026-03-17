# 🚀 Kế Hoạch Triển Khai (Implementation Plan) - Content Translator v5.0.0

Dựa trên báo cáo phân tích mã nguồn và lộ trình phát triển (Roadmap) đã được thống nhất, tài liệu này chi tiết hóa các bước thực tế cần thực hiện để hoàn thành giai đoạn tái cấu trúc hệ thống.

## 🏗️ MỤC TIÊU CỐT LÕI
1.  **Ổn định hóa**: Loại bỏ lỗi crash khi load prompt và rò rỉ bộ nhớ khi xử lý file lớn.
2.  **Module hóa**: Phân tách WebUI thành các gói nhỏ để dễ bảo trì.
3.  **Tin cậy hóa**: Sử dụng SQLite để đảm bảo tiến trình dịch thuật không bị mất mát khi gặp sự cố.
4.  **Tự nhiên hóa**: Nâng cấp thuật toán cắt câu (Chunking) để AI dịch sát nghĩa nhất.

---

## 📅 GIAI ĐOẠN 1: Tái Cấu Trúc Giao Diện & Điều Phối (Tuần 1)

### [Task 1.1] Module hóa WebUI
- **Mô tả**: Chuyển đổi `webui.py` thành thư mục `webui/`.
- **Thực hiện**:
    - Tạo `webui/__init__.py` để khởi tạo Flask App factory.
    - Tạo `webui/routes/` chứa: `projects.py` (CRUD dự án), `translation.py` (Worker điều phối), `settings.py` (Cấu hình model/prompts).
    - Tách logic `translate_worker` sang `webui/worker.py`.
- **Lợi ích**: Giảm kích thước file từ 1500+ dòng xuống còn các module < 300 dòng.

### [Task 1.2] Đơn giản hóa Core sang Functional Pipeline
- **Mô tả**: Loại bỏ EventBus/ServiceBus dư thừa.
- **Thực hiện**:
    - Refactor `core/plugin_manager.py` để hoạt động như một Dispatcher đơn giản.
    - Chuyển `translations` từ Plugin cồng kềnh sang một **Sequence of Functions** (Read -> Chunk -> Call API -> Normalize -> Save).
- **Lợi ích**: Tăng tốc độ khởi động app, dễ debug logic gọi API.

---

## 📅 GIAI ĐOẠN 2: Quản Lý Dữ Liệu & Thuật Toán (Tuần 2)

### [Task 2.1] Triển khai SQLite Project Management
- **Mô tả**: Thay thế JSON checkpoint bằng SQLite.
- **Thực hiện**:
    - Thiết kế schema: `projects`, `chunks` (status, original, translated), `metrics`.
    - Viết `services/database_service.py` để thay thế `checkpoint_service.py`.
- **Lợi ích**: Chống ghi đè file JSON khi crash, hỗ trợ truy vấn nhanh tiến độ dịch để hiển thị lên WebUI.

### [Task 2.2] Sentence Aggregation Chunker
- **Mô tả**: Nâng cấp `plugins/translation/chunker.py`.
- **Thực hiện**:
    - Sử dụng Rule-based (Regex) để xác định điểm ngắt câu thực sự.
    - Xây dựng logic **Buffer Aggregation**: Dồn các câu vào chunk cho đến khi đạt ngưỡng Token tối ưu, nếu câu tiếp theo làm tràn thì chuyển toàn bộ câu đó sang chunk sau.
- **Lợi ích**: Tuyệt đối không cắt ngang giữa chừng câu nói/đoạn văn, giúp LLM hiểu trọn vẹn ngữ cảnh.

---

## 📅 GIAI ĐOẠN 3: Tính Năng Hỗ Trợ Dịch Thuật (Tuần 3+)

### [Task 3.1] Dynamic Glossary Injection
- **Mô tả**: Tối ưu hóa việc dùng Glossary.
- **Thực hiện**:
    - Viết module quét nhanh nội dung Chunk (dùng Aho-Corasick algorithm cho hiệu năng cao).
    - Chỉ chèn các cặp từ điển có xuất hiện trong chunk vào System Prompt.
- **Lợi ích**: Giảm lãng phí Token cho các từ điển dài hàng ngàn mục.

### [Task 3.2] Side-by-Side Review Interface
- **Mô tả**: UX cho việc soát lỗi.
- **Thực hiện**:
    - Xây dựng giao diện Web split-screen (Gốc - Dịch).
    - Cho phép sửa trực tiếp vào DB SQLite và export file cuối cùng.

---

## 🛠️ CHIẾN LƯỢC KIỂM THỬ (TESTING)
1.  **Migration Test**: Kiểm tra việc convert dữ liệu từ các Project cũ (JSON) sang SQLite mới.
2.  **Stress Test**: Chạy dịch một bộ tiểu thuyết > 1 triệu chữ với 100 API Keys song song.
3.  **Accuracy Test**: So sánh tỷ lệ ký tự Trung còn sót lại giữa thuật toán Chunker cũ và mới.

---
**Duyệt/Phê duyệt bởi người dùng:** [ ] Chờ phê duyệt  
*Lưu ý: Sau khi được phê duyệt, tôi sẽ tạo nhánh `feature/v5-restructure` để bắt đầu thực hiện Task 1.1.*
