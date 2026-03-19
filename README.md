# 📚 Content Translator (v6.0.0 Alpha)

**Hệ sinh thái dịch thuật tiểu thuyết & tài liệu chuyên nghiệp, ứng dụng sức mạnh của Google Gemini AI và OpenAI-compatible API.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Content Translator được thiết kế đặc biệt để xử lý khối lượng văn bản khổng lồ (tiểu thuyết, tài liệu kỹ thuật) với độ chính xác cao nhất về văn phong, thuật ngữ và ngữ cảnh.

---

## 🔥 Tính năng Nổi bật

- 🤖 **Multi-Provider AI**: Hỗ trợ Google Gemini và OpenAI-compatible API (OpenRouter, proxy). Chuyển đổi linh hoạt giữa các provider.
- 🧩 **Sentence-Level Chunker**: Tuyệt đối không cắt ngang câu, đảm bảo bản dịch liền mạch.
- 📖 **Dynamic Glossary**: Tự động nhận diện và nhúng thuật ngữ vào AI tùy theo ngữ cảnh.
- 🧠 **Translation Memory**: Tự học từ bản dịch cũ, tiết kiệm tới 30% chi phí API.
- 🛠️ **Project-Based Workspace**: Quản lý từng bộ truyện riêng biệt với prompt, glossary và TM riêng.
- 🎭 **Genre-based Prompt Sets**: Bộ prompt theo từng thể loại (Tiên hiệp, Đô thị, Ngôn tình...).
- 📄 **Format Support**: Xử lý trực tiếp TXT, EPUB và PDF (via OCR).

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
| [📗 Manual.md](docs/documents/Manual.md) | Hướng dẫn sử dụng chi tiết (Web UI, CLI, cấu hình) |
| [🗺️ Roadmap.md](docs/Roadmap.md) | Lộ trình phát triển v5.0.0 |
| [🛠️ DEVELOPMENT.md](docs/documents/DEVELOPMENT.md) | Hướng dẫn lập trình, coding convention, kiến trúc |
| [📋 CHANGELOG.md](docs/CHANGELOG.md) | Lịch sử thay đổi các phiên bản |

---

## 🏗️ Kiến Trúc (v6.0.0)

```
webui.py ──→ webui/          # Flask App (Blueprints)
main.py  ──→ core/           # Plugin Manager
             services/       # AI Provider, Cache, Translation Memory
               ├── ai_provider.py    # Multi-provider adapter
               ├── openai_client.py  # OpenAI/OpenRouter wrapper
               └── genai_client.py   # Google Gemini wrapper
             plugins/        # Translation, EPUB, OCR
             templates/
               └── partials/  # 6 Jinja2 modular templates
```

> WebUI sử dụng Flask Blueprints + Jinja2 partials. Hỗ trợ đa provider AI qua adapter pattern.

---

## 🤝 Đóng góp

Mọi đóng góp (Pull Request, Issue) đều được hoan nghênh. Xem [CHANGELOG.md](docs/CHANGELOG.md) để nắm bắt các thay đổi mới nhất.

---
**Tác giả:** Narga  
**Phiên bản:** 6.0.0-beta.1  
**Ngày:** 19/03/2026
