# 📚 Content Translator (v6.5.0)

**Hệ sinh thái dịch thuật tiểu thuyết & tài liệu chuyên nghiệp, ứng dụng sức mạnh của Google Gemini AI và OpenAI-compatible API.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Content Translator được thiết kế đặc biệt để xử lý khối lượng văn bản khổng lồ (tiểu thuyết, tài liệu kỹ thuật) với độ chính xác cao nhất về văn phong, thuật ngữ và ngữ cảnh.

---

## 🔥 Tính năng Nổi bật

- 🤖 **Multi-Provider AI**: Hỗ trợ Google Gemini và OpenAI-compatible API.
- 📋 **Advanced Logging**: Hệ thống xem nhật ký hệ thống và dự án trực quan ngay trên WebUI.
- 📦 **Project Archiving**: Hệ thống lưu trữ dự án thông minh (Zip/Restore) tối ưu không gian.
- ⚡ **High Performance UI**: Giao diện Dashboard tối giản, cực nhanh dựa trên Tachyons CSS.
- 🛡️ **Stable Layout**: Hệ thống 7-Tab hợp nhất với cơ chế Flexbox ổn định, chống chồng lấn.
- ✨ **Integrated AI Guidelines**: Tự động tạo Chỉ dẫn, Thuật ngữ, Mối quan hệ và Tóm tắt bằng AI ngay trong từng thẻ.

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
| [📗 MANUAL.md](MANUAL.md) | Hướng dẫn sử dụng chi tiết (Web UI, CLI, cấu hình) |
| [🗺️ ROADMAP.md](ROADMAP.md) | Lộ trình phát triển và kế hoạch tương lai |
| [🛠️ DEVELOPMENT.md](DEVELOPMENT.md) | Hướng dẫn lập trình, coding convention, kiến trúc |
| [📋 CHANGELOG.md](CHANGELOG.md) | Lịch sử thay đổi các phiên bản |
| [📊 REPORTS.md](REPORTS.md) | Tổng hợp các báo cáo tối ưu hóa và fix lỗi |
| [🧠 memory.md](memory.md) | "Bộ nhớ" dự án, context cho AI |

---

## 🏗️ Kiến Trúc (v6.5.0)

```
webui.py ──→ webui/          # Flask App (Blueprints)
main.py  ──→ core/           # Dispatcher / Functional Pipeline
             services/       # AI Provider, Cache, Translation Memory
               ├── ai_provider.py    # Multi-provider adapter
               ├── openai_client.py  # OpenAI/OpenRouter wrapper
               └── genai_client.py   # Google Gemini wrapper
             plugins/        # Translation, EPUB, OCR
             templates/
               └── partials/  # Modular Tachyons templates
```

---

## 🤝 Đóng góp

Mọi đóng góp (Pull Request, Issue) đều được hoan nghênh. Xem [CHANGELOG.md](CHANGELOG.md) để nắm bắt các thay đổi mới nhất.

---
**Tác giả:** Narga  
**Phiên bản:** 6.5.0  
**Ngày:** 15/04/2026
