# Changelog

Mọi thay đổi đáng chú ý của dự án được ghi tại đây, theo
[Keep a Changelog](https://keepachangelog.com/vi/1.1.0/) và
[Semantic Versioning](https://semver.org/lang/vi/).

## [Unreleased] — Phase 4 (Preview + Doc Viewer)
### Added
- Vendor offline `web/vendor/` (commit kèm, manifesto §9): `marked.min.js` 18.0.11
  (`lib/marked.umd.js` — v18 không còn bản min; nguồn `https://cdn.jsdelivr.net/npm/marked@18.0.11/lib/marked.umd.js`,
  sha256 `69451c8541c9c1e7a4bf3ffc6f73c4d89633de92bfbe3e484dfe182ef8091f88`)
  + `dompurify.min.js` 3.4.15 (nguồn `https://cdn.jsdelivr.net/npm/dompurify@3.4.15/dist/purify.min.js`,
  sha256 `f263b05369e050fa175d4ecb9c9358eb4253602d510297adfb31df48b2f1c4d5`).
  Không sửa file minified; `.gitignore` exception + verify `git check-ignore`.
- `loadScriptOnce()` trong `web/js/app.js`: vendor chỉ tải khi mở preview/tab Tài liệu.
- Preview editor: nút 👁 2 editor (`web/js/preview.js`, ext → heuristic), Markdown qua `marked` + `DOMPurify`, HTML trong `iframe sandbox=""` + `referrerpolicy="no-referrer"`, modal `<dialog>` có a11y (focus trả về nút gọi).
- Doc Viewer: `GET /api/docs` + `GET /api/docs/content` (whitelist `.md/.txt/.html`, `resolve_doc` symlink-safe + cap 2MB, lỗi đúng shape `{"error"}`: 400/403/404/413) + tab 📚 Tài liệu (viewer chỉ đọc source, không render HTML); tên file dài cuộn ngang cả khối list.
- Diff nguồn ↔ kết quả (`web/js/diff.js`): vendor `diff_match_patch.js` (Google raw build, sha256 `9a79cf03…7e4a3`, Apache-2.0 — cửa manifesto §9-điểm 2b: line-mode + timeout chống blowup khi so 2 ngôn ngữ), render 2 cột (gom cặp -/+) + liền mạch trong `<dialog>`, render DOM + `textContent` từng dòng.
- Toolbar regroup: preview/save per-editor (căn phải header), lọc/đổi tên/xóa vào tiêu đề Tập tin (đúng thứ tự); copy/wrap/find chuyển vào header Kết quả (copy giữa preview–save).
- Tab Tài liệu tự nạp khi mở (app.js gọi `loadDocList()` — onclick inline bị handler tab ghi đè nên không chạy).
- Save 2 chiều: `/api/save` thêm `side` (`sources` → status `new` vì nguồn sửa thì cần dịch lại; `results` → `done` như cũ).
- Batch coverage 3 lớp (logic skip đã có, chỉ thiếu test): API từng file (`test_batch_sequential_stops_at_failed_file`), `batchOnFileError` thuần trong `web/js/batch.js` + `node tests/test_batch_skip.mjs`, manual checklist.
- Workspace UX: header Kết quả Wrap/Preview/Tìm kiếm/Diff/Copy/Save; khối actions căn phải (Gửi AI→/Hủy/Dịch lại/Xóa trắng); `+prompts` dropdown checkbox + info luôn hiện ở info bar góc phải; filter panel restyle + neo dưới nút; 3 cột cao bằng nhau; select-all indeterminate.
- **Gỡ prompt profile** (dropdown + `GET /api/profiles` + 3 JSON) theo yêu cầu user — thừa so với nhu cầu; 2 prompt `qa_*.txt` giữ lại.
- Nút Wrap cho bảng diff (cạnh chọn 2 cột/liền mạch); refresh docs cùng dòng input lọc.

## [Unreleased] — Phase 3b stabilization
### Added
- `core/quality.py`: heuristic warnings (`empty/too_short/mostly_unchanged/md_structure_lost/possibly_truncated`); `done` kèm `warnings`; banner vàng UI (chỉ cảnh báo).
- Batch tuần tự: checkbox "bỏ qua file lỗi" (mặc định TẮT) + progress tổng.
- Prompt profiles: `GET /api/profiles` + dropdown Workspace; 3 mẫu + 2 prompt bổ sung (`qa_polish_tien_hiep.txt`, `qa_proofread.txt`).
### Fixed
- WebUI single translate tự lưu `results/` (P0.1); `run.py` đủ import (P0.2).
- Client parse chuẩn hóa cả 2 provider (JSON non-object, rỗng/whitespace parity, RequestError chung).
- `load_prompt` validate tên; `split_text` từ chối `max_chars` vô hiệu; KeyRotator dedup + message đúng SSOT.
- SSE emit chống đứt kết nối; archive verify zip trước xóa; settings XSS escape + whitelist scheme.

## [v3.1.1] - 2026-09-06 — Phase 3b stabilization (bugfixes & profiles)
### Added
- `core/quality.py`: heuristic warnings (`empty/too_short/mostly_unchanged/md_structure_lost/possibly_truncated`); `done` kèm `warnings`; banner vàng UI (chỉ cảnh báo).
- Batch tuần tự: checkbox "bỏ qua file lỗi" (mặc định TẮT) + progress tổng.
- Prompt profiles: `GET /api/profiles` + dropdown Workspace; 3 mẫu + 2 prompt bổ sung (`qa_polish_tien_hiep.txt`, `qa_proofread.txt`).
- `/api/profiles` endpoint + `wProfile` dropdown nạp preset, `applyProfile` tự c đặt prompt + extras.
### Fixed
- WebUI single translate tự lưu `results/` (P0.1); `run.py` đủ import (P0.2).
- Client parse chuẩn hóa cả 2 provider (JSON non-object, rỗng/whitespace parity, RequestError chung).
- `load_prompt` validate tên; `split_text` từ chối `max_chars` vô hiệu; KeyRotator dedup + message đúng SSOT.
- SSE emit chống đứt kết nối; archive verify zip trước xóa; settings XSS escape + whitelist scheme.
- 1 file + Gửi AI → khóa merge, mặc định tuần tự (không gộp 1 file).
- Dialog Gộp: log phiên (key/provider/model/chunks), progress chunk/attempt/key, timer clearInterval đầy đủ.
- Gộp nhiều file → log total/ngưỡng chunk + mỗi file ký tự, auto-fetch sources size.
## [3.0.0] - 2026-09-05 — Phase 3a: hoàn thiện UI
### Added
- Tách frontend: `web/css/app.css` (tokens + components) + `web/js/` theo trang (app/projects/workspace/findreplace/prompts/settings/init); MIME map css/js + test; `readSSE`/`toast()` dùng chung (xóa 3 bản copy SSE, `alert()` → toast trừ restart).
- Cards/tokens đồng bộ 4 trang (projects grid + settings 5 khối + workspace/prompts/table-minimal).
- Quản lý prompt: đổi tên, xóa, backup 1 endpoint chung vào `assets/prompts/` của dự án.
- Lưu trữ dự án: nén zip vào `workspace/archive/` + xóa gốc + dọn db.
- Hủy phiên dịch giữa chunk (không ghi output dở) + thanh tiến độ (chunk/attempt/key/file/giây chờ).
- Lịch sử chạy: `runs.file_id` + `GET /api/history` + bảng cuối trang Dự Án.
- Tìm/thay thế phạm vi tất cả file (`POST /api/find-replace`, Python re, atomic từng file).
- Nút restart server + version/giờ chạy ở sidebar + nhớ tab sau reload + health `started_at`.
### Changed
- Layout fluid khi thu gọn sidebar (bỏ `max-width`); file workspace dạng tabs Nguồn/Kết quả.
- Manifesto v2.5: chính sách lib local (§9) + restart đúng mọi launcher.
### Fixed
- Crash endpoint find-replace do `import re` cục bộ trong `do_POST` (test khóa).
- Nút restart chết lặng dưới `uv run` do `argv[0]` tương đối (absolutize + kiểm chứng live).

## [2.6.0] - 2026-09-05
### Added
- Atomic write toàn repo (`core/file_handler.atomic_write_text`): output/config/prompt không bao giờ dở dang, crash giữ nguyên file cũ.
- Error taxonomy chuẩn (`core/errors.py` + `docs/02` §5.1): 429 đổi key, timeout/5xx retry cùng key tối đa 2 attempt/chunk, 401/404/rỗng/malformed dừng ngay; SSE thêm event `progress` (chunk/attempt/key).
- Contract prefs duy nhất (`normalize_prefs`): `get_config()` và `PUT /api/settings` cùng 1 nơi validate.
- Thư mục kết quả đổi `translated/` → `results/` (chứa bản dịch, bản dịch lại, bản nâng cao…), tự migrate file cũ sang.
- Trang Dự Án chỉ còn cards dự án (số file nguồn/kết quả, tiến độ, mở workspace, xóa).
- Workspace 3 cột: danh sách file (sources/results, kéo-thả upload, đổi tên, xóa, bulk) + editor nguồn + editor kết quả; click file nguồn tự nạp kết quả cùng tên; lưu vào `results/`.
- Tìm/thay thế kiểu Sigil cho 2 editor: regex, hoa/thường, cả từ, `$1` backref, đếm, trước/tiếp.
- Endpoint file: `GET .../file`, `DELETE .../files`, `POST .../rename`, `DELETE /api/projects/{slug}` (409 khi đang dịch).
- Gộp nhiều file dịch 1 phiên (`POST /api/translate/merge`): nối file với marker `===== FILE`, chia chunk, SSE ghi rõ chunk thuộc file nào, dialog ước lượng chunk + cảnh báo quá 2 chunk; giữ tùy chọn dịch tuần tự từng file.
- Dropzone gộp thẳng vào panel danh sách file (không ô riêng).
- `/api/health` trả `version` để phát hiện server chạy code cũ.
- Nút ↻ khởi động lại server ở sidebar (đúng mọi launcher nhờ argv tuyệt đối) + hiện version/giờ chạy + nhớ tab sau reload.
- Tìm/thay thế phạm vi tất cả file (`POST /api/find-replace`, Python re, atomic write từng file).
- Workspace: tabs Nguồn/Kết quả (nút dùng chung, đổi tab là thao tác mới), layout fluid khi thu gọn sidebar.
- Manifesto v2.5: chính sách lib local (thuần trước, minimal vendor sau, cấm framework/build-chain).
### Changed
- Manifesto v2.4: chốt local-first security (FULL key hiển thị, khỏi đề xuất lại) + điều kiện READ-FIRST + contract runtime SSOT (`config/config.json`, `config/providers.json`).
- Retry giữ nguyên: mỗi key thử 1 lần/chunk với 429 (không fallback model); network/5xx retry cùng key ≤2 attempt/chunk rồi dừng.
### Fixed
- Config/PUT /api/settings không còn ghi đè giá trị sai bằng default — giữ giá trị đang lưu khi input vô hiệu.

## [3.1.0] - 2026-09-06
### Added
- `core/fileops.py`: `guard_name` (NFC + từ chối rỗng/./..), `unique_name` (`_conflict` chain), `read_text_strict`, `write_bytes_no_overwrite` (`xb` chống race); ranh giới 5 vùng trong `main.py`.
- Upload theo tab, không gate ext, raw bytes, va chạm `_conflict` + trả tên thực.
- Rename đơn va chạm `_conflict` từng bên (trả mapping); batch rename endpoint + dialog preview + auto-detect (không auto-sync, lỗi cô lập).
- Find/replace: binary skip + `skipped`/`errors`, duyệt sorted, all-or-nothing từng file.
- Toolbar SVG + status dot + selection Set + select-all-visible + khóa toolbar khi dịch.
- Find vào `<dialog>`; filter client-side (sort vi-locale, keyword, lifecycle).
- Prompt mặc định (prefs + preselect + ước lượng extras, bất khả xóa/đổi; dropdown hiện ✓ đầu list).
- Gộp 3 nút gửi thành 1 nút **Gửi AI** + dialog 2 chế độ (Gộp-chia-chunk / Tuần tự) kèm provider/model/prompt/chars/chunks; merge **tách đúng về từng file** (marker, fallback file chính, không double-count) + tự lưu `results/`.
- Nhật ký hệ thống ô đen dưới editor (timestamp, cap 200 dòng).
- Hủy **cắt cả request đang bay** (`task.cancel` + `TranslateCancelled`, abort <0.2s đã test).
- Tiêu đề cột Tập tin ngoài card; tabs wrap; tên file dài cuộn ngang khối list; info file canh phải.
- Dòng thông tin file (ký tự/từ/tokens + số file đã chọn); editor wrap mặc định + nút Wrap; link Regex Sigil.
- Prompt/Provider/Model dùng icon SVG; prompt gộp vào toolbar + extras inline.
- Project metadata (title/author/description, slug tự sinh + duy nhất) + endpoint info GET/PUT + migrate cột db; cards mới (click tên mở workspace, icon info/archive/delete, progress bar).
### Fixed (audit 3a++)
- `wBulkBar` null-throw mỗi lần tick checkbox (DOM đã xóa) — thay bằng `updSelUI`.
- Xóa chunks table mồ côi + `loadChunks` + `list_sources` + `ALLOWED_EXTS` + `prMsg` (chết sau refactor).
- Tick checkbox không re-render toàn list nữa (hết giật/mất scroll); model row gom nhóm.
### Changed
- Nguyên tắc ghi đè: tạo/đổi tên không bao giờ đè im lặng; Save/find-replace chủ động được ghi đè atomic.

## [2.5.0] - 2026-09-04
### Added
- Trang Cấu Hình 5 khối (docs/wip/SETTINGS_REDESIGN_v2.5.md): CRUD provider OpenAI-compatible, model select + lọc Bao gồm/Loại trừ (Settings + Workspace), info panel (input/output/context/quota + link docs), thinking OFF/LOW/MEDIUM/HIGH (chỉ Gemini), prefs Chunk Size/API delay/Response timeout có label.
- Backend: model metadata full object, `GET /api/settings/model-info`, quota OpenRouter (`/auth/key`), `docs_url` mặc định theo host, `api_delay_seconds` (mặc định 2s giữa chunk chống 429), thinkingBudget cho Gemini.
- Quản lý AI động: `config/providers.json` SSOT, `core/provider_manager.py` (atomic write + backup, dynamic model listing cache 5 phút, namespace validation, migration 1 chiều từ `keys.json`), endpoint `GET /api/settings/providers`, `GET /api/settings/models?provider_id=`, `POST /api/settings/save`.
### Changed
- Single-user: trang Cấu Hình hiện FULL key, sửa/xóa trực tiếp trong danh sách; model dùng select nhìn thấy được + ô custom; chưa nhập key vẫn hiện fallback kèm cảnh báo rõ (trước đây gắn nhãn `api` gây nhầm).
- `main.py` làm điểm vào chính (tự bật WebUI server). CLI giữ nguyên, không đầu tư thêm.
### Fixed
- Không còn hardcode model trong code/config — model lấy live từ API nhà cung cấp, khắc phục model cũ ngừng hoạt động.

## [1.0.0] - 2026-09-04
### Added
- Phase 1 CLI working core: chunker `smartHardSplit` (`chunker.py`), prompt engine Unicode (`prompt_engine.py`), xoay key dùng chung (`key_rotator.py`), client Gemini (`ai_client.py`) + OpenAI-compatible (`openai_client.py`) qua interface `AIClient`, cấu hình đa provider (`config.py`), đọc/ghi an toàn (`file_handler.py`), CLI `run.py` (`--provider/--model/--prompt` explicit, dừng-ngay khi lỗi), SQLite index `workspace/app.db` (`app_db.py` + `schema.sql`).
- Phase 2 Lean WebUI: `main.py` stdlib (12 endpoint JSON + SSE `chunk/done/error`, 1 phiên in-flight, lọc `assets/glossary.txt` theo chunk), UI 1 file (`web/index.html`: 4 trang, sidebar thu gọn, dual-pane sync-scroll + inline-edit).
- Tài liệu `docs/` v2.3 (manifesto, spec lõi, kế hoạch 2 phase, API contract, roadmap; OCR tạm hoãn).
