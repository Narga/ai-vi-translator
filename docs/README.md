# HỆ THỐNG TÀI LIỆU DỰ ÁN: CONTENT TRANSLATOR (NEXT-GEN)
> **Thư mục tài liệu**: `docs/` trong dự án `content-translator`  
> **Phiên bản**: v2.3 (Chốt triển khai: app.db từ Phase 1 + đa provider explicit + API contract Phase 2)  
> **Tôn chỉ tối thượng**: **Minimalist — Single-User — Hiệu Quả — Nhanh — UI Siêu Nhẹ & Thực Dụng**  
> **Bản chất**: **"Đây là công cụ gửi nội dung cho AI và nhận bản dịch về, phục vụ duy nhất một người dùng."**

---

## ⚡ HƯỚNG DẪN NHANH: CẤU HÌNH & API KEY NHẬP VÀO ĐÂU?

1. **API Key (Gemini + OpenAI-compatible)**:
   * Nhập vào file: `config/keys.json` (File tự tạo mẫu khi chạy lần đầu, đã nằm trong `.gitignore`).
     ```json
     {
       "gemini_keys": ["AIzaSyD-KEY_1"],
       "openai_compat_keys": ["sk-or-KEY_1"]
     }
     ```
   * Hoặc khai báo biến môi trường: `export GEMINI_API_KEYS="AIzaSy_1,AIzaSy_2"` và `export OPENAI_COMPAT_KEYS="sk-or-KEY_1"` (export trực tiếp, không tự load file `.env`).
   * Hoặc nếu chưa có, CLI sẽ hỏi trực tiếp khi chạy và tự động lưu.
2. **Cấu hình chung**: File `config/config.json` (`default_provider/default_model`, danh sách `providers.*.models`, `max_chunk_chars: 16000`, `timeout_seconds: 90`). Mọi lượt gọi chọn explicit `--provider/--model`, không fallback ngầm.
3. **Database**: `workspace/app.db` (SQLite stdlib) tự tạo từ Phase 1, chỉ index `projects/files/runs`, không checkpoint.
4. **Nội dung cần dịch**:
   * Dịch trực tiếp: `python run.py input.txt output.txt --provider gemini --model gemini-2.5-flash`.
   * Dịch theo dự án: Đặt file vào `workspace/projects/{ten_du_an}/sources/` và chạy `python run.py --project {ten_du_an} --file {ten_file} --provider openai_compat --model deepseek-chat`.
   * Toàn bộ thư mục `workspace/` đã được đưa vào `.gitignore` để bảo đảm riêng tư tuyệt đối cho nội dung sách.

---

## 📚 BẢN ĐỒ TÀI LIỆU TOÀN DIỆN (DOCUMENTATION SITEMAP)

| Tập tin | Tên tài liệu | Nội dung chính |
| :--- | :--- | :--- |
| **[00]** | [`00_PROJECT_MANIFESTO.md`](00_PROJECT_MANIFESTO.md) | **Tôn Chỉ & Bản Tuyên Ngôn Dự Án v2.3**: 5 nguyên tắc + nguyên tắc provider explicit/model từ danh sách/không fallback, app.db từ Phase 1, mở rộng bằng quy ước (không framework plugin), OCR loại bỏ, Litmus Test. |
| **[01]** | [`01_SILABOOK_ANALYSIS_AND_ENHANCEMENTS.md`](01_SILABOOK_ANALYSIS_AND_ENHANCEMENTS.md) | **Tham khảo non-normative**: giữ 4 giải thuật hay (`smartHardSplit` 20-80%, lọc thuật ngữ, handoff, sidebar thu gọn). Bảng định hướng FastAPI/8 trang đã bị v2.3 thay thế. |
| **[02]** | [`02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md`](02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md) | **Đặc Tả Hệ Thống v2.3**: config đa provider + danh sách models, 2 nhóm key, `PROJECT_ROOT` độc lập CWD, `relative_to()`, ghép chunk `\n\n`, xoay key chung, schema `app.db`. |
| **[03]** | [`03_PHASE_1_DETAILED_ACTION_PLAN.md`](03_PHASE_1_DETAILED_ACTION_PLAN.md) | **Kế Hoạch Phase 1 v2.3 (CLI + Gemini + OpenAI-compat + app.db)**: mã mẫu đầy đủ (`ai_base/openai_client/app_db`), test cả 2 providers + `test_prompt_engine`/`test_app_db` bổ sung, 5 milestones. **Chỉ `httpx` + stdlib!** |
| **[04]** | [`04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md`](04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md) | **Kế Hoạch Phase 2 v2.3 (WebUI stdlib + API contract 12 endpoint + SSE)**: 4 trang, sidebar thu gọn, 1 phiên in-flight, chọn provider/model explicit; Phase 3+ (assets/glossary, search/replace, diff), Phase 4 (EPUB), Phase 5 (đóng gói). |
| **[05]** | [`05_STANDALONE_PLUGINS_AND_TOOLS_GUIDE.md`](05_STANDALONE_PLUGINS_AND_TOOLS_GUIDE.md) | **Công cụ độc lập + đánh giá plugin v2.3**: EPUB 2.0 tối giản, OCR loại bỏ, glossary chuẩn `assets/glossary.txt`, mở rộng bằng quy ước file. |
| **[06]** | [`ROADMAP.md`](ROADMAP.md) | **Lộ Trình v2.3**: app.db đã có từ Phase 1 (thêm FTS5/checkpoint sau), search/replace + diff (Phase 3), EPUB + handoff (Phase 4), OCR tạm hoãn §6, chốt không fallback model. |
