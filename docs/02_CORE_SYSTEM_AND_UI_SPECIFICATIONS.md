# 02. ĐẶC TẢ HỆ THỐNG CỐT LÕI & CHỈ DẪN CẤU HÌNH
> **Mục tiêu**: Định nghĩa chuẩn xác cấu trúc hệ thống gửi–nhận, định vị đường dẫn độc lập CWD, kiểm tra an toàn đường dẫn và hướng dẫn nhập cấu hình, API key.
> **Phiên bản**: v2.3 (04/09/2026) — thêm đa provider explicit + app.db từ Phase 1.

---

## 1. CẤU HÌNH DỰ ÁN & API KEY NHẬP VÀO ĐÂU? (v2.4: providers.json SSOT)

`config/providers.json` là nguồn sự thật duy nhất (chi tiết: `docs/06_AI_MODELS_MANAGEMENT_SPEC.md`):

```json
{"version": 1, "active_id": "gemini-default", "providers": [
  {"id": "gemini-default", "type": "gemini", "name": "Google Gemini", "api_keys": [], "default_model": ""},
  {"id": "openai-compat", "type": "openai", "name": "OpenAI-Compatible", "api_key": "", "base_url": "https://openrouter.ai/api/v1", "default_model": ""}
]}
```

* **Không hardcode model trong code.** Model lấy live từ API provider (`GET /models`), cache 5 phút, fallback mềm khi mất mạng. Người dùng chọn từ danh sách hoặc tự nhập (có namespace validation).
* **Nhập key**: WebUI trang Cấu Hình — keys hiện **đầy đủ**, sửa trực tiếp trong danh sách (xóa dòng = xóa key); hoặc sửa trực tiếp file, hoặc CLI hỏi khi thiếu. Ghi file kiểu atomic (`.tmp` → validate → `.bak` → `os.replace`).
* **Thêm provider**: nút `＋ Thêm provider` trên UI (tên, loại, base_url, key) — không cần sửa file tay.
* **Model metadata**: `list_models` giữ full object (limits/pricing/free); `model_info` cho input/output/context + quota (OpenRouter) hoặc link quota AI Studio (Gemini).
* **Thinking** (mặc định OFF, per-provider): OFF/LOW/MEDIUM/HIGH → thinkingBudget 0/1024/8192/24576. **Chỉ Gemini**; OpenAI-compatible bỏ qua hoàn toàn.
* **Prefs request** (`config/config.json`): `max_chunk_chars` (Chunk Size, ký tự), `api_delay_seconds` (giây chờ giữa các request, tránh 429), `timeout_seconds` (chờ phản hồi AI).
* **Migration 1 chiều**: `keys.json`/`config.json` cũ tự chuyển sang `providers.json` lần đầu chạy. `config/providers.json*` đã gitignore.
* `config/config.json` chỉ còn prefs app (`max_chunk_chars`, `timeout_seconds`).

### 1.2. Nạp Nội Dung Cần Dịch
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

## 5. CƠ CHẾ XOAY KEY TỐI GIẢN (DÙNG CHUNG 2 PROVIDERS)

* **Chính sách**:
  * Mỗi key chỉ được thử tối đa một lần trong một lần gửi chunk (tái dùng `KeyRotator` cho cả Gemini và OpenAI-compatible).
  * Nếu gặp lỗi 429 và còn key khác trong danh sách $\to$ Chuyển lần lượt sang key kế tiếp.
  * Với trường hợp chỉ có duy nhất 1 key trong danh sách $\to$ Gặp 429 dừng ngay lập tức.
  * Nếu tất cả key đều gặp 429 $\to$ Dừng toàn bộ chương trình, báo lỗi rõ ràng.
  * **Không fallback model**: hết key của model đang chọn thì dừng, không tự đổi sang model khác.
* **Chính sách giữa các chunk**:
  * Mỗi chunk là một phiên gửi độc lập.
  * Bắt đầu từ key đang hoạt động thành công của chunk trước để tận dụng quota.
* **Chính sách thất bại**:
  * Dừng toàn bộ chương trình ngay lập tức và KHÔNG lưu trạng thái dở dang.
  * Người dùng chạy lại lệnh sẽ bắt đầu lại toàn bộ file từ chunk đầu tiên.

---

## 6. DATABASE TỐI THIỂU TỪ PHASE 1 (`workspace/app.db`)

* Tạo từ lần chạy đầu tiên bằng stdlib `sqlite3`, không thêm dependency. Nằm trong `workspace/` nên đã gitignore.
* Chỉ 3 bảng để **index + log, không checkpoint nội dung**:
  ```sql
  CREATE TABLE IF NOT EXISTS projects(slug TEXT PRIMARY KEY, title TEXT, created_at TEXT);
  CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY, project_slug TEXT, filename TEXT,
    size_bytes INT, char_count INT, chunk_count INT, status TEXT DEFAULT 'new',
    updated_at TEXT, UNIQUE(project_slug, filename));
  CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, file_id INT, provider TEXT,
    model TEXT, started_at TEXT, finished_at TEXT, status TEXT, error TEXT);
  ```
* Dùng ngay ở Phase 1: CLI cập nhật `files` sau mỗi lần dịch, ghi 1 dòng `runs` (provider/model/thời gian/lỗi). Bảng `chunks/checkpoints` và FTS5 để dành Phase 3+ (xem ROADMAP).
