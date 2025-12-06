# Integration Guide - Novel Translator v3.0.1

## 🎉 Chào mừng đến với v3.0.1!

Phiên bản này tích hợp **hoàn toàn** tất cả tính năng từ v2.7 vào kiến trúc plugin v3.0, mang đến cho bạn:
- ✅ Tất cả tính năng nâng cao từ v2.7 (đã được kiểm chứng)
- ✅ Kiến trúc plugin hiện đại v3.0 (dễ mở rộng)
- ✅ Hai cách sử dụng linh hoạt

---

## 🚀 Quick Start

### Cách 1: Plugin Architecture (Khuyến nghị cho người dùng mới)

```bash
# Chạy với kiến trúc plugin v3.0
python main.py
```

**Ưu điểm:**
- Kiến trúc hiện đại, dễ mở rộng
- Quản lý plugins linh hoạt
- Tích hợp sẵn tất cả tính năng v2.7

### Cách 2: Legacy Workflow (Cho người dùng v2.7 muốn giữ workflow cũ)

```python
# Import và sử dụng trực tiếp workflow v2.7
from src.workflow import run_translation_workflow
from src.configuration import load_all_configs

# Load config
config_params = load_all_configs()

# Run translation
run_translation_workflow(config_params)
```

**Ưu điểm:**
- Workflow đã được kiểm chứng qua nhiều dự án
- Tất cả tính năng v2.7 nguyên bản
- Dễ dàng migrate code cũ

---

## 📚 Tính Năng Chính

### Core Translation Features (từ v2.7)

#### 1. Context Chaining
Nối ngữ cảnh giữa các chunk để dịch liền mạch:
```ini
# config.ini
[PROCESSING]
CONTEXT_CHAR_COUNT = 500  # Số ký tự context từ chunk trước
```

#### 2. Smart Chunking
Thuật toán cắt văn bản thông minh:
```ini
[PROCESSING]
MIN_CHARS_PER_CHUNK = 18000
MAX_CHARS_PER_CHUNK = 22000
```

#### 3. Auto-retry với Chinese Detection
Tự động phát hiện và dịch lại chunks có ký tự Trung:
```ini
[PROCESSING]
MAX_REFINEMENT_ATTEMPTS = 2
INPUT_LANG = CN  # Bật Chinese detection
```

#### 4. Verification Mode
Kiểm tra bản dịch cũ, chỉ dịch lại chunks có vấn đề:
- Tự động hỏi khi phát hiện output đã tồn tại
- Quét và chỉ dịch lại chunks lỗi
- Tiết kiệm thời gian và API quota

#### 5. Advanced Cache System
Cache thông minh với signature-based keys:
- Bao gồm: model, temperature, prompt hash, context
- Tự động invalidate khi thay đổi config
- GeminiProjectFileManager: Upload project một lần, tái sử dụng

### Translation Guides

Hệ thống hướng dẫn dịch nâng cao:

#### Style Profile
```json
// prompts/instructions/style_profile.json
{
  "genre": "Fantasy",
  "tone": "Epic, dramatic",
  "writing_style": "Third-person narrative"
}
```

#### Glossary
```csv
# prompts/instructions/glossary.csv
Original,Translation,Type
修仙,Tu tiên,术语
金丹,Kim đan,术语
```

#### Character Relations
```csv
# prompts/instructions/character_relations.csv
Speaker,Target,Pronoun
张三,李四,你
李四,张三,前辈
```

**Tạo guidelines tự động:**
```bash
cd utils/content-analysis
python analysis.py
```

### Monitoring & Statistics

Theo dõi chi tiết quá trình dịch:
- Tổng số từ/ký tự đã xử lý
- Token estimates
- Chunks thành công/thất bại
- API quota còn lại
- Thời gian thực hiện

---

## 🛠️ Utilities

### Content Analysis Tool

Phân tích nội dung trước khi dịch:

```bash
cd utils/content-analysis

# Cấu hình trong config.ini
# Đặt file nguồn vào thư mục nguồn

python analysis.py
```

**Output:**
- Style profile (JSON)
- Glossary (CSV)
- Character relations (CSV)

→ Tự động tạo translation guidelines

### EPUB Converter

Chuyển đổi EPUB ↔ Text/Markdown:

**EPUB → Text:**
```python
from plugins.epub_converter.epub_to_text import epub2text
text = epub2text.convert("input.epub")
```

**Text → EPUB:**
```python
from plugins.epub_converter.text_to_epub import main
main.create_epub("input.txt", "output.epub")
```

---

## ⚙️ Configuration

### Config.ini Structure

```ini
[API]
# API keys từ API.txt

[MODEL]
MODEL = gemini-2.5-flash              # Model chính
QA_MODEL = gemini-2.5-flash           # QA model
CONSISTENCY_MODEL = gemini-2.5-pro    # Consistency check

[PROCESSING]
MIN_CHARS_PER_CHUNK = 18000
MAX_CHARS_PER_CHUNK = 22000
TEMPERATURE = 0.75
REQUEST_DELAY = 2
MAX_REFINEMENT_ATTEMPTS = 2
MIN_LENGTH_RATIO = 0.5
MAX_LENGTH_RATIO = 5.0
CORRECTION_MODE = parallel            # parallel hoặc legacy
INPUT_LANG = CN                       # CN để bật Chinese detection
CONTEXT_CHAR_COUNT = 500
ENABLE_CONSISTENCY_CHECK = true

[CACHE]
ENABLE_CACHE = true

[DIRECTORIES]
INPUT_DIR = workspace/input
OUTPUT_DIR = workspace/output
CACHE_DIR = workspace/cache
PROGRESS_DIR = workspace/progress
ARCHIVE_DIR_NAME = _archive

[OUTPUT]
ENCODING = utf-8
```

---

## 📖 Workflow Example

### Dịch một cuốn truyện

**Chuẩn bị:**
1. Đặt API keys vào `API.txt` (mỗi key một dòng)
2. Đặt file truyện vào `workspace/input/`
3. (Tùy chọn) Tạo translation guidelines

**Chạy dịch:**

#### Option 1: Plugin system
```bash
python main.py
```

#### Option 2: Legacy workflow
```python
from src.workflow import run_translation_workflow
from src.configuration import load_all_configs

config = load_all_configs()
run_translation_workflow(config)
```

**Kết quả:**
- File dịch: `workspace/output/[tên truyện]_dich.txt`
- Cache: `workspace/cache/`
- Log: `workspace/progress/*.log`

---

## 🔧 Advanced Usage

### Custom Workflow với Legacy Modules

```python
from src.smart_chunker import intelligent_chunking
from src.chinese_detector import has_chinese_characters
from src.text_normalizer import TextNormalizer
from src.translators.core import robust_translate
from src.translators.cache_manager import TranslationCache

# Đọc text
with open("input.txt", "r") as f:
    text = f.read()

# Chunk text
chunks = intelligent_chunking(
    text,
    min_chars=18000,
    max_chars=22000
)

# Dịch từng chunk
normalizer = TextNormalizer()
cache = TranslationCache()

for i, chunk in enumerate(chunks):
    result = robust_translate(
        chunk_text=chunk,
        chunk_index=i,
        prompts=prompts,
        config_params=config,
        cache=cache,
        normalizer=normalizer
    )
    print(f"Chunk {i}: {result}")
```

### Custom Plugin

```python
from core.interfaces import ProcessorPlugin, PluginPriority
from typing import Dict, Any, Tuple

class MyCustomPlugin(ProcessorPlugin):
    @property
    def name(self) -> str:
        return "my_custom_plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        # Setup
        return True
    
    def process(self, input_data: Any, context: Dict[str, Any] = None) -> Tuple[Any, str]:
        # Process logic
        return result, "success"
```

---

## 📊 Migration từ v2.7

### Nếu đang dùng v2.7

**Cách 1: Tiếp tục dùng workflow cũ**
```python
# Code v2.7 vẫn hoạt động 100%
from src.workflow import run_translation_workflow
```

**Cách 2: Migrate sang plugin**
- Plugin `translation` đã tích hợp tất cả tính năng v2.7
- Chỉ cần chạy `python main.py`

### Breaking Changes

❌ **Không có!** Code v2.7 vẫn hoạt động hoàn toàn.

Chỉ có thay đổi về import path nếu bạn muốn dùng plugin:
- Cũ: `from src.translator import ...`
- Mới: `from plugins.translation.translator import ...`

---

## 🐛 Troubleshooting

### Import Error: No module named 'google'

```bash
# Cài đặt dependencies
pip install -r requirements.txt

# Hoặc trong venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Chinese characters vẫn sót

Tăng số lần retry:
```ini
[PROCESSING]
MAX_REFINEMENT_ATTEMPTS = 3  # Tăng từ 2 lên 3
```

### Cache không hoạt động

Kiểm tra quyền ghi:
```bash
chmod -R 755 workspace/cache
```

---

## 📝 Support

**Documentation:**
- [README.md](README.md) - User guide
- [CHANGELOG.md](CHANGELOG.md) - Complete version history
- [docs/README.md](docs/README.md) - Plugin architecture details

**Issues:**
- GitHub Issues: https://github.com/Narga/ai-vi-translator

---

**Version:** 3.0.1  
**Date:** 2025-12-06  
**Status:** Production Ready 🚀
