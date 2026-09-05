# 11. PHASE 3a — KẾ HOẠCH THỰC THI (HOÀN THIỆN UI)

> **For agentic workers:** REQUIRED: làm theo thứ tự Task 0 → 6, mỗi Task xong chạy test liên quan + checklist tay rồi mới sang Task tiếp theo. Steps dùng checkbox (`- [ ]`).

**Goal:** Tách frontend khỏi 1 file để bảo trì được, chuẩn hóa CSS, hoàn thiện quản lý prompt + lưu trữ dự án + hủy phiên + tiến độ + lịch sử — xong là UI đủ dùng hàng ngày, không nợ cấu trúc.

**Architecture:** Tách tĩnh không build (shell + css/js rời, `<script>` thường theo thứ tự, giữ globals để refactor ít rủi ro); gom hạ tầng dùng chung (SSE reader, toast); backend thêm 6 endpoint tối thiểu, tái dùng helper hiện có (`atomic_write_text`, `_resolve_target`, `_run_chunks`, `_upsert_file`).

**Tech Stack:** giữ nguyên (stdlib + httpx + vanilla). Không thêm dependency nào trong 3a.

**Tài liệu gốc:** `docs/wip/UI_TECHNOLOGY_AND_LONG_TERM_MAINTENANCE_RECOMMENDATION.md` (áp dụng có chọn lọc — xem "Điểm cố ý làm khác" cuối file), `docs/04_*` (API contract), `docs/00_*` v2.5 §9, `docs/10_*` §1 (backlog 3a), **`docs/wip/del_PLAN_REDESIGN_PROJECTS_AND_SETTINGS_UI.md` (đối chiếu chi tiết ở "Phụ lục R" cuối file — đọc trước khi làm Task 0).**
> **TRẠNG THÁI: ĐÃ THỰC THI XONG (05/09/2026).** File này giữ nguyên làm hồ sơ đối chiếu; việc tiếp theo xem `docs/16_NEXT_PHASES.md`.

**Điều kiện vào:** branch `phase-2.5` đã merge hoặc đang đứng trên nó (code 2.6.0: results/, merge, tabs, find/replace, restart — plan này giả định đã có).

**Điều kiện vào:** branch `phase-2.5` đã merge hoặc đang đứng trên nó (code 2.6.0: results/, merge, tabs, find/replace, restart — plan này giả định đã có).

---

## Chunk 0 — Tách frontend (làm ĐẦU TIÊN, mở đường cho mọi task UI sau)

### Task 0.1: Rút CSS + MIME map + Design Tokens

**Nguồn class chuẩn:** `del_PLAN_REDESIGN` §5 (giữ nguyên tokens + components), với 1 đổi tên duy nhất: `.btn-pri` → `.btn.pri` (code hiện tại đã dùng `btn pri` ở ~10 chỗ — không sửa JS).

**Files:**
- Create: `web/css/app.css` = tokens `:root` (§5 nguyên văn: `--bg-app #f8fafc` … `--primary #2563eb` …) + toàn bộ `<style>` hiện tại + thêm `.card`, `.table-minimal`, `.label-tracked`, `.input/.select/.textarea` (+focus), `.btn-danger`, `.toast` (fixed bottom-right, tự mờ 3s — dùng cho Task 0.2 thay `alert`)
- Modify: `web/index.html` (thay `<style>` bằng `<link rel="stylesheet" href="css/app.css">`), `main.py` (`_serve_static`: thêm `MIME_MAP = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json"}`)
- Test: `tests/test_server.py::test_static_mime` (mới: GET `/css/app.css` → 200 + `text/css`; traversal `..` vẫn 404)

- [x] **Step 1:** Viết test MIME → FAIL (chưa có file/route).
- [x] **Step 2:** Tạo `app.css`, sửa `index.html`, thêm `MIME_MAP`.
- [x] **Step 3:** PASS + mở 4 trang bằng mắt thường, không vỡ layout. Commit.

### Task 0.2: Rút JS theo trang + hạ tầng dùng chung

**Files:**
- Create: `web/js/app.js` (`$`, `J`, `esc`, `toast(msg)`, `readSSE(resp, {onChunk,onProgress,onDone,onError})`, nav+hash+tab-memory, `restartSrv`, `srvInfo`), `web/js/projects.js` (cards), `web/js/workspace.js` (files/tabs/translate/bulk/merge/panes/upload), `web/js/findreplace.js` (thanh Sigil + scope), `web/js/prompts.js`, `web/js/settings.js`, `web/js/init.js` (boot: `listProjects().then(listFiles); loadMeta()...` + dropzone wiring + `tOut` input guard)
- Modify: `web/index.html` (thay `<script>` bằng 8 thẻ `<script src="js/..." defer>` đúng thứ tự: app → projects → workspace → findreplace → prompts → settings → init)
- Test: `node --check` từng file + checklist click tay 4 trang

- [x] **Step 1:** Tách `app.js` trước (helpers + `readSSE` từ 1 trong 3 bản copy SSE trong `startTl`).
- [x] **Step 2:** `startTl`/`wsBulkTranslate`/`wsMergeTranslate` chuyển sang `readSSE` (xóa 2 bản copy, giữ nguyên message/progress).
- [x] **Step 3:** Tách từng file trang, `index.html` chỉ còn markup + thẻ nạp.
- [x] **Step 4:** `node --check js/*.js` toàn PASS + checklist: tạo project → upload → dịch 1 file → save → find/replace → đổi settings → restart (không test restart ở đây, chỉ không vỡ nút).
- [x] **Step 5:** `alert()` còn lại chuyển sang `toast()` — NGOẠI TRỪ `restartSrv` (giữ `alert` vì reload xóa DOM) và `confirm()` (giữ native, không dựng dialog component ở 3a).
- [x] **Step 6:** Commit.

**Acceptance Chunk 0:** `index.html` không còn `<style>`/`<script>` lớn; `pytest -q` PASS; checklist tay không hồi quy; JS không lỗi console trên 4 trang.

### Task 0.3: Áp dụng Card/tokens theo từng trang (từ `del_PLAN_REDESIGN` §2–§4)

Triết lý giữ nguyên (§2: nền `#f8fafc`, card trắng viền `#e2e8f0` bo `8px`, tracked-labels, minimal table, badges, transition `0.15s`, không gradient/neon/blur).

- [x] **Step 1 — Projects (theo §3.1, BỎ §3.2 vì lỗi thời):** header trang + phụ đề `Quản lý thư mục tài liệu và kết quả xử lý.`; cards grid responsive (1 cột nhỏ, 2–3 cột rộng); mỗi card: 📁 slug + `N nguồn · M kết quả · tiến độ M/N` + badges + hàng nút (Mở workspace / 📦 Lưu trữ (Task 2) / Xóa). §3.2 (upload drawer + bảng file trong Projects) **không làm** — file đã chuyển sang Workspace 3 cột từ v2.6.0.
- [x] **Step 2 — Settings (theo §4, chỉ còn việc CSS vì chức năng xong ở v2.5.0):** bọc 5 khối (A Providers / B Model / C Thinking / D Tuning + 2 nút lưu riêng) vào `.card`; labels → `.label-tracked`; model info strip → chips; tuning → lưới 3 cột; textarea keys monospace; cảnh báo thinking → hộp xám viền mảnh (§4.3 nguyên văn).
- [x] **Step 3 — Workspace + Prompts (tối thiểu):** file panel + headers 2 editor vào `.card`/tracked-labels; trang Prompt bọc list + editor + nút vào `.card`; bảng chunks → `.table-minimal`.
- [x] **Step 4:** Checklist 4 trang + commit. DoD §6.2 gốc được thay bằng: cards đồng bộ 4 trang, zero npm, không hiệu ứng màu mè (bỏ tiêu chí `<35KB index.html` và `nút tải file trong Dự Án` vì đã lỗi thời sau tách file + chuyển kiến trúc).

---

## Chunk 1 — Quản lý prompt đủ dùng (theo yêu cầu user, thay hàm riêng từng dự án)

Backend dùng chung 1 endpoint backup cho mọi dự án — không viết hàm riêng từng dự án.

### Task 1.1: Rename + delete prompt

**Files:**
- Modify: `core/prompt_engine.py` (thêm `delete_prompt(name)`, `rename_prompt(old, new)`; validate chung `_check_name`: `*.txt`, không `/ \ ..`, không rỗng; xóa `default_translation.txt` được nhưng confirm ở UI vì `_ensure_default_prompt` sẽ tự tạo lại rỗng-mặc-định khi restart)
- Modify: `main.py` (`DELETE /api/prompts/{name}` → 200/`{"ok": true}`; `POST /api/prompts/rename` `{"old","new"}` → 200/`{"filename"}`; validate ext qua `ALLOWED_EXTS`? prompt là `.txt` — check `endswith(".txt")` như PUT hiện tại; 400 tên xấu, 404 thiếu file, 400 trùng tên)
- Test: `tests/test_server.py::test_prompt_rename_delete` (rename ok + trùng + ext lạ + traversal + xóa + xóa file không có → 404 + default tự tạo lại sau khi xóa và gọi lại GET)

- [x] **Step 1:** Test → FAIL. **Step 2:** Implement. **Step 3:** PASS + commit.

### Task 1.2: Backup prompt vào dự án (1 endpoint chung)

**Files:**
- Modify: `main.py` (`POST /api/projects/{slug}/prompt-backup` `{"name": "x.txt"}` → đọc `prompts/x.txt` → `atomic_write_text` vào `workspace/projects/{slug}/assets/prompts/x.txt` (tự tạo thư mục) → 200/`{"path": "assets/prompts/x.txt"}`; 404 prompt thiếu; 400 tên xấu; slug traversal → 400)
- Modify: `web/js/prompts.js` (hàng nút mỗi prompt trong dropdown? UI hiện tại là select — thêm select dự án đích (mặc định = project đang mở ở workspace, fallback dropdown dự án) + nút `⬇ Lưu vào dự án` + toast kết quả)
- Test: `tests/test_server.py::test_prompt_backup` (backup ok + file nằm đúng `assets/prompts/` + 404 + traversal)

- [x] **Step 1:** Test → FAIL. **Step 2:** Implement. **Step 3:** PASS + checklist tay (backup → kiểm tra file trên đĩa). Commit.

**Acceptance Chunk 1:** rename/delete/backup có test; không còn nhu cầu "hàm riêng từng dự án".

---

## Chunk 2 — Lưu trữ dự án (đã hứa "làm sau", làm ở 3a)

### Task 2: Archive = zip + xóa + dọn db

**Files:**
- Modify: `core/file_handler.py` (thêm `archive_project(slug, archive_dir) -> Path`: `shutil.make_archive(str(archive_dir/slug), "zip", root_dir=projects_dir, base_dir=slug)` (ghi đè cùng tên — single user, đã confirm ở UI) → `shutil.rmtree` thư mục gốc; lỗi giữa chừng (zip xong, xóa lỗi) → raise, giữ zip để xử lý tay)
- Modify: `main.py` (`POST /api/projects/{slug}/archive` → `{"path": "archive/{slug}.zip"}`; 404 thiếu project; 409 khi `_active_job` thuộc project đó; dọn `_delete_project_rows`)
- Modify: `web/js/projects.js` (nút `📦 Lưu trữ` trên card + confirm; toast đường dẫn zip)
- Test: `tests/test_server.py::test_project_archive` (seed + archive → zip tồn tại + thư mục gốc mất + GET /projects không còn + archive project không có → 404)

- [x] **Step 1:** Test → FAIL. **Step 2:** Implement. **Step 3:** PASS + kiểm tra mở được zip. Commit.

---

## Chunk 3 — Hủy phiên + tiến độ trực quan

### Task 3.1: Cancel giữa chunk

**Files:**
- Modify: `core/errors.py` (thêm `class TranslateCancelled(Exception)`)
- Modify: `main.py` (`_cancel_event = threading.Event()` module-global; `_run_chunks(..., cancel=None)`: `if cancel and cancel.is_set(): raise TranslateCancelled()` đầu mỗi vòng chunk; `POST /api/translate/cancel` → set event → 200; cả 2 handler: `clear()` sau khi acquire lock, `except TranslateCancelled` → `log_run(..., "cancelled")` + `emit("error", {"error": "Đã hủy bởi người dùng", "cancelled": True})`; KHÔNG ghi output — atomic write hiện tại đã đảm bảo không dở dang)
- Modify: `web/js/workspace.js` (nút ⏹ Hủy (confirm) + trạng thái cuối `⏹ Đã hủy` + nút ở bulk bar khi đang chạy)
- Test: unit `_run_chunks` với FakeClient mà `on_attempt` set event → assert raise `TranslateCancelled` sau đúng 1 chunk; server test cancel khi không có phiên → 200 (không crash)

- [x] **Step 1:** Test → FAIL. **Step 2:** Implement. **Step 3:** PASS + checklist tay (dịch file 3+ chunk → hủy giữa chừng → không có file dở). Commit.

### Task 3.2: Thanh tiến độ workspace

**Files:**
- Modify: `web/js/workspace.js` + `web/css/app.css` (thanh `wProg`: `chunk i/n · attempt k · key j/m · file · đã chờ Ns`, timer `setInterval` từ lúc start, dọn khi done/error/cancel; dùng event `progress` đã có từ 2.5 — không đụng backend)

- [x] **Step 1:** Implement + checklist tay (thấy attempt tăng khi timeout giả lập? — chỉ cần thấy chunk/key/file chạy). Commit.

## Chunk 4 — Lịch sử chạy (trong trang Projects, không thêm nav)

### Task 4: `GET /api/history` + bảng cuối Projects

**Files:**
- Modify: `main.py` (`GET /api/history?limit=20` → JOIN `runs LEFT JOIN files ON runs.file_id=files.id` trả `{project, file, provider, model, status, error, started_at, finished_at}` mới nhất trước; helper `_file_id(project, filename)` SELECT id; **truyền `file_id` vào mọi `log_run` trong translate/merge** (CLI giữ `None` cho chế độ dịch trực tiếp) — migration: rows cũ `file_id NULL` → hiển thị `—`)
- Modify: `web/js/projects.js` (bảng lịch sử dưới cards + ước tính chi phí từ `model_info.pricing` nếu có, ghi rõ "ước tính")
- Test: `tests/test_server.py::test_history` (dịch 1 file fake → history có đúng project/file/model/status)

- [x] **Step 1:** Test → FAIL. **Step 2:** Implement. **Step 3:** PASS + checklist tay. Commit.

**Acceptance Chunk 2–4:** archive/cancel/progress/history có test; Đóng Phase 3a khi thêm: `pytest` PASS, checklist 4 trang không hồi quy, CHANGELOG entry 3a.0.

---

## Điểm cố ý làm khác so với `UI_TECHNOLOGY_*.md` (ghi để khỏi tranh lại)

1. **Plain `<script>` thay vì ES Modules:** globals hiện tại chạy ổn; modules thêm rủi ro import-order mà lợi ích chưa tới. Xem lại khi JS > ~1500 dòng.
2. **Giữ tên `J()` thay vì `apiRequest`:** đã tập trung duy nhất 1 chỗ — đổi tên 40+ callsite lúc này rủi ro/sửa ít giá trị.
3. **Giữ `confirm()` native:** đủ cho single-user; không dựng confirm-dialog component ở 3a.
4. **Chưa làm state-object tập trung (`state.js`):** globals `_wsSrc/_wsTab/...` còn kiểm soát được; tách file (Task 0.2) đã giảm rủi ro chính. Xem lại ở 3b nếu thêm glossary/profile.
5. **Chưa hash-routing:** nav nút + `localStorage` đã giữ tab qua reload; hash thêm sau nếu cần nút Back.
6. **Chưa `textarea` thay `contenteditable`:** ô dịch hiện tại + find/replace Sigil đang chạy; đổi editor là Task 3b+ và phải có bằng chứng IME (manifesto §9).
7. **Chưa dark mode / responsive tablet / phím tắt / dirty-guard rời trang:** dồn sang 3b trừ dirty-guard file đang mở (làm gọn trong Task 3.2 nếu còn sức, không bắt buộc).

---

## Phụ lục R — Đối chiếu `del_PLAN_REDESIGN_*` (đọc trước Task 0)

| Mục trong del_PLAN_REDESIGN | Trạng thái trong 3a | Ghi chú |
|---|---|---|
| §1 phân tích hiện trạng (~250 dòng, CSS ~25 dòng, chưa upload) | Lịch sử | Code nay 482 dòng, upload/tabs/merge đã có (v2.6.0) |
| §2 triết lý minimalist + §2.1 5 điểm kế thừa Novel-Translator | **Áp dụng nguyên** | Card trắng, tracked-labels, minimal table, badges, transition 0.15s |
| §2.2 (bỏ tachyons/alpine, không hiệu ứng) | **Đã đạt** | Giữ, không thêm lib ở 3a |
| §3.1 cards grid + header + nút Vào dịch/Xóa | **Áp dụng** (Task 0.3 Step 1) | Thêm nút Archive (Task 2); badge `Đã dịch` tính trên `results/` (doc cũ ghi `translated/`) |
| §3.2 upload drawer + bảng file trong Projects | **LỖI THỜI — không làm** | File đã chuyển sang Workspace 3 cột (quyết định v2.6.0) |
| §4 settings 4–5 khối (providers/model/thinking/tuning/save riêng) | **Chức năng xong, còn CSS** (Task 0.3 Step 2) | Bọc `.card`, chips info strip, lưới tuning, hộp cảnh báo thinking nguyên văn |
| §5 tokens + components CSS | **Áp dụng nguyên** (Task 0.1) | Đổi tên duy nhất `.btn-pri` → `.btn.pri`; thêm `.toast` |
| §6.1 bước 1 (CSS foundation) | Task 0.1 | Vào `web/css/app.css` thay vì `<style>` |
| §6.1 bước 2 (projects) | Task 0.3 Step 1 | Trừ §3.2 |
| §6.1 bước 3 (settings) | Task 0.3 Step 2 | Chỉ CSS |
| §6.1 bước 4 (kiểm thử hiển thị) | Mọi Task | `<20ms` + luồng tạo→upload→dịch→lưu |
| §6.2 DoD | **Viết lại** (Task 0.3 Step 4) | Bỏ `<35KB index.html` (đã tách file) và `tải file trong Dự Án` (đã chuyển sang Workspace) |
