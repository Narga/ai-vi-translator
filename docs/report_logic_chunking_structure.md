# Báo cáo Phân tích Logic Chunking và Bảo toàn Cấu trúc Tài liệu trong MTranslator

Dựa trên việc nghiên cứu mã nguồn của dự án **Novel-Translator** (MTranslator), dưới đây là phân tích chi tiết về các giải thuật, logic xử lý và phương án kỹ thuật được sử dụng để thực hiện việc chia nhỏ tập tin (chunking) và bảo toàn cấu trúc (style, hình ảnh, liên kết) sau khi dịch bằng AI.

---

## 1. Logic và Giải thuật Chia nhỏ Tập tin (Chunking)

Hệ thống sử dụng một quy trình chia nhỏ thông minh để đảm bảo AI nhận được ngữ cảnh đầy đủ và không bị ngắt quãng giữa chừng.

### 1.1. Thuật toán Sentence Aggregation (v5.0.0)
Nằm tại `plugins/translation/chunker.py`, đây là thuật toán chủ đạo:
- **Tách câu (Sentence Splitting)**: Sử dụng Biểu thức chính quy (Regex) hỗ trợ đa ngôn ngữ (Latin, Trung, Nhật, Hàn) để tách văn bản thành các câu hoàn chỉnh dựa trên các dấu kết thúc: `. ! ? 。 ！ ？ … 》 」 』`.
- **Dồn câu vào Buffer**: Thay vì cắt theo số ký tự cứng nhắc, hệ thống duyệt qua từng câu và dồn vào một bộ đệm (buffer).
- **Kiểm soát kích thước**: Chỉ khi việc thêm câu tiếp theo làm kích thước buffer vượt quá `max_chars` (mặc định khoảng 20,000 - 22,000 ký tự), hệ thống mới chốt một "chunk".
- **Đảm bảo 100% không cắt ngang câu**: Điều này giúp AI hiểu trọn vẹn ý nghĩa của câu, tránh tình trạng dịch sai do mất đầu hoặc mất đuôi câu.

### 1.2. Giải thuật Cắt Heuristic (Heuristic Cutting)
Trong trường hợp gặp một câu quá dài (vượt quá `max_chars`), hệ thống sử dụng hàm `_find_best_cut_position`:
- **Trọng số dấu câu (Weighting)**: Ưu tiên cắt tại các vị trí có dấu câu mạnh:
    - `. ! ? 。 ！ ？` (Trọng số 1.0)
    - `\n\n` (Trọng số 0.9)
    - `\n` (Trọng số 0.7)
    - `, ` (Trọng số 0.3)
- **Điểm Proximity (Gần điểm lý tưởng)**: Ưu tiên các điểm cắt nằm trong khoảng 80% của kích thước tối đa để tối ưu hóa cửa sổ ngữ cảnh cho AI.

---

## 2. Giải pháp Bảo toàn Cấu trúc và Định dạng

Dự án sử dụng cơ chế **"Chỉ dẫn Ngữ cảnh" (Format Hints)** và **"Đánh dấu Cấu trúc" (Structural Markers)** để đảm bảo bản dịch trả về vẫn giữ đúng phong cách của bản gốc.

### 2.1. Trích xuất và Truyền tải Hint (Gợi ý định dạng)
Nằm tại `plugins/ocr/modules/formats.py` và `ai_processor.py`:
- **Metadata trích xuất**: Hệ thống quét các thuộc tính của đoạn văn (Paragraph) như:
    - **Style**: Heading (Tiêu đề) vs Normal (Văn bản thường).
    - **Font Size**: Cỡ chữ lớn thường là tiêu đề, cỡ chữ nhỏ có thể là chú thích.
    - **Attributes**: In đậm (Bold), in nghiêng (Italic), căn lề (Alignment).
    - **Position**: Vị trí trong trang (Đầu trang, giữa trang, cuối trang).
- **Nhúng vào Prompt**: Các thông tin này được biến thành chỉ dẫn cho AI:
    - "Style: Heading 1 (có thể là header/title), Vị trí: Đầu trang"
- **Lệnh thực thi**: AI được ra lệnh: *"Giữ nguyên cấu trúc ngắt đoạn của văn bản gốc"*, *"Giữ nguyên định dạng đoạn văn"*.

### 2.2. Bảo toàn Hình ảnh và Bảng biểu (Images & Tables)
- **Hình ảnh (Images)**:
    - Khi đọc file (DOCX/PDF), hệ thống lưu lại vị trí của ảnh (`run_index` hoặc tọa độ `Y-position`).
    - Sau khi AI dịch xong văn bản, hàm `re_insert_images_to_paragraph` sẽ chèn lại các đối tượng ảnh vào đúng vị trí tương ứng trong văn bản đã dịch.
- **Bảng biểu (Tables)**:
    - Sử dụng **Coordinate Markers**: Nội dung bảng được format thành dạng:
      `[CELL R=row C=col]Nội dung ô[END CELL]`
    - AI được huấn luyện (qua prompt) để dịch nội dung bên trong cặp thẻ mà không làm thay đổi các ký tự điều hướng `R=... C=...`.
    - Sau khi dịch, hệ thống parse lại các thẻ này để tái cấu trúc bảng.

### 2.3. Quy trình Xử lý "In-place Update" (Cập nhật tại chỗ)
Đối với định dạng DOCX:
- Hệ thống không thay thế toàn bộ đoạn văn mà cập nhật văn bản vào các `Run` object hiện có.
- Điều này giúp giữ lại các thuộc tính font chữ, màu sắc và kiểu dáng đã được thiết lập trong file gốc ngay cả khi nội dung đã được thay đổi sang tiếng Việt.

---

## 3. Quy trình Hoạt động Tổng quát (Workflow)

1.  **Giai đoạn Tiền xử lý (Preprocessing)**:
    - Phát hiện encoding, tách câu, chia chunk theo Sentence Aggregation.
    - Trích xuất Metadata (style, hình ảnh, tọa độ).
2.  **Giai đoạn Dịch thuật (AI Translation)**:
    - Gửi chunk kèm theo `previous_chunk_context` (ngữ cảnh của chunk trước đó) để đảm bảo tính nhất quán.
    - Nhúng Bảng thuật ngữ (Glossary) vào prompt để giữ đúng tên nhân vật/địa danh.
    - AI thực hiện dịch và tuân thủ các chỉ dẫn bảo toàn cấu trúc.
3.  **Giai đoạn Hậu xử lý (Post-processing)**:
    - `TextNormalizer`: Chuẩn hóa dấu ngoặc, dấu gạch ngang, dọn dẹp rác OCR.
    - **Re-construction**: Chèn lại hình ảnh, liên kết và định dạng dựa trên Metadata đã lưu.
    - **Merge**: Kết hợp các chunk đã dịch thành tập tin hoàn chỉnh.

---

> **Điểm mấu chốt**: Bí mật của việc bảo toàn cấu trúc không nằm ở việc AI "thông minh", mà nằm ở việc hệ thống **đóng gói văn bản kèm theo "bộ khung" siêu dữ liệu** và sử dụng các **thẻ đánh dấu (markers)** mà AI không được phép xâm phạm.
