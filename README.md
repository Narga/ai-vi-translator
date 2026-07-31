# 📚 Content Translator (v8.15.0)

**Hệ sinh thái dịch thuật tiểu thuyết & tài liệu chuyên nghiệp, ứng dụng sức mạnh của Google Gemini AI và OpenAI-compatible API.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Content Translator được thiết kế đặc biệt để xử lý khối lượng văn bản khổng lồ (tiểu thuyết, tài liệu kỹ thuật) với độ chính xác cao nhất về văn phong, thuật ngữ và ngữ cảnh.

**Tính năng mới (v8.15.0):** Hợp nhất Engine Soát lỗi AI vào `TranslationExecutor` (`core/executor.py`), xóa bỏ 2 module thừa `spellcheck_executor.py` và `spellchecker.py`; Thêm tùy chọn xóa file nguồn sau chuyển đổi MD ↔ HTML & dọn file HTML trung gian khi xuất EPUB 3; Nâng cấp API Search & Replace toàn bộ dự án (`search-all`, `replace-all` quét `rglob(*)`); Tối ưu Editor (reset vị trí cuộn/con trỏ về đầu dòng, sync scroll mượt mà, icon button Retranslate force retranslate); Tổng hợp dọn dẹp tài liệu `docs/wip/` và bổ sung `.gitignore`.

---

## 🔥 Tính năng Nổi bật

- 🏗️ **Hexagonal Backend**: CLI và WebUI dùng chung backend (`backend/` package với Application/Domain/Infrastructure/Facade layers).
- 🤖 **Multi-Provider AI**: Hỗ trợ Google Gemini và OpenAI-compatible API (OpenRouter, Xiaomi, proxy). Quản lý nhiều provider qua `providers.json`.
- 🎨 **Quản lý Dự án**: Tab "Quản lý dự án" độc lập với workspace 3 cột, import/export zip, trạng thái tự động.
- 🖥️ **So sánh bản dịch (Diff View)**: Xem Dọc/Ngang — so sánh bản gốc và bản dịch trực quan.
- 📋 **Advanced Logging**: Xem nhật ký hệ thống và dự án trực quan ngay trên WebUI.
- 📦 **Project Archiving**: Lưu trữ dự án thông minh (Zip/Restore) tối ưu không gian.
- 🧪 **Test Suite**: Unit + smoke tests cho backend, CLI, WebUI và helpers.
- 🔌 **Plugin Management**: Quản lý plugin tập trung trong tab Cấu hình. eBook Kit và OCR Toolbox tích hợp vào workspace dự án.

---

## 🚀 Bắt đầu Nhanh

### Cài đặt
```bash
git clone https://github.com/Narga/ai-vi-translator.git
cd ai-vi-translator
uv sync
```

### Cấu hình API Key
```bash
# Chạy ứng dụng lần đầu — tự động migration từ API.txt + app.ini → providers.json
# Hoặc cấu hình thủ công qua tab "Cấu hình" trên WebUI
# providers.json là nguồn duy nhất (tự động thêm vào .gitignore)
```

### Chạy ứng dụng
```bash
python main.py              # Web UI tại http://localhost:7860
python cli.py translate -i input/novel.txt  # CLI mode
```

---

## 📖 Tài liệu

| Tài liệu | Mô tả |
|-----------|--------|
| [📗 Hướng dẫn sử dụng](docs/MANUAL.md) | Hướng dẫn sử dụng chi tiết (Web UI, CLI, cấu hình) |
| [🗺️ Lộ trình (Roadmap)](roadmap.md) | Lộ trình phát triển và kế hoạch tương lai |
| [🛠️ Hướng dẫn phát triển](docs/DEVELOPMENT.md) | Hướng dẫn lập trình, coding convention, kiến trúc |
| [📋 Lịch sử thay đổi](CHANGELOG.md) | Lịch sử thay đổi các phiên bản |

---

## 🏗️ Kiến Trúc (v7.0+)

```
main.py ──→ webui/               # Flask App (Blueprints, Static, Templates)
cli.py  ──→ backend/             # Backend chung cho CLI & WebUI
            ├── application/    # Use cases + DTOs + Progress ports
            │   ├── use_cases/  # TranslateText, TranslateProjectFiles, SpellcheckProjectFiles
            │   └── dto/        # Request/Response DTOs
            ├── domain/         # Domain models
            ├── infrastructure/ # Services: Config, API Keys, Workspace, Project, File, Provider
            ├── facade/         # AppService (singleton entry point)
            └── __init__.py     # create_app_service() factory
            core/               # Core pipeline (TranslationExecutor, plugins)
            services/           # ApiService, OpenAIClient, GenAIClient, TranslationMemory, EmergencyStop, Checkpoint
            webui/static/js/    # 8 ES modules: api-client, provider-manager, project-manager,
                                #   editor-component, prompt-manager, translation-worker, ui-helpers, plugin-manager
```

---

## 🤝 Đóng góp

Mọi đóng góp (Pull Request, Issue) đều được hoan nghênh. Xem [CHANGELOG.md](CHANGELOG.md) để nắm bắt các thay đổi mới nhất.

---
**Tác giả:** Narga  
**Phiên bản:** 8.12.0  
**Ngày:** 28/07/2026
