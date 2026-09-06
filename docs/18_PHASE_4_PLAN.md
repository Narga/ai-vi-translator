# 18. PHASE 4 — KẾ HOẠCH THỰC THI (Preview + Doc Viewer + Diff + đóng batch)

> **Quyết định đánh số (theo yêu cầu user):** gộp 3b-F + 3c cũ thành **Phase 4**;
> Phase 4/5 cũ đẩy thành **Phase 5/6**. Backlog chuẩn ở `docs/16_*`.
> Spec đầu vào: `docs/EDITOR_PREVIEW_AND_DOC_VIEWER_SPEC.md`
> (gốc viết cho Flask — mọi điểm dịch sang stdlib `http.server` đã ghi rõ).
> **Quyết định user đã chốt:** Preview = modal `<dialog>` on-demand;
> Viewer = tab thứ 5 riêng; vendor commit kèm vào git.
> **Quy tắc version (user chốt): Phase chỉ là thứ tự thực hiện, KHÔNG phải phiên bản.**
> Chỉ đổi version khi user yêu cầu hoặc khi có thay đổi lớn được đề xuất + duyệt.

---

## 0. PHẠM VI & NON-GOALS

**Làm trong Phase 4:**
1. Vendor `marked` + `DOMPurify` vào `web/vendor/` (manifesto §9 hạng mục cho phép).
2. Nút Preview cho 2 editor Nguồn/Kết quả (đúng giải thuật spec §1.2–1.3).
3. Tab Tài liệu: `GET /api/docs` + `GET /api/docs/content` + reader UI.
4. Diff nguồn ↔ kết quả: vendor `diff-match-patch` (manifesto §9 pre-approved),
   so sánh từng dòng (line-mode), render 2 cột + chế độ liền mạch trong `<dialog>`.
5. Toolbar regroup: preview/save per-editor (header phải), lọc/đổi tên/xóa vào
   tiêu đề Tập tin; save 2 chiều (`/api/save` thêm `side`, sources→status `new`).
6. Đóng batch (3c cũ): coverage 3 lớp + CHANGELOG `[Unreleased]` (không bump version).

**KHÔNG làm:** `GET/POST /api/docs/config` (chốt cứng whitelist, khỏi endpoint + UI
config); tóm tắt nối tiếp, model-riêng-cho-tóm-tắt, trích xuất thực thể, glossary UI
(→ hoãn, xem ROADMAP § deferred — hiệu quả thấp, chưa cần);
token/chi phí, find-replace preview-match/undo `.bak`, EPUB (→ Phase 6/backlog khi cần);
tải 100 chương, script 1-click (→ khi cần mới làm);
diff 2 cột, checkpoint/resume (mãi mãi không, trừ manifesto đổi).

---

## 1. CONTRACT THAY ĐỔI (cập nhật `docs/04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md` bảng endpoint khi code)

| Thay đổi | Chi tiết |
|---|---|
| `GET /api/docs` | Quét: root không đệ quy + `docs/` đệ quy; whitelist `.md/.txt/.html`; trả `[{path,name,ext,dir}]` |
| `GET /api/docs/content?path=` | 400 thiếu path/sai ext; 403 traversal/ngoài whitelist; 404 không tồn tại |

---

## 2. TASK A — VENDOR (làm trước, mọi task sau phụ thuộc)

- [ ] Tải `marked.min.js` + `dompurify.min.js` từ **nguồn chính thức** (CDN của dự án
      hoặc release GitHub), ghi vào CHANGELOG: tên lib + version + URL nguồn +
      `sha256` checksum. **Không chỉnh sửa trực tiếp file minified** — cần vá thì
      vá ở lớp gọi (`preview.js`/`docs.js`), không fork vendor.
- [ ] `.gitignore` hiện chặn `web/vendor/` (dòng 13) và `*.min.js` (dòng 15) →
      chỉ exception file KHÔNG đủ vì git bỏ qua cả thư mục cha. Thêm cả hai tầng:
  ```gitignore
  # vendor JS cho preview/docs — commit kèm (manifesto §9), còn lại vẫn ignore
  !web/vendor/
  !web/vendor/marked.min.js
  !web/vendor/dompurify.min.js
  ```
  Verify bắt buộc: `git check-ignore -v web/vendor/marked.min.js` phải **không in gì**
  (exit ≠ 0); `git status --short` phải hiện `?? web/vendor/`.
- [ ] `main.py::_serve_static` + `MIME_MAP` đã đủ (`.js → text/javascript`, resolve +
      `relative_to` chống traversal — `main.py:273-296) → **chỉ verify bằng test**,
      không sửa code serve static.
- [ ] **Lazy-load thật** (không `<script defer>` toàn app): helper dùng chung trong
      `web/js/app.js`, file vendor chỉ tải khi mở preview/tab Tài liệu:
  ```javascript
  const _loadedScripts = {};
  function loadScriptOnce(src) {
      if (_loadedScripts[src]) return _loadedScripts[src];
      _loadedScripts[src] = new Promise((resolve, reject) => {
          const s = document.createElement('script');
          s.src = src; s.onload = resolve;
          s.onerror = () => reject(new Error('Không tải được ' + src));
          document.head.appendChild(s);
      });
      return _loadedScripts[src];
  }
  ```
  `openPreview`/`DocManager.loadDoc` `await loadScriptOnce('vendor/marked.min.js')`
  (và dompurify) trước khi render; lỗi tải → fallback `<pre>` + toast, không crash.
- [ ] Kiểm tra vendor: `sha256sum` khớp checksum đã ghi (bắt buộc); `node --check`
      **tùy môi trường** (máy không có Node thì bỏ qua, checksum + test trình duyệt đủ).

## 3. TASK B — PREVIEW EDITOR (spec Phần 1, dịch sang `<dialog>`)

- [ ] `web/css/app.css`: copy khối `.doc-markdown` (spec §1.4-mục 3) nguyên văn.
- [ ] `web/index.html` `wTools`: thêm 2 nút 👁 (nguồn `tSrc`, kết quả `tOut`),
      icon-btn SVG cùng họ với nút hiện có:
  ```html
  <button class="icon-btn" onclick="openPreview('tSrc','Nguồn')" title="Xem trước nguồn (Markdown/HTML)">…eye svg…</button>
  <button class="icon-btn" onclick="openPreview('tOut','Kết quả')" title="Xem trước kết quả (Markdown/HTML)">…eye svg…</button>
  ```
- [ ] `web/js/preview.js` (file mới, không nhét vào `workspace.js` — hygiene test
      quét `web/js/*.js` nên tách file không ảnh hưởng test): `async openPreview(paneId,label)`:
  1. `text = $(paneId).textContent` (pane là div, **không** `.value` — khóa bằng test §8);
     rỗng → `toast('Không có nội dung để preview', true)`, dừng.
  2. Nhận dạng định dạng — đúng spec §1.2, `filename = _wsSrc || _wsRes || ''`:
     ext `.md/.markdown → markdown`; `.html/.htm/.xhtml → html`;
     ngược lại heuristic `/<!DOCTYPE html>|<html[\s>]|<body[\s>]/i` hoặc
     `≥3` thẻ `(div|p|h[1-6]|section|article|table|ul|ol)` → html, còn lại markdown.
  3. `await loadScriptOnce('vendor/marked.min.js')` (+ dompurify cho nhánh markdown).
     Markdown → `DOMPurify.sanitize(marked.parse(text))` vào `<div class="doc-markdown">`
     (spec gốc thiếu sanitize — bắt buộc vì preview HTML lạ paste từ web).
     HTML → `<iframe sandbox="" referrerpolicy="no-referrer" srcdoc="">` —
     **không** `allow-scripts/allow-forms/allow-same-origin`; **gán `srcdoc` sau
     `showModal()`** (kỹ thuật tránh timing issue của spec).
  4. Mọi chuỗi động (title, filename, subtitle) gán bằng **`textContent`, không
     `innerHTML`** — filename chứa `"'><script>` cũng câm. Quy tắc: `innerHTML` chỉ
     cho HTML đã qua sanitize; còn lại `textContent`/`esc()`.
  5. Modal = `<dialog id="prevDlg" aria-labelledby="prevTitle">` tái dùng:
      nút đóng `aria-label="Đóng xem trước"`; khi mở gọi `dlg.showModal()` +
      `focus()` vào nút đóng; khi đóng trả focus về nút 👁 đã bấm
      (giữ `document.activeElement` trước khi mở). Fallback `<pre>` khi vendor lỗi tải.
- [ ] Test tay: paste HTML truyện (có `<script>`) → script câm; filename độc
      (`a"><img src=x onerror=...>`) → hiển thị text thô; paste md dài → typography.

## 4. TASK C — DOC VIEWER BACKEND (spec Phần 2, Flask → stdlib)

- [ ] `core/fileops.py`: helper dùng chung (symlink-safe — resolve TRƯỚC khi check;
      phân biệt lỗi bằng exception riêng để handler map đúng 400/403):
  ```python
  ALLOWED_DOC_EXTS = {".md", ".txt", ".html"}
  MAX_DOC_BYTES = 2 * 1024 * 1024  # chống size abuse (đọc MAX+1 byte, vượt → 413)

  class DocForbiddenError(ValueError):
      """Nằm ngoài vùng tài liệu được phép (whitelist/symlink chui ra ngoài) → 403."""

  def resolve_doc(root: Path, rel: str) -> Path:
      """Path xấu/traversal/sai ext/không phải file → ValueError (400).
      Ngoài whitelist hoặc symlink thoát root → DocForbiddenError (403)."""
      if not rel or "\x00" in rel or "\\" in rel:
          raise ValueError("Đường dẫn không hợp lệ")
      p = Path(rel)
      if p.is_absolute() or ".." in p.parts:
          raise ValueError("Đường dẫn không hợp lệ")
      target = (root / p).resolve()  # resolve symlink TRƯỚC…
      try:
          target.relative_to(root.resolve())  # …rồi mới check vùng
      except ValueError:
          raise DocForbiddenError("Tệp tin không thuộc vùng tài liệu được cấp quyền")
      if target.suffix.lower() not in ALLOWED_DOC_EXTS:
          raise ValueError("Định dạng tệp không được hỗ trợ")
      if not target.is_file():
          raise FileNotFoundError("Tài liệu không tồn tại")
      return target

  def read_doc_limited(target: Path) -> str:
      """Đọc tối đa MAX_DOC_BYTES+1 byte (tránh race stat→read); vượt → ValueError 413.
      File local nên race khó xảy ra, nhưng đọc-capped chắc chắn hơn stat trước."""
      raw = target.read_bytes()[:MAX_DOC_BYTES + 1]
      if len(raw) > MAX_DOC_BYTES:
          raise ValueError("Tài liệu quá lớn")
      return raw.decode("utf-8", errors="replace")
  ```
- [ ] `main.py`: 2 handler trong `do_GET` (đặt cạnh block `/api/history`):
  - `GET /api/docs`: root `iterdir()` (không đệ quy) + quét `docs/` đệ quy.
    **Guard thư mục trước `rglob`:** nếu `docs/` bản thân là symlink/file resolve ra
    ngoài root → bỏ qua cả thư mục (không liệt kê gì từ nó). Mỗi file: chỉ giữ file
    có `resolve()` còn nằm trong root; lọc ext + `is_file()`; dedup `resolve()`;
    `dir=""` cho root. Whitelist chốt cứng — **không** đọc config, không endpoint config.
  - `GET /api/docs/content?path=`: qua `resolve_doc`/`read_doc_limited` → lỗi dùng đúng
    shape `{"error": msg}` như `Handler._err` hiện có (không chế shape mới):
    400 path xấu/traversal/sai ext; 403 `DocForbiddenError`
    (ngoài whitelist, symlink thoát root); 404 không tồn tại (`FileNotFoundError`);
    413 vượt `MAX_DOC_BYTES`; trả `{path, ext, content}`.
  - Tuyệt đối không serve: `.py/.json/.env`, `.git/`, `workspace/`, `config/`.
- [ ] `tests/test_docs_api.py` (mới — tách khỏi `test_server.py` cho gọn):
  `../app.db`, `%2e%2e%2f` (URL-encoded), backslash `docs\..\main.py`, path tuyệt đối,
  `config/providers.json`, `main.py` → 400 (path xấu) / 403 (`DocForbiddenError`);
  symlink file trong `docs/` trỏ ra ngoài → 403; `docs/` bản thân là symlink ra ngoài
  → list bỏ qua cả thư mục; thư mục (`path=docs`) → 400 (không ext, input xấu);
  file > cap → 413; `README.md` → 200 đúng shape.

## 5. TASK D — DOC VIEWER FRONTEND (tab thứ 5)

> **Bất biến an ninh (ghi để sau này không ai "sửa" nhầm):**
> Doc Viewer **chỉ đọc source, không render HTML** — `.html` hiện như text trong
> `<pre>` escape. Render HTML chỉ tồn tại ở Preview editor, trong `iframe sandbox`.
> Ai đổi viewer sang render HTML trực tiếp là mở XSS.

- [ ] `web/index.html`: sidebar thêm `📚 Tài liệu` + `<section id="v-docs">`
      (layout spec §2.5: aside 320px search + list, main reader title/path/content);
      `app.js` nhớ tab (cơ chế hiện có tự nhận thêm tab).
- [ ] `web/js/docs.js` (mới, bám spec `DocManager` nhưng đổi `alert` → `toast`,
      bỏ class Tachyons của spec gốc, dùng `.card/.btn/.input` của `app.css`):
      `loadDocList / filterList (offline trên _files) / loadDoc` —
      `.md → marked+DOMPurify` (lazy qua `loadScriptOnce`), còn lại → `<pre>` escape;
      **title/path/filename gán bằng `textContent`**, không `innerHTML`.
- [ ] Acceptance: mở README + `docs/` nội bộ không rời app; search filter không gọi API.

## 6. TASK F — DIFF NGUỒN ↔ KẾT QUẢ (từng dòng, 2 cột / liền mạch)

> **Vì sao vendor thay vì viết tay:** so sánh nguồn↔bản dịch là 2 văn bản gần như
> khác hoàn toàn (khác ngôn ngữ) — thuật toán tự viết (Myers/LCS) dễ blowup hiệu năng;
> `diff-match-patch` có `Diff_Timeout` + line-mode đã kiểm chứng, đúng hạng
> manifesto §9 pre-approved (ghi 1 dòng CHANGELOG). Chỉ `diff.js` dùng, gỡ là xong.

- [ ] Vendor `web/vendor/diff_match_patch.js` (Google raw build — global sẵn, không sửa
      file): nguồn `https://raw.githubusercontent.com/google/diff-match-patch/master/javascript/diff_match_patch_uncompressed.js`,
      sha256 `9a79cf031ac7c2e366416181051acb3e6d2cacf79c5354148f4c71ea20c7e4a3`
      (Apache-2.0 — permissive, ghi CHANGELOG; 78KB > ngưỡng 50KB của §9-điểm 2
      nên đi theo cửa 2b minimal-lib-có-lý-do này).
- [ ] `web/js/diff.js`: `openDiff()` (đọc `textContent` 2 pane, cap 500KB, lazy-load vendor)
      → `diffRows()` (`diff_linesToChars_` + `diff_main` + `diff_charsToLines_`,
      `Diff_Timeout=2`, trả `[{t:'='|'-'|'+', a, b, text}]`)
      → `paintDiff()`: side gom cặp -/+ liền kề thành 1 hàng 2 cột (như Novel Translator),
      uni render liền mạch có prefix `−`/`+`; số dòng + đếm khác biệt; render DOM +
      `textContent` từng dòng (không innerHTML chuỗi động).
- [ ] `index.html`: nút ⇄ ở header Kết quả + `<dialog id="diffDlg">`
      (`aria-labelledby`, toggle 2 cột/liền mạch, focus in/out như `prevDlg`).
- [ ] `app.css`: `.diff-tbl` + `.diff-del/.diff-add/.diff-empty`.
- [ ] Test: hygiene `test_diff_wiring_and_safety` (script tag, dialog a11y, vendor lazy,
      line-mode, timeout, không innerHTML raw, không iframe).

## 7. MỤC HOÃN — TÓM TẮT NỐI TIẾP (đưa vào roadmap, chưa làm)

> **Quyết định user:** hiệu quả thấp so với chi phí (~2x request/chunk), chưa cần —
> hoãn như OCR. Phân tích đầy đủ chuyển sang ROADMAP § deferred để sau này
> không phải nghiên cứu lại. Tóm tắt nội dung đã phân tích:
> thiết kế cùng-model (~50 dòng: helper `_summarize_chunk` + vá `{{previous_summary}}`
> vào prompt chunk kế sau mỗi chunk, lỗi tóm tắt không dừng phiên, tắt ở merge mode);
> model-riêng +~120 dòng (~3x: resolve + build client thứ hai, 2 select explicit,
> quy lỗi theo provider, cờ CLI, tests ×2). Seam giữ cửa: helper nhận client bất kỳ.

## 7. TASK E — BỔ SUNG COVERAGE BATCH (không phải tính năng mới)

> **Thống nhất trạng thái (đã kiểm chứng code):** logic skip-error ĐÃ CÓ
> (`sendSkipErr` + `wsBulkTranslate`, `workspace.js:185,203,210`); thứ còn thiếu duy
> nhất là **test**. Task này chỉ bổ sung coverage, không mô tả như tính năng chưa làm.
>
> **Ranh giới trung thực (review):** logic skip nằm ở frontend `wsBulkTranslate`,
> test Python thuần KHÔNG chạm được checkbox/thứ tự gọi/hành vi dừng-bỏ qua.
> Nên chia 3 lớp, không gọi gộp là "integration test backend":
> 1. **Python** (`tests/test_server.py`): test API từng file — dịch tuần tự 3 file
>    (mock AI, file giữa lỗi) → file 1 đã lưu `results/`, file lỗi không file dở,
>    file 3 nguyên trạng thái cũ. Khóa hành vi server, không khẳng định gì về JS.
> 2. **Node tối thiểu, không framework** (`tests/test_batch_skip.mjs`, chạy
>    `node tests/test_batch_skip.mjs`): tách hàm thuần `batchOnFileError(skipErr,
>    cancelled) → 'skip'|'stop'` ra `web/js/batch.js` (dùng chung cho cả 2 điểm
>    quyết định trong `wsBulkTranslate`), test ma trận 2×2 bằng `node:assert`.
>    Không jsdom/harness DOM — chỉ logic thuần.
> 3. **Manual acceptance** (checklist tay, không tự động): tick skip TẮT → dừng đúng
>    file lỗi; BẬT → bỏ qua đủ 2/3 file + toast. Ghi kết quả vào plan khi làm.

- [ ] Full `pytest -q` xanh + `node tests/test_batch_skip.mjs` xanh; CHANGELOG ghi dưới
      `[Unreleased]` (**không** bump version — phase ≠ version);
      cập nhật `docs/04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md` bảng endpoint
      + `docs/16_*` tick acceptance.

## 8. MA TRẬN TEST (thêm mới, mock/fake, không gọi API thật)

| File | Case |
|---|---|
| `tests/test_docs_api.py` (mới) | list root+docs; traversal raw + URL-encoded + backslash + tuyệt đối → 400; symlink file chui ra ngoài → 403; `docs/` là symlink ra ngoài → list bỏ qua; thư mục → 404; vượt size cap → 413; `README.md` → 200 đúng shape (`{"error"}` khi lỗi) |
| `tests/test_frontend_hygiene.py` (bổ sung — khóa theo file mới, không cấm `innerHTML` chung chung vì `workspace.js` dùng `innerHTML+esc()` hợp lệ) | `preview.js`/`docs.js`: 2 nút 👁 `onclick` trỏ đúng `tSrc`/`tOut`; `prevDlg` + `aria-labelledby` tồn tại; pane đọc bằng `textContent` (không `.value`); nhánh markdown chứa `DOMPurify.sanitize(marked.parse(`; nhánh html chứa `sandbox=""` và vắng `allow-` trong file mới; không có pattern gán raw filename/path/title vào `innerHTML` (regex targeted trên 2 file mới, không quét toàn repo) |
| `tests/test_server.py` + `tests/test_batch_skip.mjs` | Task E 3 lớp: API từng file / decision matrix node (`node:assert`, không framework) / manual checklist |

## 9. THỨ TỰ COMMIT (tách để bisect, theo tiền lệ `docs/17_*` §11.5)

0. **Bước 0 (trước Commit A):** cập nhật trạng thái batch trong `docs/16_*`
   (tính năng đã có, chỉ thiếu test) để tài liệu hết tự mâu thuẫn.
1. Commit A (vendor + checksum + `.gitignore` exception + `loadScriptOnce` + test).
2. Commit B (preview editor + CSS + hygiene test).
3. Commit C (docs backend + `resolve_doc` + test bảo mật).
4. Commit D (docs frontend tab5).
5. Commit F (diff: vendor dmp + `diff.js` + dialog + test).
6. Commit G (toolbar regroup + save 2 chiều + test).
7. Commit E (batch coverage + docs + CHANGELOG, không bump version).

## 10. ACCEPTANCE PHASE 4 (DoD)

- [ ] Preview md/html đúng cả 2 editor, script lạ câm, offline chạy.
- [ ] Tab Tài liệu đọc được README + `docs/`, search offline, traversal bị chặn (test);
      tên file dài cuộn ngang cả khối, sidebar thu gọn vẫn dùng hết khoảng trống.
- [ ] Diff nguồn↔kết quả: từng dòng đúng, 2 cột + liền mạch chuyển qua lại được.
- [ ] Save per-editor: nguồn→`sources/` (status `new`), kết quả→`results/` (`done`).
- [ ] Batch 3-file test xanh cả 2 chế độ skip; `pytest` toàn xanh; CHANGELOG `[Unreleased]` cập nhật.
