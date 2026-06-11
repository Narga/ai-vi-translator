# 🛠️ Hướng Dẫn Phát Triển & Coding Convention

Tài liệu này dành cho các lập trình viên muốn đóng góp hoặc mở rộng hệ thống Content Translator.

## 1. Kiến Trúc Phân Tầng (Architectural Layers)

Hệ thống được cấu trúc thành ba lớp chức năng chính:

1.  **Lớp Chiến lược (`ExecutionManager`)**: Quản lý toàn bộ nhiệm vụ dịch thuật, quyết định số lượng worker tối ưu dựa trên sức khỏe hệ thống và giám sát tiến độ toàn cục.
2.  **Lớp Điều phối (`SmartKeyDistributor` / `ApiManager`)**: Quản lý vòng đời của API key, phân loại lỗi và thực hiện logic phân phối key cho từng worker.
3.  **Lớp Thực thi (`Worker`)**: Các tác vụ asyncio/threading độc lập thực hiện dịch các chunk và phản hồi trạng thái.

---

## 2. Các Giải Thuật Cốt Lõi (Core Algorithms)

### A. Gắn kết Worker-Key (Worker-Key Affinity)
Mỗi Worker được gán một **Preferred Key** duy nhất để tối đa hóa khả năng caching phía server Gemini. Nếu key bị lỗi, hệ thống sẽ tự động "mượn" key từ **Reserve Pool** trong vòng `< 1ms` để duy trì tiến độ.

### B. Kiểm soát Lưu lượng Động (Dynamic Throughput)
Hệ thống sử dụng cơ chế **Tự thích nghi (Adaptive Scaling)**:
- Theo dõi tỷ lệ thành công (success_rate) và lỗi 429 (quota_error).
- Tự động giảm số lượng worker nếu phát hiện lỗi Quota hàng loạt và vào chế độ **Khởi động chậm (Slow-Start)**.

### C. Bộ giới hạn Tốc độ Toàn cục (Global Rate Limiter)
Sử dụng cơ chế **Cửa sổ trượt 60 giây (Sliding Window)** để theo dõi RPM tổng. Nếu vượt ngưỡng IP cho phép, hệ thống kích hoạt **Global Pause** để bảo vệ uy tín IP.

### D. Sentence Aggregation (Chunking)
Thuật toán dồn câu để đảm bảo ranh giới chunk không cắt ngang ý nghĩa.

### E. Jaccard Similarity (Translation Memory)
So sánh tập hợp N-gram để tìm kiếm câu tương đồng trong bộ nhớ dịch thuật.

---

## 3. Cấu Trúc Thư Mục Dự Án

```
novel-translator/
├── main.py                 # Entry point cho CLI script
├── cli.py                  # Giao diện dòng lệnh (argparse)
├── webui.py                # Entry point cho Web UI (35 dòng)
├── webui/                  # 📦 Flask App Package
│   ├── __init__.py        # App Factory + global state
│   ├── helpers.py         # Utilities dùng chung
│   ├── routes/            # Flask Blueprints
│   │   ├── translation.py # Worker + SSE streaming
│   │   ├── settings.py    # Models, Config, Stats, Cache
│   │   ├── prompts.py     # Prompt Sets CRUD
│   │   ├── projects.py    # Project workspace + TM APIs
│   │   └── plugins.py     # EPUB Converter + OCR
│   ├── static/js/         # 7 ES modules (Alpine.js 3.x)
│   │   ├── api-client.js       # API calls, model loading
│   │   ├── project-manager.js  # Project CRUD, 3-column workspace
│   │   ├── editor-component.js # Editor, token estimate, diff view
│   │   ├── prompt-manager.js   # Prompt genres & prompts CRUD
│   │   ├── provider-manager.js # Provider CRUD, dropdown, Gemini/OpenAI switch
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
├── config/                 # Cấu hình app.ini và API keys
    └── docs/                   # Tài liệu
        ├── ROADMAP.md         # Lộ trình phát triển
        ├── DEVELOPMENT.md     # Hướng dẫn phát triển
        └── MANUAL.md          # Hướng dẫn sử dụng
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
3.  **Tự động nhận diện**: Plugin Manager sẽ tự động phát hiện và nạp plugin khi khởi chạy `main.py` hoặc `webui.py`.

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
*Phiên bản: 2.1 - Ngày cập nhật: 11/06/2026*
