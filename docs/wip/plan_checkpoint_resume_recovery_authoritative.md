# Kế hoạch authoritative: checkpoint, resume và recovery phần đã dịch

**Ngày hợp nhất:** 2026-08-16  
**Nguồn:** `plan_checkpoint_resume_recovery_merged.md`, `plan_2026-08-12_checkpoint_resume_recovery_implementation_guide.md`, review mã nguồn đính kèm.  
**Trạng thái:** Đã triển khai một phần; người dùng đã chọn **Lựa chọn A** để triển khai tiếp. Tài liệu này là handoff cho model sinh mã; chưa được phép sửa mã nguồn chỉ dựa trên tài liệu nếu chưa hoàn thành Phase 0.  
**Phạm vi đợt này:** WebUI, file đơn và batch một file; checkpoint SQLite hiện có. Smart-batch nhiều file, retry-policy tổng quát, tự động đổi provider ngoài recovery và worker supervisor riêng để P2.

## 1. Kết luận điều hành

Code hiện tại là một bản hybrid giữa hai kế hoạch. Phần nền tảng đã tốt và có thể tái sử dụng: phân loại HTTP 451, migration schema, `CheckpointService`, startup path lookup, cancel xuyên batch và route recovery cơ bản. Tuy nhiên sản phẩm chưa hoạt động đúng end-to-end vì còn bốn blocker:

1. Luồng “Chia tách phần đã dịch” gọi endpoint không tồn tại nên 404.
2. Luồng bấm “Dịch” gặp `resume_required` trả 409 nhưng frontend xử lý lỗi HTTP trước khi đọc payload, khiến modal không mở.
3. Cancel chưa hoàn toàn scoped: endpoint legacy `/api/translate/cancel` gọi `request_cancel()` không có `job_id`, kích hoạt `_cancel_all` và dừng mọi job.
4. `close_as_partial` ghi trạng thái partial rồi registry lại ghi đè thành `completed`, đồng thời đọc/assemble checkpoint trong khi worker có thể còn `save_chunk()`.

Vì vậy, **không được dùng Mục 14 của hai tài liệu cũ làm bằng chứng đã hoàn tất**. Mục đó phải được thay thế bằng trạng thái thực tế và tiêu chí nghiệm thu trong tài liệu này.

## 2. Đối chiếu kế hoạch, code và bằng chứng

| Hạng mục | Guide cũ | Merged plan cũ | Code hiện tại | Kết luận |
|---|---|---|---|---|
| Migration | Nuốt `OperationalError` | `PRAGMA table_info` + `ALTER` không che lỗi | Đã dùng `PRAGMA` và chỉ alter cột thiếu | Đạt nền tảng; cần bổ sung test DB cũ/migrate dở/chạy lặp |
| `pending_chunks` | Lưu list index trong task store | Chỉ lưu count/cache; checkpoint là nguồn sự thật | Đang lưu list JSON | Chưa thống nhất; phải bỏ list khỏi semantics |
| Error contract executor | Dict `{"_error": ...}` | Hook/config, tránh lặp executor | Có recovery method và contract theo hướng guide | Chạy được nhưng cần chuẩn hóa error/cancel/progress |
| Recovery | Method mới lặp vòng dịch | Orchestration quanh executor | Có method mới | Giữ tạm để giảm phạm vi, nhưng phải bổ sung cancel/progress và không lặp logic dài hạn |
| HTTP 451 | Cần thêm classify/map | Cần thêm classify/map | Đã có đủ policy, `error_code`, translator map và test | Đạt |
| Checkpoint | Thêm indices/clone/partial | Path tường minh, tránh hash-of-hash | Đã có nhiều method, startup đã dùng path vật lý | Đạt phần lõi; endpoint vẫn còn key drift |
| Recovery route | Hướng dẫn copy-paste có stub | Validate → clone → task → worker | Có route và validate provider trước clone | Đạt một phần; thiếu lock/lease/cancel/progress đầy đủ |
| UX resume | Modal sau response | Modal 3/4 action | Modal có nhưng không vào được từ 409 | Chưa đạt |
| Close partial | Guide không hoàn chỉnh | Cancel-and-wait, `closed_partial` | 404 qua frontend; backend clobber thành `completed` | P0 chưa đạt |

### Bằng chứng đã kiểm tra

- `pytest -q tests/unit/test_checkpoint_resume.py tests/unit/test_endpoint_policy.py tests/unit/test_task_store.py` → **28 passed**.
- `services/task_store.py` đã migration idempotent theo `PRAGMA table_info`.
- `services/checkpoint_service.py` đã có `get_resume_info_from_path`, indices, clone và partial writer.
- `webui/routes/projects.py` có recovery route, nhưng close route chỉ theo `task_id`.
- `webui/static/js/translation-worker.js` gọi route checkpoint-keyed và ném lỗi ngay khi `response.ok === false`.
- `backend/infrastructure/progress/runtime_state.py` vẫn có `_cancel_all`; `webui/routes/translation.py` vẫn gọi cancel global.

Các test hiện có là unit/primitive. Chưa có route integration hoặc kịch bản xuyên suốt 17/24 → 451 → recovery; vì vậy kết quả 28/28 không đủ chứng minh tính năng sản phẩm.

## 3. Quyết định kiến trúc cuối cùng

Về **kiến trúc recovery**, giữ **B nâng cấp**: recovery tạo session/checkpoint namespace và task mới; checkpoint nguồn bất biến; executor hiện tại tiếp tục dừng khi gặp lỗi terminal; orchestration chỉ dịch các index pending, sau đó assemble tự động.

Về **chiến lược triển khai**, người dùng đã chọn **Lựa chọn A**: hoàn tất toàn bộ P0 và integration gate trước, sau đó mới triển khai P1 durable restart/auto-merge. Không được hiểu nhầm “A” là kiến trúc executor khác với “B nâng cấp”.

Các quyết định bắt buộc:

- Không dùng `force_retranslate` cho recovery.
- Checkpoint SQLite là nguồn sự thật duy nhất cho tập `done/pending/failed`.
- `checkpoint_key` trong task phải có một convention duy nhất: hoặc logical key được resolve qua service, hoặc filename vật lý; không được hash lại chuỗi đã là tên `.db`. Mọi endpoint phải dùng helper resolve chung và fallback path vật lý.
- Tách `source_identity` (source hash, chunker, chunk size, prompt hash) khỏi `execution_identity` (provider, model, base URL, credential mode). Recovery phải khớp source identity, cho phép execution identity mới và ghi `mixed_provider`.
- Recovery clone source trước, tạo task persistent đầy đủ metadata sau clone, rồi mới register/start worker. Lỗi ở bất kỳ bước nào không được để worker chạy.
- Partial artifact không phải output chính; phải có marker, manifest `is_complete=false`, ghi tạm rồi rename atomic.
- Trạng thái hoàn tất partial là `closed_partial`, không phải `completed` hoặc `partial_completed`.
- Chỉ task recovery được `completed` sau khi đủ index `0..total-1`, assemble atomic và verify manifest/output.
- Cancel phải theo `job_id`, và close partial phải cancel → chờ worker dừng/lease hết hạn → đọc checkpoint → assemble.

## 4. State machine và hợp đồng dữ liệu

```text
queued → running → completed
                 ├→ failed
                 ├→ resumable
                 ├→ interrupted
                 ├→ cancelled
                 └→ closed_partial
```

`closed_partial` là terminal đối với worker nhưng không phải bản dịch hoàn chỉnh. Không tính trạng thái này vào completed output.

Task store tối thiểu cần có:

- `recovery_of`, `source_task_id`;
- `source_checkpoint_key`, `recovery_checkpoint_key`;
- `partial_output_path`, `final_output_path`;
- `completed_chunks`, `current_chunk` là cache hiển thị;
- `error_class`, `http_status`, `retryable`, `mixed_provider`.

`pending_chunks` nếu còn giữ vì backward compatibility chỉ được coi là cache/diagnostic, không được dùng để quyết định chunk nào cần dịch. Có thể migrate dữ liệu cũ nhưng không backfill bằng giả định “prefix”; phải query checkpoint thực tế, và task key rỗng phải resolve từ metadata/path.

## 5. Phương án thực hiện để giải quyết triệt để

### P0 — Gỡ blocker và làm đúng luồng người dùng

1. **Cancel scoped trước tiên**
   - Sửa `RuntimeState` để không còn đường gọi vô tình kích hoạt global cancel; mọi executor poll `is_cancelled(job_id)`.
   - Giữ endpoint legacy chỉ như compatibility shim nhưng bắt buộc nhận/resolve `job_id`; nếu không có job ID thì trả 400 thay vì cancel toàn cục.
   - `reset_cancel(job_id)` phải xóa đúng token; dùng lock và cơ chế dọn token sau khi job terminal.
   - Thêm test: cancel A không dừng B; cancel A rồi start A mới không bị poison; cancel batch dừng trước file kế tiếp.

2. **Sửa contract `resume_required`**
   - Frontend phải đọc JSON trước, kể cả HTTP 409; `409 + {status: "resume_required"}` là response nghiệp vụ, không phải exception UI.
   - Dùng một helper fetch cho translate project, file đơn và selected files.
   - Bổ sung `.catch` cho `translateSelectedInProject` và khóa double-click modal.

3. **Thống nhất endpoint close partial**
   - Chọn route chuẩn theo `task_id`: `POST /api/tasks/<task_id>/close-as-partial`.
   - Frontend phải resolve checkpoint → task trước khi gọi; không tạo thêm route checkpoint-keyed chỉ để che lỗi model dữ liệu.
   - Nếu buộc hỗ trợ URL cũ, thêm compatibility route có impact test, resolve task duy nhất và chuyển tiếp nội bộ; route mới vẫn là canonical.
   - Backend phải chấp nhận `running/resumable/interrupted/failed`, cancel đúng job, chờ worker/lease, rồi đọc checkpoint. Nếu chưa dừng: trả `202 {status:"close_pending"}`; không assemble đồng thời.
   - Chỉ ghi `closed_partial` một lần vào persistent store và registry; loại bỏ mọi `update_status(..., "completed")` trong flow này.

4. **Đồng bộ checkpoint key**
   - Tạo một resolver dùng chung: task key vật lý → `get_resume_info_from_path`; logical filename → `get_resume_info`; không hash hex/db stem lần nữa.
   - Dùng resolver trong recovery, export, close, task snapshot và startup scan.
   - Emit key của file đang xử lý ở cả `progress` và `task_failed` trong batch; không để task batch trỏ mãi tới file đầu tiên.

5. **Bổ sung integration tests trước khi gọi P0 hoàn tất**
   - route trả 409 mở được modal;
   - route canonical close partial trả 200/202 và giữ `closed_partial`;
   - route cũ (nếu giữ) map đúng task;
   - 17/24 → 451 → clone → recovery chỉ gửi index 17..23;
   - recovery chạy song song không làm cancel job nguồn hoặc job khác.

### P1 — Durable recovery và output đúng

1. Chuẩn hóa recovery worker thành orchestration quanh executor, truyền `job_id`, cancel token, progress base/current/total và checkpoint key trong từng event.
2. Recovery lần hai lấy recovery checkpoint gần nhất làm source trực tiếp; khóa theo source checkpoint để chống hai worker.
3. `GET /api/tasks/<id>` và task list đọc persistent snapshot, startup chuyển worker mất lease từ `running` sang `interrupted/resumable`.
4. Auto-merge: assemble theo index, kiểm tra đủ `0..total-1`, không marker, atomic write, verify, rồi mới `completed`.
5. Chỉ cleanup recovery checkpoint sau verify; giữ source checkpoint theo retention/audit.
6. Migration tests cho DB mới, DB cũ, DB migrate dở và chạy lần hai; không rollback checkpoint DB khi rollback code.

### P1b — In-flight chính xác

Ghi `in_flight` trước request, `saved` sau SQLite commit, attempt count và timestamp. MVP hiện tại chỉ cam kết các chunk đã commit; phải hiển thị cảnh báo duplicate cost khi request bay bị mất.

### P2 — Dọn nợ kỹ thuật và smart-batch

- Chuyển `_row_to_task` sang `sqlite3.Row` hoặc mapping theo tên, không zip theo vị trí `SELECT *`.
- Xóa code chết (`bind_store`, nhánh payload không dùng) sau khi integration tests khóa contract.
- Bổ sung lock cho RuntimeState và giới hạn/dọn `_cancelled_jobs`.
- Smart-batch dùng manifest bất biến theo từng file, không dùng token ngẫu nhiên làm identity.

## 6. Thứ tự sửa code bắt buộc

```text
cancel scoped
  → resume 409 contract
  → canonical close-as-partial + cancel/wait
  → checkpoint-key resolver
  → integration tests route + 451 recovery
  → recovery progress/cancel/lease
  → auto-merge + restart
  → in-flight và smart-batch
```

Trước khi sửa mỗi symbol/class/function, chạy GitNexus impact upstream; nếu HIGH/CRITICAL thì dừng và báo blast radius trước khi sửa. Trước commit chạy `gitnexus_detect_changes()`.

## 7. Tiêu chí nghiệm thu cuối

### Kịch bản 451

- 24 chunk, 17 đã commit; provider trả 451 ở chunk 18.
- Task nguồn là `failed`, error class `censorship_blocked`, HTTP 451, checkpoint nguồn không đổi.
- UI đọc được response 409 và hiển thị modal; dùng số hiển thị 18–24 nhưng lưu index 17–23.
- Recovery clone thành công, task chain có `source_task_id`, worker chỉ gửi 7 index pending.
- Cancel recovery không dừng task khác; resume/recovery sau restart không gửi lại chunk đã done.
- Khi đủ chunk, output final không marker, verify thành công rồi task recovery mới `completed`.

### Chốt partial

- Với task running, cancel-and-wait hoàn tất trước khi đọc checkpoint.
- Với task resumable/failed/interrupted, export partial thành công mà không tạo worker.
- Task luôn ở `closed_partial`; không xuất hiện trong danh sách completed.
- Partial có manifest, marker đúng vị trí, checkpoint được giữ để recovery.
- Nếu worker chưa dừng, API trả `close_pending`, không đọc/assemble cạnh tranh.

### Restart và migration

- DB cũ và DB mới đều migrate idempotent; migrate dở chạy tiếp an toàn.
- Startup không hash-of-hash; task cũ có key null được resolve bằng metadata/path nếu đủ thông tin.
- Process restart không biến task đang chạy thành completed; lease hết hạn mới chuyển interrupted/resumable.

## 8. Các lựa chọn để quyết định

### Lựa chọn A — Sửa P0 trước, giữ MVP B nâng cấp (khuyến nghị)

Sửa cancel scoped, response 409, route close canonical, close-and-wait, key resolver và integration tests; sau đó mới làm durable restart/merge. Rủi ro thấp nhất, khôi phục được luồng người dùng nhanh nhất, không đổi semantics executor quá rộng.

### Lựa chọn B — Làm recovery cùng durable restart ngay

Bao gồm A + lease/heartbeat, persistent reconciliation, SSE reconnect và auto-merge trong cùng đợt. Độ hoàn chỉnh cao hơn nhưng blast radius lớn, thời gian test dài hơn; chỉ chọn nếu cần deploy production ngay sau đợt này.

### Lựa chọn C — Đổi sang executor tiếp tục sau lỗi

Một task giữ trạng thái partial và tiếp tục từ pending ngay trong cùng worker. UX gọn hơn nhưng thay đổi lifecycle, retry, progress, cancel và semantics lỗi lớn; không khuyến nghị cho bản sửa hiện tại.

**Đề nghị:** chọn **A** làm quyết định triển khai trước mắt; coi **B** là mốc P1 bắt buộc sau khi integration suite xanh. Không chọn C ở MVP.

## 9. Quy tắc tài liệu và commit

Tài liệu này là nguồn sự thật duy nhất cho kế hoạch. Không ghi “đã sửa” nếu chưa có test/integration evidence. Mỗi commit chỉ gom một lớp thay đổi và sau mỗi lớp chạy test tương ứng; trước commit cuối dùng GitNexus detect changes để xác nhận không có symbol/flow ngoài phạm vi.

## 10. Kế hoạch triển khai theo phase — handoff cho model sinh mã

### 10.1. Luật chung, áp dụng cho mọi phase

Model sinh mã phải tuân thủ các luật sau:

1. Đây là kế hoạch **thay đổi mã nguồn**, nhưng tài liệu hiện tại chỉ là handoff. Không tự ý mở rộng phạm vi, không đổi kiến trúc sang C, không thêm `force_retranslate` vào recovery.
2. Trước khi sửa từng function/class/method, chạy `gitnexus_impact({target, direction:"upstream"})`. Phải ghi kết quả vào báo cáo phase: d=1, risk, direct callers và test bị ảnh hưởng. Nếu HIGH/CRITICAL, dừng phase và yêu cầu review.
3. Không dùng find/replace để đổi tên symbol. Không thay đổi public contract nếu chưa cập nhật mọi caller, test và tài liệu.
4. Không reset, checkout, stash, xoá DB, xoá checkpoint hoặc ghi đè thay đổi có sẵn của người dùng.
5. Mỗi phase chỉ được kết thúc khi: code compile/import được, test gate xanh, kiểm tra negative case đã chạy, và `git diff` chỉ chứa phạm vi phase.
6. Sau khi mọi phase code hoàn tất, trước commit chạy `gitnexus_detect_changes(scope:"all")`; nếu có file/symbol/flow ngoài dự kiến thì dừng để review.
7. Các tên trạng thái canonical duy nhất: `queued`, `running`, `completed`, `failed`, `resumable`, `interrupted`, `cancelled`, `closed_partial`. Không dùng `partial_completed` trong code mới.
8. Các index lưu trong DB/checkpoint là **0-based**. UI hiển thị **1-based**. Không dùng `next_chunk_index` hoặc `done_count` để suy ra tập index.

### 10.2. Blast radius cần biết trước khi code

GitNexus impact hiện tại (index có thể không bao gồm toàn bộ working-tree changes và FTS đang suy giảm, nên vẫn phải kiểm tra source/callers trực tiếp):

| Symbol | Upstream impact | Risk | Ý nghĩa triển khai |
|---|---:|---|---|
| `RuntimeState` | 23, d=1: 4 | LOW theo graph | Shared cancel/progress; phải test executor, routes và batch |
| `TaskRegistry` | 12, d=1: 3 | LOW theo graph | Đồng bộ RAM ↔ persistent; test task list/SSE |
| `TaskStore` | 17, d=1: 5 | MEDIUM | Migration/row contract ảnh hưởng mọi task persistence |
| `CheckpointService` | 27, d=1: 7 | MEDIUM | Resolver/path/indices ảnh hưởng startup, executor, routes |
| `TranslationExecutor` | 22, d=1: 8 | MEDIUM | Cancel/error/progress ảnh hưởng translation, spellcheck và recovery |

Các risk trên là tín hiệu lập kế hoạch, không thay thế impact lần cuối trước từng edit. GitNexus hiện không trả execution processes đáng tin cậy cho các truy vấn do index/FTS cũ; model phải bổ sung đọc trực tiếp callers và chạy test thực tế.

### Phase 0 — Baseline, inventory và test harness (P0, bắt buộc)

**Mục tiêu:** khóa trạng thái trước khi sửa, không tạo orphan DB/task.

**Đọc/kiểm tra:** `git status`, test config, route registration, schema thật của `workspace/tasks.db`, danh sách checkpoint `.db`, toàn bộ caller của cancel/resume/close/recovery.

**Tạo/chỉnh test harness (chưa sửa production behavior):**

- fixture temporary workspace, tasks DB và checkpoint DB;
- fake provider trả thành công cho các chunk đầu rồi trả HTTP 451;
- fake provider ghi lại danh sách chunk được gửi;
- fake worker/event collector có barrier để kiểm tra cancel-and-wait;
- route test client nếu framework hiện tại hỗ trợ.

**Exit gate:** baseline test hiện có xanh; có test fixture tái lập được 17/24; không có file ngoài phạm vi bị sửa. Nếu baseline fail, chỉ sửa harness/điều chỉnh test do môi trường, không lẫn fix production vào Phase 0.

### Phase 1 — Cancel scoped và loại bỏ cancel poisoning (P0 cao nhất)

**Files/symbols chính:**

- `backend/infrastructure/progress/runtime_state.py`: `request_cancel`, `is_cancelled`, `reset_cancel`, `reset`;
- `core/executor.py`: mọi call `is_cancelled`, `reset_cancel`, terminal event;
- `webui/routes/tasks.py`: `cancel_task`;
- `webui/routes/translation.py`: legacy `/api/translate/cancel`;
- `backend/application/use_cases/translate_project_files_use_case.py`: batch loop;
- tests tương ứng.

**Contract bắt buộc:**

- Cancel token luôn gắn với `job_id`.
- Endpoint `/api/tasks/<job_id>/cancel` chỉ cancel job đó.
- Legacy endpoint không được phép gọi cancel global. Nếu không resolve được một `job_id` duy nhất, trả HTTP 400 với mã `job_id_required` và không đổi state nào.
- `is_cancelled(job_id)` không được trả true vì một job khác bị cancel.
- Reset job A không xóa token của job B; terminal cleanup không làm job mới bị poison.
- Mỗi executor phát terminal event nhất quán (`cancelled` hoặc `failed`), không báo `completed` khi còn chunk thiếu.

**Test gate:** cancel A/B isolation, cancel-then-restart, legacy endpoint, batch stops before next file, concurrent cancel calls. Chạy unit + harness integration. Không sang Phase 2 nếu còn `_cancel_all` reachable từ production path.

### Phase 2 — Chuẩn hóa `resume_required` và frontend error handling (P0)

**Files/symbols chính:** `webui/static/js/translation-worker.js`, `webui/static/js/api-client.js`, `webui/routes/projects.py` translate/confirm-resume routes, modal template.

**Contract:**

```json
HTTP 409
{
  "status": "resume_required",
  "checkpoints": {"file.txt": {"checkpoint_key": "...", "completed_chunks": 17, "total_chunks": 24}}
}
```

Frontend phải parse JSON trước khi quyết định throw. Chỉ throw nếu payload không phải contract hoặc là lỗi thực sự. Các flow file đơn và selected files dùng cùng helper; mọi promise chain có `.catch`; modal disable double-click và luôn reset button khi đóng/lỗi.

**Không được:** đổi backend thành 200 chỉ để né lỗi frontend; nuốt 409; gọi `force_retranslate` khi user chọn close/recovery.

**Test gate:** 409 mở modal; payload lỗi hiển thị toast; modal action continue/restart/close; selected-files rejection không tạo unhandled promise.

### Phase 3 — Canonical close-as-partial, cancel-and-wait và state đúng (P0)

**Files/symbols chính:** `webui/routes/projects.py` close route, `services/task_store.py`, `backend/infrastructure/progress/task_registry.py`, `services/checkpoint_service.py`, frontend action handler/modal.

**Contract canonical:** `POST /api/tasks/<task_id>/close-as-partial`.

Request tối thiểu:

```json
{"confirm": true, "export_partial": true}
```

Response thành công:

```json
{"status":"closed_partial","task_id":"...","partial_output":"...","completed_chunks":17,"pending_chunks":7}
```

Nếu worker chưa dừng trong timeout: HTTP 202 và `{"status":"close_pending","task_id":"..."}`. Không assemble ở nhánh 202. Nếu thiếu checkpoint: resolve bằng canonical resolver ở Phase 4, không tự hash filename trong route.

**Luồng backend bắt buộc:** validate task/confirm → request cancel scoped → chờ worker kết thúc hoặc lease hết hạn → query checkpoint trong transaction/read-safe boundary → write partial + manifest atomic → persistent status `closed_partial` → registry mirror `closed_partial` → response. Không có bước nào gọi `completed`.

**Test gate:** running/resumable/failed/interrupted; worker race barrier; timeout 202; repeated request idempotency; partial marker/manifest; task list không xếp vào completed; frontend gọi đúng task route.

### Phase 4 — Một convention cho `checkpoint_key` và pending indices (P0)

**Files/symbols chính:** `services/checkpoint_service.py`, `webui/__init__.py`, `webui/routes/projects.py`, `webui/routes/tasks.py`, `services/task_store.py`, batch event code.

**Thiết kế:** tạo helper/service resolver có kết quả phân biệt rõ `logical_filename`, `physical_path`, `checkpoint_key`, `source_filename`, `checkpoint_id`. Mọi route dùng helper; không dùng `_get_db_path()` trên chuỗi đã là `.db`/MD5 stem. `db_path_override` chỉ là internal escape hatch có kiểm soát, không phải convention mới.

**Pending rule:** query `chunks.status` và trả tập index thực tế. `pending_chunks` task store chỉ giữ count/cache hoặc để null; không ghi list mới. Backfill task cũ chỉ khi checkpoint resolve được; không giả định prefix.

**Batch rule:** event `progress` và terminal failure mang `filename` + `checkpoint_key` của file hiện tại; task snapshot không trỏ cố định file đầu tiên.

**Test gate:** logical key, physical key, MD5 stem, key null + metadata fallback, non-contiguous done `[0,2,5]`, failed-as-pending, startup scan, batch file 5. Không sang Phase 5 nếu cùng một checkpoint có thể được resolve theo hai kết quả khác nhau.

### Phase 5 — Integration gate cho toàn bộ P0 (P0 release blocker)

Chạy từ đầu đến cuối trong isolated temp workspace:

1. Tạo 24 chunk, commit 0–16.
2. Fake provider trả 451 tại chunk 17.
3. Xác nhận task nguồn `failed`, error class `censorship_blocked`, HTTP 451, source checkpoint bất biến.
4. Gọi translate lại; nhận 409; modal hiển thị 17/24.
5. Chọn close partial; xác nhận `closed_partial`, partial có 17 text + 7 marker.
6. Chọn recovery bằng provider khác; clone tạo namespace mới; fake provider chỉ nhận `[17..23]`.
7. Cancel recovery; xác nhận job nguồn/job khác không bị dừng và recovery checkpoint còn nguyên.
8. Resume/recovery lại; hoàn tất; verify output không marker và task recovery `completed`.

**Exit gate P0:** mọi test route/integration/frontend contract xanh; unit baseline xanh; `pytest` command được ghi cụ thể; không còn TODO claiming P0 complete nếu chưa có evidence.

### Phase 6 — Recovery orchestration, progress và idempotency (P1)

**Files/symbols chính:** `core/executor.py` recovery method, `webui/routes/projects.py` recovery route, `TaskStore`, `TaskRegistry`, provider config.

**Yêu cầu:** truyền `job_id` vào recovery; poll cancel scoped; progress phải phản ánh base done + pending current, không đứng ở 15%; event phải chứa task/recovery checkpoint key; provider/model validate trước clone; lock/idempotency theo source task + source checkpoint; recovery lần hai chain trực tiếp từ recovery checkpoint gần nhất.

**Không tạo worker** nếu validate, clone, task persist hoặc registry hydrate thất bại. Cleanup target clone khi prepare thất bại; giữ source.

**Test gate:** double recovery request, provider invalid, clone failure, registry failure, cancel recovery, recovery retry, recovery-of-recovery.

### Phase 7 — Durable restart, lease và persistent UI (P1)

**Files/symbols chính:** `TaskStore`, `TaskRegistry`, `webui/__init__.py` startup reconciliation, task list/detail routes, SSE/client.

**Yêu cầu:** task `running` không còn worker sau restart → `interrupted/resumable` sau lease; không suy luận worker sống từ daemon thread; task list/detail đọc persistent store trước rồi mới nối SSE; tránh duplicate worker; migration test đủ bốn trạng thái DB.

**Test gate:** kill/restart mô phỏng, lease expiry, reconnect SSE, duplicate resume, DB mới/cũ/migrate dở/re-run.

### Phase 8 — Auto-merge và output lifecycle (P1)

**Yêu cầu:** assemble recovery checkpoint theo toàn bộ index; verify source identity, số index, không marker, manifest và file đọc được; ghi output tạm rồi atomic rename; chỉ sau verify mới `completed`; cleanup recovery checkpoint theo retention, không cleanup source.

**Test gate:** missing index, marker còn sót, output write failure, verify failure, retry sau failure, output path collision, completed task không chạy recovery lần nữa.

### Phase 9 — In-flight, hardening và P2

Chỉ làm sau P0/P1 xanh: `in_flight` durable, attempt/timestamp, duplicate-cost warning, `sqlite3.Row`, lock/dọn cancel tokens, loại code chết, smart-batch manifest bất biến. Mỗi thay đổi có impact riêng và test riêng; không trộn vào P0.

## 11. Bảng trạng thái phase và lệnh bàn giao

Model sinh mã phải cập nhật bảng sau trong báo cáo làm việc, không tự đánh dấu “complete” khi chỉ test unit:

| Phase | Status | Required evidence |
|---|---|---|
| 0 Baseline/harness | `pending` | baseline + fixture 17/24 |
| 1 Cancel scoped | `pending` | isolation + poisoning tests |
| 2 Resume 409 UX | `pending` | route/frontend contract tests |
| 3 Close partial | `pending` | cancel/wait + `closed_partial` tests |
| 4 Key resolver | `pending` | physical/logical/startup/batch tests |
| 5 P0 integration | `pending` | full 451 → close → recovery scenario |
| 6 Recovery orchestration | `pending` | progress/cancel/idempotency |
| 7 Durable restart | `pending` | lease/restart/SSE |
| 8 Auto-merge | `pending` | atomic output/verify/retention |
| 9 Hardening/P2 | `pending` | scoped tests per item |

Mẫu handoff cho mỗi phase:

```text
Phase: <n>
Impact trước edit: <symbols, d=1, risk>
Files changed: <danh sách>
Contract changed: <nếu có, ghi trước/sau>
Tests added/updated: <danh sách>
Commands and result: <lệnh + kết quả>
Negative cases: <kết quả>
Remaining risks/blockers: <danh sách>
Status: complete | blocked | pending
```

## 12. Lệnh yêu cầu model sinh mã ở phiên sau

Dùng nguyên văn chỉ dẫn sau khi muốn bắt đầu sửa mã:

> Đọc `docs/wip/plan_checkpoint_resume_recovery_authoritative.md`. Người dùng đã chọn chiến lược triển khai A và kiến trúc recovery B nâng cấp. Chỉ thực hiện đúng phase được chỉ định, bắt đầu bằng Phase 0 nếu chưa có baseline. Trước mỗi symbol edit, chạy GitNexus impact upstream và báo d=1/risk; nếu HIGH/CRITICAL thì dừng. Không sửa phase sau, không đổi contract ngoài tài liệu, không dùng force_retranslate cho recovery, không dùng global cancel, không dùng `partial_completed`, không coi done count là prefix, không hash lại checkpoint key, không reset/checkout/xóa dữ liệu. Sau phase chạy test gate, kiểm tra diff, và báo cáo theo Mẫu handoff. Chỉ khi Phase 5 full integration xanh mới được tuyên bố P0 hoàn tất.

## 13. Hiệu chỉnh bắt buộc của kế hoạch thực thi P0

Các chi tiết triển khai trong `docs/wip/plan_execute_p0_code_2026-08-16.md` được cập nhật bởi **REV-C** và có quyền ưu tiên khi có mâu thuẫn với snippet cũ:

- E2E phải tạo đúng 24 chunk bằng source dài đã kiểm chứng và `chunk_size=2400`; fake 451 chỉ fail một lần.
- Cancel recovery thật, có `job_id`, barrier/thread controllable và test worker đã dừng, thuộc P0; không chấp nhận test inline đã hoàn tất trước khi cancel.
- Close partial phải có completion/write barrier; polling status DB đơn thuần không đủ.
- Reset cancel phải xảy ra trước worker start hoặc theo generation token, không được xóa token giữa guard và request.
- Selected-files nhiều file chưa có per-file decision phải bị chặn bằng response/UI rõ ràng; không được silently bỏ file và không được force-retranslate toàn bộ.
- Baseline phải ghi fingerprint và `new failures=0`; “4 fail pre-existing” chỉ được chấp nhận khi traceback trùng baseline.

Sau P0, hệ thống được cam kết các luồng file đơn an toàn: resume, export partial, close partial, recovery 451, cancel scoped và chống duplicate checkpoint task. Durable restart/lease, auto-merge lifecycle đầy đủ, in-flight tracking và smart-batch vẫn thuộc P1/P2, không được ghi là đã hoàn tất trong báo cáo P0.
