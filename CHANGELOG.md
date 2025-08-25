# Changelog - Lịch sử thay đổi

Tất cả các thay đổi quan trọng của dự án sẽ được ghi lại ở đây.

## [1.2.2] - Tối ưu hóa Quy trình Ghi chú và Đầu ra

### ✨ Cải tiến (Enhancements)

* **Tối ưu hóa quy trình Ghi chú (`notes.txt`):**
    * Ghi chú cho truyện giờ đây được đưa trực tiếp vào prompt dịch chính (`01-main.txt`) và prompt dịch lại (`02-retranslate.txt`).
    * Điều này giúp AI có được ngữ cảnh về tên riêng và thuật ngữ ngay từ đầu, tăng cường tính nhất quán và giảm thiểu việc phải sửa lỗi ở các bước sau.
    * Ghi chú không còn được đưa vào prompt kiểm tra sự nhất quán cuối cùng.

### ♻️ Thay đổi (Changes)

* **Đơn giản hóa kết quả đầu ra:**
    * Chương trình giờ đây sẽ chỉ tạo ra **một file duy nhất** chứa toàn bộ bản dịch với tên `[tên_truyện]_dich.txt`.
    * Đã **loại bỏ hoàn toàn** việc tạo các file chương riêng lẻ (`_chuong_...`) và file giới thiệu (`_gioi_thieu.txt`) không cần thiết.
* **Tinh gọn Cấu hình:**
    * Xóa bỏ tùy chọn `CREATE_COMBINED` khỏi `config.ini` vì việc tạo file tổng hợp duy nhất là hành vi mặc định.
    
### [1.2.1] - Cải tiến & Tối ưu hóa

* **Tối ưu hóa Cấu trúc Thư mục:**
    * Tạo thư mục `workspace/` mới để chứa tất cả các thư mục làm việc và dữ liệu tạm thời.
    * Các thư mục `input`, `output`, `cache`, và `progress` giờ đây sẽ nằm gọn bên trong `workspace/` để giữ cho thư mục gốc của dự án luôn sạch sẽ.

* **Triển khai Lưu trữ Cache (Cache Archiving):**
    * Sau khi quá trình dịch hoàn tất, các file cache sẽ không bị xóa.
    * Thay vào đó, chúng sẽ được tự động di chuyển vào một thư mục lưu trữ có đánh dấu thời gian, ví dụ: `workspace/cache/bin_2025-08-25_18-00/`.

* **Lưu trữ các Chunk đã dịch:**
    * Sau khi ghép các chunk thành file tổng hợp, các file chunk riêng lẻ (trong thư mục `progress`) sẽ không bị xóa.
    * Chúng sẽ được di chuyển vào thư mục con `parts/` bên trong thư mục kết quả cuối cùng (ví dụ: `workspace/output/[Tên Truyện]/parts/`), giúp bạn dễ dàng đối chiếu và kiểm tra lại sau này.

## [1.2] - Giải thuật Cắt file Mới

Module `smart_chunker.py` đã được viết lại hoàn toàn để triển khai thuật toán `intelligent_chunking` mới, kết hợp ưu điểm của cả hai phiên bản:

   1. Phát hiện và Đánh dấu Tiêu đề: Trước khi cắt, toàn bộ văn bản sẽ được quét để tìm các tiêu đề chương/hồi. Các tiêu đề này sẽ được đánh dấu bằng định dạng **...** như cũ. Đây là bước ưu tiên hàng đầu.

   2. Cắt đoạn Thông minh theo Ngữ cảnh:

       - Chương trình sẽ tìm điểm cắt "tối ưu" nhất trong một khoảng cho phép (min_chars và max_chars trong config.ini).

       - Ưu tiên cắt ở cuối câu: Các dấu .!?。！？ có trọng số cao nhất.

       - Sau đó đến cuối đoạn: Dấu ngắt đoạn \n\n có ưu tiên cao thứ hai.

       - Các điểm ngắt khác như xuống dòng \n, dấu phẩy, dấu cách... sẽ được xem xét với độ ưu tiên thấp dần.

    3. Hậu xử lý: Sau khi cắt, chương trình sẽ tự động tìm các chunk quá nhỏ (thường là các đoạn ngắn cuối chương) và gộp chúng vào chunk trước đó để đảm bảo các phần dịch luôn đủ ngữ cảnh.

## [1.1.1] - Bản nâng cấp Lõi và Tăng cường Chất lượng

Phiên bản này tập trung vào việc hoàn thiện quy trình dịch thuật, tăng cường độ tin cậy và đưa vào các cơ chế đảm bảo chất lượng bản dịch một cách tự động.

### ✨ Tính năng mới (Features)

-   **Hỗ trợ dịch nguyên thư mục truyện**:
    -   Chương trình giờ đây có thể nhận một thư mục con trong `input` làm nguồn dịch.
    -   Tự động đọc và dịch tất cả các file `.txt` bên trong thư mục đó theo thứ tự tên file.
-   **Tối ưu hóa logic chia chunk**:
    -   Khi xử lý một thư mục, các file chương có dung lượng nhỏ hơn `CHUNK_SIZE` sẽ được coi là một chunk duy nhất để giữ ngữ cảnh tốt hơn.
-   **Triển khai thuật toán "Sửa lỗi Lặp lại"**:
    -   Tự động quét bản dịch sau mỗi lần dịch để tìm ký tự tiếng Trung còn sót.
    -   Nếu phát hiện lỗi, chương trình sẽ gửi lại chính bản dịch lỗi đó cho AI và yêu cầu sửa lại một cách lặp đi lặp lại cho đến khi chunk hoàn toàn "sạch".
-   **Tích hợp bước "Kiểm tra sự nhất quán"**:
    -   Sau khi dịch xong, chương trình thực hiện một bước cuối cùng: rà soát lại toàn bộ bản dịch và đối chiếu với file ghi chú (`notes.txt`) để đảm bảo tên riêng, thuật ngữ được thống nhất toàn truyện.
    -   Tính năng này có thể được bật/tắt trong `config.ini`.
-   **Hệ thống "Ghi chú cho AI" (`notes.txt`)**:
    -   Cho phép người dùng tạo một file `notes.txt` chứa danh sách tên riêng, thuật ngữ... cho từng truyện.
    -   Chương trình sẽ tự động nạp file ghi chú này và đưa vào prompt để AI tuân thủ, tăng cường tính nhất quán.
-   **Số luồng dịch bằng số API key**:
    -   Loại bỏ cấu hình `MAX_WORKERS`. Số luồng dịch song song được tự động đặt bằng số lượng API key cung cấp để tối ưu hóa việc sử dụng.

### 🐛 Sửa lỗi (Bug Fixes)

-   **Sửa lỗi `re.PatternError`**: Khắc phục lỗi nghiêm trọng khi biên dịch biểu thức chính quy (regex) để tìm ký tự tiếng Trung.
-   **Sửa lỗi `NameError` và `TypeError`**: Khắc phục các lỗi liên quan đến việc thiếu import thư viện và truyền sai tham số cho hàm dịch.
-   **Ổn định quy trình**: Loại bỏ các bước xác nhận và đếm ký tự không cần thiết ở đầu chương trình để quy trình chạy mượt mà hơn.


## [1.1] - (Bản ổn định hiện tại)

Đây là phiên bản được tinh chỉnh và bổ sung các tính năng cốt lõi để đảm bảo chất lượng và sự linh hoạt.

### ✨ Tính năng mới (Features)

-   **Triển khai thuật toán "Sửa lỗi Lặp lại"**:
    -   Tự động quét bản dịch sau mỗi lần dịch.
    -   Nếu phát hiện còn sót ký tự tiếng Trung, chương trình sẽ gửi lại chính bản dịch lỗi đó cho AI và yêu cầu sửa lại.
    -   Quá trình này lặp lại cho đến khi chunk hoàn toàn "sạch", được kiểm soát bởi tham số `MAX_REFINEMENT_ATTEMPTS` trong `config.ini`.
-   **Hỗ trợ dịch nguyên thư mục truyện**:
    -   Chương trình giờ đây có thể nhận một thư mục con trong `input` làm nguồn dịch.
    -   Tự động đọc và dịch tất cả các file `.txt` bên trong thư mục đó theo thứ tự tên file.
-   **Tối ưu hóa logic chia chunk**:
    -   Khi xử lý một thư mục, các file chương có dung lượng nhỏ hơn `CHUNK_SIZE` sẽ được coi là một chunk duy nhất, giúp giữ ngữ cảnh tốt hơn.
-   **Số luồng dịch bằng số API key**:
    -   Loại bỏ cấu hình `MAX_WORKERS`. Số luồng dịch song song được tự động đặt bằng số lượng API key cung cấp để tối ưu hóa việc sử dụng.

### 🐛 Sửa lỗi (Bug Fixes)

-   **Sửa lỗi `re.PatternError`**: Khắc phục lỗi nghiêm trọng khi biên dịch biểu thức chính quy (regex) để tìm ký tự tiếng Trung trong `translator.py`.
-   **Ổn định quy trình**: Loại bỏ các bước xác nhận và đếm ký tự không cần thiết ở đầu chương trình để quy trình chạy mượt mà hơn.

## [1.0] - Phiên bản Module hóa Đầu tiên

Phiên bản này đánh dấu bước chuyển đổi lớn từ một script đơn lẻ thành một dự án có cấu trúc module hóa rõ ràng.

### ✨ Tính năng mới (Features)

-   **Tái cấu trúc thành Module**: Toàn bộ mã nguồn được chia thành các file chức năng: `main.py`, `translator.py`, `smart_chunker.py`, `file_writer.py`.
-   **Cấu hình ngoài**: Tách toàn bộ cài đặt ra `config.ini` và "bộ não" AI ra `prompts.ini`.
-   **Triển khai tính năng Resume**: Xây dựng cơ chế lưu trạng thái vào thư mục `progress`, cho phép tiếp tục công việc nếu bị gián đoạn.
-   **Quản lý API và Quota**: Xây dựng `ApiManager` để xoay vòng API key và tự động xử lý khi một key hết quota.
-   **Hệ thống Logging**: Thay thế toàn bộ lệnh `print()` bằng module `logging` chuyên nghiệp, ghi lại mọi hoạt động vào file log.

### 🐛 Sửa lỗi (Bug Fixes)

-   **Sửa lỗi `configparser`**: Khắc phục các lỗi liên quan đến ký tự đặc biệt (`%`) và việc đọc giá trị nhiều dòng trong file `.ini`.
-   **Sửa lỗi đọc file ẩn**: Thêm logic để bỏ qua các file hệ thống như `.gitkeep` trong thư mục `input`.