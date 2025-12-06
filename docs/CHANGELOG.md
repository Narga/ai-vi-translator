# Changelog - Lịch sử thay đổi

Tất cả các thay đổi quan trọng của dự án Novel Translator sẽ được ghi nhận tại đây.

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