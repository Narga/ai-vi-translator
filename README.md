# Công cụ Dịch Thuật Tiểu Thuyết v1.1

Công cụ này sử dụng AI của Google (Gemini) để dịch thuật tiểu thuyết từ tiếng Trung hoặc tiếng Anh sang tiếng Việt. Dự án được thiết kế theo dạng module, dễ dàng cấu hình, có khả năng tự sửa lỗi và hỗ trợ các quy trình làm việc linh hoạt.

## Tính năng nổi bật

-   **Xử lý đầu vào linh hoạt**:
    -   **Dịch file lẻ**: Kéo một file truyện (`.txt`, `.docx`...) vào thư mục `input` để chương trình tự động đọc và chia nhỏ.
    -   **Dịch nguyên thư mục**: Kéo một thư mục chứa các file chương (`001.txt`, `002.txt`...) vào `input`, chương trình sẽ coi đó là một cuốn truyện và dịch lần lượt.

-   **Thuật toán "Chia file Thông minh"**:
    -   **Nhận diện chương gốc**: Tự động nhận diện các tiêu đề chương/hồi trong văn bản gốc và bọc chúng trong định dạng `**...**` để AI hiểu và giữ lại.
    -   **Tối ưu hóa chunk**: Khi dịch một thư mục truyện, các file chương có dung lượng nhỏ hơn `CHUNK_SIZE` sẽ được coi là một chunk duy nhất để tiết kiệm tài nguyên và giữ ngữ cảnh tốt hơn. Chỉ các file lớn hơn mới bị chia nhỏ.

-   **Thuật toán "Sửa lỗi Lặp lại" (Iterative Correction)**:
    -   Đây là tính năng cốt lõi để đảm bảo chất lượng. Sau khi dịch một chunk, chương trình sẽ tự động quét lại bản dịch.
    -   Nếu phát hiện còn sót ký tự tiếng Trung, nó sẽ không chuyển sang chunk tiếp theo. Thay vào đó, nó sẽ gửi lại chính bản dịch lỗi đó cho AI và ra lệnh: "Hãy tìm và dịch nốt các ký tự còn sót này".
    -   Quá trình này tự động lặp lại cho đến khi chunk hoàn toàn "sạch" ký tự Trung, giúp diệt trừ gần như 100% lỗi sót.

-   **Quản lý API Key thông minh**:
    -   **Đa luồng**: Số luồng dịch được tự động điều chỉnh bằng đúng số lượng API key bạn cung cấp, tối ưu hóa tốc độ.
    -   **Tự động xử lý Quota**: Khi một API key hết quota, chương trình sẽ tự động phát hiện, tạm vô hiệu hóa key đó và chuyển sang key tiếp theo mà không làm gián đoạn quá trình.

-   **Độ tin cậy cao**:
    -   **Tính năng Resume**: Mọi tiến trình đều được lưu lại trong thư mục `progress`. Nếu chương trình bị dừng đột ngột (mất mạng, mất điện...), bạn chỉ cần chạy lại và chọn "tiếp tục" (y), nó sẽ dịch nốt phần còn dang dở.
    -   **Hệ thống Logging**: Mọi hoạt động, cảnh báo, lỗi đều được ghi lại trong một file log có định dạng `YYYY-MM-DD_HH-MM_translator.log` trong thư mục `progress`, giúp dễ dàng chẩn đoán sự cố.

-   **Cấu hình Toàn diện**:
    -   **`config.ini`**: Cho phép tùy chỉnh mọi thứ từ model AI, kích thước chunk, độ trễ giữa các request, cho đến số lần AI tự sửa lỗi.
    -   **`prompts.ini`**: Toàn bộ "bộ não" của AI nằm ở đây. Bạn có thể tùy chỉnh văn phong, quy tắc dịch thuật mà không cần đụng đến một dòng code nào.

-   **Đầu ra có cấu trúc**:
    -   Kết quả được lưu vào thư mục `output/[tên truyện]`.
    -   Tự động tạo các file `.txt` riêng cho từng chương và một file `_full.txt` tổng hợp toàn bộ truyện.

## Hướng dẫn cài đặt và sử dụng

### 1. Yêu cầu

-   Python 3.8 trở lên.

### 2. Cài đặt

Mở terminal (hoặc Command Prompt) trong thư mục dự án và chạy lệnh:
```bash
pip install -r requirements.txt
```

### 3. Cấu hình

a. **File `config.ini`**:
   - Mở file và dán các API key của bạn vào dòng `GEMINI_API_KEYS`. Nếu có nhiều key, hãy ngăn cách chúng bằng dấu phẩy (`,`).
   - Tinh chỉnh các thông số khác nếu cần.

b. **File `prompts.ini`**:
   - File này chứa các chỉ thị cho AI. Bạn có thể tùy chỉnh để thay đổi văn phong dịch.

### 4. Sử dụng

a. **Chuẩn bị file nguồn**:
   - **Cách 1 (File lẻ):** Đặt một file truyện (ví dụ: `truyen_goc.txt`) vào thư mục `input`.
   - **Cách 2 (Thư mục truyện):** Đặt một thư mục (ví dụ: `[Tên Truyện]`) chứa các file chương (`001.txt`, `002.txt`...) vào thư mục `input`.

b. **Chạy chương trình**:
   Mở terminal và chạy lệnh:
   ```bash
   python main.py
   ```

c. **Theo dõi và nhận kết quả**:
   - Theo dõi tiến trình dịch trên màn hình.
   - Kết quả sẽ nằm trong thư mục `output/[tên truyện]`.