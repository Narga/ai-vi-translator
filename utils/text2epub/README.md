# Tiện ích chuyển đổi Văn bản sang EPUB

Một bộ script Python mạnh mẽ để tự động chuyển đổi các tệp văn bản có cấu trúc (`.txt`, `.md`) thành sách điện tử định dạng EPUB3 hoàn chỉnh.

---

## Tính năng nổi bật

-   **Tự động đóng gói:** Chuyển đổi từ một thư mục các tệp văn bản thành một tệp `.epub` duy nhất chỉ với một dòng lệnh.
-   **Nhận dạng nội dung thông minh:** Tự động phát hiện tiêu đề chương/phần dựa trên định dạng Markdown (`#`, `**`) và cấu trúc (tiêu đề 1-2 dòng).
-   **Tạo mục lục tự động:** Sinh ra các tệp mục lục tương thích với cả EPUB2 (`toc.ncx`) và EPUB3 (`toc.xhtml`) một cách chính xác.
-   **Xử lý tài sản linh hoạt:** Dễ dàng thêm CSS, ảnh bìa, và phông chữ tùy chỉnh thông qua một thư mục `assets` có cấu trúc rõ ràng.
-   **Không cần cài đặt:** Script chỉ sử dụng các thư viện chuẩn của Python, không yêu cầu cài đặt bất kỳ gói bên ngoài nào.

---

## Yêu cầu

-   **Python 3.6+**

---

## Cấu trúc thư mục dự án

Để script hoạt động chính xác, thư mục sách nguồn của bạn **phải** tuân theo cấu trúc sau:
```
ten_sach/
├── chunk_00000.txt
├── chunk_00001.md
└── assets/
├── metadata.xml   (Bắt buộc)
├── styles.css     (Bắt buộc)
├── cover.jpg      (Tùy chọn)
└── Fonts/         (Tùy chọn)
└── YourFont.ttf
```
---

## Cách sử dụng

1.  Chuẩn bị thư mục sách của bạn theo đúng **Cấu trúc thư mục dự án** ở trên.
2.  Đặt tất cả các tệp script (`main.py`, `parser.py`, `epub_creator.py`, v.v.) vào một thư mục riêng.
3.  Mở **Terminal** (macOS/Linux) hoặc **Command Prompt** (Windows) và chạy lệnh sau:

    ```bash
    python3 main.py /duong/dan/den/thu/muc/ten_sach
    ```

    *Thay thế `/duong/dan/den/thu/muc/ten_sach` bằng đường dẫn tuyệt đối hoặc tương đối đến thư mục sách của bạn.*

---

## Kết quả

Sau khi thực thi, một tệp `ten_sach.epub` sẽ được tạo ra ở **cùng cấp** với thư mục `ten_sach`.

**Ví dụ:** Nếu thư mục nguồn của bạn là `~/Documents/Quyen_1`, tệp EPUB sẽ được tạo tại `~/Documents/Quyen_1.epub`.

