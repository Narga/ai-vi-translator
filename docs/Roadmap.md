# 🗺️ Lộ Trình Phát Triển & Theo Dõi Tiến Độ (Project Roadmap)

Tài liệu này tổng hợp toàn bộ lịch sử phát triển, các tác vụ đang thực hiện và kế hoạch tương lai của dự án Novel Translator.

---

## 🟢 ĐÃ HOÀN THÀNH (COMPLETED - v4.0.0 -> v4.1.0)

### 🏗️ Lõi & SDK
- [x] Chuyển đổi sang SDK `google-genai` mới (v4.0.0).
- [x] Hỗ trợ model `gemini-3-flash-preview` và tham số `thinking_level`.
- [x] Cơ chế **Circuit Breaker** và **Emergency Stop** (v4.0.0).
- [x] Quản lý API Key đa lớp (Global RPM, Token Budget Limiter) (v4.0.1).
- [x] Hỗ trợ Async (AsyncGenAIClient) (v4.0.1).
- [x] Tối ưu hóa Cache với Gzip (`.pkl.gz`) (v4.0.2).

### 🖥️ Giao diện & Tính năng WebUI
- [x] Khởi tạo WebUI bằng Flask & SSE Streaming (v4.0.3).
- [x] Trình chỉnh sửa Prompt trực tiếp trên giao diện (v4.0.4).
- [x] Chế độ dịch Batch (Dịch hàng loạt) nhiều file (v4.0.5).
- [x] Tự động detect các model khả dụng từ Google (v4.0.5).
- [x] **Translation Memory (TM)**: Fuzzy matching 85% để tái sử dụng bản dịch (v4.0.6).
- [x] Redesign giao diện với PicoCSS, phân tách pending/done tabs (v4.0.7).
- [x] Module hóa static files (CSS/JS) (v4.1.0).

---

## ⚡ GIAI ĐOẠN HIỆN TẠI (ACTIVE: v5.0.0 Alpha)
**Mục tiêu:** Cải tổ kiến trúc, nâng cấp thuật toán xử lý câu và SQLite Checkpoint.

### 📅 GIAI ĐOẠN 1: Tái Cấu Trúc "Xương Sống" (Bắt đầu)
- [x] **1.1 Module hóa WebUI**: Tách `webui.py` sang cấu trúc gói `webui/`.
- [x] **1.2 Refactor Pipeline**: Loại bỏ ServiceBus/EventBus cũ, chuyển sang Functional Pipeline.
- [x] **1.3 Smart Chunker**: Triển khai thuật toán Sentence Aggregation (Cắt theo câu).

### 📅 GIAI ĐOẠN 2: Quản Lý Dữ Liệu & Từ Điển
- [x] **2.1 SQLite Checkpoint**: Chuyển đổi quản lý trạng thái dự án sang DB bền vững.
- [x] **2.2 Dynamic Glossary**: Tự động nhúng Glossary dựa trên nội dung chunk.

### 📅 GIAI ĐOẠN 3: Biên Tập & Xuất Bản
- [x] **3.1 Side-by-Side Editor**: Giao diện soát lỗi song ngữ.
- [ ] **3.2 Professional Docs**: Hoàn thiện Manual.md và Development.md (Đang thực hiện).

---

## 🔵 KẾ HOẠCH TƯƠNG LAI (UPCOMING)

### Ưu tiên cao
- [ ] **Async Batch Parallel**: Xử lý nhiều file song song thực thụ qua asyncio.
- [ ] **Advanced CLI**: Bổ sung lệnh `check-keys`, `manage-tm`, `stats-export`.
- [ ] **Quality Metrics**: Tích hợp các chỉ số đánh giá bản dịch (BLEU, COMET hoặc LLM-as-a-judge).

### Ưu tiên trung bình
- [ ] **PDF/EPUB Export Plugin**: Xuất bản kết quả dịch thẳng sang định dạng sách điện tử.
- [ ] **Auto-detection**: Tự động nhận diện ngôn ngữ nguồn đầu vào (CN/JP/KR/EN).
- [ ] **Docker Support**: Đóng gói container để dễ dàng triển khai trên VPS.

---

## 🟡 TẠM HOÃN (DEFERRED / PENDING)
*Các tác vụ này sẽ được thực hiện khi có nhu cầu đặc biệt hoặc tìm được giải pháp kỹ thuật tối ưu.*
- [ ] **Plugin Marketplace**: Hệ thống cho phép bên thứ 3 tự viết plugin (Tạm hoãn do kiến trúc v5.0 đang đơn giản hóa).
- [ ] **Mobile App**: Giao diện mobile native (Ưu tiên dùng Responsive Web trước).
- [ ] **Collaborative Translation**: Dịch thuật cộng đồng (Nhiều người Review 1 lúc).

---

## 🛠️ NỢ KỸ THUẬT & CÁC VẤN ĐỀ ĐANG THEO DÕI (TECH DEBT)

### Chất lượng mã nguồn
- [ ] Bổ sung Docstrings đầy đủ cho toàn bộ class/method trong v5.0.
- [ ] Viết Unit Tests bao phủ tối thiểu 70% các module core/services.
- [ ] Chuẩn hóa Error Handling: Tránh `except Exception: pass`.

### Hiệu năng & Ổn định
- [ ] Theo dõi rò rỉ bộ nhớ khi xử lý file cực lớn (>100MB).
- [ ] Cơ chế tự động dọn dẹp Cache cũ (Auto-cleanup logs/cache).
- [ ] Giảm độ phức tạp Cyclomatic của các hàm Worker trong WebUI.

---
**Lưu ý:** Tài liệu này được cập nhật sau mỗi buổi làm việc để phản ánh đúng thực tế dự án.
