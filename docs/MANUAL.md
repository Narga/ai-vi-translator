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
- Chỉnh sửa Prompt cho từng thể loại truyện (Genre-based Prompt Sets).
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
├── prompt/            # Prompt riêng cho dự án
├── profile/           # Glossary, Characters, Style guide
│   └── translation_memory/  # TM riêng dự án
└── project.json       # Metadata dự án
```

---

## 4. Các Tính Năng Nâng Cao

### 📚 Từ điển Thuật ngữ (Glossary)
Để đảm bảo tên nhân vật và chiêu thức nhất quán:
- Đặt file `glossary.txt` vào thư mục `profile/` của dự án.
- Hệ thống sẽ tự động nhúng các thuật ngữ liên quan vào prompt khi dịch.

### 🧠 Bộ nhớ Dịch thuật (Translation Memory)
Hệ thống tự động ghi nhớ các câu đã dịch. Nếu gặp lại câu tương tự ≥85%, hệ thống sẽ gợi ý hoặc tự động áp dụng để tiết kiệm API và đảm bảo tính nhất quán.

### 🎭 Prompt theo Thể loại (Genre-based Prompt Sets)
Tạo các bộ prompt riêng cho từng thể loại truyện (Tiên hiệp, Đô thị, Ngôn tình...) và chuyển đổi linh hoạt.

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
Chuyên dùng cho các tài liệu dạng ảnh hoặc PDF quét. Kể từ phiên bản 6.9.0, OCR Engine được tái cấu trúc thành kiến trúc mô-đun lớp (Layered Architecture):
- **Cấu trúc mới**: Logic được tách bạch thành các module `config`, `image`, `pdf`, `tables`, `formats`, và `ai_processor` trong thư mục `plugins/ocr/modules/`.
- **Nhận diện nâng cao**: Tích hợp các công cụ mạnh mẽ như `pytesseract`, `ocrmypdf`, `pdfplumber` và `PyMuPDF`.
- **AI Post-Processing**: Tự động làm sạch văn bản (AI Cleanup) và sửa lỗi chính tả (AI Spellcheck) sau khi quét để đạt độ chính xác cao nhất.
- **Tính tương thích**: File `ocr_engine.py` đóng vai trò là "Cửa ngõ" (Facade), đảm bảo các script cũ vẫn hoạt động bình thường.

### 💾 Hệ thống Cache JSON
Hệ thống sử dụng cơ chế lưu trữ Cache hiện đại:
- **Định dạng an toàn**: Toàn bộ dữ liệu được lưu dưới dạng `JSON` nén (Gzip) thay vì `pickle` cũ, giúp ngăn chặn các rủi ro bảo mật và dễ dàng kiểm tra nội dung.
- **Tự động hóa**: Cache được tự động nén để tiết kiệm dung lượng đĩa cứng. Bạn có thể xóa Cache thông qua tab Cấu hình trên WebUI.

## 5a. Quản lý Plugin (v7.8.0+)

### 🔌 Plugin Management
Từ v7.8.0, thẻ **Công cụ** trên main navigation đã được thay thế bằng hệ thống plugin tích hợp:

- **Quản lý Plugin**: Vào tab **Cấu hình** → cuối trang → khối **Quản lý Plugin**
- **Danh sách plugin**: Hiển thị tất cả plugin (Core + Tool) kèm tên, mô tả, phiên bản, tác giả
- **Bật/Tắt**: Tool plugins (eBook Kit, OCR Toolbox) có thể bật/tắt bằng toggle switch
- **Core plugins** (Translation, Spellcheck) mặc định bật, không thể tắt

### 📚 eBook Kit (Workspace Tab)
Khi plugin eBook Kit được bật, workspace project hiển thị tab **eBook Kit**:
- **EPUB → Text**: Trích xuất nội dung từ file EPUB, hỗ trợ Single/Multi/Both mode, xuất TXT hoặc Markdown
- **Text → EPUB**: Đóng gói lại thành EPUB, giữ cấu trúc chương hồi, hỗ trợ Markdown nguồn

### 🖼️ OCR Toolbox (Workspace Tab)
Khi plugin OCR Toolbox được bật, workspace project hiển thị tab **OCR Toolbox**:
- Nhận dạng ký tự từ PDF/Ảnh bằng Tesseract + AI Cleanup + Spellcheck
- Chế độ xử lý: Đầy đủ (OCR+Cleanup+Spell), Chỉ Cleanup, Chỉ Spell Check
- Hỗ trợ chọn trang PDF, bỏ qua Cleanup/Spellcheck riêng lẻ

---

### 🛠️ Công cụ Biên tập & Soát lỗi (v7.7.0+)
Giao diện Biên tập hợp nhất (Editor + Spellcheck) với sidebar 3 mini-tab:
- **Nội dung nguồn**: File gốc cần dịch hoặc soát lỗi. Click file để mở editor 2 cột (Nguồn + Bản dịch). Row actions: Dịch, Chuyển Markdown (đối với HTML/XHTML), Soát lỗi AI, Đổi tên, Xóa.
- **📝 Tiền xử lý HTML/XHTML → Markdown**: Hỗ trợ chuyển đổi các tệp `.html`, `.htm`, và `.xhtml` sang định dạng Markdown sạch (`.md`) ngoại tuyến trực tiếp ngay trên WebUI (bằng nút "Chuyển Markdown" trên toolbar chính hoặc mini-toolbar của từng tệp). Quá trình này dùng BeautifulSoup/html2text để bóc tách thẻ `<body>`, dọn dẹp CSS/script/style rác, chuyển `<ruby>` sang `漢字《かな》`, giữ nguyên `<u>` và inlining reference links.
- **Bản dịch**: File đã dịch xong. Click file để xem song song nguồn và bản dịch.
- **Soát chính tả**: File đã được AI soát lỗi xong (chỉ hiển thị output, không hiển thị file nguồn chưa soát).
- **Tự động clear selection**: Khi chuyển mini-tab, mọi lựa chọn đều được xoá để tránh thao tác nhầm.
- **Toolbar icons**: Upload, Chia nhỏ, Chuyển Markdown, Dịch đã chọn, Soát lỗi đã chọn, Ghép tập tin, Xóa đã chọn — hiển thị tuỳ theo mini-tab.
- **↩️ Wrap (Ngắt dòng)**: Tự động xuống dòng văn bản để hiển thị vừa vặn trong khung soạn thảo mà không cần cuộn ngang. Hữu ích khi làm việc với các đoạn văn dài.
- **📊 Diff (So sánh)**: Hiển thị sự khác biệt giữa nội dung nguồn và nội dung đích trong một cửa sổ modal chuyên biệt, giúp bạn dễ dàng đối soát các thay đổi hoặc lỗi mất đoạn.
- **🧩 Ghép tập tin (Smart Merge)**: 
    - Cho phép gộp tất cả các file đã dịch lẻ tẻ thành một tập tin duy nhất (thường dùng để xuất bản chương/truyện hoàn chỉnh).
    - **Logic sắp xếp**: Hệ thống sử dụng thuật toán **Natural Sort** (sắp xếp tự nhiên), đảm bảo thứ tự "Chương 2" luôn nằm trước "Chương 10", thay vì sắp xếp theo kiểu chữ cái truyền thống.

---

## 6. Quản Lý Chỉ Dẫn (Prompt Management)

Kể từ phiên bản 6.7.0, hệ thống hỗ trợ cơ chế biệt lập chỉ dẫn (Prompt) cực kỳ mạnh mẽ cho từng dự án:

### Phân loại Trạng thái
- **📌 Chỉ dẫn Hệ thống (Mặc định)**: Dự án sử dụng chung bộ luật lệ mặc định của hệ thống. Bất kỳ thay đổi nào tại đây (nếu lưu vào hệ thống) sẽ ảnh hưởng đến các dự án mới khác.
- **✏️ Chỉ dẫn Dự án (Tùy chỉnh)**: Dự án có một bản sao prompt riêng nằm trong thư mục `prompt/` của dự án đó. Bạn có thể tự do chỉnh sửa prompt dịch thuật, tóm tắt... cho dự án này mà không sợ ảnh hưởng đến dự án khác hay cài đặt chung của hệ thống.

### Các thao tác Quản lý
1. **💾 Lưu chỉ dẫn dự án**: Khi bạn chỉnh sửa nội dung prompt và nhấn nút này, hệ thống sẽ tự động tạo một bản sao riêng cho dự án và lưu lại. Trạng thái sẽ chuyển từ "Hệ thống" sang "Dự án".
2. **📥 Áp dụng vào dự án (Import)**: Chọn một thể loại truyện từ Thư viện (ví dụ: Tiên Hiệp) và nhấn nút này. Toàn bộ các prompt mẫu tối ưu cho thể loại đó sẽ được chép vào dự án của bạn.
3. **🗑️ Xóa chỉ dẫn riêng (Reset)**: Nếu bạn muốn dự án quay về sử dụng các quy tắc mặc định ban đầu, hãy nhấn nút này. Hệ thống sẽ xóa bản sao riêng và khôi phục trạng thái "Hệ thống".

---

## 7. Giải Quyết Sự Cố (Troubleshooting)

- **Lỗi 429 (Rate Limit):** Đừng lo lắng, hệ thống sẽ tự động chờ hoặc chuyển sang API Key khác nhờ cơ chế `AdaptiveRateLimiter`.
- **Bản dịch bị cắt dòng:** Kiểm tra lại tham số `chunk_size` hoặc dùng model mạnh hơn.
- **Lỗi Encoding:** Luôn đảm bảo file đầu vào định dạng UTF-8.
- **Port bị chiếm:** Dùng `python webui.py --port 8080` để đổi port.

---
### Lỗi Phân mảnh Module OCR (v6.9.0+)
- Nếu gặp lỗi `ImportError` liên quan đến `plugins.ocr.modules`, hãy đảm bảo bạn đang chạy ứng dụng từ thư mục gốc của dự án.
- **Xử lý Dependency**: Nếu một module báo thiếu thư viện (ví dụ: `pdfplumber`), hệ thống sẽ cố gắng tự động cài đặt qua `lazy_import_and_install`. Nếu thất bại, hãy chạy `pip install pdfplumber`.

---
*Phiên bản tài liệu: 2.4 - Ngày cập nhật: 16/06/2026*
