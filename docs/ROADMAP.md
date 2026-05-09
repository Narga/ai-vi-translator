# RoadMap - Lộ trình phát triển Content Translator

Tài liệu này theo dõi các giai đoạn phát triển của dự án, tập trung vào tính ổn định, trải nghiệm người dùng và sức mạnh AI.

---

## ✅ Giai đoạn 1-5: Hoàn thiện nền tảng (Đã xong)
- [x] Tái cấu trúc WebUI thành Blueprints.
- [x] Tích hợp Multi-Provider AI (Gemini & OpenAI).
- [x] Hệ thống quản lý dự án (Project-based Workspace).
- [x] Tối ưu hóa UI Dashboard với Tachyons Card-style.
- [x] Hệ thống lưu trữ (Archiving System) chuyên nghiệp.

---

## 🚀 Giai đoạn 6: Nâng cao trải nghiệm & Tiện ích (Hiện tại)

### 📊 6.1 Dashboard & Monitoring (v6.1 - DONE)
- [x] Thống kê hệ thống chi tiết (Active/Archived projects, Cache size/count).
- [x] Hover tooltips mô tả các chỉ số.
- [x] Cải thiện tốc độ render bảng file lớn.

### 🏗️ 6.5 Refactoring & Assets (v6.5 - DONE)
- [x] Hệ thống 7-Tab UI (Nguồn, Dịch, Chỉ dẫn, Mối quan hệ, Thuật ngữ, Prompt, Tóm tắt).
- [x] Di chuyển dữ liệu vào thư mục `assets/` từng dự án.
- [x] Tinh gọn hệ thống Prompt (1 prompt chính cho dự án).

### ⚙️ 6.6 - 6.8 UI/UX Polish & AI Resilience (v6.8 - DONE)
- [x] **Consolidated Project Modal**: Quản lý thông tin dự án tập trung qua modal.
- [x] **Scroll Fix**: Sửa lỗi layout cuộn ở Workspace & Translated tabs.
- [x] **API Resilience Overhaul**: Tái cấu trúc bộ xử lý lỗi API (Retry, Backoff, Cooldown).
- [x] **Multi-Prompt System**: Quản lý riêng biệt 5 loại prompt cho dự án.
- [x] **Real-time Progress Logs**: Đẩy log hệ thống trực tiếp lên UI modal.
- [x] **UI Polish**: Chuẩn hóa icon, căn chỉnh nút và tối ưu khối thông tin.

### 🛡️ 6.9 Remediation & Modularization (v6.9.3 - DONE)
- [x] **Security Hardening**: Vá lỗ hổng Path Traversal và bảo mật Host binding.
- [x] **Monolith Decomposition**: Phân rã `ocr_engine.py` (7.7k lines) thành kiến trúc module lớp.
- [x] **Cache Modernization**: Loại bỏ `pickle`, chuyển sang `JSON Gzip` an toàn.
- [x] **Core Refactoring**: Loại bỏ mã nguồn trùng lặp và fix hàng loạt bare excepts.
- [x] **UI/UX Remediation**: Sửa lỗi HTML, hệ thống 5-Tab, Persistence và Smart Merge.
- [ ] **Frontend Modularization**: Tách `main.js` (3k lines) thành các ES modules chuyên biệt.
- [ ] **Unit Testing Foundation**: Xây dựng bộ khung test cho core logic (Chunker, Cache).

### 💾 7.0 High-Fidelity Pipeline & Advanced AI (Next)
*Xem chi tiết tại [report-2026.05.09.md](file:///Users/narga/Briefcase/Projects/Novel-Translator/docs/report-2026.05.09.md)*
- [ ] **HTML <template> Refactor**: Đồng bộ hóa logic render bằng HTML templates.
- [ ] **EPUB/HTML Fidelity Pipeline**: Dịch bảo toàn cấu trúc DOM, ảnh và CSS cho EPUB/HTML.
- [ ] **Progressive Batch Translation**: Hỗ trợ hàng đợi dịch nhiều file với thanh tiến độ tổng thể.
- [ ] **Interactive Glossary**: Highlight thuật ngữ glossary trong Editor và cho phép áp dụng nhanh.
- [ ] **Prompt Versioning**: Lưu lịch sử các phiên bản prompt của dự án.

---

## 🧠 Giai đoạn 7: Trí tuệ nhân tạo chuyên sâu (Future)

### 🧪 7.1 Local LLM Integration
- [ ] Hỗ trợ kết nối Ollama/LocalAI cho nhu cầu dịch thuật offline.

### 🤖 7.2 Agentic Post-Editing
- [ ] AI tự động rà soát bản dịch sau khi hoàn tất để fix các lỗi xưng hô hoặc lặp từ.
- [ ] "Character Memory": AI ghi nhớ sâu bối cảnh nhân vật để nhất quán xưng hô theo giới tính/địa vị.

### 🌐 7.3 Multi-Language Expansion
- [ ] Hỗ trợ các cặp ngôn ngữ khác ngoài Trung-Việt (Anh-Việt, Nhật-Việt) với bộ prompt tối ưu riêng.

---
*Cập nhật lần cuối: 2026-05-06*
