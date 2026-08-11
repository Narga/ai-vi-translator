# 📚 Content Translator (v8.23.0)

**Công cụ cá nhân dịch tiểu thuyết từ ngoại ngữ sang tiếng Việt — chất lượng dịch thuật là trên hết.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> **Mục đích**: Biên dịch nội dung **text** của sách điện tử từ ngôn ngữ khác sang tiếng Việt, dùng một mình, nguồn đóng. EPUB xuất ra ở mức tối thiểu để biên tập sau bằng phần mềm chuyên dụng (Sigil/Calibre) — ảnh, font, stylesheet sẽ được đưa vào thủ công trong quá trình biên tập.

**Tính năng mới (v8.23.0):** Kiên cố hóa lưu trữ trạng thái tác vụ dịch xuống SQLite TaskStore (`tasks.db`), tự động quét khôi phục checkpoint mồ côi và tác vụ dở dang khi khởi động lại server / máy sleep (Sleep Recovery), vá lỗi hiển thị modal tiến trình UI.


---

## 🔥 Tính năng Nổi bật

- 🏗️ **Hexagonal Backend**: CLI và WebUI dùng chung backend (`backend/` package với Application/Domain/Infrastructure/Facade layers).
- 🤖 **Multi-Provider AI**: Hỗ trợ Google Gemini và OpenAI-compatible API (OpenRouter, Cloudflare AI Gateway, proxy). Quản lý nhiều provider qua `providers.json`. Tự động nhận dạng, lọc và hiển thị model đặc thù (VD: Workers AI).
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
**Phiên bản:** 8.21.0
**Ngày:** 05/08/2026
