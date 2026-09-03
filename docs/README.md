# HỆ THỐNG TÀI LIỆU DỰ ÁN: CONTENT TRANSLATOR (NEXT-GEN)
> **Thư mục tài liệu**: `docs/` trong dự án `content-translator`  
> **Phiên bản**: v2.2 (Sẵn sàng triển khai 100%)  
> **Tôn chỉ tối thượng**: **Minimalist — Single-User — Hiệu Quả — Nhanh — UI Siêu Nhẹ & Thực Dụng**  
> **Bản chất**: **"Đây là công cụ gửi nội dung cho AI và nhận bản dịch về, phục vụ duy nhất một người dùng."**

---

## ⚡ HƯỚNG DẪN NHANH: CẤU HÌNH & API KEY NHẬP VÀO ĐÂU?

1. **API Key (Gemini)**:
   * Nhập vào file: `config/keys.json` (File tự tạo mẫu khi chạy lần đầu, đã nằm trong `.gitignore`).
     ```json
     {
       "gemini_keys": ["AIzaSyD-KEY_1", "AIzaSyD-KEY_2"]
     }
     ```
   * Hoặc khai báo biến môi trường: `export GEMINI_API_KEYS="AIzaSy_1,AIzaSy_2"`.
   * Hoặc nếu chưa có, CLI sẽ hỏi trực tiếp khi chạy và tự động lưu.
2. **Cấu hình chung**: File `config/config.json` (Model: `gemini-2.5-flash`, `max_chunk_chars: 16000`, `timeout_seconds: 90`).
3. **Nội dung cần dịch**:
   * Dịch trực tiếp: `python run.py input.txt output.txt`.
   * Dịch theo dự án: Đặt file vào `workspace/projects/{ten_du_an}/sources/` và chạy `python run.py --project {ten_du_an} --file {ten_file}`.
   * Toàn bộ thư mục `workspace/` đã được đưa vào `.gitignore` để bảo đảm riêng tư tuyệt đối cho nội dung sách.

---

## 📚 BẢN ĐỒ TÀI LIỆU TOÀN DIỆN (DOCUMENTATION SITEMAP)

| Tập tin | Tên tài liệu | Nội dung chính |
| :--- | :--- | :--- |
| **[00]** | [`00_PROJECT_MANIFESTO.md`](00_PROJECT_MANIFESTO.md) | **Tôn Chỉ & Bản Tuyên Ngôn Dự Án**: 5 nguyên tắc bất biến, phân định lõi bắt buộc vs mở rộng, nguyên tắc thất bại (dừng ngay không checkpoint, chạy lại từ đầu), cam kết định dạng thực tế và Litmus Test. |
| **[01]** | [`01_SILABOOK_ANALYSIS_AND_ENHANCEMENTS.md`](01_SILABOOK_ANALYSIS_AND_ENHANCEMENTS.md) | **Phân Tích silaBook & Chắt Lọc Giải Thuật**: Nghiên cứu sâu thuật toán cắt thông minh `smartHardSplit` dải 20-80% ưu tiên `\n\n` để bảo toàn ranh giới tự nhiên. |
| **[02]** | [`02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md`](02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md) | **Đặc Tả Hệ Thống & Chỉ Dẫn Cấu Hình**: Hướng dẫn nhập cấu hình/API key, định vị `PROJECT_ROOT` độc lập CWD, kiểm tra an toàn đường dẫn `relative_to()`, quy ước ghép chunk `\n\n`, cơ chế xoay key đơn giản. |
| **[03]** | [`03_PHASE_1_DETAILED_ACTION_PLAN.md`](03_PHASE_1_DETAILED_ACTION_PLAN.md) | **Kế Hoạch Thực Thi Phase 1 Chi Tiết (CLI Working Core)**: Đầy đủ mã nguồn mẫu cho toàn bộ 8 file, bộ test đầy đủ (kèm mock test `ai_client.py`), chia thành 4 mốc triển khai nhỏ (Milestone 1 $\to$ 4). **Chỉ dùng `httpx`, không cần FastAPI/pydantic!** |
| **[04]** | [`04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md`](04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md) | **Kế Hoạch Phase 2 (WebUI Lean & Phản Hồi Nhanh)**: Giao diện React SPA đa trang với Sidebar thu gọn, phục vụ 1 phiên in-flight, thao tác prompt/chunk/copy/lưu/gửi lại tức thì; cùng lộ trình Phase 3 (OpenAI-compatible, Assets riêng), Phase 4 (EPUB), Phase 5 (Đóng gói). |
| **[05]** | [`05_STANDALONE_PLUGINS_AND_TOOLS_GUIDE.md`](05_STANDALONE_PLUGINS_AND_TOOLS_GUIDE.md) | **Chỉ Dẫn Công Cụ Độc Lập**: Công cụ EPUB (chỉ nhận text/md/html, convert 2 chiều) và trích xuất thuật ngữ vào `assets/glossary.txt`. |
| **[06]** | [`ROADMAP.md`](ROADMAP.md) | **Lộ Trình Tương Lai & So Sánh Checkpoint**: Phân tích so sánh tại sao bỏ Checkpoint ở Phase 1 & 2 và khi nào cần; kế hoạch khai thác SQLite cho FTS5 full-text search; tìm kiếm & thay thế hàng loạt, so sánh diff. |
