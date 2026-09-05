# HỆ THỐNG TÀI LIỆU DỰ ÁN: CONTENT TRANSLATOR (NEXT-GEN)
> **Thư mục tài liệu**: `docs/` trong dự án `content-translator`  
> **Phiên bản**: v3.0.0 (05/09/2026) — chuẩn sống: 00, 02, 04, 06, 10, 12, 16, ROADMAP, README, CHANGELOG  
> **Tôn chỉ tối thượng**: **Minimalist — Single-User — Hiệu Quả — Nhanh — UI Siêu Nhẹ & Thực Dụng**  
> **Bản chất**: **"Đây là công cụ gửi nội dung cho AI và nhận bản dịch về, phục vụ duy nhất một người dùng."**

---

## ⚡ HƯỚNG DẪN NHANH: CẤU HÌNH & API KEY NHẬP VÀO ĐÂU?

1. **API Key (Gemini + OpenAI-compatible)**:
   * Nhập trên WebUI trang Cấu Hình — keys hiện **đầy đủ**, sửa trực tiếp trong danh sách (xóa dòng = xóa key); không mask, không fingerprint (manifesto §7).
     ```json
     {"version": 1, "active_id": "gemini-default", "providers": [
       {"id": "gemini-default", "type": "gemini", "api_keys": ["AIzaSyD-KEY_1"], "default_model": ""}
     ]}
     ```
   * Hoặc sửa trực tiếp `config/providers.json` (đã gitignore), hoặc CLI hỏi khi thiếu.
   * `config/keys.json` cũ (`gemini_keys`/`openai_compat_keys`) chỉ còn giá trị migration 1 chiều.
2. **Cấu hình chung**: File `config/config.json` (`max_chunk_chars: 16000`, `api_delay_seconds`, `timeout_seconds`, `default_prompt`). Mọi lượt gọi chọn explicit provider/model, không fallback ngầm.
3. **Database**: `workspace/app.db` (SQLite stdlib) — 3 bảng `projects/files/runs` (+ cột `author`, `description` tự migrate), chỉ index + log, không checkpoint.
4. **Nội dung cần dịch**:
   * WebUI: `python main.py` → http://127.0.0.1:8000 (nhớ restart server sau khi pull code — nút ↻ cuối sidebar).
   * CLI: `python run.py input.txt output.txt` hoặc `python run.py --project {ten} --file {ten_file} --provider ... --model ...`.
   * File dự án nằm ở `workspace/projects/{slug}/sources/` (vào) và `results/` (ra).
   * Toàn bộ thư mục `workspace/` đã được đưa vào `.gitignore` để bảo đảm riêng tư tuyệt đối cho nội dung sách.

---

## 📚 BẢN ĐỒ TÀI LIỆU TOÀN DIỆN (DOCUMENTATION SITEMAP)

| Tập tin | Tên tài liệu | Nội dung chính |
| :--- | :--- | :--- |
| **[00]** | [`00_PROJECT_MANIFESTO.md`](00_PROJECT_MANIFESTO.md) | **Tôn Chỉ & Bản Tuyên Ngôn (sống, v2.5)**: READ-FIRST, single-user local, security chống-public, contract runtime SSOT (prefs + providers + error model), chính sách lib local §9. |
| **[01]** | [`01_SILABOOK_ANALYSIS_AND_ENHANCEMENTS.md`](01_SILABOOK_ANALYSIS_AND_ENHANCEMENTS.md) | **Tham khảo non-normative**: giữ 4 giải thuật hay (`smartHardSplit` 20-80%, lọc thuật ngữ, handoff, sidebar thu gọn). Bảng định hướng FastAPI/8 trang đã bị thay thế. |
| **[02]** | [`02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md`](02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md) | **Đặc Tả Hệ Thống (sống, v3.0.0)**: providers.json SSOT, prefs (+`default_prompt`), `guard_name` sanitize, chunk/error taxonomy, schema `app.db` (+cột meta). |
| **[03]** | [`03_PHASE_1_DETAILED_ACTION_PLAN.md`](03_PHASE_1_DETAILED_ACTION_PLAN.md) | **Lịch sử**: Kế hoạch Phase 1 (CLI + Gemini + OpenAI-compat + app.db). **Chỉ `httpx` + stdlib!** |
| **[04]** | [`04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md`](04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md) | **Đặc tả UI + API contract hiện hành (v3.0.0)**: 4 trang thực tế, bảng 38 endpoint, SSE, nghiệm thu theo hành vi mới. |
| **[05]** | [`05_STANDALONE_PLUGINS_AND_TOOLS_GUIDE.md`](05_STANDALONE_PLUGINS_AND_TOOLS_GUIDE.md) | **Đặc tả chờ làm**: code mẫu EPUB/converter/entity-extractor (chưa có `tools/`); prompt bổ sung là mẫu tự tạo; mở rộng bằng quy ước file. |
| **[06]** | [`06_AI_MODELS_MANAGEMENT_SPEC.md`](06_AI_MODELS_MANAGEMENT_SPEC.md) | **Đặc tả provider/model**: schema `providers.json`, FULL key mặc định (mask opt-in), live `/models` cache 5 phút, namespace validation, thinking budgets. |
| **[08]** | [`08_PHASE_3_AND_BEYOND.md`](08_PHASE_3_AND_BEYOND.md) | **SUPERSEDED** — không dùng làm plan; phần chưa làm đã chuyển sang `16_*`. |
| **[09]** | [`09_PHASE_2_5_COMPLETED.md`](09_PHASE_2_5_COMPLETED.md) | **Lịch sử**: hồ sơ hoàn thành Phase 2.5. |
| **[10]** | [`10_NEXT_PHASES_AND_BACKLOG.md`](10_NEXT_PHASES_AND_BACKLOG.md) | Backlog đã rút gọn — việc chưa làm chuẩn theo `16_*`. |
| **[11]** | [`11_PHASE_3A_IMPLEMENTATION_PLAN.md`](11_PHASE_3A_IMPLEMENTATION_PLAN.md) | **Lịch sử**: plan thực thi 3a (đã xong, checkbox đối chiếu). |
| **[12]** | [`12_DEPLOYMENT_AND_RUNBOOK.md`](12_DEPLOYMENT_AND_RUNBOOK.md) | **Sống**: cài mới, cập nhật chống server cũ, backup, bố cục dữ liệu, sự cố thường gặp. |
| **[13]** | [`13_BATCH_RENAME_SPECIFICATION.md`](13_BATCH_RENAME_SPECIFICATION.md) | Đặc tả tham khảo (nguồn: Novel-Translator): batch rename pattern `{N}` — ta đã triển khai **không auto-sync**. |
| **[14]** | [`14_FILE_FILTER_SPECIFICATION.md`](14_FILE_FILTER_SPECIFICATION.md) | Đặc tả tham khảo (nguồn: Novel-Translator): filter/sort client-side — ta triển khai 2 tabs (không có tab Soát lỗi). |
| **[15]** | [`15_PHASE_3A_PLUS_PLAN.md`](15_PHASE_3A_PLUS_PLAN.md) | **Lịch sử**: plan thực thi 3a+ v3 (đã xong, checkbox đối chiếu). |
| **[16]** | [`16_NEXT_PHASES.md`](16_NEXT_PHASES.md) | **Backlog chuẩn duy nhất**: 3b/3c/4/5 + câu hỏi mở + danh sách không-làm. |
| **[ROADMAP]** | [`ROADMAP.md`](ROADMAP.md) | Lộ trình + hồ sơ hoàn thành v2.5 → 3a + checkpoint/OCR hoãn. |
| **[wip/]** | `wip/` | Nháp + lịch sử (`del_*` giữ nguyên). `UI3.md` trống. Quy ước công nghệ UI cũ ở `UI_TECHNOLOGY_*.md`. |
