---
description: Checkpoint project - Tổng kết phiên làm việc và cập nhật Memory
---

Workflow này giúp AI hiện tại "truyền tin" cho AI tiếp theo bằng cách lưu trữ toàn bộ context quan trọng vào tập tin `memory.md`.

// turbo-all
1. **Phân tích thay đổi**: Xem xét các file đã sửa, các tính năng mới đã thêm, hoặc các lỗi đã fix trong phiên làm việc hiện tại.
2. **Cập nhật memory.md**:
    - **Kiến trúc**: Nếu có thay đổi về cấu trúc folder hoặc logic lõi.
    - **Quy tắc**: Nếu có quy tắc coding mới được thống nhất.
    - **Session Marker**: Cập nhật trạng thái sang `COMPLETED`, ghi chú "Handover Note" về các task dang dở hoặc lưu ý cho AI phiên sau.
3. **Cập nhật Documentation**:
    - `docs/documents/CHANGELOG.md`: Thêm entry cho các thay đổi vừa thực hiện.
    - `docs/documents/Roadmap.md`: Đánh dấu hoàn thành các task đã xong.
4. **Dọn dẹp**: Xóa các file log tạm thời hoặc các bản nháp không cần thiết.
5. **Đề xuất Git**: Gợi ý câu lệnh `git commit` và `git tag` (nếu có release) phù hợp.

---
> [!IMPORTANT]
> `/checkpoint` là bước bắt buộc trước khi kết thúc phiên làm việc để đảm bảo tính liên tục của dự án.
