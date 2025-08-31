# Changelog

## [2.3.1] - 2025-08-31

### Added
- **Hỗ trợ Metadata của Calibre:** Script giờ đây có khả năng đọc và ghi các metadata tùy chỉnh cho Calibre, bao gồm tên series (`calibre:series`) và chỉ số series (`calibre:series_index`) từ `metadata.xml` vào file `content.opf` cuối cùng.

### Fixed
- **Sửa lỗi `KeyError: 'title'` nghiêm trọng:** Khắc phục lỗi khiến chương trình bị dừng khi xử lý các tệp có cấu trúc không mong đợi (ví dụ: tệp không có nội dung sau tiêu đề chương cuối cùng). Script giờ đây sẽ xử lý các trường hợp này một cách an toàn mà không bị lỗi.
- **Tăng cường tính ổn định:** Bổ sung các bước kiểm tra phòng vệ trong quá trình xử lý và tạo file để đảm bảo script hoạt động ổn định hơn với nhiều loại dữ liệu đầu vào khác nhau.

## [2.3.0] - 2025-08-31

### Added
- **Cơ chế nhận dạng chương/tiêu đề nâng cao:**
  - [Chế độ Plain Text] Một dòng chỉ được xác định là tiêu đề chương nếu nó khớp với biểu thức chính quy (VD: "Chương 1").
  - Dòng ngay sau đó có thể được xác định là tiêu đề phụ nếu nó được định dạng bằng Markdown (heading `#`, bold `**`, italic `*`).
  - Các dòng không thỏa mãn điều kiện trên sẽ được coi là đoạn văn bản thông thường.
- **Thêm tùy chọn tách chương `--split-chapters`:**
  - [Chế độ Plain Text] Cho phép người dùng tự động tách một tệp `.txt` chứa nhiều chương thành nhiều tệp `.xhtml` riêng biệt.
  - Tùy chọn này chỉ được kích hoạt khi có tham số, dành cho người dùng đã kiểm tra và chuẩn bị tệp nguồn.

### Changed
- **Tái cấu trúc `parser.py`:** Logic phân tích và xử lý văn bản được viết lại hoàn toàn để hỗ trợ cơ chế nhận dạng chương mới và logic tách tệp.
- **Cập nhật `main.py`:** Luồng xử lý chính được điều chỉnh để hỗ trợ tùy chọn `--split-chapters`, quyết định việc tạo một hay nhiều tệp XHTML từ một tệp nguồn.
- **Tuân thủ tiêu chuẩn EPUB 3:** Bổ sung các ghi chú chi tiết và rà soát mã nguồn trong `epub_creator.py` để đảm bảo các thành phần như Package Document (`.opf`) và Navigation Document (`toc.xhtml`) tuân thủ chặt chẽ đặc tả kỹ thuật của EPUB 3.

## [2.2.0] - 2025-08-31

### Added
- **Thêm tham số dòng lệnh `--src-md`:** Cho phép người dùng kích hoạt một cách tường minh chế độ xử lý tệp nguồn dưới dạng Markdown.

### Changed
- **Tái cấu trúc luồng xử lý:** Script giờ đây mặc định xử lý tất cả các tệp đầu vào dưới dạng văn bản thuần túy. Chế độ xử lý Markdown chỉ được kích hoạt khi người dùng chỉ định tham số `--src-md`.
- **Logic nhận dạng tiêu đề:** Logic nhận dạng tiêu đề thông minh (`extract_full_chapter_title`) giờ đây chỉ được áp dụng cho chế độ văn bản thuần túy (mặc định). Chế độ Markdown sẽ tự động lấy tiêu đề từ thẻ `<h1>` đầu tiên.

### Dependencies
- **Thư viện `python-markdown`:** Trở thành một yêu cầu bắt buộc khi và chỉ khi sử dụng tùy chọn `--src-md`. Script sẽ tự động kiểm tra và thông báo lỗi nếu thư viện này bị thiếu khi cần thiết.

## [2.1.0] - 2025-08-31

### Added
- **Thuật toán nhận dạng tiêu đề chương thông minh:** Tự động phân tích 1-2 dòng đầu tiên của mỗi tệp để xác định tiêu đề chính và tiêu đề phụ, xử lý các định dạng Markdown (`#`, `**`) để tạo ra tên chương hoàn chỉnh cho mục lục.

### Changed
- **Tối ưu hóa luồng tạo mục lục (ToC):** Tiêu đề chương giờ đây được trích xuất một lần duy nhất và được truyền đến các hàm, thay vì mỗi hàm phải đọc lại tệp, giúp tăng hiệu quả và bảo trì mã nguồn dễ dàng hơn.
- **Nội dung đầu vào được tự động dọn dẹp:** Các ký tự gạch ngang dài (`——`) không chuẩn sẽ được tự động chuyển đổi thành ký tự gạch ngang ngắn (`-`) trong quá trình xử lý.

### Fixed
- **Sửa lỗi liên kết CSS không được áp dụng:** Khắc phục lỗi sai giá trị trong thuộc tính `type` của thẻ `<link>` (từ `text-css` thành `text/css`), đảm bảo tệp `styles.css` được áp dụng chính xác trong tệp EPUB.

## [2.0.0] - 2025-08-31

### Added
- **EPUB Packaging:** Tự động đóng gói các tệp đã xử lý thành một tệp `.epub` hoàn chỉnh.
- **New Module `epub_creator.py`:** Thêm module mới chuyên dụng để tạo cấu trúc thư mục EPUB, sinh các tệp metadata (`content.opf`, `toc.ncx`, `toc.xhtml`, `container.xml`), và thực hiện việc nén thành tệp `.epub`.
- **Automatic ToC Generation:** Tự động tạo mục lục (Table of Contents) cho cả EPUB3 (`toc.xhtml`) và EPUB2 (`toc.ncx`) bằng cách trích xuất tiêu đề từ mỗi tệp chương.
- **Asset Handling:** Tự động sao chép các tài sản cần thiết như `styles.css`, `cover.jpg`, và thư mục `Fonts` vào đúng vị trí trong cấu trúc EPUB.

### Changed
- **Output Directory:** Các tệp `.xhtml` bây giờ được tạo trong một thư mục con `epub/OEBPS/Text` thay vì ở thư mục gốc, tuân thủ theo cấu trúc EPUB tiêu chuẩn.
- **`main.py`:** Cập nhật để gọi module `epub_creator` sau khi quá trình chuyển đổi HTML hoàn tất.
- **`metadata_parser.py`:** Mở rộng để trích xuất thêm các siêu dữ liệu cần thiết cho việc đóng gói như `creator`, `identifier`, và `date`.
- **`parser.py`:** Thêm hàm `extract_chapter_title` để lấy tiêu đề chính từ mỗi tệp văn bản, phục vụ cho việc tạo mục lục.

## [1.0.0] - 2025-08-31

### Added
- **Initial Release:** Script Python 3 để tự động chuyển đổi các tệp văn bản (.txt) sang định dạng HTML (.xhtml) tương thích với EPUB3.
- **Modular Structure:** Tách mã nguồn thành các module riêng biệt (`main.py`, `parser.py`, `file_utils.py`, `metadata_parser.py`) để tăng tính rõ ràng, dễ bảo trì và mở rộng.
- **Command-Line Interface (CLI):** Tích hợp `argparse` để người dùng có thể dễ dàng chỉ định thư mục sách cần xử lý từ dòng lệnh.
- **Metadata Parsing:** Tự động đọc tệp `metadata.xml` để trích xuất tiêu đề và ngôn ngữ của sách, sau đó đưa vào các tệp HTML được tạo ra.
- **Content Recognition:**
    - Sử dụng biểu thức chính quy (Regex) để tự động nhận dạng và định dạng các tiêu đề Quyển, Chương, và các tiêu đề phụ.
    - Chuyển đổi các dòng văn bản thông thường thành các thẻ `<p>`.
    - Nhận dạng dấu phân cách `***` và chuyển thành thẻ `<hr>`.
- **EPUB3 Compliance:**
    - Tạo ra các tệp `.xhtml` với cấu trúc HTML5 chuẩn.
    - Tự động liên kết đến tệp `styles.css` theo cấu trúc thư mục EPUB tiêu chuẩn (`../Styles/styles.css`).
    - Đảm bảo tất cả các tệp được đọc và ghi với mã hóa UTF-8.
- **Cross-Platform Compatibility:** Sử dụng thư viện `pathlib` để đảm bảo script hoạt động mượt mà trên macOS, Linux và Windows.
- **Documentation:** Cung cấp tài liệu và bình luận chi tiết, chuyên nghiệp bằng tiếng Việt trong toàn bộ mã nguồn.