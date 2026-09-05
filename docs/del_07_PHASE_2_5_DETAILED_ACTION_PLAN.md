# 07. KẾ HOẠCH CHI TIẾT PHASE 2.5: STABILIZATION (TÁCH 2.5a + 2.5b)

> **For agentic workers:** REQUIRED: thực hiện theo từng Task dưới đây, mỗi Task xong phải chạy test liên quan và commit. Steps dùng checkbox (`- [ ]`).

**Goal:** Khóa độ ổn định của chu trình gửi–nhận (atomic output, error model chuẩn, config 1 contract, integration test) và lấp lỗ hổng chức năng trang Projects (upload kéo-thả, quản lý file, bulk) — xong là đóng 2.5, không lấn sang P1/P2.

**Architecture:** Tách 2 pha phụ ship độc lập: **2.5a backend hardening** (không đụng UI) và **2.5b files UI** (dùng endpoint đã có + 3 endpoint mới tối thiểu). Mỗi pha phụ có exit criteria riêng.

**Tech Stack:** Python stdlib + `httpx` (đã có), vanilla HTML/CSS/JS single-file (không thêm lib), `pytest` + `httpx.MockTransport` cho integration test.

**Tài liệu gốc:** `docs/00_PROJECT_MANIFESTO.md` (v2.4, READ-FIRST), `docs/wip/bao_cao_pha_2.md` §5.1 (P0), `docs/02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md` §5, file này là **tài liệu phát triển chuẩn cho error taxonomy** (§2.5a-2).

**Hiện trạng đã xác minh trong code (05/09/2026):**
- Atomic write mới chỉ có ở `core/provider_manager.py:153` (providers.json). Còn lại ghi trực tiếp: `main.py` (`/api/save`, `PUT /api/settings`), `core/config.py` (config.json/keys.json), `core/file_handler.py:59` (output dịch), `run.py:140`.
- Retry hiện tại: `core/ai_client.py` chỉ xoay key khi **429**; mọi lỗi khác (timeout, 5xx, 4xx) raise ngay; `main.py:427-443 run_all()` không có vòng attempt nào — lỗi đầu tiên là `emit("error")` dừng phiên.
- Upload endpoint đã có (`POST /api/projects/{slug}/upload`, multipart + raw). Chưa có: xóa/đổi tên file, xóa project, bulk. UI Projects (256 dòng `web/index.html`) chưa gọi upload.
- `.gitignore` đã chặn `config/providers.json`, `config/keys.json`, `workspace/` — chống lộ key qua git đã đủ theo manifesto v2.4 §7.

---

## Chunk 1 — Phase 2.5a: Backend Hardening (ưu tiên cao nhất, làm trước)

### Task 1: Atomic write thống nhất + bảo vệ output cũ

**Files:**
- Modify: `core/file_handler.py` (thêm `atomic_write_text(path, content)`: ghi file `.tmp` cùng thư mục → `os.replace`)
- Modify: `main.py` (`/api/save`, `PUT /api/settings`), `run.py:140` (ghi output), `core/config.py` (`_ensure_files`, `save_keys`)
- Test: `tests/test_file_handler.py` (thêm case mới)

- [ ] **Step 1:** Thêm `atomic_write_text()` vào `core/file_handler.py` (dùng `tempfile` cùng thư mục + `os.replace`; giữ nguyên quyền file cũ nếu tồn tại).
- [ ] **Step 2:** Thay mọi điểm ghi file output/config/prompt sang helper mới (danh sách ở trên; providers.json trong `provider_manager.py` đã atomic — giữ nguyên).
- [ ] **Step 3:** Test: giả lập crash giữa chừng (ghi `.tmp` rồi raise trước `os.replace`) → assert file chính còn nguyên nội dung cũ.
- [ ] **Step 4:** Chạy `pytest tests/test_file_handler.py tests/test_server.py -q` → PASS. Commit.

**Acceptance:** Không còn điểm nào ghi trực tiếp vào file đích (`grep write_text main.py core/ run.py` chỉ còn lại tạo file mặc định lần đầu + helper).

### Task 2: Error taxonomy chuẩn + retry/xoay-key/dừng-ngay (TÀI LIỆU PHÁT TRIỂN)

Bảng dưới là **chuẩn duy nhất**. Mọi client (`GeminiClient`, `OpenAICompatClient`) và `run_all()` phân loại theo bảng này, không tự chế riêng.

| Nhóm | Điều kiện nhận biết | Hành động | Thông điệp UI |
|---|---|---|---|
| **A. Đổi key rồi retry** | HTTP 429 | `try_next_key()`; hết key → dừng | "Key X bị giới hạn, đã chuyển key kế tiếp…" / hết key: "Tất cả key đều bị 429, chờ ít phút rồi Gửi Lại" |
| **B. Retry cùng key (tối đa 2 attempt/chunk)** | timeout, `ConnectError`, HTTP 408/500/502/503/504 | thử lại cùng key, giãn `api_delay_seconds` giữa attempt; hết attempt → dừng | "Mạng/provider chập chờn (lần 1/2)…" rồi lỗi cuối |
| **C. Dừng ngay, báo rõ** | HTTP 400/401/403/404 (key sai, model không tồn tại, hết quyền, payload sai), response rỗng / JSON sai cấu trúc / thiếu `text`, safety-block (không có `candidates`) | dừng phiên, KHÔNG retry, KHÔNG đổi key | nêu đúng nguyên nhân + cách sửa ("Key không hợp lệ — kiểm tra trang Cấu Hình", "Model X không tồn tại — chọn lại model", "Nội dung bị chặn bởi bộ lọc an toàn") |

**Files:**
- Create: `core/errors.py` (`classify(exc_or_status, provider_type) -> {action, code, user_msg}` + hằng `MAX_SAME_KEY_ATTEMPTS = 2`)
- Modify: `core/ai_client.py`, `core/openai_client.py` (raise lỗi có `status_code` gắn kèm thay vì message rời rạc), `main.py run_all()` (vòng attempt theo taxonomy + `emit("progress", {i, n, attempt})` để UI Phase 3 hiển thị), `run.py` (CLI dùng chung `classify`)
- Test: `tests/test_errors.py` (mới, unit cho từng dòng bảng), `tests/test_translate_flow.py` (mới, integration bằng `httpx.MockTransport`: 1 chunk ok / N chunk / 429 key1→key2 ok / all-429 dừng / timeout retry 2 lần rồi dừng / 401 dừng ngay không retry / response rỗng / JSON malformed / Unicode Việt)

- [ ] **Step 1:** Viết `tests/test_errors.py` cho toàn bộ bảng trên → FAIL (chưa có module).
- [ ] **Step 2:** Viết `core/errors.py` tối thiểu cho test PASS.
- [ ] **Step 3:** Sửa 2 client để raise lỗi mang `status_code`; sửa `run_all()` + CLI theo taxonomy (giữ nguyên: mỗi key 1 lần/chunk với 429, không fallback model — manifesto §3).
- [ ] **Step 4:** Viết `tests/test_translate_flow.py` (MockTransport, không gọi mạng thật) → PASS hết.
- [ ] **Step 5:** Mirror bảng taxonomy vào `docs/02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md` §5 (1 bảng + 1 dòng trỏ về file này). Chạy full `pytest -q` → 45+ test PASS. Commit.

**Acceptance:** Mọi case trong bảng đều có test; UI/CLI không bao giờ retry lỗi nhóm C; key index hiện tại được giữ sang chunk kế tiếp khi thành công (tận dụng quota).

### Task 3: Gom validate config về 1 nơi

**Files:**
- Modify: `core/config.py` (thêm `normalize_prefs(raw) -> dict` dùng chung), `main.py` (`PUT /api/settings` gọi `normalize_prefs`, xóa logic `float()` inline dòng 347-353)
- Test: `tests/test_config.py` (mới): số âm/chuỗi rác/thiếu field → rơi về mặc định; `max_chunk_chars` int; delay ≥ 0

- [ ] **Step 1:** Viết test → FAIL. **Step 2:** Tách `normalize_prefs()` từ `get_config()` hiện tại, cả `get_config()` và PUT đều gọi nó. **Step 3:** PASS + commit.

**Acceptance:** UI và backend không bao giờ lệch giá trị prefs; contract khớp manifesto v2.4 §8.

### Exit criteria 2.5a (đóng pha phụ khi đủ cả 3)

- [ ] `grep write_text` chỉ còn helper + tạo file mặc định.
- [ ] Full taxonomy có test; không retry nhóm C.
- [ ] `pytest -q` toàn PASS, không gọi mạng thật trong test.

---

## Chunk 2 — Phase 2.5b: Files UI (trang Projects dùng được thật)

Nguyên tắc: dùng lại endpoint đã có, chỉ thêm endpoint khi thiếu thật. Không CSS framework, không lib mới.

### Task 4: 3 endpoint file còn thiếu

| Method + Path | Request | Response | Ghi chú |
|---|---|---|---|
| `DELETE /api/projects/{slug}/files?filename=F` | — | `{"ok": true}` | Xóa cả `sources/F` và `translated/F` (nếu có); cập nhật `app.db`; `confirm()` ở UI |
| `POST /api/projects/{slug}/rename` | `{"old": "a.md", "new": "b.md"}` | `{"filename": "b.md"}` | Validate tên mới như upload (ext cho phép, sanitize qua `SafeFileHandler`); rename cả 2 thư mục nếu tồn tại |
| `DELETE /api/projects/{slug}` | — | `{"ok": true}` | Xóa `workspace/projects/{slug}` + rows `app.db`; `confirm()` ở UI; đang dịch file thuộc project → 409 |

**Files:** Modify `main.py` (do_DELETE + 1 nhánh do_POST), `core/file_handler.py` (thêm `delete_file/rename_file/delete_project` dùng `relative_to()` như hiện tại). Test: thêm case vào `tests/test_server.py`.

- [ ] **Step 1:** Test endpoint mới (happy + path traversal `../` + ext lạ + rename trùng tên) → FAIL.
- [ ] **Step 2:** Implement tối thiểu → PASS. **Step 3:** Commit.

### Task 5: UI Projects — drop zone + bảng file + bulk

**Files:** Modify duy nhất `web/index.html` (`#v-projects` + `<script>`).

- [ ] **Step 1:** Drop zone: khung dashed, kéo-thả + click chọn (accept `.txt,.md,.html`, nhiều file) → gọi upload endpoint từng file → refresh list không reload. Hiện trạng thái từng file (ok/lỗi ext).
- [ ] **Step 2:** Bảng file 2 nhóm Sources/Translated: cột tên + trạng thái badge (`Chưa dịch`/`Đã dịch`) + nút `Dịch →` (nhảy Workspace đúng project+file), `Xem`, `Xóa`, `Đổi tên` (prompt inline).
- [ ] **Step 3:** Checkbox từng dòng + thanh bulk: `Dịch tuần tự N file đã chọn` (gọi `/api/translate` lần lượt, lỗi thì dừng cả loạt — đúng failure policy), `Xóa đã chọn`. Progress text "file 2/5…".
- [ ] **Step 4:** Checklist thủ công: tạo project → thả 3 file → đổi tên 1 → xóa 1 → bulk dịch 2 file → sang Workspace đúng file. PASS. Commit.

**Acceptance 2.5b:** Vòng lặp "tạo project → nạp file → quản lý → dịch" làm được 100% trên UI, không cần chạm terminal; không thêm dependency.

---

## KHÔNG làm trong 2.5 (đã chốt — vi phạm là reopen scope)

Backoff/jitter, header Retry-After, request ID, health check provider, truncate warning, cancel request, drag-drop sắp xếp lại, dark mode, preset model, lịch sử dịch, ước tính token/chi phí, export metadata, PWA/offline. Toàn bộ dồn sang `docs/08_*` Phase 3+.

**Đóng Phase 2.5 khi:** exit criteria 2.5a + acceptance 2.5b đều checked, `pytest -q` PASS, `CHANGELOG.md` ghi 1 dòng release 2.5.x.
