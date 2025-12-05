# EPUB Converter Pro

Một công cụ dòng lệnh chuyên nghiệp, mạnh mẽ và linh hoạt được viết bằng Python để chuyển đổi sách điện tử định dạng EPUB. Công cụ này không chỉ trích xuất nội dung sang Markdown mà còn bảo toàn tối đa cấu trúc, định dạng và metadata quan trọng của sách.

## Tính năng chính

- **Chuyển đổi chất lượng cao**: Chuyển đổi nội dung HTML sang Markdown, bảo toàn định dạng văn bản như tiêu đề, in đậm, in nghiêng, danh sách, trích dẫn, và cả bảng biểu.
- **Trích xuất Metadata**: Tự động đọc và lưu toàn bộ metadata của sách (tiêu đề, tác giả, ISBN, NXB,...) vào một tệp `metadata.xml`, thuận tiện cho việc quản lý và lưu trữ.
- **Chế độ xuất file linh hoạt**: Toàn quyền kiểm soát kết quả đầu ra:
  - Xuất mỗi chương thành một tệp riêng lẻ.
  - Gộp tất cả các chương vào một tệp duy nhất.
  - Xuất đồng thời cả hai loại trên (mặc định).
- **Tùy biến cao**: Cung cấp nhiều tùy chọn dòng lệnh để kiểm soát định dạng, cấu trúc thư mục, tên tệp, và nhiều hơn nữa.
- **Hiển thị tiến trình**: Theo dõi quá trình chuyển đổi với thông báo tiến trình rõ ràng theo thời gian thực.
- **Xử lý lỗi thông minh**: Cung cấp thông báo lỗi chi tiết giúp dễ dàng xác định vấn đề.
- **Tương thích đa nền tảng**: Hoạt động mượt mà trên Windows, macOS và Linux.

## Các module yêu cầu

Script này yêu cầu các module Python sau:

- **Thư viện chuẩn**:
  - `argparse`
  - `os`
  - `re`
  - `sys`
  - `zipfile`
  - `xml.etree.ElementTree`
  - `xml.dom.minidom` (dùng để làm đẹp file XML metadata)

- **Thư viện bên ngoài**:
  - `html2text`: Cần được cài đặt để thực hiện việc chuyển đổi từ HTML sang Markdown.

## Tùy chọn dòng lệnh (Command-Line Options)

| Tham số | Viết tắt | Mô tả | Mặc định |
| :--- | :--- | :--- | :--- |
| `epub_path` | | **(Bắt buộc)** Đường dẫn đến tệp `.epub` cần chuyển đổi. | |
| `--out-dir` | `-o` | Thư mục để lưu các tệp kết quả. | `output` |
| `--mode` | | Chế độ tạo tệp: `both` (cả riêng lẻ và full), `single` (chỉ full), `multi` (chỉ riêng lẻ). | `both` |
| `--ext` | | Đuôi tệp đầu ra cho các tệp nội dung. Có thể chọn `md` hoặc `txt`. | `md` |
| `--underline`| `-u` | Giữ lại (không chuyển đổi) các cặp thẻ `<u>...</u>` trong nội dung. | `False` |
| `--include-nonspine` | | Bao gồm cả các tệp HTML không nằm trong luồng đọc chính của sách. | `False` |
| `--preserve-dirs` | | Giữ nguyên cấu trúc thư mục của EPUB (chỉ áp dụng ở chế độ `multi` hoặc `both`). | `False` |
| `--no-index-prefix` | | Không thêm tiền tố số thứ tự vào tên tệp (chỉ áp dụng ở chế độ `multi` hoặc `both`). | `False` |
| `--version` | `-v` | Hiển thị phiên bản của script và thoát. | |
| `--help` | `-h` | Hiển thị thông tin hướng dẫn chi tiết và thoát. | |