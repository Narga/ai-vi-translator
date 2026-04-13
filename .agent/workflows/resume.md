---
description: Resume project - Đọc lại toàn bộ context và chuẩn bị cho phiên làm việc mới
---

Workflow này giúp AI nhanh chóng nắm bắt tình trạng dự án khi bắt đầu một phiên làm việc mới bằng cách đọc `memory.md`.

// turbo-all
1. **Đọc Context Gốc**:
    - `memory.md`: Hiểu kiến trúc hiện tại, lịch sử và các quy tắc.
    - `CHANGELOG.md`: Xem các thay đổi gần đây nhất.
    - `ROADMAP.md`: Xác định các ưu tiên tiếp theo.
2. **Kiểm tra hiện trạng**:
    - Chạy `ls -R` ở các thư mục quan trọng (`core/`, `webui/`, `workspace/projects/`) để đối chiếu với tài liệu.
3. **Tóm tắt Project Briefing**:
    - Bản tóm tắt ngắn cho USER về: Phiên bản hiện tại, trạng thái cuối của phiên trước, và task cần làm ngay.
4. **Xác nhận**: Thông báo cho USER rằng AI đã sẵn sàng tiếp tục công việc.

---
> [!TIP]
> Luôn sử dụng `/resume` ngay khi bắt đầu một phiên chat mới để tránh lặp lại các lỗi cũ hoặc đi sai hướng kiến trúc.
> Nếu muốn khôi phục context đầy đủ từ database (bao gồm Diff Intelligence), sử dụng `/context-restore`.
