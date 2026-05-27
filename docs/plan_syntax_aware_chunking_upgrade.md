# Kế Hoạch Nâng Cấp Logic Chunking: Syntax-Aware & Bảo Toàn Cấu Trúc Định Dạng

Bản kế hoạch này tổng hợp các phân tích từ cấu trúc hiện tại (`report_logic_chunking_structure.md`) và đề xuất phương án kỹ thuật "Syntax-Aware Chunking" kết hợp "Placeholder Mapping" để bảo toàn 100% định dạng HTML và Markdown khi xử lý dịch thuật bằng AI.

---

## 1. Tóm tắt Hiện trạng và Mục tiêu

### Hiện trạng (Điểm yếu)
- Hệ thống hiện tại (v5.0.0) sử dụng **Sentence Aggregation** dựa trên Regex (dấu chấm câu) tại `chunker.py`.
- Cơ chế này an toàn cho Plain Text, DOCX, PDF (nhờ cơ chế Marker riêng), nhưng **chưa tối ưu cho HTML và Markdown**.
- Regex tách câu có thể cắt ngang một thẻ HTML (vd: `<a href="link.com">Đoạn 1. Đoạn 2</a>`) hoặc cú pháp Markdown (`[Link text.](url)`), làm hỏng định dạng khi gửi tới AI.

### Mục tiêu Kiến trúc Mới
1. **Chuyển đổi giao tiếp AI sang định dạng Markdown:** Ưu tiên chuyển đổi mọi đầu vào (đặc biệt HTML/EPUB) sang Markdown để tối ưu lượng token và giảm thiểu hallucination từ AI.
2. **Syntax-Aware Chunking:** Chia chunk dựa trên các Khối cú pháp (Blocks - Đoạn văn, Tiêu đề, Bảng) thay vì tách chuỗi ký tự thô.
3. **Placeholder Mapping:** Mã hóa các liên kết URL, thẻ HTML phức tạp hoặc code blocks thành biến tạm (`{{LINK_1}}`, `{{TAG_1}}`) để AI không can thiệp, sau đó giải mã (restore) nguyên vẹn.

---

## 2. Kế hoạch Triển khai (4 Phase Chi tiết)

### Phase 1: Xây dựng Lớp Phân tích & Bảo vệ (Protective Tokenization)
**Mục tiêu:** Nhận diện và trích xuất các cấu trúc phức tạp ra khỏi đoạn văn bản trước khi chia chunk.

**1. Thay đổi/Cài đặt Thư viện:**
- Bổ sung `markdown-it-py` (Parser Markdown ra AST - Cây cú pháp trừu tượng).
- Bổ sung `beautifulsoup4` (Xử lý DOM HTML).

**2. Viết mới mã nguồn (Thư mục đề xuất: `plugins/translation/format_protector.py`):**
- **Hàm `extract_placeholders(text, format_type='markdown') -> Tuple[str, dict]`**:
    - **Logic:** Sử dụng regex kết hợp AST để tìm các URL, thẻ HTML, thẻ in đậm/nghiêng phức tạp.
    - **Hành động:** Thay thế chúng bằng chuỗi bảo vệ, vd: `[Link text](https://...)` -> `[Link text]({{URL_001}})`.
    - **Trả về:** Chuỗi đã thay thế (an toàn cho regex tách câu) và một Dictionary ánh xạ `{ "{{URL_001}}": "https://..." }`.
- **Hàm `restore_placeholders(translated_text, mapping_dict) -> str`**:
    - **Logic:** Sau khi nhận kết quả từ AI, thay thế ngược các key `{{URL_001}}` thành giá trị ban đầu.

### Phase 2: Nâng cấp Thuật toán Cắt File (Syntax-Aware Chunking)
**Mục tiêu:** Không bao giờ cắt ngang một Block định dạng.

**1. Nâng cấp File: `plugins/translation/chunker.py`**
- **Sửa đổi hàm `_split_into_sentences(text)`**:
    - *Tối ưu:* Trước khi chạy Regex dấu câu, văn bản phải được đi qua `extract_placeholders`. Điều này đảm bảo Regex sẽ bỏ qua việc cắt câu bên trong các Placeholder.
- **Viết mới hàm `block_level_chunking(text, min_chars, max_chars) -> List[str]`**:
    - **Logic (Dành cho Markdown/HTML):** 
        1. Parse văn bản thành danh sách các Block (Paragraph, Table, List).
        2. Duyệt qua từng Block, cộng dồn độ dài vào buffer.
        3. Điểm cắt (Chunk boundary) CHỈ được phép nằm ở khoảng trắng (newline) giữa 2 Block.
        4. Nếu một Block đơn lẻ vượt quá `max_chars`, gọi lại `sentence_aggregate_chunking` (nhưng đã có Placeholder bảo vệ).
- **Cập nhật hàm điều phối `process_text_for_chunking`**:
    - Thêm tham số `format_type`. Nếu format là `markdown` hoặc `html`, ưu tiên gọi `block_level_chunking`. Nếu là plain text, giữ nguyên gọi `sentence_aggregate_chunking`.

### Phase 3: Điều chỉnh Pipeline Thực thi & Prompt Engineering
**Mục tiêu:** Dạy AI cách xử lý và trả về định dạng đúng cấu trúc.

**1. Cập nhật Prompt Templates (`workspace/prompts/...`)**:
- Bổ sung các chỉ thị cứng rắn bằng Markdown:
  ```markdown
  RÀNG BUỘC CẤU TRÚC:
  1. TUYỆT ĐỐI giữ nguyên 100% các ký tự định dạng Markdown (#, *, _, [], | bảng biểu).
  2. Bắt buộc giữ lại các biến định vị như {{URL_001}}, {{TAG_001}} ở đúng vị trí tương ứng trong câu tiếng Việt.
  3. KHÔNG dịch nội dung bên trong cặp dấu ngoặc vuông nếu nó đi liền với biến URL, ví dụ: [Tên gọi]({{URL_001}}).
  ```

**2. Cập nhật File: `core/executor.py`**
- **Nâng cấp hàm `_translate_single_chunk`**:
    - Gọi `extract_placeholders` trước khi gửi `chunk` đi.
    - Lưu giữ `mapping_dict` tương ứng với mỗi chunk.
    - Gọi `restore_placeholders` ngay khi nhận được kết quả `translated_chunk` từ AI.

### Phase 4: Lớp Kiểm định Định dạng (Sanity Check & Validation)
**Mục tiêu:** Chặn đứng các lỗi "ảo giác" (hallucination) của AI làm mất định dạng.

**1. Viết mới hàm kiểm tra (Thêm vào `plugins/translation/normalizer.py`):**
- **Hàm `validate_markdown_structure(original_chunk, translated_chunk) -> bool`**:
    - **Logic:** So sánh số lượng thẻ (vd: số lượng dấu `**`, số lượng `{{URL_...}}`, số lượng `#`) giữa bản gốc và bản dịch.
    - **Hành động:** Nếu lệch (vd: AI "quên" trả lại một Placeholder), ghi log WARNING, kích hoạt chiến lược Retry (yêu cầu AI dịch lại chunk đó) hoặc dùng fallback (chèn lại thủ công).
- **Cập nhật hàm `remove_markdown_formatting()`**:
    - Thêm tham số cờ (flag). Nếu mode đang là "Preserve Markdown", hàm này sẽ bị bypass (vô hiệu hóa) để không dọn dẹp mất các thẻ Markdown vừa bảo tồn.

---

## 3. Tóm tắt các tác vụ (Checklist Thực thi Code)

| Thư mục/File | Tác vụ | Chi tiết |
| :--- | :--- | :--- |
| `plugins/translation/format_protector.py` | 🟢 TẠO MỚI | Viết Regex extraction, hàm `extract_placeholders`, `restore_placeholders`. |
| `plugins/translation/chunker.py` | 🟡 NÂNG CẤP | Viết `block_level_chunking`, chỉnh sửa `process_text_for_chunking` hỗ trợ `format_type`. |
| `core/executor.py` | 🟡 NÂNG CẤP | Chèn hook gọi `extract_` trước khi dịch và `restore_` sau khi dịch. Thêm logic Retry nếu validation fail. |
| `plugins/translation/normalizer.py` | 🟡 NÂNG CẤP | Viết hàm `validate_markdown_structure`. Sửa đổi fallback dọn dẹp markdown. |
| `workspace/prompts/...` | 🔵 ĐIỀU CHỈNH | Thêm Prompt rèn luyện cách AI đối xử với định dạng và biến tạm (Few-shot prompting). |

---

> **Khuyến nghị Lựa chọn:** Toàn bộ dữ liệu HTML (từ EPUB hoặc Web) nên được đi qua bước `html2text` (đã có sẵn trong `plugins/epub_converter`) để biến thành Markdown trước khi đưa vào luồng Chunking này. Markdown + Placeholder là công thức hiệu quả nhất, tốn ít chi phí API nhất và dễ duy trì định dạng nhất trên hệ thống LLM hiện tại.
