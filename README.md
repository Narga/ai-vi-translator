# Novel Translator v3.0.2

Pure Plugin Architecture for Novel Translation (Chinese → Vietnamese)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup API Keys

```bash
cp config/API.txt.example config/API.txt
# Edit config/API.txt and add your Gemini API keys (one per line)
```

Get API keys from: https://aistudio.google.com/app/apikey

### 3. Add Source Files

Put your Chinese novel files in `workspace/input/`:

```bash
workspace/input/
├── novel.txt           # Single file
# OR
├── Novel-Name/         # Directory with chapters
│   ├── 001.txt
│   ├── 002.txt
│   └── ...
```

### 4. Run Translation

```bash
python3 main.py
```

Results will be saved in `workspace/output/`

---

## 📁 Project Structure

```
novel-translator/
├── main.py                 # Entry point (200 lines)
├── core/                   # Plugin infrastructure
│   ├── plugin_manager.py
│   ├── service_bus.py
│   ├── event_bus.py
│   └── interfaces/
├── services/               # Shared services
│   ├── api_service.py      # API key management
│   ├── cache_service.py    # Translation cache
│   └── config_service.py   # Configuration
├── plugins/                # All features as plugins
│   ├── translation/        # Core translation
│   ├── epub_converter/     # EPUB tools
│   ├── consistency_check/  # Terminology check
│   └── chinese_detector/   # Chinese char detection
├── config/
│   ├── API.txt            # Your API keys (git-ignored)
│   ├── API.txt.example    # Template
│   └── app.ini            # Plugin configs
├── prompts/               # Translation prompts
│   ├── 01-main.txt
│   ├── 02-retranslate.txt
│   └── 03-correction.txt
├── workspace/
│   ├── input/             # Source files
│   ├── output/            # Translations
│   ├── cache/             # Cache storage
│   └── progress/          # Logs
└── docs/                  # Documentation
    ├── QUICK_START.md
    ├── CHANGELOG.md
    └── README.md          # Architecture details
```

---

## ✨ Features

### Core Features
- ✅ Smart chunking (18,000-22,000 chars)
- ✅ Context chaining between chunks
- ✅ Auto-retry with Chinese character detection
- ✅ Translation cache (signature-based)
- ✅ Text normalization
- ✅ Detailed logging and statistics

### Plugin System
- ✅ Modular architecture
- ✅ Easy to extend
- ✅ Service dependency injection
- ✅ Event-driven communication
- ✅ Error isolation

---

## ⚙️ Configuration

Edit `config.ini` for advanced settings:

```ini
[MODEL]
MODEL = gemini-2.5-flash              # Main model
QA_MODEL = gemini-2.5-flash           # QA model
CONSISTENCY_MODEL = gemini-2.5-pro    # Consistency check

[PROCESSING]
MIN_CHARS_PER_CHUNK = 18000
MAX_CHARS_PER_CHUNK = 22000
TEMPERATURE = 0.75
MAX_REFINEMENT_ATTEMPTS = 2
CONTEXT_CHAR_COUNT = 500
CORRECTION_MODE = parallel             # or 'legacy'
INPUT_LANG = CN                        # Enable Chinese detection

[CACHE]
ENABLE_CACHE = true

[DIRECTORIES]
INPUT_DIR = workspace/input
OUTPUT_DIR = workspace/output
CACHE_DIR = workspace/cache
PROGRESS_DIR = workspace/progress
```

---

## 📚 Documentation

- **[Quick Start](docs/QUICK_START.md)** - 5-minute setup guide
- **[Integration Guide](docs/INTEGRATION_GUIDE.md)** - Detailed features
- **[Changelog](docs/CHANGELOG.md)** - Version history
- **[Architecture](docs/README.md)** - Plugin system details

---

## 🔄 Legacy Code

Legacy v2.7 workflow code preserved in `legacy` branch:

```bash
git checkout legacy    # Access legacy code
git checkout master    # Return to v3.0.2
```

---

## 📝 License

MIT License

---

## 🤝 Contributing

This is a personal project. For bugs or suggestions, open an issue.

---

**Version:** 3.0.2  
**Last Updated:** 2025-12-06  
**Status:** Production Ready 🚀
