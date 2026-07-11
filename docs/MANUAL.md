# 📖 Hướng Dẫn Sử Dụng Content Translator

Chào mừng bạn đến với hệ thống dịch thuật tiểu thuyết chuyên nghiệp sử dụng sức mạnh của Gemini AI.

## 1. Cài Đặt Ban Đầu

### Yêu cầu hệ thống
- Python 3.10+
- Bộ công cụ `uv` (khuyến nghị) hoặc `pip`
- API Keys từ Google AI Studio (Gemini)

### Các bước cài đặt
1. Giải nén/Clone mã nguồn.
2. Cài đặt các thư viện cần thiết:
   ```bash
   uv sync
   # Hoặc dùng pip:
   pip install -r requirements.txt
   ```
3. Cấu hình API: Chạy ứng dụng lần đầu → tự động migration sang `config/providers.json`. Hoặc cấu hình qua tab **Cấu hình** trên WebUI.
   ```bash
   # Cấu hình thủ công: tạo config/providers.json (xem mẫu trong code)
   # Hoặc cấu hình qua giao diện WebUI
   ```

---

## 2. Các Chế Độ Sử Dụng

### 🖥️ Chế độ Giao diện Web (WebUI)
Đây là cách dễ nhất để sử dụng cho người dùng cuối.
```bash
python webui.py
# Hoặc chỉ định port:
python webui.py --port 7860
```
Sau đó truy cập địa chỉ `http://localhost:7860` trên trình duyệt. Tại đây bạn có thể:
- Quản lý các dự án dịch thuật (Project-based Workspace).
- Xem tiến độ dịch thời gian thực (SSE Streaming).
- Quản lý Thư viện Prompt và Chỉ dẫn tùy chỉnh cho từng dự án.
- Sử dụng Translation Memory tự động ghi nhớ bản dịch.
- Chạy EPUB Converter và OCR trực tiếp từ giao diện.

### ⌨️ Chế độ Dòng lệnh (CLI)
Dành cho người dùng nâng cao hoặc muốn tự động hóa (Automation).
```bash
python cli.py translate -i input/novel.txt -o output/
```
Các tham số quan trọng:
- `-i`: Đường dẫn file hoặc thư mục đầu vào.
- `-o`: Thư mục chứa kết quả dịch.
- `--model`: Chọn model Gemini (mặc định: gemini-3-flash-preview).
- `--chunk-size`: Kích thước mỗi đoạn dịch (mặc định: 22000 ký tự).

---

## 3. Quản Lý Dự Án (Project Workspace)

Mỗi dự án dịch thuật được tổ chức riêng biệt trong `workspace/projects/<slug>/` với cấu trúc:
```
my-novel/
├── sources/           # File nguồn cần dịch (.txt)
├── translated/        # File đã dịch xong
├── prompt/            # Prompt riêng cho dự án (nếu có)
├── assets/            # Glossary, Style guide, Relationship, Summary
│   └── translation_memory/  # TM riêng dự án
└── project.json       # Metadata dự án
```

---

## 4. Các Tính Năng Nâng Cao

### 📚 Từ điển Thuật ngữ (Glossary)
Để đảm bảo tên nhân vật và chiêu thức nhất quán:
- Đặt file `glossary.txt` vào thư mục `assets/` của dự án.
- Hệ thống sẽ tự động nhúng các thuật ngữ liên quan vào prompt khi dịch.

### 🧠 Bộ nhớ Dịch thuật (Translation Memory)
Hệ thống tự động ghi nhớ các câu đã dịch. Nếu gặp lại câu tương tự ≥85%, hệ thống sẽ gợi ý hoặc tự động áp dụng để tiết kiệm API và đảm bảo tính nhất quán.

### 📚 Thư viện Prompt (Prompt Library)
Tạo và quản lý các bộ prompt mẫu. Mỗi bộ prompt lưu tại `workspace/prompts/<slug>/`. Bộ `default` là mặc định hệ thống, không thể xóa.

### ⚙️ Cấu hình Tối ưu (config/app.ini)
Bạn có thể tinh chỉnh các thông số kỹ thuật:
- `REQUEST_DELAY`: Thời gian nghỉ giữa các lần gọi API (tránh bị block).
- `MAX_REFINEMENT_ATTEMPTS`: Số lần AI tự sửa lỗi nếu phát hiện còn ký tự Trung.
- `CONTEXT_CHAR_COUNT`: Số ký tự đoạn trước được gửi kèm đoạn sau để AI nắm bắt ngữ cảnh.

---

## 5. Các Công Cụ Hỗ Trợ (Utilities)

### 📄 EPUB Converter
Hệ thống tích hợp sẵn bộ chuyển đổi dành cho sách điện tử:
- **EPUB → Text**: Tách nội dung từ file sách để bắt đầu dịch.
- **Text → EPUB**: Đóng gói lại thành file sách hoàn chỉnh sau khi dịch xong, bảo toàn Metadata và cấu trúc chương hồi.

### 🖼️ OCR Engine (Plugin)
Chuyên dùng cho các tài liệu dạng ảnh hoặc PDF quét. OCR Engine có kiến trúc mô-đun lớp (Layered Architecture):
- **Cấu trúc**: Logic được tách bạch thành các module `config`, `image`, `pdf`, `tables`, `formats`, và `ai_processor` trong `plugins/ocr/modules/`.
- **AI Post-Processing**: Tự động làm sạch văn bản (AI Cleanup) và sửa lỗi chính tả (AI Spellcheck) sau khi quét.
- **Tính tương thích**: File `ocr_engine.py` đóng vai trò Facade, đảm bảo các script cũ vẫn hoạt động.

## 5a. Quản lý Plugin (v7.8.0+)

### 🔌 Plugin Management
- **Quản lý Plugin**: Tab **Cấu hình** → cuối trang → khối **Quản lý Plugin**
- **Bật/Tắt**: Tool plugins (eBook Kit, OCR Toolbox) bật/tắt bằng toggle switch
- **Core plugins** (Translation, Spellcheck) mặc định bật, không thể tắt

### 📚 eBook Kit (Workspace Tab)
Khi plugin eBook Kit được bật, workspace hiển thị tab **eBook Kit**:
- **EPUB → Text**: Trích xuất nội dung từ EPUB, hỗ trợ Single/Multi/Both mode
- **Text → EPUB**: Đóng gói lại thành EPUB, giữ cấu trúc chương hồi

### 🖼️ OCR Toolbox (Workspace Tab)
Khi plugin OCR Toolbox được bật, workspace hiển thị tab **OCR Toolbox**:
- Nhận dạng ký tự từ PDF/Ảnh bằng Tesseract + AI Cleanup + Spellcheck
- Hỗ trợ chọn trang PDF, bỏ qua Cleanup/Spellcheck riêng lẻ

---

### 🛠️ Công cụ Biên tập & Soát lỗi (v7.7.0+)
Giao diện Biên tập hợp nhất (Editor + Spellcheck) với sidebar 3 mini-tab:
- **Nội dung nguồn**: File gốc cần dịch hoặc soát lỗi. Row actions: Dịch, Chuyển Markdown (HTML/XHTML), Soát lỗi AI, Đổi tên, Xóa.
- **📝 Tiền xử lý HTML/XHTML → Markdown**: Chuyển đổi file `.html`, `.htm`, `.xhtml` → Markdown sạch bằng nút "Chuyển Markdown".
- **Bản dịch**: File đã dịch xong. Click để xem song song nguồn + bản dịch.
- **Soát chính tả**: File đã AI soát lỗi xong.
- **↩️ Wrap**: Ngắt dòng tự động, không cần cuộn ngang.
- **📊 Diff (So sánh)**: Xem khác biệt giữa nguồn và đích trong modal.
- **🧩 Ghép tập tin (Smart Merge)**: Gộp file đã dịch thành một, dùng Natural Sort.

---

## 6. Quản Lý Chỉ Dẫn (Prompt Management)

### Hai khu vực quản lý prompt riêng biệt

#### A. Thư viện Chỉ dẫn AI (cấp hệ thống)
- Tab **Chỉ dẫn AI** → bên trái danh sách bộ prompt, bên phải editor.
- Bộ `default` là mặc định hệ thống, có thể sửa nội dung nhưng **không thể xóa**.
- **Tạo bộ mới**: Nút "+ Thêm bộ" → modal nhập Tên + Mô tả → tự động tạo thư mục `workspace/prompts/<slug>/` với 5 file prompt rỗng.
- **Editor**: Click bộ prompt → load nội dung vào 5 tab (Dịch thuật, Tóm tắt, Quan hệ, Thuật ngữ, Chính tả). Chỉnh sửa và bấm **Lưu**.
- **Thông tin bộ prompt**: Nút "Thông tin" → modal sửa Tên + Mô tả.
- **Xóa bộ prompt**: Nút "Xóa bộ" → confirm → xóa thư mục (ẩn với bộ `default`).
- Vị trí lưu: `workspace/prompts/<slug>/` (mỗi slug là một thư mục chứa `meta.json` + 5 file `.txt`).

#### B. Chỉ dẫn của Dự án (Project Override)
- Trong workspace dự án, tab **Chỉ dẫn**.
- 5 tab prompt (Dịch thuật, Tóm tắt, Quan hệ, Thuật ngữ, Chính tả) — giao diện tab-style.
- **📥 Nhập từ Thư viện**: Chọn bộ prompt nguồn từ dropdown + tab đang mở → bấm "Nhập Prompt" → nội dung được copy vào textarea (chưa lưu, có dirty flag).
- **💾 Lưu**: Lưu nội dung prompt hiện tại vào `workspace/projects/<slug>/prompt/`. Hệ thống ưu tiên prompt dự án trước; nếu file prompt rỗng → dùng prompt mặc định từ bộ `default`.
- **Cơ chế fallback**: Không cần nút "Reset" hay "Xóa riêng". Chỉ cần lưu textarea trống → file prompt rỗng → hệ thống tự dùng mặc định.

---

## 7. Giải Quyết Sự Cố (Troubleshooting)

- **Lỗi 429 (Rate Limit):** Hệ thống tự động chờ hoặc chuyển API Key nhờ `AdaptiveRateLimiter`.
- **Bản dịch bị cắt dòng:** Kiểm tra `chunk_size` hoặc dùng model mạnh hơn.
- **Lỗi Encoding:** File đầu vào phải UTF-8.
- **Port bị chiếm:** Dùng `python webui.py --port 8080`.

### Lỗi Phân mảnh Module OCR (v6.9.0+)
- Lỗi `ImportError` liên quan `plugins.ocr.modules`: chạy từ thư mục gốc dự án.
- Module báo thiếu thư viện: hệ thống tự động cài qua `lazy_import_and_install`. Nếu thất bại, chạy `pip install <package>`.

---

*Phiên bản tài liệu: 2.5 — Ngày cập nhật: 11/07/2026*
