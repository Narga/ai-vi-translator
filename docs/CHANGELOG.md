# Changelog - Lịch sử thay đổi

Tất cả các thay đổi quan trọng của dự án Content Translator sẽ được ghi nhận tại đây.

---

## [6.0.0-alpha] - 2026-03-17 - Multi-Provider AI & Project Workflow

### 🚀 Phase 1: Multi-Provider AI Integration
- **OpenAI-Compatible API**: Tích hợp OpenAI SDK (`openai>=1.0.0`) hỗ trợ OpenRouter, proxy và các dịch vụ tương thích.
  - `services/openai_client.py`: Sync + Async wrapper tương tự `genai_client.py`
  - `services/ai_provider.py`: Protocol adapter + Factory pattern cho multi-provider
- **Dual-Provider UI**: Tab Cấu hình chia 2 cột nằm ngang (Gemini | OpenAI), radio button chọn 1 trong 2.
- **Template Splitting**: Tách `index.html` monolithic (729 dòng) thành 6 Jinja2 partials (`templates/partials/`).
- **4 API endpoints mới**: `/api/provider` (GET/POST), `/api/openai/models`, `/api/openai/config`.
- **Provider-aware helpers**: 7 functions mới trong `webui/helpers.py`.

### ✨ Phase 2: Project Workflow Tabs Enhancement
- **Genre Field**: Thêm trường thể loại vào project metadata, liên kết với prompt sets.
- **Project Creation Modal**: Thay `prompt()` bằng modal form đẹp với genre selector.
- **Inline Chunk-Size**: Input số ký tự/chunk cạnh nút "Chia Chunk" (để trống = config mặc định).
- **File Upload**: Mở rộng hỗ trợ `.html`, `.epub` ngoài `.txt`, `.md`.

### 📝 Phase 3: Tab Guidelines
- **Guidelines API**: `GET/PUT /api/projects/<slug>/guidelines` – 5 fields (summary, characters, glossary, style_guide, additional_notes).
- **AI Summarize**: `POST /api/projects/<slug>/summarize` – Tự động tóm tắt nội dung sách bằng AI (Gemini/OpenAI).
- **Guidelines Tab UI**: 5 textarea với nút AI Tóm tắt và Lưu Tất cả.

### 📦 Phase 4: Tab Prompts Enhancement
- **Prompt Library Dropdown**: Nạp bộ prompt từ thư viện (Mặc định + các thể loại).
- **Priority Note**: Hiển thị ghi chú ưu tiên prompt dự án > prompt hệ thống.
- **Placeholders**: Thêm placeholder gợi ý cho các textarea prompt.

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `services/openai_client.py` | ✨ NEW – OpenAI SDK wrapper |
| `services/ai_provider.py` | ✨ NEW – Adapter pattern |
| `templates/partials/*.html` | ✨ NEW – 6 template partials |
| `templates/index.html` | Tách thành 6 includes |
| `config/app.ini` | +`[PROVIDER]`, +`[OPENAI]` |
| `.env.example` | +`OPENAI_API_KEY` |
| `requirements.txt` | +`openai>=1.0.0` |
| `webui/helpers.py` | 7 provider functions |
| `webui/routes/settings.py` | 4 API endpoints |
| `webui/routes/projects.py` | Genre create/update + Guidelines API + Summarize |
| `static/css/style.css` | Dual-provider grid CSS |
| `static/js/main.js` | Provider switching + project modal + guidelines + prompt library |

---

## [5.0.0-alpha] - 2026-03-01 - Kiến Trúc Lại & Tối Ưu Hóa Tổng Thể

### 🚀 Tái Cấu Trúc Kiến Trúc (Refactoring)
- **Core Pipeline Unification**: Xóa bỏ hoàn toàn hệ thống Plugin (PluginManager, EventBus, ServiceBus) dư thừa. Xây dựng lõi `TranslationExecutor` (`core/executor.py`) quản lý logic dịch thuật nhất quán cho cả CLI (`main.py`) và WebUI (`webui/routes/translation.py`, `projects.py`).
- **Module hóa WebUI**: Chuyển đổi `webui.py` (1820 dòng) thành package `webui/` với các Blueprints:
  - `webui/__init__.py`: Flask App Factory với global state management
  - `webui/helpers.py`: Các hàm tiện ích dùng chung (config, API keys, stats, prompts)
  - `webui/routes/translation.py`: Translation worker, SSE streaming, direct translate
  - `webui/routes/settings.py`: Models, Config, Stats, Cache, Token estimation
  - `webui/routes/prompts.py`: Genre-based prompt management CRUD
  - `webui/routes/projects.py`: Project CRUD, File management, Translation, TM APIs
  - `webui/routes/plugins.py`: EPUB Converter và OCR execution
- **Entry point**: `webui.py` giảm từ 1820 dòng xuống 35 dòng.

### ✨ Tính Năng Mới & Thuật Toán
- **Sentence Aggregation Chunker** (`chunker.py`): Thuật toán mới tách text thành danh sách câu bằng regex multi-language (Trung/Nhật/Hàn/Latin), rồi dồn câu vào chunk — đảm bảo 100% không cắt ngang câu. Giữ `intelligent_chunking()` làm fallback cho câu quá dài.
- **SQLite Checkpoint** (`checkpoint_service.py`): Thay thế JSON bằng SQLite với WAL mode và ACID transactions. Hỗ trợ per-chunk upsert, query nhanh tiến độ không cần load toàn bộ text. API tương thích v4.0 + mới (`init_session`, `save_chunk`, `get_translated_chunks`).
- **Dynamic Glossary Injection** (`glossary_service.py`): Hệ thống lọc thuật ngữ thông minh theo ngữ cảnh từng Chunk. 
  - Sử dụng `GlossaryEntry` với `__slots__` tối ưu bộ nhớ.
  - Cơ chế deduplication O(1) và sắp xếp theo độ dài giảm dần để ưu tiên match thuật ngữ dài trước.
  - Tự động nhúng vào Prompt giúp tiết kiệm Token và tăng độ chính xác của LLM. Khả dụng cho CLI, WebUI và Project-based.
- **Side-by-Side Editor** (`index.html`, `main.js`): Giao diện soát lỗi song ngữ — hiển thị bản gốc (readonly) bên trái và bản dịch (editable) bên phải. Hỗ trợ chỉnh sửa trực tiếp, lưu nhanh, sync scroll, và thống kê ký tự/tỷ lệ dịch real-time.
- **Cải thiện Trải nghiệm Người Dùng (UI/UX)**:
  - Mở rộng kích thước các Form nhập liệu, làm mới Textarea với font chữ to, border bo góc mềm mại hơn.
  - Thay thế toàn bộ hộp thoại cảnh báo `alert()` truyền thống bằng hệ thống **Toast Notifications** mượt mà.
  - Tích hợp tính năng quản lý **API Keys** trực tiếp từ tab Cấu hình (Config) trên WebUI.
- **Upload & Chunk** (`projects.py`, `main.js`): Tải file `.txt` lên dự án và chia chunk trực tiếp từ WebUI. Chunk files được liệt kê trong danh sách nguồn, cho phép sửa và lưu từng chunk riêng lẻ.
- **Robust Fallback**: Cơ chế đánh dấu `<!-- FAILED_CHUNK -->` khi gặp lỗi API thay vì dừng tiến trình.

### 📚 Tài Liệu (Documentation)
- **Roadmap 2026**: Xây dựng lộ trình phát triển chi tiết 3 giai đoạn.
- **Development & Manual**: Tách biệt tài liệu hướng dẫn cho người dùng cuối (`Manual.md`) và lập trình viên (`DEVELOPMENT.md`).

---

## [4.1.0] - Báo cáo cải tiến UI và Fixes

### 🚀 Bug Fixes & Refactoring
- **Sửa Lỗi Chunking**: Giảm `MIN_CHARS_PER_CHUNK` và `MAX_CHARS_PER_CHUNK` trong `config/app.ini` xuống `5000` và `8000` để tránh API tự động cắt ngắn output do vượt quá giới hạn token của LLM. Tối ưu lại điều kiện gom mảnh vụn cuối trong `plugins/translation/chunker.py` (hệ số `1.2` thành `1.1`).
- **Refactor Web UI (PicoCSS)**:
  - Tích hợp chuẩn **PicoCSS Classless** qua thẻ CDN. Rút gọn cấu trúc thẻ HTML sang Semantic (`<article>`, `<section>`, `<header>`).
  - Gỡ bỏ toàn bộ Inline CSS và Inline Javascript khỏi template `templates/index.html`.
  - Tách CSS ra thư mục tĩnh: `static/css/style.css` 
  - Tách logic JS ra thư mục tĩnh: `static/js/main.js`
- **Cache Busting**: Frontend script và styles hiện tại nhận biến tham số version `?v=4.0.6` truyền từ flask render_template để cập nhật cache trình duyệt ngay khi có thay đổi bản build.

Tất cả các thay đổi quan trọng của dự án Content Translator sẽ được ghi nhận tại đây.

---

## [4.0.7] - 2026-02-17 - UI Redesign & Improvements

### UI/UX Improvements
- **Clean Layout**: Thiết kế lại giao diện, gọn gàng hơn
- **Color Indicators**: Chỉ báo màu cho file đã dịch/chờ dịch
- **Two Modes**: 
  - Tab "Chờ dịch": Hiển thị form nhập text gốc + nút dịch
  - Tab "Đã dịch xong": Hiển thị text đã dịch + nút Retranslate/Correction/Both
- **Quick View**: Click vào file để load nội dung vào form
- **Removed Redundant**: Bỏ block "Đã dịch (Output)" ở sidebar
- **Simplified Stats**: Thanh header với thông tin cần thiết

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `templates/index.html` | Complete redesign |

---

## [4.0.6] - 2026-02-17 - Translation Memory & Optimizations

### ✨ Tính năng Mới

**Translation Memory (TM):**
- Dịch vụ TM với fuzzy matching
- Lưu trữ các cặp dịch (source → target)
- Tìm kiếm fuzzy với similarity threshold có thể điều chỉnh
- Tự động học từ các bản dịch đã thực hiện
- N-gram based similarity (Jaccard)
- Export/Import TM
- Thống kê TM (số entries, kích thước)

**API Optimization:**
- Chunk size có thể lên đến 100K chars (đọc từ config)
- Cache check trước khi gọi TM
- TM check cho similarity ≥ 90% trước khi gọi API

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `services/translation_memory.py` | ✨ NEW - Translation Memory service |
| `webui.py` | Thêm TM integration, APIs |

---

## [4.0.5] - 2026-02-17 - Batch Translation & Dynamic Models

### ✨ Tính năng Mới

**Batch Translation:**
- Checkbox để chọn nhiều file cùng lúc
- Nút "Dịch file đã chọn" để dịch hàng loạt
- Tab "Đã dịch xong" hiển thị file trong thư mục done

**File Management:**
- File đã dịch tự động chuyển vào thư mục `workspace/done`
- Chức năng "Dịch lại" cho file đã dịch
- Chức năng "Xem" để xem nội dung file đã dịch
- Di chuyển file từ done về input

**Dynamic Models:**
- Tự động phát hiện models khả dụng từ Google API
- Danh sách models động thay vì hard-code
- Model mặc định từ config

**Input Form:**
- Chunk size có thể nhập tay (input number) thay vì select cố định
- Giá trị mặc định được đọc từ `config/app.ini`

**Thống kê chi tiết:**
- Số từ đã dịch / đang chờ
- Số file input / output / done
- Kích thước cache

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `webui.py` | Thêm batch translate, done folder, dynamic models |
| `templates/index.html` | Checkbox, tabs, dynamic model dropdown |

---

## [4.0.4] - 2026-02-15 - WebUI Enhancements

### ✨ Tính năng WebUI

- **Input Files List**: Liệt kê files trong input, click để load nội dung
- **Cache Priority**: Kiểm tra cache trước khi gọi API, hiển thị số chunks từ cache
- **Download**: Tải file đã dịch về máy (text file)
- **Prompt Editor**: Chỉnh sửa và lưu prompts theo ngôn ngữ
- **Output Files**: Danh sách files đã dịch với link tải

### 🔧 Script Enhancements

- **Auto-merge Small Files**: Tự động gộp files nhỏ để đủ kích thước chunk tối thiểu
- Hàm `merge_small_files()` trong main.py

### 🚀 Fix

- Default port: 7860 (tránh macOS AirPlay conflict)

### 📁 Files Changed

| File | Thay đổi |
|------|----------|
| `webui.py` | Complete rewrite với tất cả APIs mới |
| `templates/index.html` | UI với file list, prompt editor |
| `main.py` | Thêm merge_small_files() |

---

## [4.0.3] - 2026-02-15 - Web UI & uv Support

### ✨ Tính năng Mới

**Web UI (Flask):**
- Giao diện web đơn giản, tối giản
- Real-time progress với Server-Sent Events (SSE)
- Form cấu hình: model, ngôn ngữ, temperature, chunk size
- Text input trực tiếp (không cần upload file)
- Log console hiển thị quá trình
- Copy kết quả dễ dàng

**uv Support:**
- Thêm `pyproject.toml` cho uv package manager
- Có thể chạy với `uv run python webui.py`
- Optional dependencies: epub, ocr, async, dev

### 📁 Files Mới

| File | Mô tả |
|------|-------|
| `webui.py` | Flask web application |
| `templates/index.html` | Web UI template |
| `pyproject.toml` | uv configuration |

### 📦 Dependencies

Thêm vào `pyproject.toml`:
- `flask>=2.0.0` - Web framework
- `flask-sock` - WebSocket support (future)

---

## [4.0.2] - 2026-02-15 - LSP Fixes & Optimizations

### 🔧 LSP/Type Fixes

- **genai_client.py**: Sửa type hints cho `generation_config`
- **chunker.py**: Fix lỗi `cut_pos` possibly unbound
- **plugin.py**: Fix Optional type cho `context` parameter

### ✨ Tính năng Mới

**Progress Bar (tqdm):**
- Tích hợp `tqdm` vào main loop
- Hiển thị tiến trình dịch cho mỗi file
- Tắt log verbose, giữ lại error messages

**Multi-language Support:**
- Hỗ trợ 3 ngôn ngữ: CN (Chinese), JP (Japanese), KR (Korean)
- Tự động detect ký tự gốc còn sót dựa trên `INPUT_LANG`
- Thêm LANGUAGE_REGEX cho mỗi ngôn ngữ

### 🚀 Optimizations

**Regex Optimization:**
- Đưa `DELIMITERS` lên module-level constant
- Tránh re-create list mỗi lần gọi `_find_best_cut_position()`

**Cache Compression:**
- Thêm gzip compression cho cache files
- File extension: `.pkl.gz` (tương thích ngược với `.pkl`)
- Giảm ~60-80% kích thước cache

**Memory Optimization:**
- Thêm `chunk_text_generator()` - generator-based chunking
- Xử lý chunk-by-chunk thay vì load all vào memory
- Phù hợp cho file lớn (>10MB)

### Files Changed

| File | Thay đổi |
|------|----------|
| `main.py` | Thêm tqdm progress bar |
| `services/genai_client.py` | Fix type hints |
| `services/cache_service.py` | Thêm gzip compression |
| `plugins/translation/chunker.py` | Regex optimization, generator |
| `plugins/translation/plugin.py` | Fix Optional type |
| `plugins/translation/translator.py` | Multi-language support |

---

## [4.0.1] - 2026-02-15 - Rate Limiting & CLI Upgrades

### 🎯 Code Review & Optimizations

**Security:**
- ✅ Thêm `.env` support với `python-dotenv`
- ✅ API keys ưu tiên từ environment variables
- ✅ Fallback về `config/API.txt` (legacy)

**API Rate Limiting:**
- ✅ `GlobalRPMRateLimiter`: Sliding window 60s, giới hạn 15 RPM toàn cục
- ✅ `TokenBudgetLimiter`: Ước tính tokens (2.5 chars/token), giới hạn 1M TPM
- ✅ Fix race condition trong `get_next_available_key()`
- ✅ Fix dead code (old SDK) trong `_call_api_with_original_context`

**CLI & Automation:**
- ✅ `cli.py`: Command-line interface với argparse
- ✅ `CheckpointService`: Lưu/khôi phục tiến trình dịch
- ✅ Auto-save checkpoint sau mỗi chunk
- ✅ Resume từ checkpoint khi bị gián đoạn

**Async Support:**
- ✅ `services/async_genai_client.py`: Async wrapper với aiohttp
- ✅ `AsyncApiManager`: Concurrent requests với semaphore

### 📦 Dependencies

Thêm vào `requirements.txt`:
- `python-dotenv` - .env file support
- `aiohttp` - Async HTTP calls (optional)

### Files Changed

| File | Thay đổi |
|------|----------|
| `main.py` | Thêm .env support |
| `cli.py` | ✨ NEW - CLI với argparse |
| `services/api_service.py` | Thêm RPM + TPM limiters |
| `services/async_genai_client.py` | ✨ NEW - Async support |
| `services/checkpoint_service.py` | ✨ NEW - Checkpoint/Resume |
| `plugins/translation/translator.py` | Fix dead code |
| `requirements.txt` | Thêm python-dotenv, aiohttp |

---

## [4.0.0] - 2026-02-01 - SDK Migration & Core Upgrades

### 🎉 Thay đổi Lớn

**SDK Migration:**
- ✅ Chuyển từ `google-generativeai` sang `google-genai` SDK mới
- ✅ Model mặc định: `gemini-3-flash-preview` (1M context window)
- ✅ Hỗ trợ `thinking_level` parameter (MINIMAL/LOW/MEDIUM/HIGH)
- ✅ Giữ `google-generativeai` làm fallback SDK

**API Rate Limiting (30 keys = 600 RPD):**
- ✅ `AdaptiveRateLimiter`: Progressive backoff 30s→300s
- ✅ Daily quota tracking với auto-reset 0:00 UTC
- ✅ Tối ưu cho 20 RPD/key limit của Google API mới

### ✨ Tính năng Mới (Merge từ Book_translator)

**GenAI Client Wrapper:**
- `services/genai_client.py`: Unified API wrapper cho cả 2 SDK
- Client caching theo API key để giảm overhead
- Auto-fallback khi SDK chính không khả dụng

**Circuit Breaker:**
- `services/circuit_breaker.py`: Ngăn cascade failures
- 3 states: CLOSED → OPEN → HALF_OPEN
- Failure threshold = 10, timeout = 5 phút

**Health Monitor:**
- `services/health_monitor.py`: Giám sát runtime và stall
- Max runtime: 48 giờ
- Stall detection: 30 phút không tiến độ
- Memory usage tracking (psutil optional)

**Emergency Stop:**
- `services/emergency_stop.py`: Thread-safe global stop flag
- Signal handlers (SIGINT, SIGTERM) cho graceful shutdown
- Decorator `@emergency_check` cho functions

### ♻️ Thay đổi

**Cấu hình (`config/app.ini`):**
```ini
[SDK]
SDK = google-genai           # SDK mới (mặc định)
FALLBACK_SDK = google-generativeai

[MODEL]
MODEL = gemini-3-flash-preview
THINKING_LEVEL = MEDIUM
TEMPERATURE = 1.0            # Gemini 3 khuyến nghị

[PROCESSING]
REQUEST_DELAY = 1            # Giảm từ 2s do có nhiều keys
```

**Files đã sửa:**
| File | Thay đổi |
|------|----------|
| `main.py` | v4.0.0 + signal handlers |
| `services/api_service.py` | v4.0.0 + AdaptiveRateLimiter |
| `services/__init__.py` | Export services mới |
| `plugins/translation/translator.py` | v4.0.0 + GenAIClient |
| `requirements.txt` | v4.0.0 + google-genai SDK |

### 📦 Dependencies

Thêm vào `requirements.txt`:
- `google-genai>=1.0.0` (SDK mới, khuyến nghị)
- `psutil` (optional, cho memory monitoring)

---

## [3.0.3] - 2025-12-06 - Plugin OCR

### ✨ Tính năng Mới

**Plugin OCR:**
- Nhận dạng text từ PDF scan và ảnh (JPG, PNG, BMP, TIFF)
- Hỗ trợ đa ngôn ngữ  (Tiếng Việt, Anh, Trung)
- AI cleanup và spell check (tích hợp Gemini API)
- Table extraction với 3 tầng fallback (unstructured → pdfplumber → OpenCV)
- Xuất đa định dạng (DOCX, TXT)

**Chức năng chính:**
- OCR PDF (cả scan và text-based)
- OCR image (JPG, PNG, BMP, TIFF, etc.)
- Auto-rotate dựa trên EXIF và OSD
- Chinese variant detection (giản thể/phồn thể)
- Format preservation trong DOCX output
- Resume capability cho long processing

**Technical:**
- Lazy dependency loading (chỉ install khi cần)
- Tesseract OCR integration
- OCRmyPDF fallback cho PDF phức tạp
- Gemini API cho cleanup và spellcheck
- ServiceBus integration cho config và API management
- Kế thừa từ `ConverterPlugin` interface

**Cấu trúc:**
```
plugins/ocr/
├── __init__.py
├── plugin.py           # ConverterPlugin implementation
└── ocr_engine.py       # Core OCR logic (7659 dòng)
```

### 🗑️ Xóa

- ❌ `ocr_reader.py` (7659 dòng - đã tích hợp vào plugin)
- ❌ `orc.txt` (documentation - không còn cần thiết)

### 📦 Dependencies

Thêm vào `requirements.txt`:
- pytesseract, pdf2image, Pillow (core OCR)
- pdfplumber, PyPDF2, PyMuPDF (PDF processing)
- python-docx, ocrmypdf (output generation)
- unstructured, opencv-python (optional - advanced features)

---

## [3.0.2] - 2025-12-06 - Kiến trúc Plugin Thuần túy

### 🎉 Thay đổi Lớn

**100% Kiến trúc Plugin:**
- Loại bỏ hoàn toàn mã nguồn legacy khỏi nhánh master
- Xóa thư mục `src/` (20 files, 3,280 dòng)
- Xóa `utils/content-analysis/` (8 files, 909 dòng)
- Master giờ là hệ thống plugin thuần túy

**Bảo toàn Legacy:**
- Toàn bộ code v2.7 được lưu trong nhánh `legacy`
- Truy cập bất cứ lúc: `git checkout legacy`

### ✨ Tính năng Mới

**main.py Đơn giản:**
- Viết lại hoàn toàn (200 dòng vs 3000+)
- Quy trình dịch hoàn chỉnh qua plugins
- Không phụ thuộc vào legacy

**Quy trình:**
1. Khởi tạo services (Config, API, Cache)
2. Nạp translation plugin
3. Tìm files trong `workspace/input/`
4. Chia chunk và dịch qua plugin
5. Lưu vào `workspace/output/`

### 🔧 Cải tiến

- Giảm 95% kích thước code (xóa 4,061 dòng)
- Kiến trúc sạch: ServiceBus + EventBus + Plugins
- Dễ bảo trì và mở rộng
- Production-ready với code tối thiểu

### 📦 Cấu trúc

```
novel-translator/ (v3.0.2)
├── main.py              # Quy trình plugin (200 dòng)
├── core/               # Hạ tầng plugin
├── services/           # Services dùng chung
├── plugins/            # Tất cả tính năng
├── config/API.txt      # API keys người dùng
└── workspace/
    ├── input/          # Files nguồn
    └── output/         # Bản dịch
```

---

## [3.0.0] - 2025-12-05 - Kiến trúc Plugin - Tái thiết kế Toàn diện

### 🎉 Thay đổi Lớn (Breaking Changes)

**Kiến trúc mới hoàn toàn:**
- Chuyển từ kiến trúc monolithic sang **plugin-based architecture**
- Tách biệt hoàn toàn code v3.0 (branch master) và v2.x (branch legacy)
- Cấu trúc thư mục mới: `core/`, `services/`, `plugins/`, `config/`, `docs/`

### ✨ Tính năng mới (Features)

#### 1. Core Infrastructure (Hạ tầng Lõi)

**Plugin System:**
- `core/plugin_manager.py`: Quản lý vòng đời plugin (discovery, loading, execution, cleanup)
  - Auto-discovery: Tự động quét và nạp plugins từ thư mục `plugins/`
  - Dependency resolution: Phân tích và sắp xếp thứ tự nạp plugin theo dependencies
  - Error isolation: Lỗi của một plugin không ảnh hưởng đến plugins khác
  - Plugin reload: Hỗ trợ tải lại plugin mà không restart hệ thống

**Service Bus:**
- `core/service_bus.py`: Registry trung tâm cho shared services
  - Quản lý các service: config, api, cache, logger
  - Dependency injection: Plugins truy cập services thông qua ServiceBus
  - Thread-safe: An toàn cho đa luồng

**Event Bus:**
- `core/event_bus.py`: Hệ thống event-driven cho plugin communication
  - Subscribe/emit pattern: Plugins giao tiếp qua events
  - Error isolation: Lỗi của một listener không ảnh hưởng listeners khác
  - Event history: Lưu lịch sử events để debug
  - Wildcard listeners: Subscribe tất cả events với `'*'`

**Plugin Interfaces:**
- `core/interfaces/plugin_base.py`: Interface cơ sở cho tất cả plugins
  - `PluginStatus`: Lifecycle states (UNLOADED, READY, RUNNING, ERROR, DISABLED)
  - `PluginPriority`: Execution priorities (CRITICAL, HIGH, NORMAL, LOW, OPTIONAL)
  - Error handling hooks: `on_error()` method
  - Configuration validation: `validate_config()` method

- `core/interfaces/processor_plugin.py`: Interface cho text processing plugins
  - `process()`: Xử lý text với context support
  - `supports_format()`: Kiểm tra định dạng được hỗ trợ
  - `validate_input()`: Validate input data

- `core/interfaces/converter_plugin.py`: Interface cho format conversion plugins
  - `convert()`: Chuyển đổi định dạng file
  - `get_supported_conversions()`: Danh sách chuyển đổi được hỗ trợ
  - `detect_format()`: Tự động nhận diện định dạng

#### 2. Shared Services (Dịch vụ Dùng chung)

**Config Service:**
- `services/config_service.py`: Quản lý cấu hình tập trung
  - App-level config: `config/app.ini`
  - Plugin-level config: `config/plugins/{plugin_name}.ini`
  - Type-safe getters: Tự động convert kiểu dữ liệu (int, float, bool)
  - Hot reload: Reload config mà không restart

**API Service:**
- `services/api_service.py`: Quản lý Gemini API keys (từ v2.x)
  - `ApiManager`: Xoay vòng API keys thông minh
  - `SmartRateLimiter`: Backoff và cooldown tự động
  - Multi-key support: Hỗ trợ nhiều API keys
  - Thread-safe: An toàn cho đa luồng

**Cache Service:**
- `services/cache_service.py`: Caching kết quả dịch (từ v2.x)
  - MD5-based hashing: Cache key theo hash
  - Smart key: Bao gồm model, temperature, prompts, context, input
  - File-based cache: Lưu cache vào files `.pkl`
  - Thread-safe: An toàn cho đa luồng

#### 3. Plugins (4 plugins được triển khai)

**Translation Plugin:**
- `plugins/translation/`: Core translation engine
  - `chunker.py`: Smart text chunking (từ `smart_chunker.py`)
  - `normalizer.py`: Text normalization (từ `text_normalizer.py`)
  - `translator.py`: Translation logic (từ `translators/core.py`)
  - Hỗ trợ: Context chaining, Chinese detection, preventive translation

**EPUB Converter Plugin:**
- `plugins/epub_converter/`: Format conversion
  - `epub_to_text/`: EPUB → Text/Markdown (từ `utils/epub2md/`)
  - `text_to_epub/`: Text/Markdown → EPUB (từ `utils/text2epub/`)
  - Metadata preservation: Giữ nguyên metadata khi convert

**Consistency Check Plugin:**
- `plugins/consistency_check/`: QA checking
  - `checker.py`: Kiểm tra consistency (từ `translators/consistency.py`)
  - Terminology verification: Kiểm tra thuật ngữ
  - Character names: Kiểm tra tên nhân vật

**Chinese Detector Plugin:**
- `plugins/chinese_detector/`: Quality assurance
  - `detector.py`: Phát hiện ký tự Trung (từ `chinese_detector.py`)
  - File scanning: Quét files có ký tự Trung
  - Chunk scanning: Quét chunks có ký tự Trung

####  4. Main Entry Point

**New Main:**
- `main.py`: Entry point mới với plugin architecture
  - Service initialization: Khởi tạo tất cả services
  - ServiceBus setup: Đăng ký services
  - EventBus setup: Cấu hình event listeners
  - Plugin discovery & loading: Tự động nạp plugins
  - Error handling: Xử lý lỗi toàn diện

**Legacy Backup:**
- `main_legacy.py`: Backup entry point v2.x
  - Giữ nguyên logic cũ để rollback nếu cần

### ♻️ Thay đổi (Changes)

**Cấu trúc Thư mục:**
```
novel-translator/ (v3.0)
├── main.py              # Entry point mới
├── main_legacy.py       # Backup v2.x
├── core/               # Hạ tầng lõi (8 files)
├── services/           # Shared services (6 files)
├── plugins/            # Plugins (24 files)
├── config/            # Cấu hình
│   ├── app.ini
│   └── plugins/
├── docs/              # Tài liệu
│   ├── README.md
│   ├── CHANGELOG.md
│   └── TODO.md
└── workspace/         # Dữ liệu runtime
```

**Removed (Đã loại bỏ):**
- ❌ `src/`: Toàn bộ mã nguồn v2.x (chuyển sang branch legacy)
- ❌ `utils/`: Toàn bộ utilities v2.x (đã tích hợp vào plugins)
- ❌ `references/`: Thư mục tham khảo thừa

**Moved (Di chuyển):**
- 📁 `README.md` → `docs/README.md`
- 📁 `CHANGELOG.md` → `docs/CHANGELOG.md`
- 📁 `TODO.md` → `docs/TODO.md`

### 📊 Thống kê

**Code Statistics:**
| Category | Files | Lines |
|----------|-------|-------|
| Core Infrastructure | 8 | 1,296 |
| Shared Services | 6 | 617 |
| Plugins | 24 | 2,741 |
| Main + Config | 5 | ~500 |
| **TOTAL** | **43** | **~5,150** |

**Git Commits:**
```
b9ab127 - Phase 4: New main.py with plugin system + updated README
7aee0cd - Phase 3: All plugins created
618decd - Phase 2: Shared services
2b74ccc - Phase 1: Core infrastructure
07af835 - Pre-migration checkpoint
```

### ⚡ Cải tiến (Improvements)

**Extensibility (Khả năng mở rộng):**
- ✅ Thêm feature mới: Chỉ cần tạo plugin mới
- ✅ Không cần sửa core code
- ✅ Plugin có thể enable/disable độc lập

**Error Isolation (Cách ly lỗi):**
- ✅ Plugin crash không ảnh hưởng hệ thống
- ✅ Lỗi của listener không ảnh hưởng listeners khác
- ✅ Có thể retry hoặc disable plugin lỗi

**Maintainability (Dễ bảo trì):**
- ✅ Code modular, tách biệt rõ ràng
- ✅ 100% docstrings cho public APIs
- ✅ Type hints đầy đủ
- ✅ Comprehensive logging

**Testing (Khả năng test):**
- ✅ Test từng plugin độc lập
- ✅ Mock services dễ dàng
- ✅ Integration tests rõ ràng

**Performance (Hiệu năng):**
- ✅ Plugin load on-demand
- ✅ Hot reload support
- ✅ Cached services

### 🔧 Migration Guide

**Từ v2.x sang v3.0:**

1. **Checkout branch mới:**
   ```bash
   git checkout master  # v3.0 plugin architecture
   ```

2. **Hoặc quay lại v2.x:**
   ```bash
   git checkout legacy  # v2.x original code
   ```

3. **Run v3.0:**
   ```bash
   python main.py
   ```

4. **Run v2.x:**
   ```bash
   python main_legacy.py
   # Hoặc
   git checkout legacy && python main.py
   ```

### 📝 Lưu ý

**Backward Compatibility:**
- ✅ Code v2.x vẫn hoạt động (branch legacy, main_legacy.py)
- ✅ Config cũ tương thích (`config.ini` → `config/app.ini`)
- ✅ API.txt format không đổi

**Breaking Changes:**
- ⚠️ Import paths thay đổi (từ `src.*` sang `core.*`, `services.*`, `plugins.*`)
- ⚠️ Workflow code cần viết lại để dùng plugins
- ⚠️ Custom modifications cần port sang plugin

**Recommendations:**
- 💡 Test kỹ trước khi deploy production
- 💡 Giữ branch legacy để rollback
- 💡 Đọc `docs/README.md` để hiểu plugin architecture

### 🎯 Future Work

**Planned Enhancements:**
- [ ] Complete workflow integration using plugins
- [ ] Unit tests cho core components
- [ ] Integration tests
- [ ] Plugin development documentation
- [ ] Performance benchmarks
- [ ] Additional plugins (PDF converter, Web UI, etc.)

---

## Lịch sử v2.x

*Xem branch `legacy` hoặc file `docs/CHANGELOG.md` trong branch đó để xem lịch sử đầy đủ v2.x*

Các phiên bản chính:
- v2.8.0: Tối ưu sửa lỗi ký tự Trung (parallel correction)
- v2.7.0: Cache key nâng cấp + GeminiProjectFileManager
- v2.6.3: Mở rộng regex phát hiện ký tự Trung
- v2.6.0: Auto-retry chunks lỗi + Verification mode
- v2.5.1: Translation Guidelines system
- v2.4.1: Statistics + Text normalization
- v2.0.0: Tái cấu trúc lớn sang src/
- v1.x: Các phiên bản đầu tiên

---

**Version:** 3.0.0  
**Date:** 2025-12-05  
**Architecture:** Plugin-based with ServiceBus and EventBus  
**Author:** Narga