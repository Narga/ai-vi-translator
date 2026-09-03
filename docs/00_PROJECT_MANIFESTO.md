# 00. TÔN CHỈ & BẢN TUYÊN NGÔN CỐT LÕI DỰ ÁN
> **Dự án**: Content Translator (Next-Gen)  
> **Phiên bản tài liệu**: v2.1 (Tinh giản tối đa sau phản biện)  
> **Cập nhật ngày**: 03/09/2026

---

## 1. BẢN CHẤT CỐT LÕI (CORE ESSENCE)

> **"Đây KHÔNG PHẢI là một hệ thống quản lý quá trình dịch tiểu thuyết.**  
> **Đây là một CÔNG CỤ GỬI NỘI DUNG CHO AI VÀ NHẬN BẢN DỊCH VỀ, phục vụ duy nhất MỘT NGƯỜI DÙNG."**

Mọi kiến trúc của dự án chỉ xoay quanh chu trình gửi–nhận nguyên bản:

```text
GIAO DIỆN (UI) / CLI
 ├── Chọn / Nhập văn bản nguồn
 ├── Cắt chunk tự nhiên (15.000 - 20.000 ký tự, thường 2-3 chunk/file)
 ├── Dựng prompt đơn giản
 ├── Gửi request tuần tự
 ├── Nhận response
 ├── Ghép kết quả (nối bằng \n\n)
 └── Hiển thị kết quả / Ghi ra file (Gửi lại thủ công khi lỗi)

AI CLIENT
 ├── Gemini REST adapter (sử dụng httpx thuần túy, zero SDK nặng)
 ├── Xử lý Timeout & Bắt lỗi HTTP / Lỗi mạng
 └── Xoay key đơn giản: Mỗi key thử tối đa 1 lần/chunk; 429 thì chuyển key kế tiếp; hết key thì dừng

FILE & CẤU HÌNH (LOCAL)
 ├── Prompt dạng file .txt đơn giản
 ├── config.json mỏng & keys.json nhạy cảm (nằm trong .gitignore)
 └── Toàn bộ thư mục workspace/ KHÔNG track với Git (bảo đảm riêng tư tuyệt đối)
```

---

## 2. PHÂN ĐỊNH RANH GIỚI: LÕI BẮT BUỘC VS. TIỆN ÍCH MỞ RỘNG

Để tránh việc phình to mã nguồn và hiểu lầm khi triển khai, các thành phần được phân định rạch ròi:

### A. Thành Phần Lõi Bắt Buộc (Phải có để Phase 1 chạy được)
* **`chunker`**: Chia văn bản thành 2-3 chunk tự nhiên ($\le 20.000$ ký tự), ưu tiên ranh giới đoạn/câu, xử lý file rỗng, không làm mất nội dung gốc.
* **`prompt_engine`**: Thay thế biến `{{source_text}}` vào template prompt `.txt` mà không làm hỏng Unicode tiếng Việt.
* **`ai_client`**: Gọi Google Gemini API qua HTTP REST, bắt lỗi mạng, timeout, response rỗng và xoay key khi 429.
* **`run.py` (CLI)**: Đọc file đầu vào, chạy luồng gửi-nhận, in tiến độ và ghi file đầu ra.

### B. Thành Phần Tiện Ích Mỏng (Hỗ trợ cấu hình và an toàn cơ bản)
* **`config`**: Đọc cấu hình JSON mỏng, tách biệt `keys.json`.
* **`key_rotator`**: Bộ xoay key tối giản không trạng thái phức tạp.
* **`file_handler`**: Lớp đọc/ghi file có kiểm tra an toàn đường dẫn (chống path traversal `..`).

### C. Tiện Ích Mở Rộng (Chuyển sang các Phase tiếp theo)
* Hỗ trợ OpenAI-compatible $\to$ Chuyển sang **Phase 3**.
* Quản lý `assets/` riêng của từng dự án & `glossary.txt` $\to$ Chuyển sang **Phase 3**.
* Tìm kiếm & thay thế hàng loạt, so sánh Diff chi tiết $\to$ Chuyển sang **Phase 3**.
* Công cụ đóng gói EPUB & chuyển đổi 2 chiều $\to$ Chuyển sang **Phase 4**.
* Checkpoint lưu tạm từng chunk $\to$ Chuyển sang **ROADMAP** (chỉ làm khi thực sự có nhu cầu).

---

## 3. NGUYÊN TẮC THẤT BẠI & KHÔNG CHECKPOINT (FAILURE POLICY)

1. **Mỗi chunk là một phiên gửi độc lập**:
   * Khi gửi một chunk: thử key hiện tại $\to$ gặp 429 thì chuyển lần lượt sang key kế tiếp trong danh sách (mỗi key thử tối đa 1 lần).
   * Nếu tất cả key đều bị 429 hoặc gặp lỗi mạng/timeout: **Dừng toàn bộ chương trình ngay lập tức**, in thông báo lỗi rõ ràng.
2. **Quy tắc chạy lại (Không Resume)**:
   * **Khi một chunk bị lỗi, chương trình dừng và KHÔNG lưu trạng thái dở dang.**
   * Người dùng kiểm tra lại mạng/key và chạy lại lệnh thủ công. Lần chạy lại sẽ **bắt đầu lại toàn bộ file từ chunk đầu tiên**.
   * *Lý do*: Thông thường mỗi chương truyện chỉ có 2-3 chunk (15k-20k ký tự/chunk). Việc bắt đầu lại từ đầu là cực kỳ nhanh chóng, không đáng để phải mang vác thêm hệ thống lưu trạng thái, database hay checkpoint phức tạp.

---

## 4. CAM KẾT ĐỊNH DẠNG THỰC TẾ (REALISTIC FORMATTING CRITERIA)

Chúng ta **tuyệt đối không tuyên bố bảo toàn định dạng 100%** vì AI là mô hình xác suất. Tiêu chí đánh giá thực tế bao gồm:
* ✅ **Bảo toàn 100% nội dung**: Không bỏ sót bất kỳ câu, đoạn văn bản nguồn nào.
* ✅ **Tôn trọng ranh giới tự nhiên**: Ưu tiên cắt tại dấu xuống dòng kép `\n\n`, xuống dòng đơn `\n`, hoặc dấu chấm câu kết thúc `. `, không cắt đứt đôi câu văn.
* ✅ **Quy ước ghép chunk đơn giản**: Các chunk dịch xong được ghép nối với nhau bằng một dòng trống (`\n\n`).
* ✅ **Kiểm soát người dùng**: Cho phép người dùng xem và kiểm tra kết quả trước khi lưu hoặc xuất bản.

---

## 5. CÂU HỎI SÁT HẠCH (LITMUS TEST)

> **"Tính năng này có giúp việc gửi chunk cho AI và nhận bản dịch về nhanh hơn, nhẹ hơn không?"**  
> Nếu làm tăng trạng thái, thêm luồng ngầm, hoặc không phục vụ trực tiếp chu trình gửi-nhận: **LOẠI BỎ NGAY LẬP TỨC**.
