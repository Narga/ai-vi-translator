# 🛠️ Hướng Dẫn Phát Triển & Coding Convention

Tài liệu này dành cho các lập trình viên muốn đóng góp hoặc mở rộng hệ thống Content Translator.

## 0. Mục Đích Dự Án & Nguyên Tắc Thiết Kế

Dự án phục vụ **một người dùng duy nhất**: biên dịch nội dung text của sách điện tử từ ngoại ngữ sang tiếng Việt, ưu tiên **chất lượng dịch** và thói quen cá nhân. Mọi quyết định kiến trúc nghiêng về tối giản và đúng-ngữ-cảnh-sử-dụng thay vì tổng quát hóa.

**Nguyên tắc cốt lõi:**

- **Chỉ xử lý text**: Công cụ không resolve, copy, hay rewrite ảnh/font/style — người dùng tự đưa vào khi biên tập bằng phần mềm chuyên dụng (Sigil/Calibre).
- **EPUB tối thiểu, mở được**: Output là EPUB 3 đúng cấu trúc `OEBPS/` (Sigil-style) với metadata tối thiểu. Mọi thứ tự sinh (nav, titlepage, cover) bị loại bỏ có chủ đích.
- **Ghi file an toàn mặc định**: atomic write (`os.replace` từ temp) + từ chối ghi đè trùng nguồn.
- **"Đơn giản hơn" > "tổng quát hơn"**: ví dụ — footnote dùng cú pháp chuẩn `[^id]` thay vì hệ placeholder riêng; dùng python-markdown thay vì tự viết parser regex.

Khi thêm tính năng, hỏi: *"Một người dùng cá nhân biên tập sách dịch của mình có thực sự cần cái này, hay đây là over-engineering?"* Nếu không chắc → đưa vào mục "Đã hoãn" của ROADMAP.md thay vì code.

## 1. Kiến Trúc Phân Tầng (Architectural Layers)

Hệ thống được cấu trúc thành ba lớp chức năng chính:

1.  **Lớp Chiến lược (`ExecutionManager`)**: Quản lý toàn bộ nhiệm vụ dịch thuật, quyết định số lượng worker tối ưu dựa trên sức khỏe hệ thống và giám sát tiến độ toàn cục.
2.  **Lớp Điều phối (`ApiManager` / `AdaptiveRateLimiter`)**: Quản lý vòng đời của API key, phân loại lỗi (quota, rate limit, invalid key), điều tiết RPM toàn cục và thực hiện logic xoay vòng key thông minh (`least_used` / `round_robin`). Xem đặc tả chi tiết tại [🔑 Kiến Trúc & Cơ Chế Xoay Vòng API Key](API_KEY_ROTATION.md).
3.  **Lớp Thực thi (`Worker`)**: Các tác vụ asyncio/threading độc lập thực hiện dịch các chunk và phản hồi trạng thái.

---

## 2. Các Giải Thuật Cốt Lõi (Core Algorithms)

### A. Gắn kết Worker-Key (Worker-Key Affinity)
Mỗi Worker được gán một **Preferred Key** duy nhất để tối đa hóa khả năng caching phía server Gemini. Nếu key bị lỗi, hệ thống sẽ tự động "mượn" key từ **Reserve Pool** trong vòng `< 1ms` để duy trì tiến độ.

### B. Kiểm soát Lưu lượng Động (Dynamic Throughput)
Hệ thống sử dụng cơ chế **Tự thích nghi (Adaptive Scaling)**:
- Theo dõi tỷ lệ thành công (success_rate) và lỗi 429 (quota_error).
- Tự động giảm số lượng worker nếu phát hiện lỗi Quota hàng loạt và vào chế độ **Khởi động chậm (Slow-Start)**.

### C. Bộ giới hạn Tốc độ Toàn cục & Xoay vòng Key (Global Rate Limiter & Key Rotation)
- Sử dụng cơ chế **Cửa sổ trượt 60 giây (Sliding Window Log)** để theo dõi RPM tổng, ngăn chặn vượt ngưỡng IP cho phép.
- Điều phối key thích ứng dựa trên **Least-Used + Round-Robin Offset** và xử lý lỗi phân tầng (Exponential Backoff, Quota Cooldown 30m, Invalid Key Cooldown 24h).
- Chi tiết giải thuật và mã nguồn: [API_KEY_ROTATION.md](API_KEY_ROTATION.md).

### D. Sentence Aggregation (Chunking)
Thuật toán dồn câu để đảm bảo ranh giới chunk không cắt ngang ý nghĩa.

### E. Jaccard Similarity (Translation Memory)
So sánh tập hợp N-gram để tìm kiếm câu tương đồng trong bộ nhớ dịch thuật.

---

## 3. Cấu Trúc Thư Mục Dự Án

```
novel-translator/
├── main.py                 # Entry point cho Web UI (Flask)
├── cli.py                  # Entry point cho CLI (argparse)
├── webui/                  # 📦 Flask App Package
│   ├── __init__.py        # App Factory + global state
│   ├── helpers.py         # Utilities dùng chung
│   ├── routes/            # Flask Blueprints
│   │   ├── translation.py # Worker + SSE streaming
│   │   ├── settings.py    # Models, Config, Stats, Cache
│   │   ├── prompts.py     # Prompt Sets CRUD
│   │   ├── projects.py    # Project workspace + TM APIs
│   │   └── plugins.py     # EPUB Converter + OCR
│   ├── static/js/         # 8 ES modules (Alpine.js 3.x)
│   │   ├── api-client.js       # API calls, model loading
│   │   ├── project-manager.js  # Project CRUD, 3-column workspace
│   │   ├── editor-component.js # Editor, token estimate, diff view
│   │   ├── prompt-manager.js   # Prompt library & project prompts CRUD
│   │   ├── provider-manager.js # Provider CRUD, dropdown, Gemini/OpenAI switch
│   │   ├── plugin-manager.js   # Plugin list, toggle, workspace tabs (v7.8.0)
│   │   ├── translation-worker.js # SSE, progress, spellcheck
│   │   └── ui-helpers.js       # Toast, modals, provider switching
│   └── templates/partials/ # Jinja2 partials cho từng tab
├── backend/                # Backend chung cho CLI & WebUI
│   ├── application/       # Use cases + DTOs
│   ├── domain/            # Domain models
│   ├── infrastructure/    # Services (Config, API, Project, File...)
│   └── facade/            # AppService entry point
├── core/                   # Core pipeline (TranslationExecutor)
├── services/               # Cache, TranslationMemory, Health
├── plugins/                # Plugin thực thi
│   ├── translation/       # Lõi dịch thuật chính
│   ├── spellcheck/        # Kiểm chính tả AI
│   ├── epub_converter/    # Chuyển đổi EPUB
│   └── ocr/               # Nhận diện ảnh/PDF
├── core/interfaces/        # PluginBase, ConverterPlugin (v7.8.0)
├── config/                 # Cấu hình app.ini và API keys (providers.json)
└── docs/                   # Tài liệu
    ├── API_KEY_ROTATION.md # Kiến trúc & giải thuật xoay vòng API Key
    ├── DEVELOPMENT.md      # Hướng dẫn phát triển
    ├── MANUAL.md           # Hướng dẫn sử dụng
    └── ROADMAP.md          # Lộ trình phát triển
```

---

## 4. Hướng Dẫn Phát Triển Plugin Mới

Mọi plugin mới phải kế thừa từ `core.interfaces.ProcessorPlugin`.

### Quy trình tạo Plugin:
1.  **Tạo thư mục**: `plugins/ten_plugin/`.
2.  **Tạo file `plugin.py`**:
    ```python
    from core.interfaces import ProcessorPlugin
    from typing import Any, Tuple

    class Plugin(ProcessorPlugin):
        @property
        def name(self) -> str:
            return "my_plugin"
        
        def process(self, input_data: Any, context: dict = None) -> Tuple[Any, str]:
            # Logic xử lý chính
            return result, "success"
    ```
3.  **Tự động nhận diện**: Plugin Manager sẽ tự động phát hiện và nạp plugin khi khởi chạy `main.py` hoặc `cli.py`.

---

## 5. Hướng Dẫn Thêm Blueprint Mới cho WebUI

Kể từ v5.0.0, WebUI sử dụng Flask Blueprints. Để thêm API mới:

1.  **Tạo file route**: `webui/routes/ten_module.py`
    ```python
    from flask import Blueprint, request, jsonify
    
    my_bp = Blueprint("my_module", __name__)
    
    @my_bp.route("/api/my-endpoint")
    def my_endpoint():
        return jsonify({"status": "ok"})
    ```
2.  **Đăng ký Blueprint** trong `webui/__init__.py`:
    ```python
    from webui.routes.ten_module import my_bp
    app.register_blueprint(my_bp)
    ```

---

## 6. Quy Định Coding Convention

### Đặt tên (Naming)
- **Biến & Hàm**: Sử dụng `snake_case` (ví dụ: `translate_chunk`, `api_key`).
- **Lớp (Class)**: Sử dụng `PascalCase` (ví dụ: `ApiManager`, `PluginLoader`).
- **Hằng số**: Sử dụng `UPPER_SNAKE_CASE` (ví dụ: `MAX_RETRIES`, `DEFAULT_MODEL`).

### Logging
Tuyệt đối không sử dụng `print()`. Sử dụng module `logging` của Python:
- `logging.info()`: Thông tin tiến trình bình thường.
- `logging.warning()`: Các lỗi có thể tự phục hồi (ví dụ: Retry API).
- `logging.error()`: Lỗi nghiêm trọng ảnh hưởng đến kết quả chunk.

### Xử lý Lỗi (Error Handling)
- Luôn sử dụng `try...except` tại các điểm tiếp xúc với ngoại cảnh (IO, API).
- Đối với các lỗi logic dịch thuật, ưu tiên trả về text gốc kèm đánh dấu lỗi thay vì crash chương trình.

---

## 7. Quản Lý Dependencies

Dự án sử dụng `uv` để quản lý package. 
- Thêm package mới: `uv add <package>`
- Cập nhật lock file: `uv lock`

---
---

## 8. Viết Kế Hoạch Thực Thi cho AI Model (AI-Executable Plan)

Khi lập kế hoạch để giao cho AI model thực thi, chất lượng của plan quyết định trực tiếp chất lượng của code output. Phần này quy định cách viết plan đạt tỷ lệ thực thi đúng cao nhất.

### 8.1 Dùng định dạng diff chuẩn cho thay đổi code

**Quy tắc bắt buộc**: Mọi thay đổi code trong plan phải được viết theo định dạng diff (`-` dòng xóa, `+` dòng thêm), không dùng hai block "code cũ" và "code mới" đặt cạnh nhau.

**Sai – dễ bị model bỏ sót:**
```
Code cũ:
    file_overhead = 0
    if current_batch:
        batch_index = len(current_batch)
        file_overhead = self._delimiter_overhead(...)

Code mới:
    batch_index = len(current_batch)
    file_overhead = self._delimiter_overhead(...)
```

**Đúng – model nhận biết chính xác:**
```diff
-            file_overhead = 0
-            if current_batch:
-                batch_index = len(current_batch)
-                file_overhead = self._delimiter_overhead(session_token, batch_index)
+            batch_index = len(current_batch)
+            file_overhead = self._delimiter_overhead(session_token, batch_index)
```

> **Lý do**: Model được huấn luyện nhận diện diff format chuẩn. Khi đọc "code cũ / code mới" song song, model có xu hướng chỉ áp dụng thay đổi hiển nhiên nhất (dòng đang được nhắc đến) và bỏ qua các dòng liên quan cần xóa/thêm đồng thời.

### 8.2 Cấu trúc bắt buộc của một plan

Mỗi plan phải có đủ 5 thành phần sau theo đúng thứ tự:

```
1. PHẠM VI (Scope)
   - File(s) cần sửa, liệt kê đường dẫn đầy đủ
   - Hàm(s) cần sửa, liệt kê tên chính xác

2. KHÔNG ĐƯỢC SỬA (Out of scope)
   - Danh sách tường minh các hàm/file KHÔNG được đụng
   - Lý do ngắn gọn

3. THAY ĐỔI (Changes) – dùng diff format
   - Mỗi thay đổi: tên hàm + số dòng tham chiếu + diff

4. KIỂM TRA (Verification)
   - Lệnh shell cụ thể để xác minh (grep, git diff --stat, v.v.)
   - Kết quả kỳ vọng rõ ràng

5. QUY TẮC (Rules)
   - Không thêm import
   - Không đổi tên biến ngoài phạm vi
   - Không tự ý sửa thêm (kể cả warnings)
   - Báo cáo nếu phát hiện bất thường, không tự xử lý
```

### 8.3 Ghi số dòng tham chiếu

Luôn ghi số dòng hiện tại khi viết plan. Nếu plan được thực thi sau nhiều lần sửa khác, số dòng có thể lệch – model phải tìm bằng context, không được đoán mò.

Ví dụ:
```
Hàm `_build_batches`, khoảng line 82–110 (tìm bằng signature nếu số dòng lệch):
```diff
...
```
```

### 8.4 Kiểm tra sau thực thi

Sau mỗi plan được thực thi, model thực thi **phải** chạy tối thiểu:

```bash
# 1. Xác nhận chỉ đúng file trong phạm vi thay đổi
git diff --stat

# 2. Xác nhận biến/pattern đã xóa không còn tồn tại
grep -rn "<pattern_cần_xóa>" <file>

# 3. Kiểm tra diagnostics không có error mới
# (dùng tool diagnostics của editor)
```

Nếu có kết quả bất ngờ (file ngoài phạm vi thay đổi, pattern còn sót, error mới), **báo cáo ngay, không tự sửa thêm**.

### 8.5 Đánh giá chất lượng thực thi

Sau khi model hoàn thành, người review đánh giá theo thang:

| Tiêu chí | Điểm |
|---|---|
| Đúng tất cả thay đổi trong plan | 40% |
| Không sửa ngoài phạm vi | 30% |
| Verification pass đầy đủ | 20% |
| Không giới thiệu lỗi mới | 10% |

**Ngưỡng chấp nhận: ≥ 80%.** Dưới ngưỡng → review thủ công toàn bộ diff trước khi merge.

---

*Phiên bản: 2.4 - Ngày cập nhật: 27/07/2026*
