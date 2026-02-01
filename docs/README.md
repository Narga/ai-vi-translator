# Novel Translator v4.0.0 - SDK Migration & Core Upgrades

Công cụ dịch tiểu thuyết với kiến trúc plugin linh hoạt, sử dụng **google-genai SDK** và model **gemini-3-flash-preview**.

## 🎯 Tính năng Mới v4.0

### SDK Migration
- **google-genai SDK**: SDK mới của Google (thay thế google-generativeai)
- **gemini-3-flash-preview**: Model mới nhất với 1M context window
- **thinking_level**: Control reasoning depth (MINIMAL/LOW/MEDIUM/HIGH)
- **Fallback support**: Tự động fallback sang SDK cũ nếu cần

### Protection Services (từ Book_translator)
- **AdaptiveRateLimiter**: Progressive backoff 30s→300s, daily quota tracking
- **CircuitBreaker**: Ngăn cascade failures với 3 states (CLOSED/OPEN/HALF_OPEN)
- **HealthMonitor**: Giám sát runtime (max 48h) và stall detection (30 phút)
- **Emergency Stop**: Thread-safe graceful shutdown với signal handlers

### Plugin Architecture (v3.0)
- **Extensible**: Thêm features mới = tạo plugin mới
- **Error Isolation**: Plugin crash không ảnh hưởng hệ thống
- **Event-Driven**: Plugins giao tiếp qua events
- **Service-Oriented**: Shared services qua ServiceBus

### Plugins Hiện tại
1. **Translation** - Core translation engine
2. **EPUB Converter** - Format conversion (EPUB ↔ Text/Markdown)
3. **Consistency Check** - QA checking
4. **Chinese Detector** - Quality assurance
5. **OCR** - PDF/Image text recognition

## 🚀 Quick Start

### Requirements
```bash
Python 3.10+
pip install -r requirements.txt
```

### Configuration
1. Tạo `config/API.txt` với Gemini API keys (mỗi key một dòng)
2. Điều chỉnh `config/app.ini` nếu cần (SDK, model, thinking_level)

### Run
```bash
python main.py
```

## 📁 Project Structure

```
novel-translator/
├── main.py                 # Entry point v4.0 (google-genai SDK)
├── core/                   # Core infrastructure
│   ├── plugin_manager.py   # Plugin lifecycle management
│   ├── service_bus.py      # Service registry
│   └── event_bus.py        # Event system
│
├── services/               # Shared services
│   ├── genai_client.py     # ✨ GenAI wrapper (SDK mới + fallback)
│   ├── api_service.py      # AdaptiveRateLimiter (20 RPD/key)
│   ├── circuit_breaker.py  # ✨ Circuit Breaker pattern
│   ├── health_monitor.py   # ✨ Runtime/stall monitoring
│   ├── emergency_stop.py   # ✨ Graceful shutdown
│   ├── cache_service.py    # Translation caching
│   └── config_service.py   # Configuration
│
├── plugins/                # Plugin directory
│   ├── translation/        # Core translation (GenAIClient)
│   ├── epub_converter/     # EPUB conversion
│   ├── consistency_check/  # Consistency checking
│   ├── chinese_detector/   # Chinese detection
│   └── ocr/               # OCR plugin
│
└── config/
    ├── app.ini            # Main config (SDK, model, thinking_level)
    └── API.txt            # API keys
```

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