# Công cụ Dịch Thuật Tiểu Thuyết v1.0

Công cụ này sử dụng AI của Google (Gemini) để dịch thuật tiểu thuyết từ tiếng Trung hoặc tiếng Anh sang tiếng Việt. Dự án được thiết kế theo dạng module, dễ dàng cấu hình và mở rộng.

## Tính năng nổi bật

-   **Module hóa**: Mã nguồn được chia thành các module chức năng (chia file, dịch, ghi file), dễ bảo trì và nâng cấp.
-   **Cấu hình linh hoạt**: Dễ dàng thay đổi model AI, API key, kích thước chunk... thông qua file `config.ini`.
-   **Quản lý Prompt thông minh**: Toàn bộ prompt được quản lý trong file `prompts.ini`, giúp bạn tùy chỉnh "tính cách" của AI mà không cần đụng vào code.
-   **Chia file thông minh**: Tự động nhận diện chương, hồi và chia nhỏ file một cách hợp lý, ưu tiên không ngắt giữa các đoạn văn.
-   **Dịch song song**: Tận dụng đa luồng để tăng tốc độ dịch thuật một cách đáng kể.
-   **Quản lý API Key**: Tự động xoay vòng qua danh sách API key, hữu ích khi một key hết hạn mức.
-   **Hệ thống Cache**: Lưu lại các đoạn đã dịch để tiết kiệm chi phí gọi API khi dịch lại cùng một nội dung.
-   **Xuất file theo chương**: Tự động tạo các file `.txt` riêng cho từng chương và một file tổng hợp toàn bộ truyện.

## Hướng dẫn cài đặt và sử dụng

### 1. Yêu cầu

-   Python 3.8 trở lên.

### 2. Cài đặt

a. Clone repository này về máy của bạn.

b. Cài đặt các thư viện cần thiết bằng cách mở terminal (hoặc Command Prompt) trong thư mục dự án và chạy lệnh:

```bash
pip install -r requirements.txt
```

### 3. Cấu hình

a. **Mở file `config.ini`:**

-   Tại dòng `GEMINI_API_KEYS`, dán một hoặc nhiều API key của bạn vào. Nếu có nhiều key, hãy ngăn cách chúng bằng dấu phẩy (`,`).
    *Để lấy API key, hãy truy cập [Google AI Studio](https://aistudio.google.com/app/apikey).*
-   Chỉnh sửa các thông số khác như `MODEL`, `INPUT_LANG`, `CHUNK_SIZE` nếu cần.

b. **(Tùy chọn) Mở file `prompts.ini`:**

-   Bạn có thể chỉnh sửa các prompt để thay đổi văn phong hoặc cách AI dịch thuật.

### 4. Sử dụng

a. Đặt file truyện gốc (ví dụ: `truyen_goc.txt`) vào thư mục `input`.

> **Lưu ý**: Script sẽ chỉ xử lý file **đầu tiên** mà nó tìm thấy trong thư mục `input`.

b. Chạy script chính từ terminal:

```bash
python main.py
```

c. Quá trình dịch sẽ bắt đầu. Bạn có thể theo dõi tiến trình trên màn hình terminal.

d. Sau khi hoàn tất, kết quả sẽ nằm trong thư mục `output`. Một thư mục con mới mang tên file gốc của bạn sẽ được tạo ra, chứa các file chương riêng lẻ và một file tổng hợp (nếu được bật trong config).

## Chạy các module độc lập (Dành cho nhà phát triển)

Bạn có thể chạy các module riêng lẻ để kiểm thử:

-   **Kiểm tra việc chia chunk:**
    ```bash
    python smart_chunker.py "đường/dẫn/tới/file/test.txt"
    ```
-   **Kiểm tra module dịch (yêu cầu đặt biến môi trường `GEMINI_API_KEYS`):**
    ```bash
    python translator.py
    ```
-   **Kiểm tra module ghi file:**
    ```bash
    python file_writer.py
    ```
    Thao tác này sẽ tạo một thư mục `test_output` để bạn kiểm tra kết quả.