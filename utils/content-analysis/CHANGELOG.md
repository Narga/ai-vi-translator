# Content Analysis Utility - CHANGELOG

## [1.1.1] - 2025-10-11
### Nâng cấp
- Hỗ trợ `SOURCE_PATH` có khoảng trống và giá trị có ngoặc kép; chuẩn hóa đường dẫn trước khi xử lý để tránh lỗi hệ điều hành.
- Vá lỗi 403 khi dùng File API với quay vòng key bằng cơ chế cache fileUri theo fingerprint API key và “ghim key” cho lượt gọi tương ứng; nếu hết quota, tự re-upload với key kế tiếp.
- Cho phép `SOURCE_PATH` là URL http(s); tự tải về tạm rồi upload lên Gemini; khuyến nghị dùng liên kết tải trực tiếp (Google Drive cần public direct link).

## [1.1.0] - 2025-10-11
### Nâng cấp
- Ép ngôn ngữ đầu ra hoàn toàn bằng tiếng Việt cho cả 3 tác vụ (style/glossary/relations) thông qua tiền tố chỉ dẫn, đồng thời vẫn giữ nguyên schema CSV/JSON trong prompt.
- Bổ sung AI file cache dùng Gemini File API: tải nguồn lên một lần và tái sử dụng qua file_uri, lưu metadata cục bộ.
- Điều chỉnh cấu hình nguồn: ưu tiên `SOURCE_PATH` (đường dẫn đầy đủ TỚI FILE). Nếu thiếu, chấp nhận `SOURCE_DIR` như đường dẫn đầy đủ TỚI FILE. Loại bỏ gán cứng `source-cn.txt` trong mã.

## [1.0.0] - 2025-10-11
### Thêm mới
- Ra mắt tiện ích phân tích nội dung độc lập (analysis.py) đọc config.ini cùng thư mục và tạo ba tệp: style_profile.json, glossary.csv, character_relations.csv.
- Tìm API.txt bằng cơ chế đi ngược thư mục để dùng chung hạ tầng khóa; hỗ trợ REQUEST_DELAY, temperature, và model từ config.
- Hỗ trợ ghép {SOURCE_TEXT} trong prompt hoặc tự nối block SOURCE_CN khi không có placeholder; log chi tiết và xử lý lỗi có backoff quota/rate-limit.
