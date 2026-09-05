# 15. PHASE 3a+ — KẾ HOẠCH THỰC THI (WORKSPACE REWORK + PROMPTS)

> **For agentic workers:** REQUIRED: làm theo thứ tự Task 1 → 7, mỗi Task xong chạy test liên quan + `node --check` + checklist tay rồi mới sang Task tiếp theo.
> Bản v3 (05/09/2026): cập nhật toàn bộ review v2 của user — `(R2#)` dẫn tới số góp ý vòng 2.
> **TRẠNG THÁI: ĐÃ THỰC THI XONG (05/09/2026, 92 tests PASS).** File này giữ nguyên làm hồ sơ đối chiếu; việc tiếp theo xem `docs/16_NEXT_PHASES.md`.

**Goal:** Sửa các lệch UI ở Workspace, thêm đổi tên hàng loạt + bộ lọc hiển thị (theo docs/13, docs/14), gọn trang Prompt — xong là Workspace đủ dùng với project hàng trăm file mà không mất tối giản.

**Architecture:** Không thêm dependency; icon SVG inline + `title`; modal `<dialog>` native; filter client-side; batch rename 1 endpoint; default prompt vào prefs. Không auto-sync ở bất cứ đâu.

**Tech Stack:** giữ nguyên (stdlib + httpx + vanilla + plain `<script>`).

**Tài liệu gốc:** `docs/13_BATCH_RENAME_SPECIFICATION.md`, `docs/14_FILE_FILTER_SPECIFICATION.md`, `docs/11_*` (3a đã xong).

## 0. GIẢ ĐỊNH ĐẦU VÀO (R2#docs — đọc trước khi code)

- Phase 3a đã xong và đang chạy: endpoints upload (ghi đè lặng lẽ — SẼ ĐỔI ở Task 1), rename đơn (đổi cả 2 bên, 400 khi trùng — SẼ ĐỔI sang `_conflict`), `DELETE .../files`, `DELETE project`, archive, cancel flag giữa chunk, `progress` SSE, history, find-replace phạm vi (chưa có binary-skip), settings PUT 3 keys, prompt rename/delete/backup (chưa có default-guard).
- Plan này SỬA các hành vi trên theo spec dưới; không giả định auto-sync còn tồn tại (đã bỏ từ v2).
- Quy ước hậu tố duy nhất: **`_conflict`** (`name.ext` → `name_conflict.ext` → `name_conflict2.ext`…).

## 1. NGUYÊN TẮC GHI ĐÈ (R2#1 — quan trọng nhất, chốt trước mọi code)

- **Không ghi đè ngầm** (va chạm → `_conflict` + trả tên thực): upload, rename đơn, batch rename, archive/copy tạo file mới, mọi thao tác tạo file mới.
- **Cho phép ghi đè có chủ đích** (luôn atomic write): nút Lưu vào file, find/replace trên file đã chọn, lưu lại sau inline edit/retry, merge-save khi user đã xác nhận tên.
- Acceptance sửa thành: *"Không thao tác tạo/đổi tên nào ghi đè im lặng; cập nhật nội dung là hành động chủ động của user + atomic write."*

## Task 1 — Layout, tabs, scroll và upload

### 1a. Header 3 cột + tabs + scroll
- [x] Mỗi cột đúng 1 dòng tiêu đề cùng độ cao; subtitle duy nhất `Kéo-thả tập tin để tải lên.` (click mở chọn file, 0 nút).
- [x] CSS: `#wFiles{display:flex;flex-direction:column;height:55vh}` + `#wFileList{overflow-y:auto;flex:1;min-height:0}`.

### 1b. Upload cứng theo tab (R2#upload)
- [x] `POST .../upload?filename=&side=` (mặc định sources), **không gate ext cả 2 tab**; đọc **raw bytes** (non-text giữ nguyên bit — test hash roundtrip).
- [x] Tên qua `guard_name()` (NFC + từ chối rỗng/`.`/`..`/separator); va chạm → `write_bytes_no_overwrite()` (`"xb"`, thử tên tiếp theo — **chống race 2 request đồng thời**, R2#2); response trả **tên thực tế**, UI dùng tên đó + toast.
- [x] **Test:** text + non-text (so hash), trùng → `_conflict` → `_conflict2`, rỗng/`. `/`..`/traversal/side lạ → 400.
- **Files:** `core/fileops.py` (mới), `core/file_handler.py` (`_sanitize_name` → NFC + từ chối `.`), `main.py`, `tests/test_server.py`.

### `unique_name()` chốt (R2#2)
```python
guard_name(name): strip → NFC → từ chối rỗng/./..//,\ → trả normalized (raise ValueError)
unique_name(directory, name) -> str: guard → còn trống trả luôn;
  stem, suffix = Path.stem/suffix (book.v1.md→book.v1+.md; không ext→suffix '');
  thử _conflict, _conflict2…; check filesystem MỖI lần thử; không dùng tên chưa normalize.
```
Các case phải pass: `conflict` tồn tại → `conflict2`; stem đã có `_conflict`; không ext; nhiều dấu chấm; NFC trùng (`é` NFC vs NFD → 1 file).

## Task 2 — Toolbar SVG + hàng file + status + select-all + khóa khi dịch

- [x] Toolbar trái Bắt đầu dịch: `[rename][delete][filter][find][merge][sequential]` SVG 16px `currentColor` + `title`; xóa nút từng dòng + `wBulkBar` (giữ `wBulkMsg`).
- [x] Hàng = `[dot][checkbox][tên]`; dot xanh khi có cặp cùng tên (`R#6` gốc); `.dot/.off` CSS.
- [x] **Selection = Set tên file** (R2#8): render check từ set; đổi tab → **clear**; đổi filter → giữ set (file ẩn giữ trạng thái, file mới KHÔNG tự chọn); chọn-hết chỉ thêm file đang hiển thị; bulk hiện `N đã chọn (+M ẩn)`; bulk tác động trên set.
- [x] `window._running` disable toolbar khi dịch (rename/delete/merge/sequential/upload/start); done/error/cancel đều tắt lại. Backend 409 là chốt thật.
- **Files:** `web/index.html`, `web/css/app.css`, `web/js/workspace.js`.

## Task 3 — Find dialog + semantics khóa (R2#6)

- [x] `<dialog id="findDlg">` + icon 🔍 (Esc miễn phí).
- [x] `POST /api/find-replace`: regex lỗi → 400 chưa chạm file; `\1`; không match → `{files:{},total:0}` không ghi; binary (`read_text_strict`, `errors="strict"`) → `skipped: [...]`, **không decode-replace-rồi-ghi**; lỗi ghi 1 file → `errors:{name:msg}`, file khác vẫn chạy, vẫn 200; duyệt `sorted()`; all-or-nothing từng file (`subn` dựng xong + `atomic_write_text`).
- [x] **Test:** đủ 6 case + binary roundtrip nguyên bit khi skip.
- **Files:** `main.py`, `web/js/findreplace.js`, `tests/test_server.py`.

## Task 4 — Batch rename (R2#3, R2#preview)

- [x] Endpoint `POST .../rename-batch` `{"side","pattern","start","zeropad","old_names"}` → `{"results":[{old,new,ok,error}],"renamed":n}`:
  - **Lỗi toàn batch → 400, không chạy:** thiếu `{N}`, 0 file, pattern sinh tên trái `guard_name`.
  - **Lỗi từng file → entry lỗi, vẫn chạy phần còn lại:** nguồn đã mất, đích đã tồn tại, trùng trong batch, traversal entry.
  - Giữ đuôi old khi new thiếu `.`; **không auto-sync, không ghi đè**; dọn `_rename_file_row` file thành công.
- [x] Dialog (DOM docs/13 §2 + auto-detect): preview MỖI DÒNG old → new → trạng thái (ok / trùng batch / đã tồn tại / có counterpart — chỉ thông tin); nút xác nhận **disabled** chỉ với 4 lỗi toàn batch; 4 lỗi từng file vẫn cho chạy.
- [x] Rename đơn đổi theo: conflict → `_conflict` tự động, trả `{old, filename}`, UI toast tên thực + cập nhật file đang mở. (Không batch nào tự sinh suffix — preview phải đoán được.)
- [x] **Test:** mapping/pad/giữ đuôi; conflict cô lập; trùng nội bộ; traversal entry; thiếu `{N}`; đơn-conflict → `_conflict`.
- **Files:** `main.py`, `core/file_handler.py`, `web/js/workspace.js`, `web/index.html` (`<dialog>`), `tests/test_server.py`.

## Task 5 — Filter + lifecycle kiểm chứng (R2#8)

- [x] `_flt={sortBy,sortOrder,keyword}`; `applyFlt` (includes + `localeCompare vi`, ext 2 cấp); panel + icon phễu (click-outside + Esc); giữ khi đổi tab, reset khi đổi project; filter rỗng do keyword → `Không có file nào khớp lọc.`
- [x] **Checklist tay bắt buộc:** đổi tab giữ filter; đổi project reset; refresh vẫn áp filter; file chọn bị ẩn không bị chọn-hết tác động; đổi tab reset selection; filter đổi không tự chọn file mới.
- **Files:** `web/js/workspace.js`, `web/index.html`, `web/css/app.css`.

## Task 6 — Prompt: hàng nút + mặc định được bảo vệ

- [x] Hàng `[Đổi tên][Xóa] …(đẩy phải) [⬇ Lưu vào dự án][dropdown]` (`.row.spread`).
- [x] `default_prompt` vào prefs (mặc định `default_translation.txt`); `PUT` chấp nhận (sai → giữ cũ); `GET` trả kèm (file mất → fallback + warn).
- [x] Nút `★ Đặt mặc định`; workspace gộp select + badge vào dòng model; extras `<details>` + ước lượng ký tự/chunk (khuyên < 2000).
- [x] **Mặc định bất khả xóa/đổi tên** → 400 (sửa endpoint 3a). (R2#accept)
- [x] **Test:** roundtrip + fallback + PUT xấu + xóa/rename default → 400.
- **Files:** `core/config.py`, `main.py`, `web/index.html`, `web/js/prompts.js`, `web/js/workspace.js`, `tests/`.

## Task 7 — Concurrency + verify + đóng

- [x] **Invariant khóa (R2#concurrency) — chốt:** phiên dịch file X trong project P: sửa/xóa/rename/batch-dính-X/archive-P/delete-P → **409**; project khác → cho phép; file khác cùng project → **cho phép** (đọc/ghi độc lập, lock phiên vẫn giữ 1-phiên-chung).
- [x] **Test:** translate treo (FakeClient sleep) trong thread → DELETE/rename/batch/archive dính X → 409; file khác cùng project → 200; project khác → 200; done/error/cancel đều giải phóng (finally đã có — test cancel rồi save được).
- [x] **Cancel chốt (R2#cancel) — SỬA THEO CODE THẬT:** cancel **cắt cả request đang bay** (`_post_or_abort`: `task.cancel()` → `TranslateCancelled`, test abort <0.2s với request 5s); client nhận error event `cancelled:true` (không event riêng); chunk trong RAM **giữ trên UI cho user copy**, không ghi file. (Text cũ "chỉ dừng giữa chunk" đã lỗi thời — flag giữa chunk vẫn còn như lớp thứ hai.)
- [x] `pytest` + `node --check` + checklist trình duyệt + CHANGELOG 3a+; tick `docs/10`.

**Acceptance 3a+:** test + checklist Task 1–7 PASS; không ghi đè im lặng ở bất cứ luồng tạo/đổi tên nào; save/find-replace chủ động ghi atomic; binary nguyên bit; prompt mặc định bất khả xóa/đổi; Esc đóng dialog; filter rỗng có thông báo; 409 đúng invariant; cancel giữ nháp UI + không file dở.

---

## `core/fileops.py` — API chốt (R2#archi)

```python
guard_name(name) -> str                       # validation, raise ValueError
unique_name(directory, name) -> str           # naming, KHÔNG chạm FS ngoài exists-check
read_text_strict(path) -> str                 # I/O, raise ValueError nếu không UTF-8
atomic_write_text(target, content)            # chuyển từ file_handler sang (giữ import tương thích)
write_bytes_no_overwrite(directory, name, data) -> actual_name   # "xb" loop, chống race
```
`main.py` thêm ranh giới comment 5 vùng (validation / file operation / database / HTTP response / SSE session); mọi endpoint file gọi helper chung.

## Góp ý của tôi (giữ từ v2, đã chốt cùng bạn)

1. `_conflict` rác tên theo thời gian: chấp nhận, dọn tay (không cơ chế tự động nguy hiểm).
2. Dot "có cặp" là công cụ phát hiện lệch sau batch (không auto-sync).
3. Thay trong `.epub` để tool riêng sau này, không nhét vào endpoint text.
4. 409 backend là chốt thật; disable toolbar là UX.
