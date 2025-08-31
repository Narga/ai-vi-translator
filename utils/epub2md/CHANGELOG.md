# Changelog

Tất cả các thay đổi đáng chú ý của dự án này sẽ được ghi lại trong tệp này.

## [2.0.0] - 2025-08-31

### Đã thêm (Added)
- **Trích xuất Metadata**: Tự động đọc tệp `.opf` và trích xuất toàn bộ khối `<metadata>` của sách, lưu thành một tệp `metadata.xml` riêng biệt để quản lý và tái sử dụng.
- **Chế độ xuất file linh hoạt**: Thêm tham số `--mode` với các lựa chọn:
  - `both` (mặc định): Tạo cả các tệp chương riêng lẻ và một tệp full duy nhất.
  - `single`: Chỉ tạo tệp full duy nhất.
  - `multi`: Chỉ tạo các tệp chương riêng lẻ.
- **Tùy chọn định dạng đầu ra**: Thêm tham số `--ext` cho phép lưu tệp với đuôi `.txt` nhưng nội dung vẫn là Markdown.
- **Bảo toàn thẻ `<u>`**: Thêm tham số `--underline` (`-u`) để giữ lại nguyên vẹn cặp thẻ `<u>...</u>` trong nội dung đầu ra thay vì chuyển đổi hoặc loại bỏ.
- **Hiển thị tiến trình**: Hiển thị tiến trình chuyển đổi theo dạng `(số file đã xử lý/tổng số file)` và phần trăm hoàn thành.
- **Thông tin phiên bản**: Thêm tham số `-v` / `--version` để hiển thị phiên bản hiện tại của script.

### Đã thay đổi (Changed)
- **Nâng cấp công cụ chuyển đổi**: Cải thiện khả năng chuyển đổi HTML sang Markdown, hỗ trợ tốt hơn cho các cấu trúc phức tạp như bảng (table), danh sách (list), và trích dẫn (blockquote).
- **Hành vi mặc định**: Script giờ đây sẽ mặc định tạo cả tệp riêng lẻ và tệp full, thay vì chỉ tạo các tệp riêng lẻ như trước.
- **Cấu trúc mã nguồn**: Tái cấu trúc toàn diện để hỗ trợ các tính năng mới, cải thiện khả năng đọc và bảo trì. Các hàm được module hóa rõ ràng hơn.

## [1.0.0] - 2025-08-25

### Đã thêm (Added)

- **Phiên bản đầu tiên của `epub_to_markdown.py`.**
- **Chức năng chuyển đổi cốt lõi**: Đọc và phân tích cấu trúc tệp EPUB (container.xml, .opf, manifest, spine).
- **Chuyển đổi sang Markdown**: Tích hợp thư viện `html2text` để chuyển đổi nội dung HTML sang Markdown, giữ lại các định dạng cơ bản (tiêu đề, in đậm, in nghiêng, danh sách, v.v.).
- **Hai chế độ đầu ra**:
  - Hỗ trợ xuất thành nhiều tệp Markdown, mỗi tệp tương ứng với một chương/tệp HTML.
  - Hỗ trợ gộp tất cả nội dung thành một tệp Markdown duy nhất (`--single-file`).
- **Giao diện dòng lệnh (CLI)**: Xây dựng CLI mạnh mẽ bằng `argparse` với các tùy chọn linh hoạt:
  - `-o` / `--out-dir`: Chỉ định thư mục đầu ra.
  - `-s` / `--single-file`: Kích hoạt chế độ một tệp.
  - `--include-nonspine`: Tùy chọn bao gồm các tệp HTML không thuộc luồng đọc chính.
  - `--preserve-dirs`: Tùy chọn giữ lại cấu trúc thư mục gốc.
  - `--no-index-prefix`: Tùy chọn bỏ tiền tố số thứ tự cho tên tệp.
- **Xử lý lỗi và độ bền**: Cải thiện khả năng xử lý lỗi tệp, lỗi định dạng và tự động nhận diện bảng mã (encoding).
- **Tài liệu dự án**: Tạo tệp `README.md` hướng dẫn cài đặt, sử dụng và `CHANGELOG.md` để theo dõi phiên bản.
