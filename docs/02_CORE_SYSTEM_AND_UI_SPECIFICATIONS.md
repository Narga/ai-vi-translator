# 02. ĐẶC TẢ HỆ THỐNG CỐT LÕI & CHỈ DẪN CẤU HÌNH
> **Mục tiêu**: Định nghĩa chuẩn xác cấu trúc hệ thống gửi–nhận, định vị đường dẫn độc lập CWD, kiểm tra an toàn đường dẫn và hướng dẫn nhập cấu hình, API key.

---

## 1. CẤU HÌNH DỰ ÁN & API KEY NHẬP VÀO ĐÂU?

Hệ thống cung cấp 3 cách nạp API Key rõ ràng, linh hoạt, tự động fallback:

### 1.1. Nạp API Key (3 Cách)
* **Cách 1 (Chuẩn nhất cho người dùng cá nhân)**:
  * Mở file `config/keys.json` (hệ thống tự tạo file mẫu nếu chưa có) và dán các key vào:
    ```json
    {
      "gemini_keys": [
        "AIzaSyD-KEY_1",
        "AIzaSyD-KEY_2"
      ]
    }
    ```
  * File này đã được đưa vào `.gitignore`, không bao giờ bị lộ lên Git.
* **Cách 2 (Biến môi trường - Phù hợp khi chạy VPS)**:
  * Khai báo trong terminal hoặc file `.env`:
    ```bash
    export GEMINI_API_KEYS="AIzaSyD-KEY_1,AIzaSyD-KEY_2"
    ```
* **Cách 3 (Nhập tương tác CLI)**:
  * Nếu cả 2 cách trên đều chưa có key, khi chạy lệnh `python run.py`, màn hình sẽ hỏi trực tiếp:
    ```text
    👉 Chưa tìm thấy API Key! Nhập Gemini API Key của bạn: AIzaSy...
    ```
    và tự động ghi nhớ vào `config/keys.json`.

### 1.2. Nạp Cấu Hình Chung (`config/config.json`)
Chứa các tham số vận hành, có kiểm tra tính hợp lệ tối thiểu (`max_chunk_chars > 0`, `timeout_seconds > 0`):
```json
{
  "provider": "gemini",
  "gemini_model": "gemini-2.5-flash",
  "max_chunk_chars": 16000,
  "timeout_seconds": 90
}
```

### 1.3. Nạp Nội Dung Cần Dịch
* **Chế độ trực tiếp**: Để file ở bất kỳ đâu trên máy tính và chạy:
  `python run.py /duong/dan/input.txt /duong/dan/output.txt`
* **Chế độ dự án**: Tạo thư mục dự án trong `workspace/projects/{ten_du_an}/sources/` và đặt file nguồn vào đó.

---

## 2. ĐỊNH VỊ ĐƯỜNG DẪN ĐỘC LẬP THƯ MỤC CHẠY LỆNH (PROJECT_ROOT)

Để tránh lỗi khi người dùng đứng ở bất kỳ thư mục nào chạy lệnh (`cd /tmp && python /path/to/content-translator/run.py`), toàn bộ đường dẫn của ứng dụng được tính dựa trên vị trí của file mã nguồn:

```python
# PROJECT_ROOT luôn là thư mục gốc của dự án content-translator
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # (nếu gọi từ core/)
# Hoặc
PROJECT_ROOT = Path(__file__).resolve().parent         # (nếu gọi từ run.py)

CONFIG_DIR = PROJECT_ROOT / "config"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
```

* **Lợi ích**: Không bao giờ tạo nhầm thư mục `workspace/` hoặc `config/` ở nơi khác khi chạy lệnh ngoài thư mục dự án.

---

## 3. AN TOÀN ĐƯỜNG DẪN (CHỐNG PATH TRAVERSAL BẰNG `relative_to()`)

Trong chế độ `--project`, cả `slug` và `filename` phải được kiểm tra chặt chẽ trước khi truy cập ổ cứng:

1. **Quy tắc Sanitize tên file & slug**:
   * Không được rỗng.
   * Không chứa ký tự đi lùi thư mục `..`.
   * Không chứa dấu phân cách thư mục `/` hoặc `\`.
2. **Kiểm tra lồng thư mục bằng `relative_to()`**:
   * Thay vì dùng `startswith()` (dễ bị lỗi chuỗi tương đồng như `/tmp/workspace2` với `/tmp/workspace`), hệ thống bắt buộc dùng:
     ```python
     resolved = target_path.resolve()
     try:
         resolved.relative_to(base_dir.resolve())
     except ValueError:
         raise ValueError(f"Đường dẫn không hợp lệ, nằm ngoài phạm vi cho phép: {target_path}")
     ```
3. **Quy tắc trong `run.py`**:
   * Tuyệt đối không tự nối chuỗi `proj_dir / "sources" / fname`.
   * Bắt buộc phải gọi qua phương thức chuyên trách: `file_handler.get_source_path(project, filename)`.

---

## 4. QUY TRÌNH CHIA CHUNK THỰC TẾ & QUY ƯỚC GHÉP NỐI

### 4.1. Kích Thước & Số Lượng Chunk
* Cấu hình mặc định: `max_chunk_chars = 16000` ký tự.
* Với các chương truyện có kích thước phổ biến (15.000 – 45.000 ký tự), hệ thống **thường tạo khoảng 2–3 chunk**; file dài hơn sẽ tạo nhiều chunk hơn tùy theo độ dài thực tế.

### 4.2. Cam Kết Nội Dung & Quy Ước Khoảng Trắng
* **Cam kết nội dung**: Bảo toàn 100% nội dung có ý nghĩa, không bỏ sót câu/đoạn văn bản nguồn ở tầng phân chia chunk.
* **Quy ước ghép nối**: Các chunk sau khi dịch xong được ghép nối với nhau bằng **một dòng trống (`\n\n`)**. Khoảng trắng quanh ranh giới cắt được chuẩn hóa theo quy ước này; không cam kết bảo toàn tuyệt đối từng byte khoảng trắng gốc.
* **Kỳ vọng đối với AI**: Tiêu chuẩn nghiệm thu của mã nguồn là: Gửi đầy đủ các chunk, nhận response hợp lệ từ AI, không bỏ qua chunk nào và ghép nối chính xác theo quy ước. Người dùng luôn là người kiểm tra kết quả cuối cùng trước khi sử dụng.

---

## 5. CƠ CHẾ XOAY KEY TỐI GIẢN (GEMINI CLIENT)

* **Chính sách**:
  * Mỗi key chỉ được thử tối đa một lần trong một lần gửi chunk.
  * Nếu gặp lỗi 429 và còn key khác trong danh sách $\to$ Chuyển lần lượt sang key kế tiếp.
  * Với trường hợp chỉ có duy nhất 1 key trong danh sách $\to$ Gặp 429 dừng ngay lập tức.
  * Nếu tất cả key đều gặp 429 $\to$ Dừng toàn bộ chương trình, báo lỗi rõ ràng.
* **Chính sách giữa các chunk**:
  * Mỗi chunk là một phiên gửi độc lập.
  * Bắt đầu từ key đang hoạt động thành công của chunk trước để tận dụng quota.
* **Chính sách thất bại**:
  * Dừng toàn bộ chương trình ngay lập tức và KHÔNG lưu trạng thái dở dang.
  * Người dùng chạy lại lệnh sẽ bắt đầu lại toàn bộ file từ chunk đầu tiên.
