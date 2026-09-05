# 09. PHASE 2.5 — HỒ SƠ HOÀN THÀNH (DONE, CHI TIẾT)

> **Phạm vi:** mọi việc từ sau commit `178f532` (🔖 v2.5.0, 04/09/2026) đến 05/09/2026,
> trên branch `phase-2.5` (chưa commit lúc viết file này).
> **Quy mô:** 18 files, **+1024 / −148** dòng; tests **45 → 70** (toàn PASS);
> `web/index.html` 256 → 482 dòng; `main.py` 467 → 741 dòng.
> **Kết luận:** Phase 2.5 đạt toàn bộ exit criteria (`docs/del_07_*`) + các rework phát sinh.
> File này là hồ sơ chuẩn duy nhất của Phase 2.5; các plan nháp trong `docs/wip/del_*` chỉ còn giá trị lịch sử.

---

## A. Backend hardening (2.5a)

### A1. Atomic write toàn repo
- **Mới:** `core/file_handler.atomic_write_text()` (`.tmp` cùng thư mục + `fsync` + `os.replace`; crash giữa chừng giữ nguyên file cũ, tự dọn `.tmp`).
- **Chuyển qua:** `save_output`, `PUT /api/settings` (config.json), `PUT /api/prompts/*`, `run.py` (output), `config.py` (`_ensure_files`, `save_keys`).
- **Còn `write_text` trực tiếp (đúng acceptance):** tạo placeholder `index.html` khi thiếu + tạo default prompt lần đầu.
- **Test:** crash giả lập (`os.replace` raise) → file cũ nguyên + không sót `.tmp`.

### A2. Error taxonomy chuẩn — `core/errors.py` (mới)
| Nhóm | Điều kiện | Hành động |
|---|---|---|
| Đổi key rồi retry | HTTP 429 | `try_next_key()`; hết key → dừng |
| Retry cùng key (tối đa 2 attempt/chunk) | timeout, mất kết nối, HTTP 408/500/502/503/504 | thử lại cùng key; hết attempt → dừng |
| Dừng ngay | HTTP 400/401/403/404, response rỗng/JSON sai cấu trúc, safety-block | không retry, không đổi key, báo đúng nguyên nhân + cách sửa |
- **Sửa:** `GeminiClient` + `OpenAICompatClient` (giữ nguyên 100% message cũ để không vỡ UI/CLI/test), callback `on_attempt(attempt, key_idx)` → SSE event `progress {i, n, attempt, key, keys, file, files}`.
- **Mirror:** `docs/02` §5.1 (bảng) trỏ về file này.
- **Tests:** `tests/test_errors.py` (6), `tests/test_translate_flow.py` (sequence timeout/500/401/429/rỗng/Unicode + `_attribute`).

### A3. Contract prefs duy nhất — `normalize_prefs` (`core/config.py`)
- `get_config()` và `PUT /api/settings` dùng chung; sai → default; key lạ → bỏ.
- PUT giữ ngữ nghĩa cũ: giá trị sai thì **giữ giá trị đang lưu** (không ghi đè default).
- **Test:** `tests/test_config.py` (4).

## B. `translated/` → `results/` (theo yêu cầu user, chọn tên `results/`)
- `file_handler`: `get_output_path`/`save_output`, thư mục `results/`; `_migrate_translated()` chuyển file cũ sang (không đè, tự xóa thư mục rỗng) — có test migration.
- Endpoints/keys: `/files` → `{sources, results}`; `/file?side=` → `sources|results`; `/api/save` → `results/{file}`; `/api/projects` → `{slug, sources, results}` (phục vụ cards).
- `run.py`: `out_chunks`, ghi qua atomic vào `results/`.
- Dữ liệu thật: project `Thử` đã migrate xong, không còn `translated/`.
- Docs cập nhật: 03 (code mẫu), 04 (API contract), 05, 08, README, ROADMAP, CHANGELOG. File `del_*` giữ nguyên làm lịch sử.

## C. Projects → cards dự án only (bỏ quản lý file khỏi đây)
- Card: tên, số file nguồn/kết quả, tiến độ M/N, nút mở workspace + xóa (confirm).
- Không upload/danh sách file/bulk ở trang này nữa.

## D. Workspace 3 cột (file | nguồn | kết quả)
- Cột file: tabs **Nguồn/Kết quả** (1 danh sách duy nhất, nút dùng chung, đổi tab = thao tác mới, không nhớ selection); dropzone gộp thẳng vào panel (không ô riêng); đổi tên, xóa (confirm, 409 khi đang dịch), checkbox bulk.
- Click file nguồn → nạp trái + **tự nạp kết quả cùng tên sang phải** (chưa có thì báo rõ); click file kết quả → nạp cả 2 chiều cùng tên.
- Lưu editor phải vào `results/`; sync-scroll giữ nguyên; layout fluid (bỏ `max-width:1200px`).
- Endpoints file: `GET .../file`, `DELETE .../files?filename=`, `POST .../rename`, `DELETE /api/projects/{slug}` (409 khi có phiên dịch dính dáng, nhờ `_active_job`).

## E. Tìm/thay thế kiểu Sigil, không CodeMirror
- Thanh chung 2 editor: regex on/off, hoa/thường, cả từ, `$1` backref, đếm, trước/tiếp, thay/thay hết; highlight `<mark>` trên text đã escape (không XSS); gõ tiếp tự gỡ mark giữ caret; regex lỗi báo không crash.
- Phạm vi tất cả file: `POST /api/find-replace` (Python `re`, backref `\1`, atomic từng file, lọc ext, trả số chỗ/file; 400 khi regex lỗi/thiếu mẫu/traversal) + confirm chống bấm nhầm + tự nạp lại editor.

## F. Gộp nhiều file dịch 1 phiên
- `POST /api/translate/merge`: nối file với marker `===== FILE: tên =====`, chia chunk chung, dịch lần lượt, SSE ghi rõ chunk thuộc file nào (kể cả chunk trải 2 file), `done {chars, chunks, files}`; 400 khi chưa chọn file, 404 khi thiếu file.
- Tái dùng lõi: `_build_prompts` + `_run_chunks` + `_attribute` (map chunk→file bằng find tiến dần, pure function có unit test) — hành vi `/translate` cũ giữ nguyên (đã refactor chung, tests khóa).
- UI: dialog ước lượng ký tự/chunk + **cảnh báo quá 2 chunk**; hỏi tên lưu (mặc định `fileđầu_gop.ext`); giữ tùy chọn **dịch tuần tự** không gộp.

## G. Restart server đúng mọi launcher + chống stale
- **Nguyên nhân nút cũ chết dưới `uv run`:** `os.execv(sys.executable, [sys.executable] + sys.argv)` với `argv[0]` tương đối + CWD lệch = tiến trình mới chết lặng sau khi đã báo thành công.
- **Sửa:** `_restart_args()` absolutize script (có unit test) + `POST /api/restart` + nút cuối sidebar + hiện version/giờ chạy + **nhớ tab qua reload**.
- `/api/health` trả `{ok, version, started_at}` (test khóa version) — lệch version = server cũ.
- **Đã kiểm chứng live đúng bằng `uv run`:** `started_at` đổi, server khỏe sau restart.

## H. Sự cố server cũ (bài học, đã xử lý)
- Triệu chứng: bản dịch vẫn vào `translated/`, danh sách kết quả trống — trong khi code trên đĩa đã đúng.
- Bằng chứng: server PID 59968 chạy từ 10:18 (code cũ), sửa code lúc 10:48–10:50, `Thử/translated` mọc lại lúc 11:59 sau khi đã xóa xác minh; `index.html` đọc tươi mỗi request nên UI mới chạy trên API cũ.
- Xử lý: tắt server cũ, verify lại trên server tươi, thêm health-version + nút restart để không tái diễn.

## I. Manifesto + docs (v2.4 → v2.5)
- §0 READ-FIRST (đọc trước mọi sửa đổi, đổi contract thì sửa file này trước).
- §7 local-first security (FULL key, chống public = gitignore + không push secret; danh sách cấm đề xuất lại).
- §8 contract runtime SSOT (prefs, providers.json, migration, error model).
- §9 chính sách lib local (thuần trước; minimal vendor: `diff-match-patch`, `marked`, `DOMPurify`; cấm framework/build-chain/CDN cứng; lib nặng chỉ khi có bằng chứng bug; restart đúng mọi launcher).
- CHANGELOG entry v2.6.0; ROADMAP §9 hoàn thành; README (4 trang, 3 cột, find/replace); `.gitignore` (+`.vscode`, `*.swp`, `node_modules/`, `web/vendor/`, `*.bundle.js`, `dist/`, `.cache/`).
- Dọn docs: 5 file `wip/` → `del_`, `07` → `del_07` (giữ làm lịch sử, không xóa).

## J. Verify tổng
- `pytest`: **70 passed** (45 cũ + 25 mới: atomic 2, errors 6, flow 7, config 4, server +6).
- `node --check` script UI sau mỗi lần sửa.
- Curl trên server tươi: cards counts, files keys, 404 results→UI báo "chưa có", save→`results/`, migration legacy, merge validation, find-replace counts, health version, restart đổi `started_at`.
- Workspace dọn sạch sau test (chỉ còn project `Thử` có sẵn).
