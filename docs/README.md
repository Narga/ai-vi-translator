# Novel Translator v4.0.7 - UI Redesign

Công cụ dịch tiểu thuyết với kiến trúc plugin linh hoạt, sử dụng **google-genai SDK**.

## 🎯 Tính năng Mới v4.0.7

### Translation Memory
- **Fuzzy Matching**: Tìm kiếm các đoạn tương tự đã dịch trước đó
- **N-gram Similarity**: Sử dụng Jaccard similarity với n-grams
- **Auto-learning**: Tự động học từ các bản dịch thành công
- **Configurable**: Ngưỡng similarity có thể điều chỉnh (default 85%)
- **Export/Import**: Chia sẻ TM giữa các phiên làm việc

### API Optimizations
- Chunk size lên đến 100K chars (từ config)
- Priority: Cache → TM → API

### SDK Migration
- **google-genai SDK**: SDK mới của Google (thay thế google-generativeai)
- **gemini-3-flash-preview**: Model mới nhất với 1M context window
- **thinking_level**: Control reasoning depth (MINIMAL/LOW/MEDIUM/HIGH)

### Protection Services (từ Book_translator)
- **AdaptiveRateLimiter**: Progressive backoff 30s→300s, daily quota tracking (20 RPD/key)
- **GlobalRPMRateLimiter**: Giới hạn 15 RPM toàn cục (sliding window)
- **TokenBudgetLimiter**: Giới hạn 1M TPM (token estimation)
- **CircuitBreaker**: Ngăn cascade failures với 3 states (CLOSED/OPEN/HALF_OPEN)
- **HealthMonitor**: Giám sát runtime (max 48h) và stall detection (30 phút)
- **Emergency Stop**: Thread-safe graceful shutdown với signal handlers

### CLI & Automation
- **Argparse CLI**: Giao diện dòng lệnh mạnh mẽ (`cli.py`)
- **Checkpoint/Resume**: Lưu tiến trình, tiếp tục khi bị gián đoạn
- **Async Support**: AsyncGenAIClient cho concurrent requests

### Security
- **.env Support**: API keys từ environment variables (ưu tiên)
- **Fallback**: Vẫn hỗ trợ file `config/API.txt` (legacy)

### Plugin Architecture (v3.0)
- **Extensible**: Thêm features mới = tạo plugin mới
- **Error Isolation**: Plugin crash không ảnh hưởng hệ thống
- **Event-Driven**: Plugins giao tiếp qua events
- **Service-Oriented**: Shared services qua ServiceBus

### Plugins Hiện tại
1. **Translation** - Core translation engine
2. **EPUB Converter** - Format conversion (EPUB ↔ Text/Markdown)
3. **OCR** - PDF/Image text recognition

## 🚀 Quick Start

### Requirements
```bash
Python 3.10+
pip install -r requirements.txt
```

### Configuration (Khuyến nghị: dùng .env)
```bash
# Cách 1: Sử dụng .env (khuyến nghị)
cp .env.example .env
# Edit .env và thêm API keys:
# GEMINI_API_KEYS=key1,key2,key3

# Cách 2: Sử dụng file text (legacy)
# Tạo config/API.txt với mỗi key một dòng
```

### Chạy với uv (Khuyến nghị)
```bash
# Cài đặt dependencies
uv sync

# Chạy trực tiếp
uv run python main.py

# Hoặc chạy CLI
uv run python cli.py translate -i input/novel.txt

# Hoặc chạy Web UI
uv run python webui.py --port 7860
```

### Chạy thông thường (pip)
```bash
pip install -r requirements.txt

# Cách 1: Chạy trực tiếp
python main.py

# Cách 2: Sử dụng CLI
python cli.py translate -i input/novel.txt -o output/
python cli.py translate -i input/ --dry-run  # Chạy thử không gọi API
python cli.py status --api-keys               # Xem trạng thái

# Resume từ checkpoint
python cli.py resume --checkpoint workspace/checkpoints/xxx.json
```

## ⚙️ Rate Limiting & Optimization

### Gemini API Free Tier Limits
| Limit | Value | How We Handle |
|-------|-------|---------------|
| RPM | 15 | GlobalRPMRateLimiter (sliding window 60s) |
| TPM | 1M | TokenBudgetLimiter (estimate ~2.5 chars/token) |
| RPD | 1500/key | AdaptiveRateLimiter (20 RPD/key) |

### Performance Tips
- **Nhiều API keys**: Tăng throughput (mỗi key 20 RPD)
- **Cache**: Bật cache để tránh dịch lại text đã dịch
- **Cache Compression**: Cache files được nén gzip (giảm ~60-80%)
- **Chunk size**: Điều chỉnh `MAX_CHARS_PER_CHUNK` (mặc định 22000)
- **Memory Mode**: Dùng `chunk_text_generator()` cho file lớn

## 🌏 Multi-language Support (v4.0.2+)

### Supported Languages

| Language | Code | Character Detection |
|----------|------|-------------------|
| Chinese | CN | 中文字符 |
| Japanese | JP | ひらがな / カタカナ |
| Korean | KR | 한글 |

### Configuration
```ini
[PROCESSING]
INPUT_LANG = CN  # Options: CN, JP, KR
```

Hệ thống tự động detect và sửa ký tự gốc còn sót dựa trên ngôn ngữ đã chọn.

## 📁 Project Structure

```
novel-translator/
├── main.py                 # Entry point v4.0
├── cli.py                  # ✨ CLI with argparse
├── core/                   # Core infrastructure
│   ├── plugin_manager.py   # Plugin lifecycle management
│   ├── service_bus.py      # Service registry
│   └── event_bus.py       # Event system
│
├── services/               # Shared services
│   ├── genai_client.py     # GenAI wrapper
│   ├── async_genai_client.py  # ✨ Async support
│   ├── api_service.py      # ✨ RPM + TPM limiters
│   ├── cache_service.py    # Translation caching
│   ├── checkpoint_service.py # ✨ Checkpoint/Resume
│   ├── circuit_breaker.py  # Circuit Breaker pattern
│   ├── health_monitor.py   # Runtime monitoring
│   ├── emergency_stop.py   # Graceful shutdown
│   └── config_service.py   # Configuration
│
├── plugins/                # Plugin directory
│   ├── translation/       # Core translation
│   ├── epub_converter/    # EPUB conversion
│   └── ocr/              # OCR plugin
│
├── config/
│   ├── app.ini           # Main config
│   └── API.txt           # API keys (legacy)
│
└── .env.example          # ✨ Environment template
```

## 🌐 Web UI (v4.0.3+)

Giao diện web đơn giản với Flask, hỗ trợ real-time progress.

### Chạy Web UI
```bash
uv run python webui.py
# Hoặc: python webui.py --port 7860

# Mở trình duyệt: http://localhost:7860
```

### Tính năng Web UI (v4.0.6)
- ✅ **Real-time Progress**: Progress bar cập nhật live với SSE
- ✅ **Form Cấu hình**: Chọn model, ngôn ngữ, temperature, chunk size
- ✅ **Dynamic Models**: Tự động phát hiện models khả dụng từ API
- ✅ **Chunk Size Input**: Nhập giá trị tay thay vì chọn cố định
- ✅ **Batch Translation**: Checkbox chọn nhiều file, dịch hàng loạt
- ✅ **Done Folder**: File đã dịch tự động chuyển vào workspace/done
- ✅ **Retranslate**: Dịch lại file đã hoàn thành
- ✅ **File Management**: Di chuyển file giữa done/input
- ✅ **Detailed Stats**: Số từ đã dịch, đang chờ, số file input/output/done
- ✅ **Translation Memory**: Fuzzy matching với similarity threshold
- ✅ **TM Stats**: Hiển thị số entries, kích thước TM

### Cấu trúc Web UI
```
webui.py              # Flask app chính
templates/
└── index.html        # Giao diện ngườii dùng
```

---

## 🔌 Creating a Plugin

### 1. Create Plugin Directory
```bash
mkdir plugins/my_plugin
```

### 2. Create `plugin.py`
```python
from core.interfaces import ProcessorPlugin
from typing import Dict, Any, Tuple

class Plugin(ProcessorPlugin):
    @property
    def name(self) -> str:
        return "my_plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        # Initialize plugin
        self.service_bus.get_service('logger').info("My plugin initialized!")
        return True
    
    def cleanup(self) -> None:
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {'features': ['my_feature']}
    
    def process(self, input_data: Any, context: Dict[str, Any] = None) -> Tuple[Any, str]:
        # Process data
        result = f"Processed: {input_data}"
        return result, 'success'
    
    def supports_format(self, format: str) -> bool:
        return format in ['txt', 'md']
```

### 3. Plugin Will Auto-Load
Plugin Manager auto-discovers plugins in `plugins/` directory.

## 💻 CLI Usage

```bash
# Dịch file
python cli.py translate -i input/novel.txt -o output/

# Dịch thư mục
python cli.py translate -i input/ -o output/

# Chạy thử (không gọi API)
python cli.py translate -i input/novel.txt --dry-run

# Xem trạng thái
python cli.py status
python cli.py status --api-keys
python cli.py status --cache

# Tiếp tục từ checkpoint
python cli.py resume --checkpoint workspace/checkpoints/abc123.json

# Tùy chọn khác
python cli.py translate -i input/ -o output/ --lang CN --model gemini-3-flash-preview --chunk-size 20000
```

## 🛠️ Development

### Run Tests
```bash
python -m pytest tests/
```

### Debug Mode
Set logging level in code:
```python
logging.basicConfig(level=logging.DEBUG)
```

## 📊 Architecture Benefits

| Feature | v2.x (Monolithic) | v3.0 (Plugin) |
|---------|-------------------|---------------|
| Add new feature | Modify core code | Create new plugin |
| Error isolation | ❌ One error crashes all | ✅ Plugin errors contained |
| Extensibility | ⚠️ Limited | ✅ Unlimited |
| Testing | ⚠️ Full system | ✅ Per-plugin |
| Maintenance | ⚠️ Complex | ✅ Simple |

## 🔄 Migration from v2.x

Old code still works! `main_legacy.py` contains the original implementation.

To migrate:
1. Use `main.py` for new plugin-based workflow
2. Gradually port custom modifications to plugins
3. Test both versions side-by-side

## 📝 Documentation

- [Implementation Plan](file:///Users/narga/.gemini/antigravity/brain/fc8c458b-838b-463d-a6b3-95ce68d2b8f4/implementation_plan.md)
- [Development Walkthrough](file:///Users/narga/.gemini/antigravity/brain/fc8c458b-838b-463d-a6b3-95ce68d2b8f4/walkthrough.md)

## 🤝 Contributing

1. Create a new plugin in `plugins/`
2. Follow the interface conventions
3. Add tests in `tests/plugins/`
4. Submit PR

## 📄 License

Same as v2.x

---

**Version**: 4.0.0  
**Author**: Narga  
**Architecture**: Plugin-based with google-genai SDK