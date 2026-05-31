# 📚 Content Translator (v7.0.0)

**Hệ sinh thái dịch thuật tiểu thuyết & tài liệu chuyên nghiệp, ứng dụng sức mạnh của Google Gemini AI và OpenAI-compatible API.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Content Translator được thiết kế đặc biệt để xử lý khối lượng văn bản khổng lồ (tiểu thuyết, tài liệu kỹ thuật) với độ chính xác cao nhất về văn phong, thuật ngữ và ngữ cảnh.

---

## 🔥 Tính năng Nổi bật

- 🏗️ **Hexagonal Backend**: CLI và WebUI dùng chung backend (`backend/` package với Application/Domain/Infrastructure/Facade layers).
- 🤖 **Multi-Provider AI**: Hỗ trợ Google Gemini và OpenAI-compatible API (41 models).
- 🎨 **Minimalist UI**: Tông Slate & Indigo, loại bỏ emoji rác, tập trung vào trải nghiệm dịch.
- 📋 **Advanced Logging**: Xem nhật ký hệ thống và dự án trực quan ngay trên WebUI.
- 📦 **Project Archiving**: Lưu trữ dự án thông minh (Zip/Restore) tối ưu không gian.
- 🧪 **Test Suite**: 158 tests (smoke + unit) cho backend, CLI, WebUI và helpers.

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
# Tạo file .env (khuyến nghị)
echo "GEMINI_API_KEYS=your_key_1,your_key_2" > .env
# Hoặc OpenAI/OpenRouter
echo "OPENAI_API_KEY=your_openai_key" >> .env
```

### Chạy ứng dụng
```bash
python webui.py              # Web UI tại http://localhost:7860
python cli.py translate -i input/novel.txt  # CLI mode
```

---

## 📖 Tài liệu

| Tài liệu | Mô tả |
|-----------|--------|
| [📗 Hướng dẫn sử dụng](docs/MANUAL.md) | Hướng dẫn sử dụng chi tiết (Web UI, CLI, cấu hình) |
| [🗺️ Lộ trình (Roadmap)](docs/ROADMAP.md) | Lộ trình phát triển và kế hoạch tương lai |
| [🛠️ Hướng dẫn phát triển](docs/DEVELOPMENT.md) | Hướng dẫn lập trình, coding convention, kiến trúc |
| [📋 Lịch sử thay đổi](CHANGELOG.md) | Lịch sử thay đổi các phiên bản |
| [📊 Báo cáo dự án](docs/REPORTS.md) | Tổng hợp các báo cáo tối ưu hóa và fix lỗi |

---

## 🏗️ Kiến Trúc (v7.0.0)

```
webui.py ──→ webui/               # Flask App (Blueprints, Static, Templates)
cli.py   ──→ backend/             # Backend chung cho CLI & WebUI
main.py       ├── application/    # Use cases + DTOs + Progress ports
              │   ├── use_cases/  # TranslateText, TranslateProjectFiles, SpellcheckProjectFiles
              │   └── dto/        # Request/Response DTOs
              ├── domain/         # Domain models
              ├── infrastructure/ # Services: Config, API Keys, Workspace, Project, File, Provider
              ├── facade/         # AppService (singleton entry point)
              └── __init__.py     # create_app_service() factory
              core/               # Core pipeline (TranslationExecutor, plugins)
              services/           # Cache, TranslationMemory, Health
```

---

## 🤝 Đóng góp

Mọi đóng góp (Pull Request, Issue) đều được hoan nghênh. Xem [CHANGELOG.md](CHANGELOG.md) để nắm bắt các thay đổi mới nhất.

---
**Tác giả:** Narga  
**Phiên bản:** 7.0.0  
**Ngày:** 31/05/2026
