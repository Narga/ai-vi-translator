# LỘ TRÌNH PHÁT TRIỂN TƯƠNG LAI (FUTURE ROADMAP)
> **Tài liệu**: Lưu trữ các tính năng nâng cao được dời lại từ Phase 1 & Phase 2 nhằm giữ cho lõi gửi–nhận của dự án luôn tinh gọn, nhẹ và không phát sinh lỗi.  
> **Địa chỉ**: `docs/ROADMAP.md`

---

## 1. PHÂN TÍCH SO SÁNH VỀ TÍNH NĂNG CHECKPOINT (LƯU TẠM TIẾN TRÌNH)

### 1.1. So Sánh Hai Cách Tiếp Cận

| Tiêu chí | **Phương Án Hiện Tại: Không Checkpoint (Minimalist Gửi–Nhận)** | **Phương Án Tương Lai: Có Checkpoint (Lưu Tạm Từng Chunk)** |
| :--- | :--- | :--- |
| **Bản chất** | Một phiên gửi–nhận trực tiếp. AI trả lời chunk nào thì giữ trong RAM, dịch xong toàn bộ chunk của file thì ghép lại và lưu thành file `.md`/`.txt`. | Ghi tạm từng chunk đã dịch vào database SQLite hoặc file JSON tạm. Nếu rớt mạng ở chunk 5, lần sau đọc lại chunk 1–4 và chỉ dịch tiếp từ chunk 5. |
| **Độ phức tạp code** | **Rất thấp (0 dòng code lưu trạng thái)**. Không lo lỗi khóa DB (Database Lock), không lo xung đột ghi file. | **Cao**. Phải thêm logic kiểm tra chunk nào đã dịch, xử lý file dở dang, xóa checkpoint khi xong, phục hồi khi crash. |
| **Giao diện WebUI** | Cực nhẹ, phản hồi tức thì, không có bảng điều khiển Resume / Recovery rườm rà. | Cần thêm UI hiển thị tiến trình phục hồi, nút "Dịch tiếp" hoặc "Dịch lại từ đầu". |
| **Khi gặp lỗi** | Dừng lại, báo lỗi rõ ràng. Người dùng xem lại mạng/key rồi bấm nút **[Gửi lại]** hoặc **[Xóa & gửi lại]**. | Tự động hoặc bán tự động nhảy cóc các chunk đã dịch. |
| **Mức độ phù hợp** | **Phù hợp tuyệt đối với mục tiêu gửi–nhận gọn nhẹ của dự án hiện tại**. | Chỉ cần thiết khi người dùng có nhu cầu dịch những file đơn lẻ khổng lồ (>100.000 từ / file). |

### 1.2. Kết luận
Trong Phase 1 và Phase 2, **loại bỏ hoàn toàn Checkpoint** giúp code giảm hơn 40% độ phức tạp, loại bỏ hoàn toàn các lỗi tiềm ẩn về lưu trạng thái. Tính năng này được bảo lưu tại tài liệu này và chỉ xem xét triển khai nếu người dùng thực sự có nhu cầu dịch các tệp khổng lồ trong tương lai.

---

## 2. KẾ HOẠCH SỬ DỤNG SQLITE CHO TƯƠNG LAI

File `workspace/app.db` được tạo sẵn sàng dưới dạng SQLite database tối giản. Trong tương lai (Phase 3 trở đi), SQLite sẽ được tận dụng cho các tính năng sau:

1. **Đánh chỉ mục tìm kiếm toàn văn (SQLite FTS5 Full-Text Search)**:
   * Cho phép người dùng gõ từ khóa để tìm kiếm ngay lập tức xem nhân vật hoặc thuật ngữ xuất hiện ở những chương nào trong hàng trăm chương truyện.
2. **Quản lý danh mục dự án lớn**:
   * Khi người dùng tích lũy hàng chục đầu sách với hàng ngàn chương, SQLite giúp tải danh sách dự án tức thì mà không phải duyệt quét ổ đĩa mỗi lần mở app.
3. **Lưu trữ Checkpoint (Nếu kích hoạt lại)**:
   * Sẵn sàng bảng `checkpoints` để lưu tạm các chunk nếu tính năng Checkpoint được kích hoạt.

---

## 3. CÁC TÍNH NĂNG XỬ LÝ TẬP TIN NÂNG CAO (PHASE 3 TRỞ ĐI)

1. **Bộ công cụ Tìm kiếm & Thay thế Hàng loạt (Batch Search & Replace)**:
   * Cho phép người dùng tìm một từ bị dịch sai (ví dụ: tên riêng dịch gượng gạo) và thay thế đồng loạt trên toàn bộ các file bản dịch trong thư mục `translated/`.
   * Hỗ trợ tìm kiếm theo chuỗi văn bản thường hoặc biểu thức chính quy (Regex).
2. **Công cụ So Sánh Chênh Lệch Nâng Cao (Diff Viewer)**:
   * So sánh chi tiết từng câu giữa bản gốc và bản dịch, hoặc giữa 2 lần dịch khác nhau (khi đổi prompt).

---

## 4. CÔNG CỤ EPUB & CHUYỂN ĐỔI ĐỊNH DẠNG 2 CHIỀU (PHASE 4)

1. **Đóng gói sách EPUB tối giản**:
   * Chỉ nhận đầu vào là các file text (`.txt`, `.md`, `.html`), tự động ghép thành sách `.epub` tiêu chuẩn có mục lục TOC.
2. **Chuyển đổi định dạng văn bản 2 chiều**:
   * `Markdown (.md)` $\longleftrightarrow$ `Text thuần (.txt)`.
   * `HTML (.html)` $\longleftrightarrow$ `Markdown (.md)`.
   * Áp dụng cho cả thư mục `sources/` và thư mục `translated/`.

---

## 5. CƠ CHẾ NGỮ CẢNH TỰ ĐỘNG & TRÍCH XUẤT THUẬT NGỮ (PHASE 4)

1. **Tự động tóm tắt chương trước (`previous_chunk_handoff` - Kế thừa từ silaBook)**:
   * Sau khi dịch xong một chương, AI tự sinh tóm tắt 3 câu và tự động truyền vào biến `{{previous_summary}}` của chương kế tiếp để giữ giọng điệu liền mạch.
2. **Công cụ Trích xuất Thực thể & Nhân vật tự động**:
   * Quét các chương truyện nguồn và tự động trích xuất danh sách nhân vật, môn phái, địa danh vào file `workspace/projects/{slug}/assets/glossary.txt`.
