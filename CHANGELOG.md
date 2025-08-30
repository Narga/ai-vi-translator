# Changelog - Lịch sử thay đổi


## [2.0.1] - Sửa lỗi Nghiêm trọng và Hoàn thiện Tái cấu trúc

### 🐛 Sửa lỗi (Bug Fixes)

* **Sửa lỗi `ImportError`:** Khắc phục lỗi không nhất quán về tên hàm (`load_prompts`) giữa `workflow.py` và `configuration.py`, đảm bảo module được nạp chính xác.
* **Sửa lỗi `SyntaxError`:** Sửa các lỗi cú pháp do thiếu dấu ngoặc nhọn `}` trong các chuỗi f-string ở `workflow.py` và `translator.py`.
* **Sửa lỗi `NameError`:** Bổ sung `from threading import Lock` vào `translator.py` để khắc phục lỗi `name 'Lock' is not defined`.

### ✒️ Chất lượng Mã nguồn (Code Quality)

* **Hoàn thiện Ghi chú:** Rà soát và bổ sung comment chi tiết, chuyên nghiệp cùng docstring đầy đủ cho tất cả các file và hàm trong dự án, đảm bảo mã nguồn rõ ràng, dễ đọc, dễ bảo trì và nâng cấp.


# [2.0.0] - Phiên bản Tái cấu trúc Lớn

## 🚀 Tái cấu trúc & Tối ưu hóa (Refactoring & Optimizations)

* **Tái cấu trúc mã nguồn sang `src/`:**
    * Di chuyển toàn bộ các module xử lý lõi (`translator.py`, `smart_chunker.py`, `file_writer.py`) vào thư mục `src/`.
    * Tách `main.py` thành các module chức năng chuyên biệt:
        * `src/configuration.py`: Quản lý việc nạp và xử lý tất cả các file cấu hình.
        * `src/workflow.py`: Chứa toàn bộ logic điều phối quy trình dịch thuật từ đầu đến cuối.
    * `main.py` giờ đây chỉ còn vai trò là điểm khởi đầu (entry point), giúp cấu trúc dự án cực kỳ gọn gàng, chuyên nghiệp và dễ bảo trì.

## ✨ Cải tiến (Enhancements)

* **Nâng cấp Thuật toán Cắt file:**
    * Tích hợp hoàn toàn thuật toán `intelligent_chunking` mới do người dùng cung cấp vào module `src/smart_chunker.py`.
    * Thuật toán mới kết hợp khả năng nhận diện tiêu đề chương và phương pháp cắt đoạn dựa trên ngữ cảnh (trọng số dấu câu), giúp các chunk được chia ra một cách tự nhiên nhất.
* **Cập nhật Cấu hình Mặc định:**
    * Bổ sung các comment chi tiết, tỉ mỉ cho từng mục trong `config.ini`.

## ✒️ Chất lượng Mã nguồn

* **Review và Ghi chú Chi tiết:** Toàn bộ mã nguồn đã được rà soát và bổ sung comment chi tiết, chuyên nghiệp theo chuẩn phát hành chính thức, giúp người khác có thể đọc hiểu, bảo trì và nâng cấp trong tương lai.

## [1.2.3] - Tái cấu trúc Lớn và Tối ưu hóa Cấu hình

### ✨ Cải tiến & Tái cấu trúc (Enhancements & Refactoring)

* **Tối ưu hóa Cấu trúc Dự án:**
    * Tạo thư mục `src/` mới để chứa tất cả các module xử lý lõi (`translator.py`, `file_writer.py`, `smart_chunker.py`).
    * Thư mục gốc của dự án giờ đây gọn gàng hơn, chỉ chứa các file chính: `main.py`, `README.md`, `CHANGELOG.md`, `config.ini`, và `requirements.txt`.

* **Tái cấu trúc `main.py`:**
    * `main.py` đã được tinh gọn lại, chỉ còn vai trò là điểm khởi đầu của chương trình.
    * Toàn bộ logic phức tạp đã được tách ra các module chuyên biệt mới trong `src/`:
        * `src/config_manager.py`: Chuyên quản lý việc đọc/ghi file `config.ini` và nạp toàn bộ các prompt.
        * `src/workflow_manager.py`: Chuyên điều phối toàn bộ quy trình dịch thuật (resume, chia chunk, dịch, kiểm tra, ghép file, dọn dẹp).

* **Cập nhật Cấu hình Mặc định:**
    * File `config.ini` đã được cập nhật với một bộ giá trị mặc định mới, toàn diện và tối ưu hơn, dựa trên các tham số từ phiên bản tham khảo `v13.3.9`.

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