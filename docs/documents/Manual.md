# 📖 Hướng Dẫn Sử Dụng Novel Translator

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
3. Cấu hình API: Tạo file `config/API.txt` và dán các API Keys vào (mỗi key một dòng).

---

## 2. Các Chế Độ Sử Dụng

### 🖥️ Chế độ Giao diện Web (WebUI)
Đây là cách dễ nhất để sử dụng cho người dùng cuối.
```bash
python webui.py
```
Sau đó truy cập địa chỉ `http://localhost:5000` trên trình duyệt. Tại đây bạn có thể:
- Quản lý các dự án dịch thuật (Project-based).
- Xem tiến độ dịch thời gian thực (SSE Streaming).
- Chỉnh sửa Prompt cho từng thể loại truyện.
- Tải file kết quả trực tiếp.

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

## 3. Các Tính Năng Nâng Cao

### 📚 Từ điển Thuật ngữ (Glossary)
Để đảm bảo tên nhân vật và chiêu thức nhất quán:
- Đặt file `glossary.csv` vào thư mục dự án.
- Hệ thống sẽ tự động ưu tiên các từ này trong bản dịch.

### 🧠 Bộ nhớ Dịch thuật (Translation Memory)
Hệ thống tự động ghi nhớ các câu đã dịch. Nếu gặp lại câu tương tự >85%, hệ thống sẽ gợi ý hoặc tự động áp dụng để tiết kiệm API Key và đảm bảo tính nhất quán.

### ⚙️ Cấu hình Tối ưu (config/app.ini)
Bạn có thể tinh chỉnh các thông số kỹ thuật:
- `REQUEST_DELAY`: Thời gian nghỉ giữa các lần gọi API (tránh bị block).
- `MAX_REFINEMENT_ATTEMPTS`: Số lần AI tự sửa lỗi nếu phát hiện còn ký tự Trung.
- `CONTEXT_CHAR_COUNT`: Số ký tự đoạn trước được gửi kèm đoạn sau để AI nắm bắt ngữ cảnh.

---

## 4. Các Công Cụ Hỗ Trợ (Utilities)

### 📄 EPUB Converter
Hệ thống tích hợp sẵn bộ chuyển đổi dành cho sách điện tử:
- **EPUB → Text**: Tách nội dung từ file sách để bắt đầu dịch.
- **Text → EPUB**: Đóng gói lại thành file sách hoàn chỉnh sau khi dịch xong, bảo toàn Metadata và cấu trúc chương hồi.

### 🖼️ OCR Engine (Plugin)
Chuyên dùng cho các tài liệu dạng ảnh hoặc PDF quét:
- Nhận diện đa ngôn ngữ (Trung, Nhật, Hàn, Việt).
- Tích hợp AI để làm sạch văn bản sau khi quét (AI Cleanup).

---

## 5. Giải Quyết Sự Cố (Troubleshooting)

- **Lỗi 429 (Rate Limit):** Đừng lo lắng, hệ thống sẽ tự động chờ hoặc chuyển sang API Key khác.
- **Bản dịch bị cắt dòng:** Kiểm tra lại tham số `chunk_size` hoặc dùng model mạnh hơn như `gemini-1.5-pro`.
- **Lỗi Encoding:** Luôn đảm bảo file đầu vào định dạng UTF-8.

---
*Phiên bản tài liệu: 1.0.0 - Ngày cập nhật: 01/03/2026*
