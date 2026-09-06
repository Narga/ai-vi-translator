# 17. PHASE 3b — KẾT QUẢ REVIEW NGOÀI, PHẢN BIỆN & KẾ HOẠCH KHẮC PHỤC

> **Nguồn review:** `docs/wip/2026-09-05_BAO_CAO_REVIEW_TOAN_DIEN_VA_DE_XUAT_TOI_UU.md`
> (Antigravity AI) và `docs/wip/2026-09-05_CODEBASE_REVIEW_AND_OPTIMIZATION_REPORT.md`.
> **Phương pháp:** mọi cáo buộc đã được đối chiếu trực tiếp với code hiện tại trên branch
> `phase-2.5` (92 tests PASS) trước khi kết luận — không tin mù quáng, kể cả review ngoài.
> **Nguyên tắc:** chỉ sửa cái đã chứng minh sai; cái đúng thì giữ; cái thổi phồng thì bác kèm bằng chứng.

---

## 1. BẢNG KIỂM CHỨNG (claim → kết luận + bằng chứng)

| # | Cáo buộc | Kết luận | Bằng chứng |
|---|---|---|---|
| P0.1 | WebUI đơn file không ghi output, status kẹt `translating`, log `ok` | **ĐÚNG — nghiêm trọng nhất** | `main.py` `_handle_translate_sse`: sau `_run_chunks` chỉ `_upsert_file(..., "translating")` + `log_run(ok)` + `emit(done)`, **không gọi `save_output`**. Merge (`_handle_merge_sse`) thì có lưu → lệch pha 2 luồng |
| P0.2 | `run.py` thiếu import → `NameError` | **ĐÚNG** | `run.py:81` dùng `SafeFileHandler`, `run.py:138` dùng `atomic_write_text`; top-import (dòng 8–15) không có cả hai, không có import cục bộ |
| P0.3a | Log `ok` trước khi ghi file xong | **ĐÚNG** (cả `run.py` CLI và WebUI) | Thứ tự hiện tại: dịch xong → log `ok` → (WebUI: không ghi gì; CLI: ghi sau log — đọc `run.py` sẽ thấy `log_run(ok)` trước/sau cần chuẩn hóa) |
| P0.3b | `size_bytes` ước lượng vô nghĩa (`len(name)+chars`) | **ĐÚNG** | `main.py:69`: `len(filename.encode)+chars`. Sau khi atomic write xong, lấy `len(content.encode())` là chính xác, 0 chi phí |
| P1.3 | `load_prompt()` không validate tên | **ĐÚNG** | `prompt_engine.py:56` nối path trực tiếp; `delete/rename` thì có `_check_name` |
| P1.4 | `split_text(max_chars<=0)` đệ quy vô tận | **ĐÚNG** | `chunker.py:38` không guard; `max_chars=0` → `cut=0` → `part2=text` → `RecursionError` |
| P1.5 | `contenteditable` dính rác rich-text khi paste | **ĐÚNG về nguy cơ** | `index.html:110` `tOut` contenteditable, không có handler `paste` nào trong `web/js/` |
| KeyRotator msg | Thông báo còn ghi `config/keys.json` cũ | **ĐÚNG** | `key_rotator.py:21` |
| P2.1 | Test sandbox bị proxy chặn | **ĐÚNG một nửa** | Repo không có `pytest.ini`/`conftest.py` cấu hình `no_proxy`; đây là vấn đề môi trường, không phải bug code — sửa bằng doc/env, không sửa logic test |
| P1.2 | Cần class `TranslationError` có cấu trúc | **BÁC (xem §2.4)** | Taxonomy đã tập trung ở `classify()`; SSE `progress` đã mang attempt/key/file; thêm class = thêm API surface không ai tiêu thụ |
| P1.1/P1.3-shared | Tách `main.py` thành `server/routes_*.py` hoặc `translation_flow.py` | **BÁC tách lớn, CHẤP NHẬN tách mỏng (xem §2.3)** | Single+merge đã dùng chung `_run_chunks`; phần lệch thật chỉ là 3 dòng persist cuối — không đáng 1 module mới + import graph mới |
| 4.4-per-chunk-client | Mỗi chunk tạo mới `AsyncClient` là vấn đề | **BÁC** | File thường 2–3 chunk; tạo mới mỗi chunk còn **cách ly lỗi tốt hơn** (đúng failure policy). Không tối ưu thứ không đo được |
| 4.4-key-URL | "Không nên log URL có key" | **BÁC mức P-liệt-kê** | Không có `logger.*url` nào trong code; `e.response.text` đến từ Google, không chứa key ta. Mức rủi ro ≈ 0 |
| 4.4-raw-exceptions | `KeyError`/`AttributeError` từ JSON sai cấu trúc | **ĐÚNG một nửa** | Gemini: `candidates[0].get(...)` — phần tử non-dict gây `AttributeError` thô; OpenAI đã check rỗng. Cần chuẩn hóa cả hai (test khóa) |
| 4.4-empty-parity | Gemini thiếu check rỗng như OpenAI | **ĐÚNG** | Gemini `return parts[0]["text"]` không `.strip()`; OpenAI có |
| 4.6-route-paths | Route tự nối path, không qua helper | **ĐÚNG hình thức, THẤP rủi ro thực** | Các nối path đều dùng hằng `"sources"/"results"/"assets"` sau `get_project_dir()` đã sanitize — an toàn nhưng nên gom helper cho đồng nhất |
| 4.6-archive | Zip xong xóa gốc, không verify | **ĐÚNG** | `file_handler.py:110-121`: `make_archive` → `rmtree` ngay, không kiểm tra zip |
| 4.6-read-modify-write | `errors="replace"` khi ghi lại làm hỏng binary | **ĐÚNG nguyên tắc, code HIỆN TẠI đã đúng** | `find-replace` đã dùng `read_text_strict` + skip. Cần ghi nguyên tắc vào doc để luồng sau không tái phạm |
| 4.7-db | Thiếu context manager/index | **ĐÚNG mức vệ sinh** | Mở/commit/close thủ công khắp nơi; `runs` không index; không duration/chunks (bỏ qua — history view không cần) |
| 4.8-CLI | `default_prompt` hardcode; key lưu `keys.json`; lỗi project-mode thiếu `file_id` | **ĐÚNG 2/3, SAI 1**: `--prompt` default cứng + log error thiếu `file_id` là thật; **lưu key qua `providers.json` manager là ĐÚNG rồi** (`run.py` gọi `update_provider_keys_and_model`) — reviewer đoán sai điểm này |
| 4.9-restart-load | Chưa test restart khi đang dịch | **ĐÚNG là thiếu test** | `execv` thay process giữa phiên: lock trong RAM nên process mới sạch; SSE cũ đứt; output dở không ghi (atomic). Hành vi chấp nhận được — cần test + document, không cần sửa code |
| 4.9-SSE-disconnect | Client ngắt giữa SSE | **ĐÚNG một nửa** | Không có `try/except BrokenPipeError` quanh `emit()`; `BrokenPipeError ⊂ ConnectionError` nên bị bắt nhầm thành "lỗi mạng" + emit lần 2 ném ra thread (lock vẫn được `finally` giải phóng — không deadlock, chỉ log rác) |
| 4.9-provider-mismatch | Khác biệt `provider_id` UI vs `active_id` | **CHƯA CÓ BẰNG CHỨNG** | `_resolve_target` dùng explicit `provider_id` hoặc active — nhất quán. Không sửa khi không có repro |
| XSS settings | `p.id`/`p.name` và `quota_url` vào `innerHTML` không escape | **ĐÚNG, mức thấp** (single-user local) | `settings.js`: option value/name từ form add-provider; `quota_url` từ API NCC. `findreplace` đã escape đúng. Sửa nhỏ, chi phí thấp |
| 4.5-KeyRotator | Key trùng/edge cases | **ĐÚNG là thiếu test** | Dedup key trùng lúc init để "mỗi key 1 lần/chunk" có nghĩa thực tế + thêm test biên |
| P1.6-cancel-tests | Thiếu test delay-cancel, after-response, restart-during-cancel, lock release | **ĐÚNG một nửa** | Đã có: idle, between-chunks, abort-mid-request (<0.2s), concurrency 409 scope. Thiếu: cancel-trong-delay, restart-khi-đang-dịch, `active_job`/lock sau mọi đường |

---

## 2. PHẢN BIỆN CHI TIẾT (nơi tôi không đồng ý với review ngoài)

### 2.1. P0 của họ là đúng — nhưng nguyên nhân cốt lõi khác với mô tả
Reviewer mô tả P0.1/P0.2 như "thiếu kiểm thử". Nguyên nhân sâu hơn: **luồng single được viết trước, luồng merge viết sau có autosave, không ai quay lại đồng bộ single** (lệch pha tiến hóa, không phải thiếu năng lực). Bằng chứng: merge lưu đúng, single không — cùng 1 tác giả, 2 thời điểm. Fix đúng không phải "thêm test" mà là **gộp bước persist thành 1 helper dùng chung** (§4 Task A), test chỉ khóa lại.

### 2.2. Bác tách module lớn (P1.1/P1.3-shared)
`main.py` ~1000 dòng là xấu về thẩm mỹ nhưng **mọi route đã tuân thủ ranh giới comment 5 vùng + helper chung** (`fileops`, `_upsert/*`, `_resolve_target`, `_run_chunks`). Tách thành `server/routes_*.py` với stdlib `http.server` (không có router, phải tự dispatch) chỉ chuyển `if/elif` từ file này sang file khác + thêm import graph — rủi ro hồi quy cao, lợi ích ≈ 0 cho team 1 người. **Chốt:** chỉ tách helper `persist_output()` (save + upsert + log đúng thứ tự) dùng chung single/merge; CLI giữ flow riêng vì khác ngữ cảnh (in terminal, không SSE).

### 2.3. Bác class `TranslationError` (P1.1)
SSE `progress` đã mang `{attempt, key, file}`; taxonomy đã tập trung ở `classify()`; message lỗi hiện tại đủ cho UI hiển thị. Class mới bắt mọi raise-site phải bọc lại — đụng ~10 chỗ để phục vụ nhu cầu chưa ai gọi. **Chốt:** không thêm type; nếu UI sau này cần dữ liệu có cấu trúc khi lỗi, quay lại đề xuất này.

### 2.4. Bác tối ưu per-chunk client + key-URL (4.4)
Không đo, không sửa. Ghi vào đây để lần sau không ai "phát hiện lại".

### 2.5. Bác localStorage cho prompt profile (reviewer §5.2 mục 6)
Reviewer đề xuất lưu checkbox tick vào `localStorage` thay vì JSON. **Sai với dự án này:** localStorage không backup cùng repo, mất khi đổi trình duyệt/profile, không đồng bộ với file `prompts/*.txt` (quy ước §6.4 manifesto: "prompt mới = thêm file"). **Chốt:** profile = file JSON trong `prompts/profiles/` như `docs/16` đã định.

### 2.6. Đồng ý có điều kiện: contenteditable (P1.5)
Không đổi sang `textarea` (find/replace highlight `<mark>` đang sống nhờ contenteditable). Fix đúng bệnh: handler `paste` chỉ chèn plain-text (~8 dòng JS). Rẻ, giữ nguyên mọi thứ khác.

---

## 3. NGUYÊN NHÂN CỐT LÕI (tại sao lọt nhiều lỗi đúng cùng lúc)

1. **Lệch pha tiến hóa:** single-flow (cũ) vs merge-flow (mới, có autosave) không được đồng bộ lại.
2. **Test khóa hành vi sai chỗ:** 92 tests nhưng thiếu integration trên chính đường thành công (single-save, CLI end-to-end) — test đếm số lượng, không đếm đường đi quan trọng.
3. **Docs viết trước code:** hồ sơ "hoàn thành" được chốt khi code chưa qua smoke test runtime (báo cáo ngoài §5.1 nói đúng).
4. **Refactor dở dang:** helper chung tồn tại (`_run_chunks`, `fileops`) nhưng persist-cuối-phiên chưa được gom — đúng chỗ reviewer gọi là "thắt nút".

---

## 4. KẾ HOẠCH KHẮC PHỤC PHASE 3b (tối thiểu, có test khóa từng mục)

### Đợt A — Hotfix P0 (làm trước, không tính năng mới)
- [x] **A1. Single autosave:** `_handle_translate_sse` sau `_run_chunks` → `output = "\n\n".join(outs)` → `fh.save_output` → `_upsert_file(..., "done")` → `log_run(ok)` → `emit done`. Dùng chung helper mới `persist_output()` (single + merge).
- [x] **A2. Sửa import `run.py` (GIỮ CLI — quyết định cuối §10.2):** CHỈ thêm 2 dòng import còn thiếu (mã mẫu §11.2). Không đụng default_prompt/file_id/helper DB ở đây — các mục đó thuộc C-CLI riêng để revert được độc lập.
- [x] **A3. Thứ tự an toàn:** save → upsert(`done`, `len(content.encode())` thay ước lượng vô nghĩa) → log → emit. Ghi file lỗi → run `error`, output cũ nguyên (atomic có sẵn).
- [x] **A4. Defensive nhỏ:** `load_prompt()` gọi `_check_name()` đầu tiên; `split_text` guard `max_chars<=0 → ValueError`; KeyRotator message → `config/providers.json`; dedup key trùng lúc init.
- [x] **A5. Emit chống đứt SSE:** bọc `wfile.write/flush` trong `try/except (BrokenPipeError, ConnectionResetError)` → dừng lặng lẽ (lock vẫn `finally` giải phóng).

### Đợt B — Khóa contract bằng test (song song A)
- [x] **B1. Integration:** CLI direct + project (mock AI, tmp fs): output tồn tại + đủ chunk + lỗi chunk 2 → không output mới; WebUI single: `results/` tồn tại + đủ nội dung; lỗi → không file dở; cancel giữa request + giữa delay + sau response (không ghi).
- [x] **B2. Chunker property:** mọi chunk `<= max_chars`; nối lại (strip) khớp input theo contract whitespace; Unicode; không khoảng trắng; đoạn dài vô ngắt.
- [x] **B3. Client lỗi:** JSON non-object, candidates sai kiểu, parts rỗng, text rỗng/whitespace (cả 2 client parity), 408/5xx đủ số lần, 4xx dừng ngay, `httpx.RequestError` lạ → lỗi chuẩn (không raw traceback), no-fallback, no-key-trong-log (assert message không chứa key).
- [x] **B4. KeyRotator biên:** trùng/whitespace/rỗng/`try_next_key` sau hết/tái dùng key chunk trước.
- [x] **B5. File ops:** find-replace lỗi ghi cô lập (đã có? kiểm tra lại); archive verify zip trước `rmtree`; restart-args tuyệt đối (đã có); `no_proxy` cho localhost trong `tests/conftest.py` mới (sửa P2.1 đúng chỗ: env test, không đụng logic).
- [x] **B6. XSS settings:** escape `p.id/p.name/quota_url` (test assert không còn HTML thô).

### Đợt C — Ổn định mỏng (sau A+B xanh)
- [x] `persist_output()` dùng chung (đã làm ở A1 — kiểm tra lại merge dùng cùng hàm).
- [x] Paste-plain-text cho `tOut` (~8 dòng JS, test tay).
- [x] `app_db`: helper `db()` contextmanager cho code mới (không rewrite hàng loạt); index `runs(started_at)`; KHÔNG thêm cột/bảng.
- [x] `run.py`: GIỮ (quyết định cuối §10.2) — chi tiết tách riêng ở **C-CLI** dưới đây, không gộp vào A2.
- [x] **C-CLI. Cải tiến CLI (riêng 1 commit, revert được độc lập với hotfix):** `--prompt default=None` → fallback `cfg.default_prompt`; log error project-mode kèm `file_id` (qua `app_db.file_id` mới, KHÔNG import từ `main` để tránh circular); chuyển `_file_id`/`_upsert_file` dùng chung vào `core/app_db.py`; giữ direct-mode ngoài workspace (không áp restriction nhầm). Mã mẫu §11.2 + §11.2b.
- [x] Archive: verify zip (`isfile + size>0`, brutal nhưng đủ) trước `rmtree`; lỗi → raise, giữ thư mục gốc.
- [x] Routes nối path trực tiếp → qua `get_side_dir(slug, side)` mới trong `file_handler` (4 chỗ: files/file/find-replace/upload-listing).
- [x] Restart-khi-đang-dịch: document hành vi (process mới sạch, SSE cũ đứt, output dở không ghi) + test mức args; không test execv thật trong pytest.

### Đợt D — Tính năng 3b (chỉ sau A+B xanh, theo litmus; Glossary UI ĐÃ HOÃN theo §6-Q4)
- [x] Heuristic warnings sau `done` (rỗng/ngắn/trùng/mất MD/cắt dở) + banner vàng; unit từng heuristic.
- [x] Batch "bỏ qua file lỗi" (checkbox, mặc định TẮT) + progress tổng + test batch 3 file.
- [x] Prompt profile **file JSON** (bác localStorage — §2.5), 3 preset mẫu.
- [x] KHÔNG làm ở 3b: Glossary UI (hoãn), CodeMirror, preview realtime (chỉ nút "Xem thử" on-demand nếu rẻ), EPUB (sang 4), checkpoint/resume/queue (mãi mãi không, trừ manifesto đổi).

---

## 5. NÂNG CẤP ĐỀ XUẤT THÊM (của tôi, ngoài 2 báo cáo)

1. **Một nguồn version duy nhất:** `core/__init__.py: __version__ = "3.1.0"`; `server_version`, `/api/health`, test version, CHANGELOG đều đọc từ đó. Hết lệch version vĩnh viễn (báo cáo ngoài §5.3 chỉ đòi "kiểm tra", tôi đề xuất triệt tiêu nguyên nhân).
2. **Reindex nhẹ:** `POST /api/projects/{slug}/reindex` — quét đĩa dựng lại rows `files` (phục hồi sau crash/db lệch). Không checkpoint, chỉ đồng bộ index (đúng tinh thần "DB là index").
3. **Trạng thái `error`/`cancelled` cho `files.status`** (reviewer §7.2 đề xuất — tôi đồng ý, rẻ): `done` chỉ sau khi file tồn tại; lỗi → `error`; hủy → giữ trạng thái cũ (không ghi gì thêm).
4. **Không làm:** TranslationError class, tách `server/`, ORM, context manager rewrite hàng loạt, duration/chunks columns, mở thư mục OS-gated (khác OS khác lệnh — để sau).

---

## 6. CÂU HỎI CẦN BẠN QUYẾT (chặn khởi công)

> **Quyết định user (06/09/2026) — giữ nguyên câu hỏi gốc làm tham chiếu, quyết định ghi rõ dưới mỗi mục:**

1. **Autosave single có làm mất nút Save tay không?** (Đề xuất: không — autosave ghi file, Save giữ để lưu bản đã inline-edit.)
   → **QUYẾT ĐỊNH: Giữ nút Save tay.** Dùng khi sửa nội dung trong editor cần lưu thủ công (ghi đè chủ đích, đã có policy).
2. **`TranslationError` có cấu trúc: bỏ hẳn (đề xuất tôi) hay giữ backlog?**
   → **QUYẾT ĐỊNH: Không tạo class.** Chuyển vào `docs/ROADMAP.md` để tham khảo sau.
3. **Tách module: chỉ `persist_output()` (đề xuất tôi) hay cả `translation_flow.py`?**
   → **QUYẾT ĐỊNH: Làm `persist_output()` trước.** `translation_flow.py` chỉ tách khi phát hiện lần thứ 2 phải sửa cùng logic ở 2 nơi (quy tắc "rule of three" thu gọn) — xem §10.2.
4. **Glossary UI đặt ở Workspace tab mới hay nhét vào dialog/tab sẵn có?**
   → **QUYẾT ĐỊNH: Chưa làm, để lại sau.** Giữ backend `_glossary_for_chunk` nguyên; không thêm UI 3b.
5. **Reindex endpoint + version-source-duy-nhất: duyệt cả hai?**
   → **QUYẾT ĐỊNH: Đồng ý tất cả các mục đề xuất thêm** (mục 5).

## 7. LỊCH SỬ — ĐỀ XUẤT XÓA CLI ĐÃ BỊ THAY THẾ (GIỮ `run.py` — xem §10.2)

> **Không thực hiện bất kỳ checklist nào trong mục này. Checklist chỉ được giữ lại để audit lịch sử.**

## 10. Ý KIẾN CỦA TÔI VỀ §9 + QUYẾT ĐỊNH CHỐT (06/09/2026, sau review)

> Quy tắc của turn này: nội dung cũ (§1–§9) giữ nguyên làm tham chiếu; mọi thay đổi
> quyết định chỉ ghi ở §10 này + annotation tại chỗ (banner `QUYẾT ĐỊNH CUỐI`).

### 10.1. Về §9.1 (tách xóa CLI khỏi hotfix P0): ĐỒNG Ý toàn bộ

§7 của tôi vội vàng: ra quyết định vòng đời trong cùng turn review, trước cả phản biện §8
của Antigravity. Đúng ra §7 chỉ được là "đề xuất", không phải "quyết định". Từ nay: quyết định
đổi contract (Manifesto §0) phải đứng riêng 1 turn review, không gộp vào turn sửa lỗi.

### 10.2. Về §9.2 (hai nhánh CLI): chọn NHÁNH GIỮ CLI — và đây là quyết định CUỐI

Bổ sung 2 bằng chứng mà cả §8 và §9 đều chưa nêu:

1. `tests/test_file_handler.py:64` đã `from run import main` thành công → module `run.py`
   **import được bình thường**; `NameError` chỉ nổ ở 2 nhánh runtime thiếu import. Lỗi nhỏ hơn
   vẻ ngoài của nó — không đáng để xóa cả file.
2. CLI là entry point duy nhất cho cron/script ngoài (`run.py input output`, direct-mode
   file ngoài `workspace/`). WebUI không thay thế được, xóa là mất năng lực thật.

**QUYẾT ĐỊNH CUỐI: GIỮ `run.py`.** Hệ quả (đã cập nhật trong file này):
- §7 chuyển thành lịch sử bị thay thế (banner bên dưới), không xóa nội dung.
- Task A2 khôi phục: sửa import + test CLI (B1 giữ nguyên test CLI).
- Đợt C khôi phục các mục `run.py` (bỏ gạch ngang).
- ROADMAP §7 revert dòng CLI về "`run.py` CLI giữ nguyên".

### 10.3. Về §9.3 (contract `persist_output` 8 điểm): ĐỒNG Ý toàn bộ + 2 bổ sung

1. **Exception mapping:** helper KHÔNG swallow — `OSError`/`ValueError` từ `save_output`
   propagate ra caller; caller map: single/merge `except OSError as e → log error + emit error`
   (đã có `except` tương ứng, chỉ cần không thêm `except` mới nuốt lỗi). Không emit `done` khi helper raise.
2. **Test seam:** helper dùng `_upsert_file`/`log_run` module-level của `main.py` + `fh.save_output`;
   test monkeypatch 3 điểm này (pattern đã có trong `test_server.py` cho `build_client`).
3. Câu §9.3 bị cắt dở ("Signature có thể dùng làm contract ban đầu:") được hoàn thiện bằng
   signature ở §8.3 — tôi **chấp nhận nguyên văn**, xem mã mẫu §11.1.

### 10.4. Về §8.4 (reindex trong `GET /files`) và §8.5 (`get_side_dir` trước Glossary)

- **Đồng ý cả hai.** Bổ sung guard chống ghi đè: reindex chỉ `INSERT OR IGNORE` + `UPDATE status`
  cho row đã có? Không — giữ đơn giản: `INSERT OR IGNORE` cho file thiếu row; không đụng row
  đã có (tránh ghi đè `status=done` thành `new`). Chi tiết ở mã mẫu §11.6.
- Thứ tự: `get_side_dir()` làm trong Đợt C trước mọi việc chạm `assets/` (Glossary ở Đợt D).

### 10.5. Về XSS settings (§8.1 xác nhận + tôi kiểm thêm)

`settings.js:8-9` (`p.id`/`p.name`), `:18` (`value="${p}"` prompt name — `_check_name` cho phép `"`),
`:85` (`quota_url`) đều chưa escape. `prOpt` (:15) đã escape đúng — làm mẫu. Fix: bọc `esc()`
3 chỗ (mã mẫu §11.7). Mức thấp (single-user local) nhưng chi phí ~3 dòng nên làm luôn ở Đợt A.

**Lý do:** CLI (`run.py`) lỗi thời, trùng lặp 100% năng lực WebUI, là nguồn P0.2 và hàng loạt edge-case audit (default_prompt hardcode, file_id thiếu, direct-mode restriction). Single-user local dùng WebUI duy nhất.

- [ ] Xóa `run.py` + test CLI (nếu có) + mọi ref CLI trong docs (`00` §2A `run.py`, `02` §2–§3 quy tắc `run.py`, `04` ví dụ CLI, `12` §1 lệnh CLI?, README Phase 1).
- [ ] `build_client()` chuyển vào `core/` (dùng chung WebUI single/merge) hoặc giữ trong `main.py` — quyết khi tách `persist_output()` (mục 6.3).
- [ ] Manifesto §1/§2/§3: sửa "UI / CLI" → "UI (WebUI)"; failure policy giữ nguyên cho WebUI.
- [ ] Acceptance: `pytest` PASS, `grep -rn "run\.py" docs/ core/ main.py tests/` trống (trừ CHANGELOG lịch sử).

---

## 8. PHẢN BIỆN CỦA ANTIGRAVITY AI — ĐỌC VÀ ĐÁNH GIÁ KẾ HOẠCH (06/09/2026)

> **Phương pháp:** Đọc lại code trực tiếp để xác nhận mọi nhận định trong §1–§7. Chỉ tranh luận nơi có bằng chứng code. Đồng ý nơi đúng, phản biện nơi cần thiết.

### 8.1. Xác nhận và đồng ý hoàn toàn

Các mục sau được xác minh trực tiếp qua code — **tôi đồng ý 100%** với kết luận đã ghi trong bảng §1:

| Mục | Xác minh thêm |
|---|---|
| **P0.1 — Single không ghi output** | `main.py:956` chỉ upsert `"translating"`, không có `save_output`. Merge `main.py:1039–1042` thì có. Lệch pha hoàn toàn. |
| **P0.2 — `run.py` thiếu import** | Đọc toàn bộ `run.py:1–15`, không có `SafeFileHandler` hay `atomic_write_text`. Dòng 81 và 138 dùng nhưng không import. Crash ngay khi chạy `--project`. |
| **A5 — Chống đứt SSE (BrokenPipeError)** | `emit()` hiện không bọc `try/except`, nếu client đóng tab giữa dịch sẽ bắn `BrokenPipeError` ra thread worker mà không có nơi xử lý tốt. Sửa đúng như đề xuất. |
| **Archive không verify** | `file_handler.py:118–120`: `make_archive()` xong, `rmtree()` ngay, không check `zip_path.stat().st_size > 0`. Đây là lỗi thật, dữ liệu mất nếu disk full giữa chừng. |
| **Gemini thiếu `.strip()`** | `ai_client.py:83`: `return parts[0]["text"]` — không strip, nếu API trả chuỗi rỗng/toàn whitespace sẽ qua, trong khi OpenAI compat đã check `not text.strip()`. Nên chuẩn hóa parity. |

---

### 8.2. Phản biện: Quyết định xóa `run.py` (§7) — CẦN CÂN NHẮC KỸ HƠN

**Tôi không đồng ý với quyết định xóa `run.py` theo lý do đã đưa ra.** Bằng chứng và lập luận:

#### 8.2.1. Manifesto §2A vẫn liệt kê `run.py` là thành phần lõi bắt buộc

`docs/00_PROJECT_MANIFESTO.md:55` ghi rõ:
> `run.py (CLI)`: Đọc file đầu vào, chạy luồng gửi-nhận, in tiến độ và ghi file đầu ra.

Đây không phải tiện ích mở rộng — CLI được xếp vào **§2A "Thành Phần Lõi Bắt Buộc"** cùng chunker, prompt_engine và ai_client. Quyết định xóa `run.py` thực chất **là sửa đổi contract của Manifesto**, không phải chỉ dọn code. Theo §0 READ-FIRST:
> *mọi thay đổi làm đổi contract phải cập nhật file này TRƯỚC khi sửa code.*

Kế hoạch §7 hiện tại chưa cập nhật Manifesto trước khi ra quyết định — điều này vi phạm đúng nguyên tắc tự đặt ra.

#### 8.2.2. "Trùng lặp 100% năng lực WebUI" là nhận định sai kỹ thuật

CLI có ít nhất **2 khả năng mà WebUI không có và không thể có**:
1. **Dịch file tùy ý ngoài `workspace/`** (`python run.py /path/to/any/file.txt output.txt`) — WebUI bắt buộc phải upload vào `workspace/projects/{slug}/sources/` trước.
2. **Tự động hóa và pipeline** — Người dùng có thể gọi `run.py` từ script shell, cron job, hoặc kết hợp với công cụ khác (`cat *.txt | python run.py ...`). WebUI không hỗ trợ điều này.

Manifesto §1 ghi `GIAO DIỆN (UI) / CLI` — cả hai là điểm vào hợp lệ của cùng một chu trình gửi-nhận.

#### 8.2.3. Lý do xóa thực chất là "sửa P0.2 bằng cách xóa thay vì sửa"

P0.2 chỉ cần **thêm 1 dòng import**:
```python
from core.file_handler import SafeFileHandler
from core.fileops import atomic_write_text
```

Điều này không phải lý do xóa toàn bộ file. "Sửa đúng căn bệnh" (§2.1 của bạn) trong trường hợp này là sửa import, không phải xóa module.

#### 8.2.4. Đề xuất thay thế: Sửa và giữ CLI, nhưng đơn giản hóa

Thay vì xóa, tôi đề xuất:
- **Sửa P0.2:** Thêm import còn thiếu.
- **Bỏ chế độ `--project`** (nếu muốn giảm phức tạp) — giữ chỉ `python run.py input.txt output.txt`. Chế độ project-mode (`SafeFileHandler`) là nguồn phần lớn edge-case được liệt kê.
- **Giữ `build_client()` ở `run.py`** — hàm này cần tồn tại ở đâu đó; xóa `run.py` chỉ chuyển vấn đề sang việc tìm chỗ đặt nó.

> **Nếu quyết định xóa vẫn giữ nguyên:** Trước tiên cần cập nhật `docs/00_PROJECT_MANIFESTO.md` §1, §2A, §6 để loại `CLI/run.py` ra khỏi contract, theo đúng §0 READ-FIRST.

---

### 8.3. Đồng ý có điều kiện: `persist_output()` helper (§2.2, §4 Đợt A)

Đề xuất gom `save + upsert + log` thành một hàm `persist_output()` là **đúng và cần thiết** — tôi đồng ý. Tuy nhiên cần nêu rõ signature để không có lần 2 phải tranh luận lại:

```python
def _persist_output(
    fh: SafeFileHandler,
    project: str,
    fname: str,
    content: str,
    n_chunks: int,
    provider_id: str,
    model: str,
    file_id: int | None,
) -> None:
    """Ghi output atomic → upsert done → log_run ok. Thứ tự không đổi."""
    fh.save_output(project, fname, content)
    _upsert_file(project, fname, len(content.encode("utf-8")), n_chunks, "done")
    log_run(provider_id, model, "ok", file_id=file_id)
```

Nếu `save_output` ném exception (đĩa đầy), hàm dừng tại đó, `_upsert_file` và `log_run` không chạy — output cũ nguyên, DB không ghi nhận thành công. Đây chính xác là thứ tự an toàn mà §4-A3 yêu cầu.

---

### 8.4. Phản biện bổ sung: `reindex` endpoint (§5 mục 2)

Endpoint `POST /api/projects/{slug}/reindex` được đề xuất để "phục hồi sau crash/db lệch". Tôi **ủng hộ ý tưởng nhưng đề xuất không tạo endpoint riêng** — thay vào đó, tích hợp logic reindex vào `GET /api/projects/{slug}/files` hiện có:

Khi `GET /files` được gọi, nếu phát hiện file tồn tại trên đĩa nhưng không có trong `files` table → tự động upsert với status `"new"`. Chi phí: thêm ~3 dòng SQL vào handler đã có. Lợi ích: không thêm endpoint mới, không thêm nút trên UI, người dùng chỉ cần refresh danh sách file là index được đồng bộ.

Nếu lo ngại về overhead trên mỗi request (kiểm tra file so với DB), có thể giới hạn: chỉ reindex khi số file trên đĩa khác với số row trong DB.

---

### 8.5. Điều chỉnh ưu tiên trong Đợt C: `get_side_dir()` helper

Kế hoạch §4-C liệt kê `get_side_dir(slug, side)` như một refactor ổn định. Tôi **đồng ý nhưng nên làm trước Đợt D** (trước khi thêm Glossary UI), vì Glossary cũng sẽ cần truy cập `assets/` theo cùng pattern. Làm helper trước, Glossary dùng luôn ngay từ đầu — tránh phải refactor lần 2.

---

### 8.6. Tóm tắt thay đổi đề xuất vào Kế hoạch

| Mục | Hành động đề xuất |
|---|---|
| §7 — Xóa `run.py` | **Tạm hoãn.** Sửa P0.2 bằng thêm import trước. Xem xét bỏ chỉ `--project` mode nếu muốn giảm phức tạp. **Bắt buộc cập nhật Manifesto §0/§2A trước khi xóa.** |
| §4-A1 — `persist_output()` | Đồng ý. Signature cụ thể nêu ở §8.3 trên. |
| §5 — `reindex` endpoint | Tích hợp vào `GET /files` hiện có thay vì tạo endpoint riêng. Nhẹ hơn, không tăng API surface. |
| §4-C — `get_side_dir()` | Nâng ưu tiên: làm trước Đợt D (Glossary) để tránh refactor lần 2. |
| Gemini response parity | Thêm `.strip()` và check rỗng ở `ai_client.py:83` để ngang bằng với OpenAI compat. Rẻ, làm luôn trong Đợt A4. |

---

## 9. REVIEW BỔ SUNG VÀ ĐIỀU CHỈNH KẾ HOẠCH

### 9.1. Quyết định xóa `run.py` cần được tách khỏi hotfix P0

Phần phản biện tại §8.2 nêu đúng một rủi ro quan trọng: xóa `run.py` không chỉ là xử lý lỗi import, mà là thay đổi contract của dự án. Hiện tại Manifesto vẫn liệt kê CLI trong nhóm thành phần lõi bắt buộc. Vì vậy:

- Không xóa `run.py` trong cùng commit hotfix P0.
- Không dùng việc xóa CLI để thay thế cho việc sửa lỗi P0.2.
- Trước khi xóa, phải cập nhật Manifesto, README, các tài liệu tham chiếu và acceptance criteria.
- Phải quyết định rõ CLI còn là một entry point được hỗ trợ hay chỉ là legacy code sẽ bị loại bỏ.
- Nếu giữ CLI, phải sửa import, chuẩn hóa thứ tự persist và bổ sung test trực tiếp.
- Nếu bỏ CLI, phải loại các yêu cầu test CLI khỏi B1 sau khi cập nhật contract.

**Kết luận tạm thời:** hoãn xóa `run.py` ra khỏi Đợt A. Đợt A chỉ xử lý các lỗi runtime độc lập với quyết định vòng đời CLI. Quyết định xóa hoặc giữ CLI được chốt trong một task riêng sau khi rà soát toàn bộ tài liệu và test.

### 9.2. Sửa mâu thuẫn giữa B1 và §7

Kế hoạch hiện tại vừa yêu cầu:

- B1: integration test CLI direct và project;
- §7: xóa `run.py` và xóa test CLI.

Hai yêu cầu này không thể cùng tồn tại trong cùng một milestone. Cần áp dụng một trong hai nhánh:

**Nhánh giữ CLI:**

- Giữ các test CLI trong B1.
- Sửa import và các lỗi contract của CLI.
- Bổ sung test direct-mode và project-mode.
- Không xóa `run.py`.

**Nhánh bỏ CLI:**

- Trước tiên cập nhật Manifesto và tài liệu liên quan.
- Xóa `run.py`, các test CLI và reference không còn hợp lệ.
- B1 chỉ giữ integration test WebUI.
- Acceptance phải xác nhận không còn entry point hoặc tài liệu nào coi CLI là contract được hỗ trợ.

Không được đánh dấu A2 hoàn thành nếu chưa chọn một trong hai nhánh trên.

### 9.3. Contract bắt buộc của `persist_output()`

`persist_output()` được chấp nhận là helper dùng chung cho single và merge, nhưng cần ghi rõ contract trước khi triển khai:

1. Ghi content bằng cơ chế atomic.
2. Chỉ khi bước ghi thành công mới cập nhật `files.status = "done"`.
3. `size_bytes` lấy từ `len(content.encode("utf-8"))`, không dùng giá trị ước lượng.
4. Chỉ sau khi DB update thành công mới ghi `log_run(..., "ok")`.
5. Chỉ emit SSE `done` sau khi toàn bộ persist hoàn tất.
6. Nếu save thất bại:
   - không gọi `_upsert_file(..., "done")`;
   - không gọi `log_run(..., "ok")`;
   - output cũ phải còn nguyên;
   - exception phải được chuyển thành trạng thái lỗi phù hợp.
7. `file_id` có thể là `None` đối với những flow chưa có row tương ứng.
8. Helper không được tự xử lý SSE; emit là trách nhiệm của caller sau khi helper trả về thành công.

> §9.3 kết thúc tại đây (câu dở dang gốc đã được hoàn thiện bằng signature §8.3, chấp nhận tại §10.3).

---

## 11. MÃ MẪU TRIỂN KHAI (copy-paste được, đã đối chiếu signature thật)

> Mọi đoạn dưới dùng đúng tên hàm/signature hiện có trong code (`_upsert_file(project,
> filename, chars, chunks, status)`, `log_run(provider, model, status, error="",
> file_id=None)`, `fh.save_output(project, fname, content)`). Chỉ việc áp dụng + chạy test.

### 11.1. `persist_output()` + tích hợp single/merge (`main.py`) [CONTRACT + CODE]

```python
def _persist_output(fh: SafeFileHandler, project: str, fname: str, content: str,
                    n_chunks: int, provider_id: str, model: str,
                    file_id: int | None) -> None:
    """Contract §9.3: atomic → upsert done (size thật) → log ok. Raise để caller map lỗi."""
    fh.save_output(project, fname, content)
    _upsert_file(project, fname, len(content.encode("utf-8")), n_chunks, "done")
    log_run(provider_id, model, "ok", file_id=file_id)
```

Single (`_handle_translate_sse`, thay khối hiện tại sau `asyncio.run`):

```python
        try:
            client = build_client(provider, model, keys, cfg["timeout_seconds"])
            prompts = _build_prompts(project, chunks, base_tpl, extras)
            outs = asyncio.run(_run_chunks(client, prompts, [[fname]] * len(prompts),
                                           cfg.get("api_delay_seconds", 2.0), len(keys), emit,
                                           cancel=_cancel_event))
            output = "\n\n".join(outs)
            _persist_output(fh, project, fname, output, len(chunks),
                            provider["id"], model, _file_id(project, fname))
            emit("done", {"chars": len(output.encode("utf-8"))})
        except TranslateCancelled as e:
            log_run(provider["id"], model, "cancelled", str(e), file_id=_file_id(project, fname))
            emit("error", {"error": str(e), "cancelled": True})
        except (ConnectionError, TimeoutError, RuntimeError, ValueError, OSError) as e:
            log_run(provider["id"], model, "error", str(e), file_id=_file_id(project, fname))
            emit("error", {"error": str(e)})
        finally:
            ... (giữ nguyên)
```

Merge: thay khối `for f in files: fh.save_output...` + `_upsert_file` + `log_run` bằng vòng gọi
`_persist_output(fh, project, f, parts_out.get(f, ""), <n_chunks_file_f>, ...)` cho từng file
(`file_id=_file_id(project, f)` từng file — sửa luôn điểm "merge không gắn rõ từng file" ở §1-P1.4).

> **Policy merge tối thiểu, phương án tối thiểu (review §9.3 — đã chốt):**
> persist từng file như hiện tại; file nào lỗi → `except OSError` ghi entry lỗi, tiếp tục file sau;
> cuối vòng: nếu có lỗi → **không emit `done` tổng thể**, emit `error` kèm danh sách
> `{"saved": [...], "failed": [{"file":..., "error":...}]}`; run log `error`.
> Ghi rõ trong UI/docs: **merge KHÔNG có atomicity đa file** — đây là giới hạn được chấp nhận,
> không tuyên bố ngược lại.
>
> ```python
> # CODE — vòng persist merge (thay khối for hiện tại):
> saved, failed = [], []
> for f in files:
>     try:
>         _persist_output(fh, project, f, parts_out.get(f, ""), n_chunks_of(f),
>                         provider["id"], model, _file_id(project, f))
>         saved.append(f)
>     except OSError as e:
>         failed.append({"file": f, "error": str(e)})
> if failed:
>     log_run(provider["id"], model, "error", f"merge partial: {len(saved)} ok, {len(failed)} fail")
>     emit("error", {"error": f"Một số file lỗi: {', '.join(x['file'] for x in failed)}",
>                    "saved": saved, "failed": failed})
> else:
>     emit("done", {"chars": ..., "chunks": ..., "files": saved})
> ```
>
> **Lỗ hổng `_active_job` đa file (phát hiện khi đối chiếu §9.7):** merge chỉ gán
> `_active_job = (project, files[0])` nên rename-batch/delete file thứ 2+ không bị chặn 409.
> Sửa tối thiểu (CODE):
> ```python
> _active_job = (project, list(files))  # merge: giữ CẢ danh sách
> ```
> và chuẩn hóa mọi điểm check thành helper duy nhất:
> ```python
> # CODE — main.py, dùng chung cho 5 điểm check 409 (dòng 517/552/603/850/865):
> def _job_blocks(slug: str, fname: str | None = None) -> bool:
>     """True nếu phiên đang chạy đụng project/file. fname=None = cả project."""
>     if not _active_job:
>         return False
>     job_slug, job_files = _active_job[0], _active_job[1]
>     if isinstance(job_files, str):
>         job_files = [job_files]
>     if job_slug != slug:
>         return False
>     return fname is None or fname in job_files
> ```
> Single giữ `_active_job = (project, fname)` (str) — helper tương thích cả 2 dạng, không đụng
> code đường single. Invariant chốt: **đụng file đang dịch → 409; project khác → cho phép;
> file khác cùng project → cho phép** (đọc/ghi độc lập).

### 11.2. `run.py`: import (A2) + default_prompt/file_id (C-CLI riêng) [CODE]

> Nhãn: CODE — áp dụng trực tiếp. (Tách theo review §9: A2 chỉ import; C-CLI commit riêng.)

```python
# CODE — A2, 2 dòng duy nhất:
from core.file_handler import SafeFileHandler
from core.fileops import atomic_write_text   # canonical source là fileops
```

```python
# CODE — C-CLI (commit riêng, revert độc lập với A2):
ap.add_argument("--prompt", default=None)                          # bỏ hardcode
...
    prompt_file = args.prompt or cfg.get("default_prompt", "default_translation.txt")
    ...
    prompt = prompt_engine.assemble_prompt(chunk_text, prompt_filename=prompt_file)
    ...
        except Exception as e:
            ...
            fid = file_id(args.project, args.file) if (args.project and args.file) else None
            log_run(provider["id"], model, "error", str(e), file_id=fid)
            return 1
```

> ⚠️ `run.py` import từ `main.py` sẽ tạo circular import (`main.py` import `run.build_client`).
> Vì vậy **không reuse `_file_id` của main** — 2 lựa chọn, chốt **(b)**: `(a)` duplicate 6 dòng
> SELECT id vào `run.py`; `(b)` chuyển `_file_id` + `_upsert_file` + `log_run`-wrapper vào
> `core/app_db.py` (nơi đã có `log_run`), cả `main.py` và `run.py` cùng dùng. **Chọn (b)** —
> đúng hướng "helper chung", không circular (core không import main/run).

```python
# CODE — core/app_db.py, thêm (cần import logging + sqlite3 đã có; logger module-level):
import logging
logger = logging.getLogger(__name__)

def file_id(project: str, filename: str, db_path: Path = DB_PATH) -> int | None:
    # Policy (review §9.4): chỉ bắt sqlite3.Error (schema/lock/path sai) + warning có trace;
    # KHÔNG nuốt mọi Exception — lỗi lập trình phải nổ to để thấy.
    try:
        con = get_db(db_path)
        try:
            row = con.execute("SELECT id FROM files WHERE project_slug=? AND filename=?",
                              (project, filename)).fetchone()
        finally:
            con.close()  # (review §11: finally bắt buộc — execute() lỗi vẫn phải đóng)
        return row[0] if row else None
    except sqlite3.Error:
        logger.warning("Cannot resolve file_id for %s/%s", project, filename, exc_info=True)
        return None
```

`main.py`: `from core.app_db import ..., file_id as _file_id` — hmm, tên ngắn hơn: đổi `main._file_id`
thành dùng chung `app_db.file_id`, xóa def cũ (giữ alias `_file_id = file_id` 1 dòng để diff nhỏ,
xóa hẳn ở lần refactor sau). `run.py` dùng `app_db.file_id` trực tiếp.

### 11.3. Defensive: prompt/chunker/keyrotator/emit/archive/settings-XSS [CODE]

```python
# core/prompt_engine.py — load_prompt:
    def load_prompt(self, prompt_filename: str = "default_translation.txt") -> str:
        name = self._check_name(prompt_filename)
        file_path = self.prompts_dir / name
        ...

# core/chunker.py — split_text, ngay sau docstring:
    if max_chars is None or max_chars <= 0:
        raise ValueError(f"max_chunk_chars phải lớn hơn 0, nhận được: {max_chars!r}")

# core/key_rotator.py:
#  - message: "config/providers.json" thay "config/keys.json"
#  - __init__: self.keys = list(dict.fromkeys(k.strip() for k in keys if k.strip()))  # dedup giữ thứ tự

# main.py — đầu file (hiện chưa có logging, thêm mới):
import logging
logger = logging.getLogger(__name__)

# main.py — emit() chống đứt SSE (A5):
        def emit(event, payload):
            line = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            try:
                self.wfile.write(line.encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError) as e:
                # (review §11: log để phân biệt client-đóng-tab vs lỗi mạng server)
                logger.debug("emit(): kết nối đứt (%s), dừng lặng lẽ", type(e).__name__)
                raise TranslateCancelled("Client đã ngắt kết nối giữa phiên")
```
> Lưu ý thiết kế: tái dùng `TranslateCancelled` cho client-disconnect để đi chung đường
> `except` đã có (log `cancelled`, không ghi file, finally giải phóng). Không thêm except mới.

```python
# CODE — core/file_handler.py, archive_project, trước rmtree:
# (review §9.9: size-check là smoke verification, không phải toàn vẹn;
#  testzip có điều kiện theo kích thước để khỏi treo với archive lớn)
import zipfile
_TESTZIP_LIMIT = 100 * 1024 * 1024  # 100MB: dưới thì testzip, trên chỉ check size
        if not zip_path.is_file() or zip_path.stat().st_size == 0:
            raise OSError(f"Archive lỗi/không tạo được: {zip_path}")
        if zip_path.stat().st_size <= _TESTZIP_LIMIT:
            bad = zipfile.ZipFile(zip_path).testzip()
            if bad is not None:
                raise OSError(f"Archive hỏng tại entry: {bad}")
        shutil.rmtree(d)
```

```javascript
// web/js/settings.js — escape 3 chỗ (mẫu prOpt đã đúng):
$('wProv').innerHTML=pv.providers.map(p=>`<option value="${esc(p.id)}" ...>${esc(p.name)}</option>`)...
// wExtra checkbox: value="${esc(p)}" — label text cũng esc()
// CODE — whitelist scheme cho MỌI href gán từ dữ liệu ngoài (quota_url VÀ docs_url),
// vì escape HTML không chặn được javascript:/data: trong href:
function safeHref(u){
  if(typeof u!=="string")return "#";
  const t=u.trim();
  return /^https?:\/\//i.test(t)?t:"#";  // chỉ https (+http); từ chối javascript:, data:, vbscript:
}
if(d.quota_url){const h=safeHref(d.quota_url);
  parts.push(h==="#"?`quota (link bị chặn)`:`<a href="${esc(h)}" target="_blank" rel="noopener">quota↗</a>`);}
...
if(d.docs_url){const h=safeHref(d.docs_url);
  if(h==="#"){$('mDocs').style.display='none';}
  else{$('mDocs').style.display='';$('mDocs').href=h;}}
```

### 11.4. Test khóa (CODE cho conftest/chunker; PSEUDOCODE cho CLI/single/cancel — cần điều chỉnh theo fixture)

```python
# tests/test_run_cli.py (mới) — PSEUDOCODE, điều chỉnh FakeMgr/fixture khi viết:
def test_cli_project_mode_saves_output(tmp_path, monkeypatch):
    from core import app_db
    monkeypatch.setattr(app_db, "DB_PATH", tmp_path / "app.db")  # cách ly db thật
    async def fake_translate_chunk(self, prompt):
        return "DỊCH:" + prompt[:10]
    monkeypatch.setattr("core.ai_client.GeminiClient.translate_chunk", fake_translate_chunk)
    monkeypatch.setattr("run.AIProviderManager", lambda: FakeMgr())  # keys=[DUMMY], model=m (mẫu cũ test_file_handler.py:64)
    src = tmp_path / "in.txt"; src.write_text("Nội dung nguồn. " * 200, encoding="utf-8")
    out = tmp_path / "out.txt"
    assert asyncio.run(run.main([str(src), str(out)])) == 0
    assert out.exists() and "DỊCH:" in out.read_text(encoding="utf-8")

# tests/test_server.py — single autosave — PSEUDOCODE (viết đầy đủ khi có fixture seed):
def test_translate_single_saves_results(app):
    seed 1 file; POST /api/translate ...; đọc done;
    assert (workspace/results/fname).exists() với nội dung ghép đủ chunk;
    GET /api/projects/{slug}/files → status done (không còn "translating").

# tests/test_server.py — cancel giữa delay + sau response — PSEUDOCODE:
#   FakeClient sleep 0.3 ở chunk 2 rồi cancel → assert không file mới trong results/,
#   lock thả (request tiếp theo không 409).

# tests/conftest.py (mới, P2.1 đúng chỗ) — CODE, dùng nguyên văn:
def _add_no_proxy_hosts(name):
    current = os.environ.get(name, "")
    values = [item.strip() for item in current.split(",") if item.strip()]
    for host in ("127.0.0.1", "localhost"):
        if host not in values:
            values.append(host)
    os.environ[name] = ",".join(values)

_add_no_proxy_hosts("NO_PROXY")
_add_no_proxy_hosts("no_proxy")

# tests/test_chunker.py — property (CODE — contract chuẩn hóa, review §9.8):
# Contract chốt: NORMALIZED — xóa MỌI whitespace rồi so sánh, vì split_text()
# rstrip/lstrip ở điểm cắt và join "\n\n" đều thêm/bớt whitespace (lossless từng byte
# là SAI contract; `" ".join(split())` cũng SAI với text vốn không có khoảng trắng).
def _norm(t: str) -> str:
    return re.sub(r"\s+", "", t)

@pytest.mark.parametrize("size", [10, 16000, 100000])
@pytest.mark.parametrize("text", [
    "ascii simple text " * 5000,          # thường
    "Tiếng Việt có dấu ễ ộ ư đ. " * 2000,  # unicode đa byte
    "x" * 50000,                            # không khoảng trắng
    ("đoạn rất dài không ngắt " * 5000).replace(" ", ""),  # vô ngắt
    "",                                     # rỗng
    "   \n\t  ",                            # chỉ whitespace
])
def test_chunks_within_limit_and_rejoin(text, size):
    if not text.strip():
        assert split_text(text, size) == []
        return
    chunks = split_text(text, size)
    assert all(len(c) <= size for c in chunks)
    assert _norm("\n\n".join(chunks)) == _norm(text)
    if size == 1:
        assert all(len(c) <= 1 for c in chunks)  # biên cực đoan: cắt từng ký tự, không treo
```

### 11.5. Thứ tự triển khai đề xuất — PROCESS (không gộp commit — tách để bisect, review §11)

1. **Commit 1a** (output pipeline): A1 persist + A3 thứ tự + A2 import.
2. **Commit 1b** (I/O safety): A4 defensive + A5 emit + archive verify.
3. **Commit 1c** (vệ sinh): settings XSS + KeyRotator message.
4. Commit 2 (test khóa): B1 integration/cli + B2 chunker + B3 client + B4 rotator + B6 XSS + conftest.
5. Commit 3 (ổn định mỏng): Đợt C (db helper dùng cho code mới, paste-handler, get_side_dir, doc restart-load).
6. Commit 4 (3b tính năng): Đợt D theo litmus + file profile JSON (bác localStorage, xem §2.5).

---

## 12. PHẢN HỒI REVIEW CỦA USER LÊN BẢN NÀY (06/09/2026 — đã cập nhật vào plan)

| # | Điểm user nêu | Kết quả kiểm chứng | Hành động |
|---|---|---|---|
| 1 | `con.close()` thiếu `finally` trong mẫu `file_id` | **ĐÚNG** | Mẫu §11.2 đã bọc `try/finally` |
| 2 | `TranslateCancelled` trong `emit()` che lỗi I/O thật | **ĐÚNG một nửa** | Giữ tái dùng đường `except` cũ + thêm `logger.debug` ghi loại exception (cần thêm `import logging` vào `main.py` vì hiện chưa có) |
| 3 | Import `atomic_write_text` sai module | **NGƯỢC LẠI — mẫu cũ vẫn chạy**: `file_handler.py:6` re-export từ `fileops`. Tuy vậy đồng ý đổi sang canonical `from core.fileops import atomic_write_text` cho rõ nguồn (không còn 2 đường import song song gây nhầm lần sau) |
| 4 | Commit 1 quá lớn, khó bisect | **ĐÚNG** | Tách 1a (output pipeline) / 1b (I/O safety) / 1c (vệ sinh) theo đúng bảng user đưa |
| 5 | `§10.5 → §2.5` lẫn lộn | **ĐÚNG** | Sửa thành `xem §2.5` (ref đúng: localStorage bị bác tại §2.5) |

---

## 13. PHẢN HỒI REVIEW VÒNG 2 — 10 ĐIỂM CỦA USER (06/09/2026, đã cập nhật vào plan)

> Quy tắc giữ nguyên: nội dung cũ (§1–§12) không sửa; mọi thay đổi ghi ở đây + annotation tại chỗ.

| # | Điểm user nêu | Ý kiến của tôi + hành động |
|---|---|---|
| 1 | §7 còn checklist xóa CLI gây nhầm | **ĐỒNG Ý, ĐÃ SỬA.** Tiêu đề → `§7. LỊCH SỬ — ĐỀ XUẤT XÓA CLI ĐÃ BỊ THAY THẾ` + dòng cảnh báo đỏ ngay trước checklist. Không chuyển sang `wip/` vì §7 là mắt xích tham chiếu của §9–§10 (chuyển đi gãy ref chéo, đúng lo ngại của bạn nhưng chi phí cao hơn lợi ích). |
| 2 | Tách A2 khỏi cải tiến CLI | **ĐỒNG Ý, ĐÃ TÁCH.** A2 = đúng 2 dòng import (revert an toàn). `default_prompt`/`file_id`/helper DB dồn vào mục **C-CLI riêng**, commit riêng. Ghi chú: nếu C-CLI lỗi, revert không chạm hotfix output pipeline. |
| 3 | Merge atomicity: chọn tối thiểu + ghi rõ giới hạn | **ĐỒNG Ý, ĐÃ GHI.** Policy trong §11.1-merge: per-file `saved`/`failed`, lỗi → không emit `done` tổng thể, UI/docs ghi rõ **merge KHÔNG có atomicity đa file**. Bổ sung ngoài yêu cầu: phát hiện `_active_job` chỉ giữ `files[0]` → rename-batch file thứ 2+ lọt 409; đã thêm fix giữ cả list + helper `_job_blocks()` + invariant khóa vào plan. |
| 4 | `file_id()` không nuốt mọi exception | **ĐỒNG Ý, ĐÃ SỬA MẪU.** Chỉ bắt `sqlite3.Error` + `logger.warning(exc_info=True)`; lỗi lập trình nổ to. Mẫu gồm `import logging` vì `app_db.py` hiện chưa có. |
| 5 | Phân biệt disconnect vs cancel; thread-safety emit | **ĐỒNG Ý có điều chỉnh.** Giữ 1 trạng thái `cancelled` (không thêm giá trị mới vào taxonomy/DB/UI history — chi phí lan tỏa cao), nhưng message phân biệt (`"Client đã ngắt kết nối..."` vs `"Đã hủy..."`) + document rằng `cancelled` bao gồm cả 2 trường hợp. Về thread: `emit()` chạy trong worker thread của `ThreadingHTTPServer`, `_cancel_event`/`_active_job` chỉ đọc-ghi trong chính thread đó + `finally` giải phóng — không share state giữa thread (GIL + thứ tự code bảo đảm), đã ghi chú vào plan. |
| 6 | Whitelist scheme `quota_url` | **ĐỒNG Ý + MỞ RỘNG.** Escape không chặn `javascript:` trong `href`. Thêm helper `safeHref()` (chỉ `https?`, còn lại render text/bỏ link) + áp dụng cho **cả `docs_url`** (gán qua `.href` property cũng thực thi khi click — điểm mẫu cũ bỏ sót). |
| 7 | `no_proxy` helper | **ĐỒNG Ý NGUYÊN VĂN.** Đã thay mẫu `setdefault` sai bằng code của bạn trong §11.4. Ghi chú thêm: `conftest.py` import cực sớm (trước mọi import tạo client) — thứ tự này là bắt buộc, không phải style. |
| 8 | Chunker contract + edge cases | **ĐỒNG Ý chọn normalized.** Kiểm chứng code: `rstrip`/`lstrip` ở điểm cắt nên lossless từng byte là **sai sự thật** — assertion cũ trong plan sẽ false-negative. Đổi sang `_norm()` + đủ 6 edge (rỗng, whitespace-only, `max_chars=1`, unicode đa byte, vô ngắt). Ghi thêm: `max_chars=1` terminate được vì `cut>=1` khi `len>1`. |
| 9 | Archive testzip có điều kiện | **ĐỒNG Ý.** Gate 100MB (dưới testzip, trên chỉ check size) + ghi rõ size-check là smoke, không phải toàn vẹn. |
| 10 | Nhãn CODE/PSEUDOCODE/CONTRACT | **ĐỒNG Ý, ĐÃ GẮN.** §11.1 CONTRACT+CODE; §11.2/11.3 CODE; §11.4 phân biệt từng block; §11.5 PROCESS. |

### Đối chiếu Manifesto (`docs/00_PROJECT_MANIFESTO.md` v2.5) — theo yêu cầu review

| Điều khoản | Plan 3b có vi phạm? |
|---|---|
| §0 READ-FIRST (đổi contract phải cập nhật manifesto trước) | **Không vi phạm.** Giữ CLI = không đổi contract (Manifesto §2A vẫn liệt kê `run.py`). Không mục nào thêm endpoint đổi semantics cũ ngoài additive (`rename-batch` đã có? — kiểm tra: có, additive). Không sửa manifesto ở turn này. |
| §1 chu trình gửi–nhận / §3 failure policy | Khớp: autosave + atomic + dừng-rõ-ràng + chạy-lại-từ-đầu giữ nguyên. Merge partial-failure được document, không checkpoint. |
| §5 litmus test | Khớp: toàn bộ Đợt A–C là sửa đúng/sửa an toàn, không tính năng mới (trừ reindex-INSERT-OR-IGNORE đã chứng minh là đọc-ghi index, không phải workflow). |
| §7 security | Khớp: XSS fix là vệ sinh single-user local, không thêm auth/mask/vault. `safeHref` không phải cơ chế public-app. |
| §9 kỹ thuật local | Khớp: 0 dependency mới (stdlib + `zipfile` stdlib cho testzip), không build-step, không CDN, không framework. `conftest.py` chỉ là test-env. |
| §2C/§6 mở rộng | Glossary/profile/diff/EPUB giữ nguyên ở Đợt D/Phase 4, không lấn sang 3b. |

**Kết luận đối chiếu:** plan 3b sau cập nhật **không đòi hỏi sửa Manifesto**. Nếu Đợt D sau này thêm endpoint/UI mới, áp §0 lúc đó.

