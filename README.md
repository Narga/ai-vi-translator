# 📚 Novel Translator (v5.0.0 Alpha)

**Hệ sinh thái dịch thuật tiểu thuyết & tài liệu chuyên nghiệp, ứng dụng sức mạnh của Google Gemini AI.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Novel Translator không chỉ là một công cụ dịch thuật thông thường. Nó được thiết kế đặc thý để xử lý khối lượng văn bản khổng lồ (tiểu thuyết) với độ chính xác cao nhất về văn phong, thuật ngữ và ngữ cảnh.

---

## 🔥 Tính năng Nổi bật

- 🤖 **Multi-Model Support**: Tối ưu nhất cho `gemini-3-flash-preview` và `gemini-1.5-pro`.
- 🧩 **Sentence-Level Chunker**: Tuyệt đối không cắt ngang câu, đảm bảo bản dịch liền mạch.
- 📖 **Dynamic Glossary**: Tự động nhận diện và nhúng thuật ngữ vào AI tùy theo ngữ cảnh.
- 🧠 **Translation Memory**: Tự học từ bản dịch cũ, tiết kiệm tới 30% chi phí API.
- 🛠️ **Project-Based Workspace**: Quản lý từng bộ truyện riêng biệt với trạng thái (Checkpoint) bền vững.
- 📄 **Format Support**: Xử lý trực tiếp TXT, EPUB và PDF (via OCR).

---

## 🚀 Bắt đầu Nhanh

### Cài đặt
```bash
# Clone dự án
git clone https://github.com/Narga/ai-vi-translator.git
cd ai-vi-translator

# Cài đặt môi trường
uv sync
```

### Chạy ứng dụng
Mở giao diện Web (Khuyên dùng):
```bash
python webui.py
```
Sau đó truy cập: `http://localhost:5000`

---

## 📖 Tài liệu & Hướng dẫn

Để đảm bảo bạn khai thác hết sức mạnh của hệ thống, vui lòng tham khảo các tài liệu chuyên sâu trong thư mục `docs/`:

- [**Hướng dẫn sử dụng (Manual.md)**](docs/Manual.md): Chi tiết cách dùng UI, CLI và cấu hình.
- [**Lộ trình phát triển (Roadmap.md)**](docs/Roadmap.md): Kế hoạch nâng cấp v5.0.0.
- [**Hướng dẫn lập trình (DEVELOPMENT.md)**](docs/DEVELOPMENT.md): Dành cho các dev muốn mở rộng plugin.

---

## 🤝 Đóng góp

Mọi đóng góp (Pull Request, Issue) đều được hoan nghênh. Hãy xem qua `CHANGELOG.md` để nắm bắt các thay đổi mới nhất.

---
**Tác giả:** Narga  
**Phiên bản:** 5.0.0-alpha  
**Ngày:** 01/03/2026
