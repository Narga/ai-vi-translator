# Novel Translator v3.0.0 - Plugin Architecture

Công cụ dịch tiểu thuyết với kiến trúc plugin linh hoạt, extensible, và error-isolated.

## 🎯 Tính năng Mới v3.0

### Plugin Architecture
- **Extensible**: Thêm features mới = tạo plugin mới
- **Error Isolation**: Plugin crash không ảnh hưởng hệ thống
- **Event-Driven**: Plugins giao tiếp qua events
- **Service-Oriented**: Shared services qua ServiceBus

### Plugins Hiện tại
1. **Translation** - Core translation engine
   - Smart chunking
   - Text normalization
   - Chinese character detection & fixing
   - Context chaining

2. **EPUB Converter** - Format conversion
   - EPUB → Text/Markdown
   - Text/Markdown → EPUB

3. **Consistency Check** - QA checking
   - Character name consistency
   - Terminology consistency

4. **Chinese Detector** - Quality assurance
   - Detect untranslated Chinese characters
   - File/chunk scanning

## 🚀 Quick Start

### Requirements
```bash
Python 3.10+
pip install -r requirements.txt
```

### Configuration
1. Create `API.txt` with your Gemini API keys (one per line)
2. Adjust `config/app.ini` if needed

### Run
```bash
python main.py
```

## 📁 Project Structure

```
novel-translator/
├── main.py                 # New plugin-based entry point
├── main_legacy.py         # Old monolithic version (backup)
│
├── core/                  # Core infrastructure
│   ├── plugin_manager.py  # Plugin lifecycle management
│   ├── service_bus.py     # Service registry
│   ├── event_bus.py       # Event system
│   └── interfaces/        # Plugin interfaces
│
├── services/              # Shared services
│   ├── api_service.py     # API key management
│   ├── cache_service.py   # Translation caching
│   └── config_service.py  # Configuration
│
├── plugins/               # Plugin directory
│   ├── translation/       # Translation plugin
│   ├── epub_converter/    # EPUB conversion plugin
│   ├── consistency_check/ # Consistency checking
│   └── chinese_detector/  # Chinese character detection
│
├── config/
│   ├── app.ini           # Main configuration
│   └── plugins/          # Plugin-specific configs
│
└── src/                  # Legacy code (kept for reference)
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

**Version**: 3.0.0  
**Author**: Narga  
**Architecture**: Plugin-based with ServiceBus and EventBus