# Kế hoạch thực thi P0 — Mã hoàn chỉnh (handoff cho model sinh mã)

> **For agentic workers:** Thực thi theo `executing-plans`. Mỗi task là một đơn vị độc lập, chạy đúng lệnh, đúng thứ tự. Không vượt phase. Không tự đánh dấu "complete" nếu test gate chưa xanh.
>
> **Nguồn bắt buộc:** `docs/wip/plan_checkpoint_resume_recovery_authoritative.md` (§10 phase P0: Phase 0→5), `ARCHITECTURE.md`, `docs/wip/del_SKILL.md`.

**Goal:** Hoàn tất toàn bộ P0 — cancel scoped, contract `resume_required` 409, close-as-partial canonical (cancel-and-wait), checkpoint-key resolver thống nhất, và integration gate 451→close→recovery.

**Architecture:** Giữ MVP "B nâng cấp" (recovery = namespace mới + task mới; checkpoint nguồn bất biến; executor dừng khi lỗi terminal). Chỉ sửa các file đã liệt kê. Không đổi sang C, không `force_retranslate` trong recovery.

**Tech stack:** Python 3.10+ / Flask / SQLite (WAL) / vanilla JS. Không thêm dependency. Test bằng `pytest` trong `.venv`.

---

## 0.0 REV-B — Các sửa chữa bắt buộc so với bản nháp đầu (đã đối chiếu mã nguồn thật)

> **Đọc mục này trước khi code.** Bản nháp trước có 9 lỗi chặn (sẽ làm test đỏ hoặc phá dữ liệu thật) và 8 lỗi tiềm ẩn. Tất cả đã được sửa **trực tiếp trong các phase bên dưới**; mục này chỉ để bạn biết *tại sao* các bước đọc khác so với trước.

| # | Vấn đề trong bản nháp | Bằng chứng trong mã | Đã sửa ở đâu |
|---|---|---|---|
| B1 | Phase 0 "Create `tests/conftest.py`" — file **đã tồn tại** (50 dòng, chứa `sys.path.insert` + fixture `flask_app`/`flask_client`/`workspace_dir`…). Ghi đè sẽ làm hỏng các test đang xanh. | `tests/conftest.py:1-50` | Phase 0 Step 1 → **APPEND**, không ghi đè |
| B2 | `resolve_checkpoint_key` dùng `info.get("filename")` nhưng `get_resume_info()` **không trả key `filename`** → luôn fallback về chính key vật lý → `get_done_pending_indices` hash-of-hash → path sai → 400. | `services/checkpoint_service.py:717-772` (dict trả về không có `filename`) | Phase 0.5 (mới): thêm `filename` vào `get_resume_info`, resolver đọc metadata trực tiếp |
| B3 | Phase 1 Step 5 gọi `resolve_checkpoint_key` nhưng hàm này chỉ được tạo ở Phase 4 Step 1 → Phase 1 không chạy được. Bản nháp cũng tự thừa nhận Phase 3 phải chạy sau Phase 4. | thứ tự phase trong chính tài liệu | Resolver được hoisted lên **Phase 0.5**, trước mọi phase dùng nó |
| B4 | `checkpoint_key` ghi vào task row là **tên logic** (`book.txt`, từ `emit("task_failed", checkpoint_key=output_filename)`), còn `_checkpoint_key_for()`/payload 409 là **tên vật lý** (`f1ed….db`) → `/api/tasks/by-checkpoint/<key>` so sánh thô luôn 404 → **Phase 5 Step 3 fail**. | `core/executor.py:249`, `webui/routes/projects.py:1510` | Phase 0.5 + Phase 4: mọi so sánh đi qua `same_checkpoint_key()` |
| B5 | Executor **xóa checkpoint** khi identity lệch: `saved_ident == identity` (so sánh 13 field gồm cả provider) → `init_session(reset=True)` → `DELETE FROM chunks`. Phase 2 mở đường "Tiếp tục" cho identity nguồn khớp → bấm Tiếp tục sau khi đổi provider = **mất 17 chunk đã dịch**. | `core/executor.py:166-193`, `services/checkpoint_service.py:139-141` | **Phase 0.5 Step 3** (bắt buộc trong P0, không dời sang Phase 6) |
| B6 | `emit_event` ghi failure 2 lần, `registry.append_event` ghi lần thứ 3 với `completed_chunks=task.current` (=0 với single-file) → **ghi đè 17 chunk đúng bằng 0**. | `task_registry.py:159-176` | Phase 1 Step 5 viết lại: chỉ 1 nguồn ghi failure |
| B7 | Event `"error"` (kwargs phẳng) và `"task_failed"` (lồng `error_context`) khác shape; bản nháp chỉ đọc `error_context` cho cả hai và mark `failed` ngay ở `"error"` — mà `ProgressLogHandler` cũng phát `"error"` từ log record thường → task bị đánh fail oan. | `core/executor.py:681-687` vs `246-249` | Phase 1 Step 5: chuẩn hóa 2 shape, chỉ `task_failed` mới terminal |
| B8 | Test E2E Phase 5 dùng fake fail cứng tại `idx == 17` cho **cả** lần dịch đầu **và** lần recovery → recovery fail lại tại 17 → `rec_task["status"] == "completed"` không bao giờ đúng. | logic fake trong chính test | Phase 5 Step 2: fake **stateful** (chỉ fail lần gặp đầu tiên) |
| B9 | `scan_and_recover` so sánh `t.get("checkpoint_key") == db_file.name` thô → task cũ lưu tên logic sẽ không match → **mỗi lần khởi động sinh thêm 1 task resumable trùng** trong `workspace/tasks.db` (dữ liệu thật). | `webui/__init__.py:118` | Phase 4: dedupe qua `same_checkpoint_key()` |
| B10 | **Test E2E không thể tạo 24 chunk.** `"\n\n".join(f"chunk {i}")` + `chunk_size` mặc định 22000 → chunker legacy trả **1 chunk** (`len(text) <= max_chars`). Đã chạy thử để xác nhận. Mọi assertion 17 done / 7 pending / `count("CHUNK")==7` đều không thể đúng. | `plugins/translation/chunker.py:450`, đã kiểm chứng bằng `process_text_for_chunking` | Phase 0 `make_chunked_source()` + `chunk_size=2400` (đã kiểm chứng: đúng 24 chunk) |
| B11 | Executor **tự xóa checkpoint khi dịch thành công** (`cleanup(output_filename)`). Assertion kiểu "sau khi xong vẫn còn 24 done" là sai. | `core/executor.py:284` | Phase 0.5 Step 4 + Phase 5 assert theo hướng khác |
| L1 | `<path:checkpoint_key>` + `self.checkpoint_dir / cand` không validate → path traversal (`../../etc/passwd`). | route mới trong Phase 4 | Phase 0.5 Step 2: `_assert_safe_key()` |
| L2 | `tests/integration/` thiếu `__init__.py` và repo **không có** cấu hình pytest nào (`pytest.ini`/`setup.cfg`/`tool.pytest.ini_options`) → `from tests.conftest import SyncThread` phụ thuộc rootdir may rủi. | không tìm thấy file cấu hình | Phase 0 Step 2: import qua fixture/`conftest` chung, thêm `__init__.py` |
| L3 | `_cancel_all` chỉ xuất hiện trong `runtime_state.py` (4 chỗ, 0 caller ngoài) → phải **xóa hẳn**; bản nháp vẫn đọc nó trong `is_cancelled` (vẫn còn cancel poisoning). | `runtime_state.py:53,80,84,95` | Phase 1 Step 1: xóa hoàn toàn |
| L4 | `executor.recover_from_checkpoint()` **không có** `job_id` → `test_cancel_recovery_isolated` là test rỗng (recovery chạy xong trước khi cancel dưới `SyncThread`). | `core/executor.py:312` | **REV-C C3:** sửa ngay trong P0, không còn placeholder/P1 |
| L5 | `update_recovery_task()` có allowlist **không chứa** `checkpoint_key` → `projects.py:2049` truyền `checkpoint_key=recovery_ck_key` bị **âm thầm bỏ qua**. | `services/task_store.py` allowlist | Phase 4 Step 6: dùng `update_status` cho field này |
| L6 | `recovery_progress` dùng `event["type"]` (bracket) → `KeyError` với event thiếu `"type"`. | `webui/routes/projects.py:2116` | Phase 4 Step 7 |
| L7 | Step 6b/6c của Phase 1 mô tả tự mâu thuẫn ("sau `if translated_text:` … ngay trước `if translated_text:`"). | chính tài liệu | Phase 1 Step 6: anchor chính xác kèm số dòng |
| L8 | `executor.translate_text` gọi `RuntimeState().reset_cancel(job_id)` ở dòng đầu → trong vòng lặp fallback, cancel phát ra ở file 1 bị **xóa sạch** khi file 2 bắt đầu. | `core/executor.py:144` | Phase 1 Step 6d: check cancel **trước** mỗi `translate_text` |
| L9 | `tasks.py::get_task` fallback đọc checkpoint bằng `CheckpointService()` — **thư mục mặc định hardcode** `workspace/checkpoints`, bỏ qua `AppConfigService().get_checkpoints_dir()`. Sai tiến độ nếu user đổi thư mục checkpoint; và ghi/đọc sai chỗ trong test tmp. | `webui/routes/tasks.py:106` | Phase 4 Step 5 |
| L10 | `TranslationExecutor.__init__` cũng hardcode `CheckpointService("workspace/checkpoints")` — lệch với route (dùng AppConfigService). | `core/executor.py:60` | Phase 0.5 Step 3b (additive: `config.get("checkpoint_dir")`) |
| L11 | `TaskStore.update_status(task_id, status, **kwargs)` ghép SQL từ **key của kwargs** (không allowlist). Gõ sai tên cột → `OperationalError` lúc runtime, không phải lúc test. Mọi lời gọi mới phải dùng đúng tên cột trong `_row_to_task`. | `services/task_store.py` | ghi chú ở §4 |

**Thứ tự phase sau khi sửa:** 0 → **0.5 (mới)** → 1 → 2 → 3 → 4 → 5. Phase 0.5 là hạ tầng dùng chung (resolver + identity nguồn); không có nó thì Phase 1/3/4/5 đều không xanh được.

## 0.0-REV-C — Bản vá bắt buộc sau review khả năng thực thi

> **Quy tắc ưu tiên:** mục này ghi đè mọi đoạn/snippet mâu thuẫn ở các phase phía dưới. Model sinh mã phải đọc và áp dụng REV-C trước khi thực hiện bất kỳ step nào. Không được tuyên bố P0 hoàn tất nếu các điều kiện dưới đây chưa có test thật.

### C1 — E2E phải tạo đúng 24 chunk

`tests/integration/test_resume_recovery_e2e.py` không được dùng `_source_text()` ngắn kiểu `"chunk 0"...` với chunk size mặc định. Dùng lại helper `make_chunked_source()` từ Phase 0, hoặc tạo source tương đương dài khoảng 1200 ký tự/block, và gửi rõ:

```python
E2E_CHUNK_SIZE = 2400
E2E_TOTAL_CHUNKS = 24

resp = client.post(
    "/api/projects/p/translate",
    json={"files": ["book.txt"], "model": "gpt-test", "chunk_size": E2E_CHUNK_SIZE},
)
```

Fake phải nhận diện nhãn `SEG000`…`SEG023` hoặc một index tương đương đã được kiểm chứng. Test bắt buộc assert ngay sau chunking/translation rằng tổng là 24; nếu không đạt thì dừng, không sửa assertion để che lỗi.

### C2 — Fake 451 chỉ fail một lần

Fake trong E2E phải dùng state theo test:

```python
state = {"failed": False}
if idx == CENSOR_AT and not state["failed"]:
    state["failed"] = True
    return None, "censorship_blocked", "key-451"
```

Recovery phải gửi được chunk 17–23 và hoàn tất. Không dùng fake fail vĩnh viễn tại `idx == 17`. Test phải assert cả `sent_initial == [0..17]` và `sent_recovery == [17..23]`, thay vì gộp toàn bộ log rồi chỉ lọc `>= 17`.

### C3 — Cancel recovery là P0 bắt buộc, không phải test placeholder

Các đoạn cũ nói `recover_from_checkpoint()` chưa có `job_id` và dời sang P1 bị ghi đè như sau:

- `TranslationExecutor.recover_from_checkpoint(..., job_id: str, ...)` phải nhận job ID.
- Vòng lặp recovery phải kiểm tra `RuntimeState().is_cancelled(job_id)` trước mỗi request và phát đúng event `cancelled`.
- Route recovery truyền `recovery_job_id` vào executor.
- `cancel_task` chỉ đánh dấu `cancel_requested`/gửi token; không reset token hoặc ghi terminal `cancelled` trước khi worker xác nhận dừng. Worker/event writer mới là nơi chốt terminal state.
- Test cancel recovery phải dùng worker thật chạy trên thread controllable + barrier/provider block, không dùng `SyncThread` đã hoàn tất trước khi gọi cancel.
- P0 chỉ hoàn tất khi chứng minh cancel recovery không dừng task nguồn và job B, recovery checkpoint vẫn đọc được và worker thực sự đã dừng.

`SyncThread` chỉ được dùng cho các test route không cần concurrency; không được dùng để chứng minh cancel, wait hoặc race.

### C4 — Close-and-wait phải chứng minh worker đã rời vùng ghi checkpoint

Không coi việc task store đổi status là bằng chứng worker đã kết thúc. P0 phải chọn một contract cụ thể và test được:

1. Worker registry giữ `Thread`/completion event theo `job_id`, route gọi `join(timeout)`/completion event trước assemble; hoặc
2. Worker phát completion event sau khi toàn bộ `save_chunk()`/finally đã kết thúc, route chờ event đó; hoặc
3. Có lease/heartbeat tối thiểu và một write barrier rõ ràng.

Chỉ polling `TaskStore.status` là **không đủ**. Khi timeout, trả `202 close_pending`, không assemble, không đổi `closed_partial`, không dọn cancel token.

### C5 — Loại race reset cancel

Không reset cancel ở đầu `translate_text()` sau khi worker đã bắt đầu. Việc reset phải diễn ra tại boundary tạo job mới, trước khi worker chạy; hoặc dùng generation/token mới cho mỗi execution. Guard trước mỗi file là cần nhưng không đủ nếu `translate_text()` tự xóa token giữa guard và request. Phải có test cancel đúng tại cửa sổ này.

### C6 — Không silently bỏ file ở selected-files

P0 chỉ hỗ trợ recovery an toàn cho một file tại một thời điểm. Nếu request selected-files có nhiều file và ít nhất một file có checkpoint, frontend/backend phải trả contract rõ ràng (`multi_file_resume_requires_per_file_decision`) và không restart chỉ `names`, vì sẽ bỏ qua các file mới không có checkpoint. Không được gọi `force_retranslate` toàn bộ danh sách để che lỗi.

Nếu muốn hỗ trợ selected-files trong P0, phải triển khai quyết định per-file và test đầy đủ; nếu không, UI phải hiển thị thông báo chuyển sang xử lý từng file. P0 không được tuyên bố hỗ trợ batch nhiều file khi chưa có contract này.

### C7 — Impact tĩnh không thay thế impact hiện tại

Bảng impact ở Phase 0 chỉ là baseline tham khảo. GitNexus hiện cho thấy `_build_translate_worker` risk HIGH, `TaskRegistry.update_status` risk CRITICAL và `CheckpointService.get_resume_info` risk HIGH. Model phải chạy impact lại trước từng edit và đọc toàn bộ d=1 callers; không dùng kết luận LOW trong bảng cũ để bỏ qua.

### C8 — Baseline phải có snapshot, không chấp nhận “4 fail” mơ hồ

Phase 0 phải lưu commit/worktree fingerprint, lệnh test, danh sách test fail và traceback. Chỉ chấp nhận 4 failure nếu chứng minh cùng test/node/traceback với baseline trước sửa. Nếu số lượng hoặc traceback đổi, dừng. Full gate phải báo `new failures = 0`; không dùng “301 passed, 4 failed” như một trạng thái xanh.

---

## 0. Baseline đã khóa (kiểm chứng trước khi bắt đầu)

Chạy ngay khi nhận việc; nếu lệch thì báo cáo chứ không sửa production.

```bash
cd /Users/narga/Briefcase/Projects/Novel-Translator
.venv/bin/python -m pytest tests/unit/test_checkpoint_resume.py tests/unit/test_endpoint_policy.py tests/unit/test_task_store.py -q
# Kỳ vọng: 28 passed
.venv/bin/python -m pytest -q --ignore=test_debug.py
# Kỳ vọng: 301 passed, 4 failed (test_file_operations::TestSplitFiles x2, test_provider_services::TestPromptServiceMethods x2) — LÀ pre-existing, KHÔNG sửa
git status --short   # đúng 18 file modified + docs/wip/ untracked (đã có từ trước, KHÔNG reset/checkout/stash)
```

**Pre-flight bắt buộc (mới — chống lỗi im lặng ở runtime thật):**

```bash
# 1. TaskStore._row_to_task zip theo VỊ TRÍ với 28 tên cột hard-code.
#    DB thật đã qua _migrate_schema/ALTER nên thứ tự cột phải khớp đúng.
sqlite3 workspace/tasks.db "PRAGMA table_info(tasks)" | awk -F'|' '{print $1, $2}'
# So sánh thứ tự với list keys trong services/task_store.py::_row_to_task.
# LỆCH THỨ TỰ → DỪNG, báo cáo. KHÔNG migrate, KHÔNG sửa DB.

# 2. Đếm task đang có theo checkpoint_key để phát hiện B9 (task resumable trùng) sau này
sqlite3 workspace/tasks.db "SELECT checkpoint_key, COUNT(*) FROM tasks GROUP BY checkpoint_key HAVING COUNT(*)>1"
# Ghi kết quả vào báo cáo Phase 0 (baseline). Sau Phase 4 con số này KHÔNG được tăng.
```

Schema `workspace/tasks.db` hiện có đủ cột recovery (xác nhận qua `sqlite3 workspace/tasks.db "PRAGMA table_info(tasks)"`). Đây là dữ liệu thật — **không xóa, không migrate lại, không chạm** vào các dòng task hiện có.

Impact (đã chạy, kết quả ghi vào đây để không chạy lại):

| Symbol | d=1 | Risk | Ghi chú |
|---|---:|---|---|
| `RuntimeState` | 4 | LOW | thêm lock + bỏ global cancel |
| `request_cancel` | 1 | LOW | route cancel duy nhất |
| `close_as_partial` | 0 | LOW | route thay toàn bộ |
| `recover_from_checkpoint` (route + executor) | 0 | LOW | chỉ đổi cách resolve key |
| `CheckpointService` | 7 | MEDIUM | thêm method mới, không đổi method cũ |
| `TaskStore` | 5 | MEDIUM | chỉ thêm 1 method lookup, không đổi schema |
| `get_resume_info` | 9 | MEDIUM | **chỉ THÊM key `filename`** vào dict trả về; mọi caller dùng `.get()` nên additive là an toàn |
| `translate_text` | 6 | MEDIUM | sửa cổng resume (so identity nguồn) — xem Phase 0.5 Step 3 |
| `_checkpoint_key_for` | 2 | LOW | giữ nguyên hành vi, chỉ thêm resolver bọc ngoài |

Chưa có symbol nào HIGH/CRITICAL → được phép sửa.

---

## 1. Luật áp dụng mọi phase

1. Trước khi sửa mỗi symbol, chạy `gitnexus_impact({target, direction:"upstream", repo:"ai-vi-translator"})`; ghi d=1/risk vào báo cáo phase. HIGH/CRITICAL → dừng.
   **Nếu MCP GitNexus không có trong session** (tool không tồn tại / index stale): KHÔNG bỏ qua bước impact — thay bằng (a) bảng impact đã ghi ở §0 phía trên, và (b) `grep -rn "<symbol>" --include="*.py" --include="*.js" .` rồi **đọc từng caller** trước khi sửa. Ghi rõ trong báo cáo phase là đã dùng đường thay thế nào.
2. Không reset/checkout/stash/xóa DB/xóa checkpoint. Không sửa file ngoài danh sách phase.
3. Tên trạng thái canonical khi **ghi**: `queued|running|completed|failed|resumable|interrupted|cancelled|closed_partial`. KHÔNG ghi `partial_completed`, `started`, `paused` từ code mới.
   Khi **đọc** thì vẫn phải chấp nhận giá trị legacy: `Task.__init__` hiện set `status="started"`, `Task.iter_events` coi `"paused"` là terminal, `tasks.py::get_task` kiểm tra `("resumable","paused","failed","interrupted")`. P0 **không** đổi các chỗ này (ngoài scope) → mọi so sánh mới phải dùng tập hợp bao gồm cả legacy, không dùng `==` với một giá trị duy nhất.
4. Index trong DB/checkpoint là **0-based**; UI hiển thị **1-based**. Không suy tập index từ `next_chunk_index` hay `done_count`.
5. Không hash lại chuỗi đã là tên file `.db` / MD5 stem (chống hash-of-hash). Cụ thể: `CheckpointService._get_db_path(x)` = `md5(x)[:12] + ".db"` → nếu `x` đã là `f1ed388c8e76.db` thì kết quả là một file **khác** và rỗng. Mọi chỗ nhận `checkpoint_key` từ HTTP/DB phải đi qua `resolve_checkpoint_key()` (Phase 0.5).
6. Cuối mỗi phase: test gate xanh + `git diff` chỉ nằm trong scope phase. Cuối tất cả: `gitnexus_detect_changes(scope:"all")` (nếu MCP không có → `git diff --stat` + đọc lại danh sách file của từng phase và xác nhận không có file lạ).
7. **Không sửa `workspace/tasks.db` và `workspace/checkpoints/` bằng tay trong bất kỳ phase nào.** Mọi test phải chạy trên `tmp_path`. Nếu một test cần `WORKSPACE_DIR`, set qua `monkeypatch.setenv` — không export ra shell.

---

## Phase 0 — Test harness (bắt buộc, không đụng production)

**Files:**
- **Modify (APPEND, KHÔNG ghi đè): `tests/conftest.py`** ← file này **đã tồn tại** (50 dòng)
- Create: `tests/integration/__init__.py` (rỗng)
- Create: `tests/unit/test_cancel_scoped.py` (đi cùng Phase 1)

> **⚠️ B1 — `tests/conftest.py` ĐÃ TỒN TẠI.** Nó đang giữ `PROJECT_ROOT`/`sys.path.insert` (điều kiện để mọi test import được `services.*`, `webui.*`) và các fixture `project_root`, `config_dir`, `workspace_dir`, `app_config_path`, `flask_app`, `flask_client`. Ghi đè = 301 test đang xanh chuyển thành lỗi import. **Chỉ APPEND vào cuối file.** Không tên fixture nào dưới đây trùng với fixture đã có (đã kiểm tra), nên append là an toàn.

- [ ] **Step 1: APPEND vào cuối `tests/conftest.py`** (giữ nguyên 50 dòng đầu)

```python
# ============================================================
# P0 harness (append 2026-08-16) — cancel scoped / resume / recovery
# `pytest`, `Path`, `sys.path.insert(PROJECT_ROOT)` đã có ở đầu file; không import lại.
# ⚠️ KHÔNG dùng fixture `workspace_dir`/`flask_app`/`flask_client` sẵn có trong các test P0:
#    `workspace_dir` trỏ workspace THẬT và `flask_app` gọi create_app() (chạy startup scan +
#    ghi vào workspace/tasks.db thật). Test P0 chỉ dùng `tmp_path` + `sync_app`.
# ============================================================
import re as _re

from services.checkpoint_service import CheckpointService
from services.task_store import TaskStore

# Chunker legacy: process_text_for_chunking(text, min_chars=size-2000, max_chars=size).
# Đã kiểm chứng bằng chính chunker: 24 câu x 1207 ký tự + chunk_size=2400 → ĐÚNG 24 chunk,
# mỗi chunk 1 câu (không gộp, không cắt). ĐỪNG đổi 2 hằng số này nếu không chạy lại kiểm chứng.
E2E_CHUNK_SIZE = 2400
E2E_TOTAL_CHUNKS = 24


def make_chunked_source(n: int = E2E_TOTAL_CHUNKS, body_chars: int = 1200) -> str:
    """Sinh source ép chunker tạo ĐÚNG n chunk, mỗi chunk mang nhãn SEG{index:03d}.

    Mỗi block là MỘT câu (kết thúc bằng '.', không có dấu câu bên trong) dài ~1207 ký tự:
      - < max_chars (2400) → không rơi vào fallback intelligent_chunking
      - 2 block = 2415 > 2400 → không bao giờ gộp 2 block vào 1 chunk
      - > min_chars*0.3 = 120 → không bị hậu xử lý "gộp chunk nhỏ"
    KHÔNG dùng chữ "CHUNK" trong nhãn: test đếm marker "[CHUNK n CHƯA DỊCH …]" bằng
    text.count("CHUNK") nên nhãn nguồn phải không chứa chuỗi đó.
    """
    filler = ("ma " * (body_chars // 3)).strip()
    return "\n\n".join(f"SEG{i:03d} {filler}." for i in range(n))


def make_fake_robust_translate(sent_log, fail_at=None, fail_once=True,
                               fail_status="censorship_blocked"):
    """Fake cho `core.executor.robust_translate` — KHÔNG gọi mạng.

    Chữ ký thật (core/executor.py:659) gọi bằng keyword:
        robust_translate(original_chunk=…, api_manager=…, prompts=…,
                         config_params=…, previous_chunk_context=…)
    → trả về tuple (result, status, api_key_used). Nhận **kwargs để không vỡ nếu
    executor thêm tham số.

    `fail_once=True` (mặc định) là BẮT BUỘC cho luồng 451→recovery: nếu fail vĩnh viễn
    tại `fail_at` thì lần recovery sẽ fail lại đúng chunk đó và task recovery không bao
    giờ `completed` (đây chính là lỗi B8 của bản nháp).
    """
    state = {"failed": False}

    def fake_rt(original_chunk=None, api_manager=None, prompts=None,
                config_params=None, previous_chunk_context="", **kwargs):
        m = _re.search(r"SEG(\d+)", original_chunk or "")
        idx = int(m.group(1)) if m else -1
        sent_log.append(idx)
        if fail_at is not None and idx == fail_at and not (fail_once and state["failed"]):
            state["failed"] = True
            return None, fail_status, "key-451"
        return f"[dịch {idx}]", "success", "key-ok"

    return fake_rt


@pytest.fixture
def rt_reset():
    """Reset singleton RuntimeState + TaskRegistry trước/sau mỗi test."""
    from backend.infrastructure.progress.runtime_state import RuntimeState
    from backend.infrastructure.progress.task_registry import TaskRegistry

    TaskRegistry._instance = None
    RuntimeState.reset()
    yield
    TaskRegistry._instance = None
    RuntimeState.reset()


@pytest.fixture
def task_store(tmp_path):
    return TaskStore(str(tmp_path / "ws"))


@pytest.fixture
def checkpoint_service(tmp_path):
    return CheckpointService(str(tmp_path / "ws" / "checkpoints"))


class FakeProvider:
    """Provider config giả cho route translate/recovery (không gọi mạng).

    `base_url` phải là host thật trong `classify_endpoint` (api.openai.com → NativeOpenAIPolicy)
    và model phải qua `validate_model` (đã kiểm chứng: "gpt-test" hợp lệ).
    """

    CONFIG = {
        "type": "openai",
        "api_key": "test-key",
        "gateway_api_key": "",
        "credential_mode": "default",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-test",
        "id": "openai-test",
        "name": "OpenAI Test",
    }

    def get_active_provider_config(self):
        return dict(self.CONFIG)

    def get_provider_by_id(self, provider_id):
        return dict(self.CONFIG)


@pytest.fixture
def fake_provider():
    return FakeProvider()


def bind_tmp_task_store(monkeypatch, workspace_dir):
    """Gắn TaskStore/TaskRegistry vào tmp workspace và CẮT mọi đường ghi vào DB thật.

    ⚠️ `webui/routes/tasks.py` tạo `registry = TaskRegistry(store=_get_task_store())` ở
    MODULE LEVEL. Vì TaskRegistry là singleton, sau khi ta set `_instance = None` và tạo
    instance mới, biến `webui.routes.tasks.registry` VẪN trỏ tới instance cũ đang gắn
    `workspace/tasks.db` THẬT — mọi POST /api/tasks/<id>/cancel trong test sẽ ghi vào dữ
    liệu thật. Phải patch cả biến module đó (đây là điều bản nháp thiếu).
    """
    from backend.infrastructure.progress.task_registry import TaskRegistry

    TaskRegistry._instance = None
    tmp_store = TaskStore(str(workspace_dir))
    registry = TaskRegistry(store=tmp_store)
    monkeypatch.setenv("WORKSPACE_DIR", str(workspace_dir))
    monkeypatch.setattr("webui.routes.tasks._task_store", tmp_store, raising=False)
    monkeypatch.setattr("webui.routes.tasks._get_task_store", lambda: tmp_store)
    monkeypatch.setattr("webui.routes.tasks.registry", registry)
    return tmp_store, registry


@pytest.fixture
def sync_app(tmp_path, monkeypatch):
    """Flask app tối thiểu (projects_bp + tasks_bp + translation_bp) trỏ tới tmp_path.

    TRÁNH create_app() thật vì nó chạy startup scan và tạo DB trong workspace thật.
    Tất cả route tạo TaskStore/CheckpointService qua _get_workspace_dir/_get_checkpoint_dir
    nên chỉ cần patch 2 hàm đó + _get_project_dir.

    Trả về: (client, tmp_store, ws, proj)
    """
    from flask import Flask

    from webui.routes.projects import projects_bp
    from webui.routes.tasks import tasks_bp
    from webui.routes.translation import translation_bp

    ws = tmp_path / "ws"
    ck_dir = ws / "checkpoints"
    proj = tmp_path / "proj"
    ck_dir.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("webui.routes.projects._get_checkpoint_dir", lambda: str(ck_dir))
    monkeypatch.setattr("webui.routes.projects._get_workspace_dir", lambda: str(ws))
    monkeypatch.setattr("webui.routes.projects._get_project_dir", lambda slug: proj)

    tmp_store, _registry = bind_tmp_task_store(monkeypatch, ws)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(translation_bp)

    return app.test_client(), tmp_store, ws, proj


class SyncThread:
    """Thread chạy inline — dùng để test route mà worker hoàn tất ngay trong request.

    Chỉ nhận các tham số mà production đang dùng (`target`, `args`, `daemon`).
    `join()`/`is_alive()` được cung cấp để route nào gọi cancel-and-wait (Phase 3) vẫn chạy.
    """

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self._done = False

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)
        self._done = True

    def join(self, timeout=None):
        return None

    def is_alive(self):
        return False
```

- [ ] **Step 2: Tạo `tests/integration/__init__.py` (rỗng) và kiểm tra import path**

```bash
mkdir -p tests/integration && touch tests/integration/__init__.py
ls tests/__init__.py tests/unit/__init__.py 2>/dev/null || echo "(thiếu __init__ ở tests/ hoặc tests/unit — xem ghi chú L2)"
.venv/bin/python -m pytest tests/unit/test_checkpoint_resume.py tests/unit/test_endpoint_policy.py tests/unit/test_task_store.py -q
# Kỳ vọng: 28 passed
```

> **L2 — repo KHÔNG có `pytest.ini`/`setup.cfg`/`[tool.pytest.ini_options]`.** Vì vậy `from tests.conftest import SyncThread` chỉ hoạt động nhờ rootdir + `sys.path.insert` trong `tests/conftest.py`. Trong các test mới, **ưu tiên dùng fixture** (`sync_app`) hoặc import trong hàm (`from tests.conftest import SyncThread` bên trong test) thay vì import ở module level; nếu import module-level báo `ModuleNotFoundError: tests`, thêm `tests/__init__.py` (không tạo file cấu hình pytest mới — ngoài scope P0).

- [ ] **Step 3: Exit gate Phase 0**

`git status --short` — production **chưa** đụng. Kỳ vọng chính xác:
- `M tests/conftest.py` (chỉ có phần append ở cuối; `git diff tests/conftest.py` không có dòng `-` nào ngoài dòng trắng cuối file)
- `?? tests/integration/` (chỉ chứa `__init__.py`)
- 18 file modified có từ trước vẫn nguyên trạng.

---

## Phase 0.5 — Hạ tầng dùng chung: resolver key + identity nguồn (MỚI, chặn Phase 1/3/4/5)

**Lý do phase này tồn tại:** bản nháp đặt `resolve_checkpoint_key` ở Phase 4 nhưng Phase 1 Step 5, Phase 3 Step 2 và Phase 5 đều gọi nó → không phase nào chạy được đúng thứ tự (B3). Đồng thời `get_resume_info()` không trả `filename` (B2) và executor xóa chunk khi identity lệch (B5) — hai lỗi này làm mọi phase sau vô nghĩa. Làm ở đây, một lần.

**Files:**
- Modify: `services/checkpoint_service.py` (chỉ THÊM; không đổi method cũ)
- Modify: `core/executor.py` (`_build_checkpoint_identity` + cổng resume)
- Create: `tests/unit/test_checkpoint_resolver.py`
- Create: `tests/unit/test_source_identity_resume.py`

**Impact trước edit:** `CheckpointService` d=1:7 MEDIUM; `get_resume_info` d=1:9 MEDIUM (chỉ additive); `translate_text` d=1:6 MEDIUM. Không HIGH/CRITICAL.

### Step 1: `services/checkpoint_service.py` — `get_resume_info` trả thêm `filename`

Thay đúng 1 dòng trong dict trả về của `get_resume_info` (dòng ~758-768), thêm key `filename` (additive, mọi caller dùng `.get()` nên không ai vỡ):

```python
            return {
                "can_resume": done_count < total,
                "filename": meta.get("filename") or filename,   # ← THÊM (B2)
                "next_chunk_index": next_chunk_index,
```
(giữ nguyên các key còn lại.)

> **Vì sao bắt buộc:** resolver trong bản nháp làm `logical = info.get("filename") or key`. Không có key này thì với `key = "f1ed388c8e76.db"` nó trả `filename = "f1ed388c8e76.db"`, rồi `get_done_pending_indices(filename)` hash lại chuỗi đã hash → mở file `md5("f1ed388c8e76.db")[:12].db` **không tồn tại** → `None` → route 400. Toàn bộ Phase 3/4/5 sẽ đỏ.

### Step 2: `services/checkpoint_service.py` — hằng số identity + resolver (chèn NGAY SAU `get_resume_info_from_path`, dòng ~795)

Phần A — module level, đặt ngay trước `class CheckpointService` (sau block `import`):

```python
# ============================================================
# Checkpoint identity: tách "nguồn" và "thực thi"
# Nguồn đổi  → checkpoint KHÔNG còn dùng được (phải dịch lại từ đầu).
# Thực thi đổi → checkpoint VẪN dùng được, chỉ cần ghi nhận mixed_provider.
# Dùng CHUNG cho core/executor.py và webui/routes/projects.py — không nhân bản logic.
# ============================================================
SOURCE_IDENTITY_FIELDS = (
    "project_file", "project_slug", "source_hash",
    "chunker_version", "chunk_size", "prompt_hash", "schema_version",
)
EXECUTION_IDENTITY_FIELDS = (
    "provider_kind", "provider_id", "base_url", "model", "qa_model", "credential_mode",
)


def source_identity(identity: Optional[dict]) -> Dict[str, str]:
    """Chỉ giữ các field quyết định checkpoint còn dùng được hay không."""
    identity = identity or {}
    return {k: str(identity.get(k, "")) for k in SOURCE_IDENTITY_FIELDS}


def execution_identity(identity: Optional[dict]) -> Dict[str, str]:
    identity = identity or {}
    return {k: str(identity.get(k, "")) for k in EXECUTION_IDENTITY_FIELDS}


def same_source_identity(saved: Optional[dict], current: Optional[dict]) -> bool:
    return source_identity(saved) == source_identity(current)


def execution_drift(saved: Optional[dict], current: Optional[dict]) -> List[str]:
    """Danh sách field thực thi đã đổi (sorted). Rỗng = không đổi."""
    a, b = execution_identity(saved), execution_identity(current)
    return sorted(k for k in EXECUTION_IDENTITY_FIELDS if a[k] != b[k])


def _is_hex12(value: str) -> bool:
    return len(value) == 12 and all(c in "0123456789abcdef" for c in value)
```

Phần B — method của `CheckpointService`, chèn sau `get_resume_info_from_path`:

```python
    @staticmethod
    def _assert_safe_key(key: str) -> str:
        """Chặn path traversal: key đến từ URL `<path:checkpoint_key>` và từ DB.

        Chỉ cho phép MỘT thành phần tên file. Không '/', '\\', '..', không absolute.
        """
        key = (key or "").strip()
        if not key:
            raise ValueError("checkpoint_key rỗng")
        if key in (".", "..") or "/" in key or "\\" in key or "\x00" in key:
            raise ValueError(f"checkpoint_key không hợp lệ: {key!r}")
        if Path(key).name != key:
            raise ValueError(f"checkpoint_key không hợp lệ: {key!r}")
        return key

    def physical_checkpoint_key(self, key: str) -> Optional[str]:
        """Chuẩn hóa key về TÊN FILE VẬT LÝ, KHÔNG cần đọc đĩa.

        - "f1ed388c8e76.db"  → chính nó          (đã vật lý, không hash lại)
        - "f1ed388c8e76"     → + ".db"           (MD5 stem)
        - "book.txt", "f1ed388c8e76.db.9a1b2c3d" → md5(...)[:12] + ".db"

        Nhận diện "đã vật lý" bằng ĐÚNG khuôn `<12 hex>.db` — không dùng
        `endswith(".db")` để một file nguồn tên "notes.db" không bị hiểu sai.
        Dùng cho SO SÁNH key (task row lưu tên logic, payload 409 lưu tên vật lý — B4/B9).
        """
        try:
            key = self._assert_safe_key(key)
        except ValueError:
            return None
        if key.endswith(".db") and _is_hex12(key[:-3]):
            return key
        if _is_hex12(key):
            return key + ".db"
        return self._get_db_path(key).name

    def same_checkpoint_key(self, a: Optional[str], b: Optional[str]) -> bool:
        """True nếu 2 key (logic hoặc vật lý, lẫn lộn tùy ý) chỉ về cùng 1 checkpoint."""
        if not a or not b:
            return False
        if a == b:
            return True
        pa, pb = self.physical_checkpoint_key(a), self.physical_checkpoint_key(b)
        return bool(pa) and pa == pb

    def _read_logical_filename(self, db_path: Path) -> Optional[str]:
        """Đọc metadata['filename'] — tên logic thật của checkpoint."""
        try:
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'filename'"
            ).fetchone()
            conn.close()
            return row[0] if row and row[0] else None
        except Exception as e:
            self._logger.error(f"❌ Lỗi đọc metadata filename: {e}")
            return None

    def resolve_checkpoint_key(self, key: Optional[str]) -> Optional[Dict[str, Any]]:
        """Resolve một checkpoint key bất kỳ về MỘT checkpoint vật lý duy nhất.

        Chấp nhận: logical filename ("book.txt"), tên file .db ("f1ed388c8e76.db"),
        MD5 stem ("f1ed388c8e76"), hoặc namespace recovery ("f1ed…db.9a1b2c3d").

        Trả về dict {checkpoint_key, filename, path, resume_info} hoặc None.
        `filename` là tên LOGIC đọc từ metadata của chính file đó — đây là giá trị
        duy nhất được phép truyền vào get_done_pending_indices / write_partial_file /
        assemble_partial / get_translated_chunks (các hàm đó tự hash).
        """
        if not key:
            return None
        try:
            key = self._assert_safe_key(key)
        except ValueError as e:
            self._logger.warning(f"⚠️ resolve_checkpoint_key bị từ chối: {e}")
            return None

        path = None
        # 1) key trỏ trực tiếp tới file trong checkpoint_dir (KHÔNG hash lại)
        for cand in (key, f"{key}.db"):
            p = self.checkpoint_dir / cand
            if p.is_file() and p.stat().st_size > 0:
                path = p
                break
        # 2) coi key là logical filename
        if path is None:
            lp = self._get_db_path(key)
            if lp.is_file() and lp.stat().st_size > 0:
                path = lp
        if path is None:
            return None

        logical = self._read_logical_filename(path)
        info = self.get_resume_info(logical) if logical else None
        # Bất biến: metadata phải trỏ về đúng file vừa mở. Nếu lệch (checkpoint bị copy
        # tay/rename) thì tin PATH, không tin metadata, và không hash lại.
        if logical and self._get_db_path(logical).name != path.name:
            self._logger.warning(
                f"⚠️ Checkpoint {path.name} có metadata filename={logical!r} không khớp hash; dùng path."
            )
            info = self.get_resume_info_from_path(str(path))

        return {
            "checkpoint_key": path.name,   # LUÔN là tên vật lý
            "filename": logical,           # có thể None nếu metadata hỏng
            "path": str(path),
            "resume_info": info,
        }
```

> `resolve_checkpoint_key` trả dict **kể cả khi `resume_info` là None** (checkpoint đã hoàn tất hoặc metadata hỏng). Caller phải tự kiểm tra `resolved["resume_info"]` trước khi dùng — Phase 4 Step 2 dựa vào đúng điều này.
>
> **Hợp đồng bắt buộc cho MỌI caller — `resolved["filename"]` có thể là `None`.**
> Chỉ `get_done_pending_indices` có tham số `db_path_override` (checkpoint_service.py:797);
> `write_partial_file`, `assemble_partial`, `clone_namespace`, `get_translated_chunks` **đều tự
> hash `filename`**. Truyền `None` vào chúng là `_get_db_path(None)` → `TypeError` giữa request.
> Vì vậy mọi caller dùng `filename` phải mở đầu bằng đúng 2 dòng này:
>
> ```python
> resolved = checkpoint_service.resolve_checkpoint_key(<key>)
> if not resolved or not resolved.get("filename"):
>     return jsonify({"error": "Checkpoint không đọc được hoặc metadata hỏng"}), 400
> ck_logical = resolved["filename"]
> ```
>
> Checkpoint mất `metadata.filename` là không dùng được với toàn bộ API hash-based — trả 400 là
> đúng, **không** được đoán tên từ task row (đoán sai sẽ hash sang một file khác và ghi partial rỗng).
> Caller chỉ cần đọc chỉ số (không assemble) thì được phép dùng
> `get_done_pending_indices(None, db_path_override=resolved["path"])` thay vì trả 400.

### Step 3: `core/executor.py` — resume theo identity NGUỒN, không bao giờ xóa chunk vì đổi provider (B5)

**Đây là bug phá dữ liệu, không phải tối ưu.** Hiện tại `saved_ident == identity` so cả 13 field; đổi model/provider → `init_session(..., reset=True)` → `DELETE FROM chunks` → mất toàn bộ chunk đã dịch. Phase 2 mở đường cho người dùng bấm "Tiếp tục" đúng vào luồng này.

3a. Thêm import (đầu file, cạnh các import `services.*`):

```python
from services.checkpoint_service import (
    CheckpointService,
    execution_drift,
    same_source_identity,
)
```
(nếu `CheckpointService` đã được import ở dạng khác thì chỉ thêm 2 tên mới, không nhân bản import.)

3b. `__init__` (dòng ~60) — cho phép trỏ checkpoint dir qua config, mặc định giữ nguyên hành vi:

```python
        self.checkpoint_service = CheckpointService(
            self.config.get("checkpoint_dir") or "workspace/checkpoints"
        )
```

3c. Thay cổng resume (dòng ~166-193) bằng:

```python
            if not self.force_retranslate:
                resume_info = self.checkpoint_service.get_resume_info(output_filename)

                can_resume = False
                if resume_info and resume_info.get("total_chunks") == len(chunks):
                    saved_ident = resume_info.get("identity", {})
                    if same_source_identity(saved_ident, identity):
                        can_resume = True
                        drift = execution_drift(saved_ident, identity)
                        if drift:
                            # Thực thi đổi (model/provider/base_url/...) KHÔNG làm checkpoint
                            # vô hiệu. Ghi nhận để UI/task hiển thị mixed_provider, giữ nguyên
                            # chunk đã dịch. TUYỆT ĐỐI không reset ở nhánh này.
                            emit(
                                "info",
                                message=(
                                    "Tiếp tục checkpoint với thông số thực thi đã thay đổi "
                                    f"({', '.join(drift)}). Chunk đã dịch được giữ nguyên."
                                ),
                                mixed_provider=True,
                                execution_drift=drift,
                            )
                    else:
                        emit(
                            "info",
                            message="Nội dung nguồn/chunk size/prompt đã thay đổi. Checkpoint cũ không dùng được, dịch lại từ đầu...",
                        )

                if can_resume:
                    translated_chunks = self.checkpoint_service.get_translated_chunks(output_filename)
                    start_index = resume_info.get("next_chunk_index", 0)
                    emit("info", message=f"Resume từ chunk {start_index + 1}/{len(chunks)}")
                    emit("progress", percent=15, message=f"Resume từ chunk {start_index + 1}/{len(chunks)}")

                    if start_index > 0 and (start_index - 1) in translated_chunks:
                        prev_context = self._tail_context(translated_chunks[start_index - 1])
                else:
                    self.checkpoint_service.init_session(
                        filename=output_filename,
                        total_chunks=len(chunks),
                        chunks_text=chunks,
                        identity=identity,
                        reset=True,
                    )
```

> **Không đổi `_build_checkpoint_identity`** — nó vẫn ghi cả 13 field vào metadata (execution identity là dữ liệu chẩn đoán cần thiết cho `mixed_provider`). Chỉ đổi *cách so sánh*.
>
> **Ghi chú `reset=True` còn lại:** nhánh else chỉ chạy khi (a) chưa có checkpoint, (b) `total_chunks` khác, hoặc (c) identity **nguồn** đổi — cả ba đều là trường hợp checkpoint thật sự vô giá trị. Đây là chỗ duy nhất trong P0 được phép `reset=True`.

### Step 4: Test Phase 0.5

Tạo `tests/unit/test_checkpoint_resolver.py`:

```python
import pytest

from services.checkpoint_service import (
    CheckpointService,
    execution_drift,
    same_source_identity,
)


def _ident(**over):
    base = {
        "project_file": "book.txt", "project_slug": "p",
        "source_hash": "h" * 8, "chunker_version": "v2", "chunk_size": "2400",
        "prompt_hash": "p" * 8, "schema_version": "1.0",
        "provider_kind": "native_openai", "provider_id": "openai-test",
        "base_url": "https://api.openai.com/v1", "model": "gpt-test",
        "qa_model": "gpt-test", "credential_mode": "default",
    }
    base.update({k: str(v) for k, v in over.items()})
    return base


@pytest.fixture
def ck(tmp_path):
    service = CheckpointService(str(tmp_path / "checkpoints"))
    service.init_session("book.txt", total_chunks=3, chunks_text=["a", "b", "c"],
                         identity=_ident())
    service.save_chunk("book.txt", 0, "a", "A", status="done")
    return service


def test_physical_key_khong_hash_lai(ck):
    physical = ck._get_db_path("book.txt").name
    assert ck.physical_checkpoint_key("book.txt") == physical
    assert ck.physical_checkpoint_key(physical) == physical          # đã vật lý
    assert ck.physical_checkpoint_key(physical[:-3]) == physical     # MD5 stem


def test_physical_key_khong_nhan_dam_file_nguon_ten_db(ck):
    # "notes.db" là tên file NGUỒN, không phải checkpoint vật lý → phải hash
    assert ck.physical_checkpoint_key("notes.db") == ck._get_db_path("notes.db").name


def test_same_checkpoint_key_logic_vs_vat_ly(ck):
    physical = ck._get_db_path("book.txt").name
    assert ck.same_checkpoint_key("book.txt", physical) is True
    assert ck.same_checkpoint_key(physical, physical[:-3]) is True
    assert ck.same_checkpoint_key("book.txt", "other.txt") is False
    assert ck.same_checkpoint_key(None, physical) is False


@pytest.mark.parametrize("key_kind", ["logical", "physical", "stem"])
def test_resolve_tra_ve_logical_filename(ck, key_kind):
    physical = ck._get_db_path("book.txt").name
    key = {"logical": "book.txt", "physical": physical, "stem": physical[:-3]}[key_kind]
    resolved = ck.resolve_checkpoint_key(key)
    assert resolved is not None
    assert resolved["checkpoint_key"] == physical
    assert resolved["filename"] == "book.txt"          # B2: KHÔNG được là tên vật lý
    assert resolved["resume_info"]["total_chunks"] == 3
    # filename dùng lại được ngay, không hash-of-hash
    idx = ck.get_done_pending_indices(resolved["filename"])
    assert idx["done_indices"] == [0]
    assert idx["pending_indices"] == [1, 2]


def test_resolve_khong_ton_tai_va_traversal(ck):
    assert ck.resolve_checkpoint_key("khong-co-file.txt") is None
    assert ck.resolve_checkpoint_key(None) is None
    assert ck.resolve_checkpoint_key("") is None
    for evil in ("../../etc/passwd", "..", "a/b.db", "\\\\srv\\x.db"):
        assert ck.resolve_checkpoint_key(evil) is None
        assert ck.physical_checkpoint_key(evil) is None


def test_resolve_namespace_recovery(ck):
    physical = ck._get_db_path("book.txt").name
    ck.clone_namespace("book.txt", f"{physical}.9a1b2c3d")
    resolved = ck.resolve_checkpoint_key(f"{physical}.9a1b2c3d")
    assert resolved is not None
    assert resolved["filename"] == f"{physical}.9a1b2c3d"
    assert resolved["checkpoint_key"] != physical      # namespace riêng, không đè nguồn


def test_identity_nguon_vs_thuc_thi():
    assert same_source_identity(_ident(), _ident(model="gpt-other")) is True
    assert same_source_identity(_ident(), _ident(source_hash="khac")) is False
    assert same_source_identity(_ident(), _ident(chunk_size=3000)) is False
    assert execution_drift(_ident(), _ident(model="gpt-other")) == ["model"]
    assert execution_drift(_ident(), _ident()) == []
```

Tạo `tests/unit/test_source_identity_resume.py` — chứng minh B5 đã hết:

```python
"""Đổi provider/model KHÔNG được xóa chunk đã dịch (B5)."""
import pytest

from core.executor import TranslationExecutor
from services.checkpoint_service import CheckpointService
from tests.conftest import E2E_CHUNK_SIZE, E2E_TOTAL_CHUNKS, make_chunked_source, make_fake_robust_translate


def _config(tmp_path, model="gpt-test"):
    return {
        "chunk_size": E2E_CHUNK_SIZE,
        "checkpoint_dir": str(tmp_path / "checkpoints"),
        "provider_kind": "native_openai",
        "provider_id": "openai-test",
        "base_url": "https://api.openai.com/v1",
        "model_name": model,
        "qa_model": model,
        "credential_mode": "default",
        "project_slug": "p",
        "prompts": {"main": "dịch đi"},
        "context_char_count": 200,
    }


def _run(monkeypatch, tmp_path, model, sent, fail_at):
    monkeypatch.setattr("core.executor.ApiManager", lambda keys: None)
    monkeypatch.setattr("core.executor.robust_translate",
                        make_fake_robust_translate(sent, fail_at=fail_at, fail_once=False))
    ex = TranslationExecutor(api_keys=["k"], config=_config(tmp_path, model))
    return ex.translate_text(
        text=make_chunked_source(),
        output_filename="book.txt",
        output_file_path=tmp_path / "out.txt",
        job_id="job-1",
    )


def test_doi_model_van_giu_chunk_da_dich(monkeypatch, tmp_path):
    sent = []
    assert _run(monkeypatch, tmp_path, "gpt-test", sent, fail_at=17) is None

    ck = CheckpointService(str(tmp_path / "checkpoints"))
    before = ck.get_done_pending_indices("book.txt")
    assert len(before["done_indices"]) == 17

    # Chạy lại với MODEL KHÁC → phải resume, không reset
    sent2 = []
    result = _run(monkeypatch, tmp_path, "gpt-other", sent2, fail_at=None)
    assert result is not None
    assert sorted(set(sent2)) == list(range(17, E2E_TOTAL_CHUNKS))   # chỉ gửi pending
    assert result.count("[dịch") == E2E_TOTAL_CHUNKS                 # ghép đủ 24 chunk
    # Dịch xong → executor tự dọn checkpoint (core/executor.py:284 `cleanup`), KHÔNG phải
    # do reset identity. Đừng assert done_indices == 24 ở đây (checkpoint đã bị xóa).
    assert ck.get_resume_info("book.txt") is None


def test_doi_noi_dung_nguon_thi_dich_lai_tu_dau(monkeypatch, tmp_path):
    sent = []
    _run(monkeypatch, tmp_path, "gpt-test", sent, fail_at=17)

    monkeypatch.setattr("core.executor.ApiManager", lambda keys: None)
    sent2 = []
    monkeypatch.setattr("core.executor.robust_translate",
                        make_fake_robust_translate(sent2, fail_at=None))
    ex = TranslationExecutor(api_keys=["k"], config=_config(tmp_path))
    ex.translate_text(text=make_chunked_source(n=E2E_TOTAL_CHUNKS, body_chars=1500),
                      output_filename="book.txt",
                      output_file_path=tmp_path / "out2.txt", job_id="job-2")
    assert 0 in sent2   # source_hash đổi → reset → dịch lại từ chunk 0
```

### Step 5: Test gate Phase 0.5

```bash
.venv/bin/python -m pytest tests/unit/test_checkpoint_resolver.py tests/unit/test_source_identity_resume.py -q
# Kỳ vọng: all passed (9 + 2)
.venv/bin/python -m pytest tests/unit/test_checkpoint_resume.py tests/unit/test_task_store.py tests/unit/test_endpoint_policy.py -q
# Kỳ vọng: 28 passed — additive không phá gì
.venv/bin/python -m pytest -q --ignore=test_debug.py
# Kỳ vọng: vẫn đúng 4 failed pre-existing, không thêm
git diff --stat   # chỉ services/checkpoint_service.py + core/executor.py + 2 test mới
```

---

## Phase 1 — Cancel scoped và loại bỏ cancel poisoning (P0)

**Files:**
- Modify: `backend/infrastructure/progress/runtime_state.py`
- Modify: `backend/infrastructure/progress/task_registry.py`
- Modify: `core/executor.py`
- Modify: `backend/application/use_cases/translate_project_files_use_case.py`
- Modify: `webui/routes/translation.py`
- Modify: `webui/routes/projects.py` (`_build_translate_worker.emit_event`)
- Test: `tests/unit/test_cancel_scoped.py`

**Impact trước edit:** `RuntimeState` d=1:4 LOW; `request_cancel` d=1:1 LOW. Đã xác nhận — không cần chạy lại.

### Step 1: `backend/infrastructure/progress/runtime_state.py` — thay toàn bộ nội dung

```python
# backend/infrastructure/progress/runtime_state.py
# RuntimeState - Quản lý runtime state cho WebUI

"""
RuntimeState tách global state ra khỏi webui/__init__.py.
Cung cấp singleton quản lý progress_queue, translation_result, v.v.

P0: Cancel luôn scoped theo job_id. KHÔNG còn global cancel.
"""

import logging
import threading
from queue import Queue
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class RuntimeState:
    """Quản lý runtime state cho WebUI."""

    _instance: Optional["RuntimeState"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls) -> "RuntimeState":
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._state_lock = threading.RLock()

        self.progress_queue: Queue = Queue()
        self.translation_result: Dict[str, Any] = {}
        self.translation_stats: Dict[str, Any] = {
            "translated_words": 0,
            "pending_words": 0,
            "tokens_used": 0,
            "total_input_words": 0,
            "total_done_words": 0,
            "total_translation_time": 0,
            "total_chunks_translated": 0,
            "cache_hit_rate": 0,
            "tm_hits": 0,
        }
        self.translation_memory = None
        # L3: KHÔNG còn `self._cancel_all` — attribute này là cửa hậu global cancel duy nhất
        # còn lại. Đã grep: chỉ runtime_state.py tự đọc/ghi nó (4 vị trí 53/80/84/95),
        # 0 caller ngoài file ⇒ xóa hẳn thay vì để lại và không bao giờ set.
        self._cancelled_jobs: Set[str] = set()

        logger.info("RuntimeState initialized")

    def reset_translation(self) -> None:
        """Reset translation state."""
        while not self.progress_queue.empty():
            try:
                self.progress_queue.get_nowait()
            except Exception:
                break
        self.translation_result = {}

    def set_translation_result(self, result: Dict[str, Any]) -> None:
        """Set translation result."""
        self.translation_result = result

    def get_translation_result(self) -> Dict[str, Any]:
        """Get translation result."""
        return self.translation_result

    def request_cancel(self, job_id: Optional[str] = None) -> None:
        """Yêu cầu dừng MỘT job.

        KHÔNG có global cancel: thiếu job_id → no-op (log cảnh báo) để không
        bao giờ kích hoạt dừng toàn bộ job khác.
        """
        if not job_id:
            logger.warning("request_cancel() thiếu job_id — bỏ qua để tránh global cancel")
            return
        with self._state_lock:
            self._cancelled_jobs.add(job_id)

    def is_cancelled(self, job_id: Optional[str] = None) -> bool:
        """Kiểm tra job cụ thể có bị yêu cầu dừng không. Không bao giờ true vì job khác."""
        if not job_id:
            return False
        with self._state_lock:
            return job_id in self._cancelled_jobs

    def reset_cancel(self, job_id: Optional[str] = None) -> None:
        """Xóa đúng token của job_id; KHÔNG đụng token job khác."""
        if not job_id:
            return
        with self._state_lock:
            self._cancelled_jobs.discard(job_id)

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
```

### Step 2: `backend/infrastructure/progress/task_registry.py` — 1 writer duy nhất cho failure + dọn token

> **Đây là step quan trọng nhất của Phase 1.** Nguồn gốc 2 blocker:
>
> - **B6 (clobber `completed_chunks` = 0):** `append_event` dòng 161 hiện tính
>   `completed = task.current if task else 0`. Nhưng `Task.current` CHỈ được cập nhật ở
>   `file_complete` / `complete` (task_registry.py:42-55) — event `progress` per-chunk KHÔNG
>   cập nhật `current`. Khi 1 file đơn fail ở chunk 7/24, `task.current` vẫn là **0**, nên
>   `update_status(..., completed_chunks=0)` **ghi đè** số chunk đã dịch thật xuống 0 trong
>   `tasks.db`. UI resume sau đó hiển thị "0/24 chunk" dù checkpoint có 6 chunk done.
> - **B7 (SSE đóng sớm, mất event `task_failed`):** `_translate_single_chunk` emit `"error"`
>   (executor.py ~681) **TRƯỚC**, rồi `translate_text` mới emit `"task_failed"` kèm
>   `error_context.http_status` + `checkpoint_key` (executor.py:246-249). `emit_event` hiện tại
>   (projects.py:1618) map `("error", "task_failed")` → `registry.update_status(job_id, "failed")`
>   ngay ở event `"error"`. `Task.iter_events` (task_registry.py:86) `break` khi
>   `status in (... "failed" ...)` ⇒ **stream SSE đóng trước khi `task_failed` được đẩy ra**.
>   Frontend không bao giờ nhận `http_status=451` + `checkpoint_key` ⇒ toàn bộ UX 451→resume chết.
>   Đây là lý do phải phân biệt rõ: `"error"` = **non-terminal** (lỗi 1 chunk), `"task_failed"` =
>   **terminal**.

**2a.** Thay toàn bộ `Task.append_event` phần phân loại event (task_registry.py:41-55) để `progress`
cập nhật `current`, và để `"error"` không còn tự làm task terminal:

```python
            evt_type = event.get("type", "")
            if evt_type == "progress":
                # Chunk-level progress: cập nhật current/total để completed_chunks không bị
                # ghi 0 khi task fail giữa file (B6). executor emit current=i+1, total=len(chunks).
                cur = event.get("current")
                tot = event.get("total")
                if isinstance(cur, int) and cur > self.current:
                    self.current = cur
                if isinstance(tot, int) and tot > 0:
                    self.total = tot
                if isinstance(event.get("percent"), int):
                    self.percent = event["percent"]
            elif evt_type == "file_complete":
                self.completed_files += 1
                if self.total_files > 0:
                    self.current = self.completed_files
                    self.total = self.total_files
                    self.percent = int((self.completed_files / self.total_files) * 100)
            elif evt_type in ("file_error", "batch_error", "error", "task_failed"):
                self.error_count += 1
            if evt_type in ("complete", "cancelled", "task_failed"):
                self.finished_at = time.time()
                if evt_type == "complete":
                    self.current = self.total_files
                    self.total = self.total_files
                    self.percent = 100
```

> ⚠️ Chú ý 2 điều: (1) `if evt_type in ("complete", ...)` là `if` **độc lập** (không `elif`) vì
> `task_failed` phải vừa tăng `error_count` vừa set `finished_at`. (2) `current` chỉ đi lên
> (`cur > self.current`) — batch nhiều file dùng `current = completed_files`, không được để
> progress của file sau kéo tụt số đã đếm.

**2b.** Thay toàn bộ `TaskRegistry.append_event` (dòng 152-176) — chỉ `task_failed` mới persist
trạng thái `failed`, và không bao giờ ghi `completed_chunks` xuống thấp hơn giá trị đang có:

```python
    # Chỉ những event này mới được phép chuyển task sang failed trong tasks.db.
    # "error" là lỗi cấp chunk/không terminal — KHÔNG persist failed (B7).
    _TERMINAL_FAILURE_EVENTS = ("task_failed",)

    @staticmethod
    def _error_context_of(event: Dict[str, Any]) -> Dict[str, Any]:
        """Chuẩn hóa 2 shape: task_failed (lồng error_context) và error (phẳng)."""
        ctx = event.get("error_context")
        if isinstance(ctx, dict) and ctx:
            return ctx
        return {
            "status": event.get("status"),
            "http_status": event.get("http_status"),
            "retryable": event.get("retryable"),
            "message": event.get("message"),
            "chunk_index": event.get("chunk_index"),
        }

    def append_event(self, job_id: str, event: Dict[str, Any]):
        task = self.get_task(job_id)
        if task:
            task.append_event(event)
        if not getattr(self, "_store", None):
            return
        self._store.append_event(job_id, event)

        if event.get("type") not in self._TERMINAL_FAILURE_EVENTS:
            return

        ctx = self._error_context_of(event)
        kwargs = {
            "error_class": ctx.get("status"),
            "http_status": ctx.get("http_status"),
            "retryable": ctx.get("retryable"),
            "last_error": ctx.get("message") or event.get("message"),
        }
        if event.get("checkpoint_key"):
            kwargs["checkpoint_key"] = event["checkpoint_key"]

        # B6: chỉ ghi completed_chunks khi có số dương VÀ không nhỏ hơn số đã lưu.
        # KHÔNG BAO GIỜ ghi 0 lên một task đã có tiến độ — checkpoint mới là nguồn sự thật.
        progress = task.current if task else 0
        if progress > 0:
            try:
                row = self._store.get_task_by_job_id(job_id) or {}
                if progress >= (row.get("completed_chunks") or 0):
                    kwargs["completed_chunks"] = progress
            except Exception:
                kwargs["completed_chunks"] = progress

        self._store.update_status(job_id, status="failed", **kwargs)
```

**2c.** Sửa `update_status` (dòng 178) — thêm status mới vào danh sách terminal + dọn cancel token:

```python
    def update_status(self, job_id: str, status: str):
        task = self.get_task(job_id)
        if task:
            with task._cond:
                task.status = status
                task.updated_at = time.time()
                if status in ("completed", "failed", "cancelled", "closed_partial"):
                    task.finished_at = time.time()
                task._cond.notify_all()
        if getattr(self, "_store", None):
            kwargs = {}
            if task:
                if task.current > 0:
                    kwargs["completed_chunks"] = task.current
                if task.checkpoint_key:
                    kwargs["checkpoint_key"] = task.checkpoint_key
            self._store.update_status(job_id, status, **kwargs)
        # Dọn cancel token sau khi task rời trạng thái đang chạy (chống poison job mới
        # cùng job_id). KHÔNG xóa token của job khác — reset_cancel chỉ discard đúng id.
        if status not in ("running", "started"):
            from backend.infrastructure.progress.runtime_state import RuntimeState
            RuntimeState().reset_cancel(job_id)
```

> Giữ nguyên `"started"` trong danh sách "đang chạy": `Task.__init__` (dòng 14) vẫn set
> `status="started"` và `list_active_tasks` fallback (dòng 207) filter theo `"started"`.
> Đổi default sẽ làm fallback in-memory trả rỗng — không sửa trong P0.

**2d.** Sửa danh sách terminal trong `Task.iter_events` (dòng 86) để SSE tự đóng ở trạng thái mới:

```python
                    if self.status in ("completed", "failed", "cancelled", "resumable", "paused",
                                       "closed_partial", "interrupted"):
                        break
```

**2e.** `create_task` (dòng 111) — nhận và forward `checkpoint_key` xuống store. Hiện tại signature
không có tham số này nên `translate_project_file` (projects.py:1738) **không thể** gán checkpoint_key
lúc tạo task; row chỉ có checkpoint_key sau khi `append_event` bắt được event đầu tiên mang key.
Phase 4 Step 5 (`/api/tasks/by-checkpoint/...`) phụ thuộc vào việc row có key ngay từ đầu:

```python
    def create_task(
        self,
        kind: str,
        title: str,
        total_files: int = 0,
        project_slug: str = "",
        filename: str = "",
        checkpoint_key: Optional[str] = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        task = Task(job_id, kind, title, total_files)
        task.checkpoint_key = checkpoint_key
        with self._lock:
            self._tasks[job_id] = task
        if getattr(self, "_store", None):
            self._store.create_task(
                job_id=job_id,
                kind=kind,
                title=title,
                project_slug=project_slug,
                filename=filename,
                total_chunks=total_files,
                checkpoint_key=checkpoint_key,
            )
        return job_id
```

> `TaskStore.create_task` đã có tham số `checkpoint_key=None` (task_store.py) — không cần sửa store.


### Step 3: `core/executor.py` — terminal event nhất quán + http_status trong error_context

**3a.** Thêm 2 helper module-level (đặt sau `logger = logging.getLogger(__name__)`, trước `_try_calculate_stats`):

```python
_STATUS_TO_HTTP = {
    "censorship_blocked": 451,
    "auth_error": 401,
    "model_not_found": 404,
    "invalid_request": 400,
    "upstream_empty": 204,
}

_RETRYABLE_STATUSES = {"all_keys_exhausted", "upstream_empty", "api_error"}


def _status_to_http_status(status: str) -> Optional[int]:
    return _STATUS_TO_HTTP.get(status)


def _status_retryable(status: str) -> bool:
    return status in _RETRYABLE_STATUSES
```

**3b.** Trong `translate_text`, nhánh check cancel trong vòng lặp (dòng ~213) — thay:

```python
                from backend.infrastructure.progress.runtime_state import RuntimeState
                if RuntimeState().is_cancelled(job_id):
                    emit("info", message="Đã dừng theo yêu cầu")
                    break
```
bằng:
```python
                from backend.infrastructure.progress.runtime_state import RuntimeState
                if RuntimeState().is_cancelled(job_id):
                    emit("cancelled", message=f"Đã dừng theo yêu cầu ở chunk {i + 1}/{len(chunks)}")
                    return None
```

**3c.** Nhánh "chưa đủ chunk" (dòng ~262) — thay:
```python
            if len(translated_chunks) != len(chunks):
                from backend.infrastructure.progress.runtime_state import RuntimeState
                if RuntimeState().is_cancelled(job_id):
                    emit("info", message="Dịch chưa hoàn tất do đã bị dừng.")
                else:
                    emit("error", message="Dịch chưa hoàn tất: vẫn còn chunk chưa xử lý")
                return None
```
bằng:
```python
            if len(translated_chunks) != len(chunks):
                from backend.infrastructure.progress.runtime_state import RuntimeState
                if RuntimeState().is_cancelled(job_id):
                    emit("cancelled", message="Dịch chưa hoàn tất do đã bị dừng.")
                else:
                    emit("error", message="Dịch chưa hoàn tất: vẫn còn chunk chưa xử lý")
                return None
```

**3d.** `_translate_single_chunk` — error_context phải mang `http_status` + `retryable` (dòng ~681). Thay:
```python
        error_context = {
            "chunk_index": i,
            "status": status,
            "message": f"Dịch thất bại tại chunk {i + 1}: {status}",
        }
        emit("error", **error_context)
        return {"_error": True, "context": error_context}
```
bằng:
```python
        error_context = {
            "chunk_index": i,
            "status": status,
            "http_status": _status_to_http_status(status),
            "retryable": _status_retryable(status),
            "message": f"Dịch thất bại tại chunk {i + 1}: {status}",
        }
        emit("error", **error_context)
        return {"_error": True, "context": error_context}
```

**3e. (BẮT BUỘC — hệ quả của B7)** Sau khi Step 2b làm `"error"` thành **non-terminal**, mọi đường
thoát terminal của `translate_text` mà hiện đang emit `"error"` sẽ **không còn** đánh dấu task failed.
Grep xác nhận có đúng 2 vị trí như vậy, phải đổi sang `task_failed` (cả 2 đều `return None` ngay sau):

Dòng ~267 (nhánh "chưa đủ chunk", nội dung sau khi áp 3c) — thay:
```python
                else:
                    emit("error", message="Dịch chưa hoàn tất: vẫn còn chunk chưa xử lý")
                return None
```
bằng:
```python
                else:
                    emit(
                        "task_failed",
                        error_context={
                            "status": "incomplete_chunks",
                            "http_status": None,
                            "retryable": True,
                            "message": "Dịch chưa hoàn tất: vẫn còn chunk chưa xử lý",
                        },
                        checkpoint_key=output_filename,
                    )
                return None
```

Dòng ~306 (`except Exception` ngoài cùng của `translate_text`) — thay:
```python
        except Exception as e:
            logger.error(f"Translation execution error: {e}", exc_info=True)
            emit("error", message=f"Lỗi: {e}")
            return None
```
bằng:
```python
        except Exception as e:
            logger.error(f"Translation execution error: {e}", exc_info=True)
            emit(
                "task_failed",
                error_context={
                    "status": "executor_exception",
                    "http_status": None,
                    "retryable": True,
                    "message": f"Lỗi: {e}",
                },
                checkpoint_key=output_filename,
            )
            return None
```

> Vì sao `retryable=True` cho cả 2: checkpoint vẫn còn nguyên (không có `cleanup` trên đường lỗi),
> nên chạy lại luôn resume được. Đây là dữ liệu cho UI quyết định hiện nút Resume, không phải
> auto-retry.

**3f. Không đổi `recover_from_checkpoint`.** Nó vẫn emit `"error"`/`"complete"` phẳng, nhưng
`recovery_progress` (projects.py:2114) **tự** gọi `registry.update_status(...,"failed")` +
`task_store.update_recovery_task(...)`, nên không phụ thuộc auto-persist của `append_event`.
Lỗi `event["type"]` → KeyError (L6) và việc recovery thiếu `job_id` (L4) xử lý ở Phase 4.


### Step 4: `webui/routes/translation.py` — legacy cancel thành compatibility shim (không global)

Route hiện tại (dòng 169-177) gọi `state.request_cancel()` **không có job_id** — sau Step 1 đây là
no-op nhưng vẫn trả `success: True`, tức là UI báo "đã dừng" mà không dừng gì. Phải trả 400 để lỗi
lộ ra thay vì im lặng. Thay toàn bộ route `cancel_translation`:

```python
@translation_bp.route("/api/translate/cancel", methods=["POST"])
def cancel_translation():
    """Compatibility shim: chỉ cancel khi có job_id. KHÔNG BAO GIỜ cancel toàn cục."""
    from backend.infrastructure.progress.runtime_state import RuntimeState
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id") or request.args.get("job_id")
    if not job_id:
        return jsonify({
            "error": "Thiếu job_id — không thể cancel toàn cục",
            "code": "job_id_required",
        }), 400
    state = RuntimeState()
    state.request_cancel(job_id)
    # GIỮ LẠI: SSE legacy của trang dịch đơn lẻ đọc từ progress_queue (generate() cùng file).
    # Bỏ dòng này là mất phản hồi "đã dừng" trên UI dịch đơn — đây là hồi quy UX, không phải dọn rác.
    from webui import progress_queue
    progress_queue.put({"type": "cancelled", "message": "Đã dừng theo yêu cầu"})
    return jsonify({"success": True, "message": "Đã gửi yêu cầu dừng"})
```

> Frontend nào đang gọi endpoint này mà chưa gửi `job_id` sẽ nhận 400. Đã grep
> `api/translate/cancel` trong `webui/static/js/` khi thực thi Step 4 — nếu có caller thiếu
> `job_id`, bổ sung `job_id` từ state của trang đó **trong cùng step này**, đừng để sang phase sau.


### Step 5: `webui/routes/projects.py` — `emit_event` trong `_build_translate_worker` (dòng 1614-1629)

**Nguyên tắc: 1 writer duy nhất.** Sau Step 2b, `registry.append_event` là nơi DUY NHẤT persist
metadata failure (`last_error/error_class/http_status/retryable/completed_chunks/checkpoint_key`).
`emit_event` **không** được gọi `registry._store.update_status` nữa — đó chính là cái tạo ra 3 lần
ghi chồng nhau (append_event → update_status → _store.update_status) với thứ tự không xác định.

Thay toàn bộ hàm `emit_event` bằng:
```python
            def emit_event(event):
                event_type = event.get("type", "info")
                # append_event TRƯỚC: nó là writer duy nhất của metadata failure, và phải chạy
                # khi task còn non-terminal để iter_events chưa break (B7).
                registry.append_event(job_id, event)
                if event_type == "complete":
                    registry.update_status(job_id, "completed")
                elif event_type == "task_failed":
                    registry.update_status(job_id, "failed")
                elif event_type == "cancelled":
                    registry.update_status(job_id, "cancelled")
                # "error" / "file_error" / "batch_error": KHÔNG terminal. Chỉ log vào stream.
                # Lỗi chunk lẻ không được đóng SSE trước khi task_failed kịp mang
                # http_status + checkpoint_key ra frontend.
```

Và sửa `except Exception` của worker (dòng 1646-1648) cho khớp giao ước mới — `"error"` không còn
đánh dấu failed, nên phải emit `task_failed`:
```python
        except Exception as e:
            logger.error(f"Lỗi Translate Worker: {str(e)}")
            registry.append_event(job_id, {
                "type": "task_failed",
                "message": f"❌ Lỗi hệ thống: {str(e)}",
                "error_context": {
                    "status": "worker_exception",
                    "http_status": None,
                    "retryable": False,
                    "message": f"❌ Lỗi hệ thống: {str(e)}",
                },
            })
            registry.update_status(job_id, "failed")
```

> **Thứ tự `append_event` trước `update_status` là bắt buộc, không phải style.**
> `Task.iter_events` break ngay khi `task.status` terminal. Nếu `update_status(...,"failed")` chạy
> trước, generator SSE có thể thoát trước khi event cuối được append ⇒ frontend mất event mang
> `error_context`. Đổi thứ tự = tái tạo B7.
>
> **Không cần `resolve_checkpoint_key` ở đây.** `completed_chunks` do Step 2b lấy từ `task.current`
> (đã đúng nhờ 2a) và có guard không-ghi-lùi; số chunk done chính xác luôn đọc từ checkpoint SQLite
> ở thời điểm resume (Phase 2), không phải ở thời điểm ghi log lỗi.


### Step 6: `backend/application/use_cases/translate_project_files_use_case.py` — cancel dừng batch + terminal đúng

> **Cạm bẫy phải biết trước khi sửa (L8):** `TranslationExecutor.translate_text` gọi
> `RuntimeState().reset_cancel(job_id)` ở **dòng 144** — tức mỗi lần gọi `translate_text` là **xóa
> sạch cancel token của job đó**. Hệ quả: người dùng bấm Dừng khi đang dịch file 1 của vòng
> fallback, đến file 2 `translate_text` reset token ⇒ `is_cancelled` False ⇒ **dịch tiếp toàn bộ
> file còn lại**. Vì vậy mọi guard cancel phải nằm **TRƯỚC** lời gọi `translate_text`, không chỉ sau
> nó. Guard sau lời gọi chỉ để không đếm fail oan.
>
> Không sửa `reset_cancel` ở dòng 144 trong P0: nó cần thiết để resume một job từng bị cancel không
> chết ngay. Sửa call-site là đúng chỗ.

**6a.** Terminal event đúng ở cuối `execute`. Hiện tại dòng 420-423 **luôn** emit `"complete"` bất kể
`fail`/cancel. Thay khối:
```python
        emit({
            "type": "complete",
            "message": f"🚀 Đã hoàn tất: {ok} thành công, {fail} thất bại, {skipped} bỏ qua, trên tổng {total_files} file!"
        })
```
bằng:
```python
        summary = f"{ok} thành công, {fail} thất bại, {skipped} bỏ qua, trên tổng {total_files} file!"
        if job_id and runtime_state.is_cancelled(job_id):
            emit({"type": "cancelled", "message": f"⏹️ Đã dừng theo yêu cầu: {summary}"})
        elif fail > 0 and ok == 0:
            # Chỉ terminal-fail khi KHÔNG có file nào thành công. Có file thành công thì
            # task vẫn là "completed" với error_count > 0 — người dùng còn kết quả để dùng.
            emit({
                "type": "task_failed",
                "message": f"🚫 Dịch thất bại: {summary}",
                "error_context": {
                    "status": "all_files_failed",
                    "http_status": None,
                    "retryable": True,
                    "message": f"🚫 Dịch thất bại: {summary}",
                },
            })
        else:
            emit({"type": "complete", "message": f"🚀 Đã hoàn tất: {summary}"})
```

> ⚠️ `runtime_state` được khai báo ở dòng 239, **trong** `execute` — khối trên nằm sau vòng batch nên
> vẫn trong scope. Nhưng nó nằm **sau** `save_meta_callback()` (dòng 414-415): giữ nguyên thứ tự đó,
> meta phải được lưu cả khi cancel.
>
> ⚠️ Không xoá `return {...}` ở dòng 425 và không đổi `success: ok > 0` — `_build_translate_worker`
> không đọc return value, nhưng test/caller khác có thể.

**6b.** Nhánh batch đơn. Guard **trước** lời gọi (dòng 271) và **sau** lời gọi (dòng 280).

Trước dòng 271 `result = executor.translate_text(` — chèn:
```python
                    if job_id and runtime_state.is_cancelled(job_id):
                        emit({"type": "info", "message": f"⏹️ Bỏ qua {filename}: đã có yêu cầu dừng."})
                        break
```
Sửa dòng 280 `if result:` thành:
```python
                    if job_id and runtime_state.is_cancelled(job_id):
                        # Bị dừng giữa file: KHÔNG đếm fail, KHÔNG emit file_error.
                        # Checkpoint còn nguyên nên file này resume được.
                        break
                    if result:
```

**6c.** Nhánh batch nhiều file. Trước dòng 320 `translated_text = executor.translate_text(` — chèn:
```python
                    if job_id and runtime_state.is_cancelled(job_id):
                        emit({"type": "info", "message": f"⏹️ Bỏ qua batch {batch_idx}: đã có yêu cầu dừng."})
                        break
```
Sửa dòng 329 `if translated_text:` thành:
```python
                    if job_id and runtime_state.is_cancelled(job_id):
                        break
                    if translated_text:
```

**6d.** Vòng fallback (dòng 354 `for fallback_filename in batch_files:`). Đây là chỗ L8 gây hại nhất
vì `translate_text` được gọi lặp lại. Ngay sau dòng 354, **trước** `fallback_text = ...`, chèn:
```python
                                if job_id and runtime_state.is_cancelled(job_id):
                                    emit({"type": "info", "message": "⏹️ Dừng vòng dịch lại (fallback) theo yêu cầu."})
                                    break
```
Và sửa dòng 385 `if result:` thành:
```python
                                    if job_id and runtime_state.is_cancelled(job_id):
                                        break
                                    if result:
```

> `break` ở 6d chỉ thoát vòng fallback; vòng batch ngoài (dòng 241) có guard đầu vòng
> (dòng 242-244) nên vòng kế tiếp cũng dừng. Đúng ý muốn: dừng tất cả, không bỏ sót.
>
> **Kiểm tra indent trước khi dán:** vòng fallback nằm sâu 8 cấp (36 space cho thân `for`,
> 40 space cho thân `try`). Dán sai indent ở đây là `IndentationError` — chạy
> `.venv/bin/python -m py_compile backend/application/use_cases/translate_project_files_use_case.py`
> ngay sau khi sửa file này.


### Step 7: Tạo `tests/unit/test_cancel_scoped.py`

```python
# tests/unit/test_cancel_scoped.py
import pytest

from backend.infrastructure.progress.runtime_state import RuntimeState
from backend.infrastructure.progress.task_registry import TaskRegistry
from services.task_store import TaskStore


@pytest.fixture(autouse=True)
def _reset_rt():
    RuntimeState.reset()
    yield
    RuntimeState.reset()


@pytest.fixture
def _reset_registry():
    TaskRegistry._instance = None
    yield
    TaskRegistry._instance = None


def test_cancel_A_does_not_stop_B():
    state = RuntimeState()
    state.request_cancel("job-A")
    assert state.is_cancelled("job-A") is True
    assert state.is_cancelled("job-B") is False


def test_cancel_then_restart_no_poison():
    state = RuntimeState()
    state.request_cancel("job-A")
    assert state.is_cancelled("job-A") is True
    state.reset_cancel("job-A")
    assert state.is_cancelled("job-A") is False


def test_reset_A_keeps_B_token():
    state = RuntimeState()
    state.request_cancel("job-A")
    state.request_cancel("job-B")
    state.reset_cancel("job-A")
    assert state.is_cancelled("job-A") is False
    assert state.is_cancelled("job-B") is True


def test_request_cancel_without_job_id_is_noop():
    state = RuntimeState()
    state.request_cancel()  # không job_id -> không set global
    assert state.is_cancelled("job-X") is False


def test_no_global_cancel_attribute_left():
    """L3: `_cancel_all` phải bị xóa hẳn, không chỉ 'không dùng nữa'."""
    state = RuntimeState()
    assert not hasattr(state, "_cancel_all")


def test_legacy_cancel_requires_job_id(sync_app):
    client, _store, _ws, _proj = sync_app

    r = client.post("/api/translate/cancel", json={})
    assert r.status_code == 400
    assert r.get_json()["code"] == "job_id_required"

    r = client.post("/api/translate/cancel", json={"job_id": "job-1"})
    assert r.status_code == 200
    assert RuntimeState().is_cancelled("job-1") is True


def test_cancel_task_route_only_cancels_that_job(sync_app):
    client, _store, _ws, _proj = sync_app
    client.post("/api/tasks/job-1/cancel", json={})
    assert RuntimeState().is_cancelled("job-1") is True
    assert RuntimeState().is_cancelled("job-2") is False


# ---- Regression B6/B7: giao ước terminal của event ----

def test_error_event_is_not_terminal(_reset_registry, tmp_path):
    """B7: event 'error' (lỗi 1 chunk) KHÔNG được chuyển task sang failed,
    nếu không SSE đóng trước khi task_failed mang http_status ra frontend."""
    store = TaskStore(str(tmp_path))
    registry = TaskRegistry(store=store)
    job_id = registry.create_task("translation", "T", 24)

    registry.append_event(job_id, {
        "type": "error", "chunk_index": 6, "status": "censorship_blocked",
        "http_status": 451, "retryable": False, "message": "chunk 7 bị chặn",
    })

    row = store.get_task_by_job_id(job_id)
    assert row["status"] != "failed"
    task = registry.get_task(job_id)
    assert task.status not in ("failed", "completed", "cancelled")


def test_task_failed_persists_error_context(_reset_registry, tmp_path):
    store = TaskStore(str(tmp_path))
    registry = TaskRegistry(store=store)
    job_id = registry.create_task("translation", "T", 24)

    registry.append_event(job_id, {
        "type": "task_failed",
        "checkpoint_key": "book.txt",
        "error_context": {
            "chunk_index": 6, "status": "censorship_blocked",
            "http_status": 451, "retryable": False, "message": "chunk 7 bị chặn",
        },
    })

    row = store.get_task_by_job_id(job_id)
    assert row["status"] == "failed"
    assert row["error_class"] == "censorship_blocked"
    assert row["http_status"] == 451
    assert row["checkpoint_key"] == "book.txt"
    assert "chunk 7" in (row["last_error"] or "")


def test_task_failed_flat_shape_is_normalized(_reset_registry, tmp_path):
    """B7: chấp nhận cả shape phẳng (không có error_context lồng)."""
    store = TaskStore(str(tmp_path))
    registry = TaskRegistry(store=store)
    job_id = registry.create_task("translation", "T", 24)

    registry.append_event(job_id, {
        "type": "task_failed", "status": "auth_error", "http_status": 401,
        "retryable": False, "message": "sai key",
    })

    row = store.get_task_by_job_id(job_id)
    assert row["status"] == "failed"
    assert row["error_class"] == "auth_error"
    assert row["http_status"] == 401


def test_failure_never_clobbers_completed_chunks(_reset_registry, tmp_path):
    """B6: task fail giữa file KHÔNG được ghi completed_chunks=0 lên tiến độ đã có."""
    store = TaskStore(str(tmp_path))
    registry = TaskRegistry(store=store)
    job_id = registry.create_task("translation", "T", 24)
    store.update_status(job_id, "running", completed_chunks=6)

    # task.current vẫn 0 vì chưa có event progress/file_complete nào
    registry.append_event(job_id, {
        "type": "task_failed",
        "error_context": {"status": "censorship_blocked", "http_status": 451,
                          "retryable": False, "message": "blocked"},
    })

    row = store.get_task_by_job_id(job_id)
    assert row["status"] == "failed"
    assert row["completed_chunks"] == 6, "completed_chunks bị ghi đè về 0 — B6 tái xuất"


def test_progress_event_advances_current(_reset_registry, tmp_path):
    """2a: progress per-chunk phải nâng task.current để completed_chunks có số thật."""
    store = TaskStore(str(tmp_path))
    registry = TaskRegistry(store=store)
    job_id = registry.create_task("translation", "T", 24)

    registry.append_event(job_id, {"type": "progress", "current": 7, "total": 24, "percent": 40})
    assert registry.get_task(job_id).current == 7

    # không đi lùi
    registry.append_event(job_id, {"type": "progress", "current": 3, "total": 24, "percent": 20})
    assert registry.get_task(job_id).current == 7

    registry.append_event(job_id, {
        "type": "task_failed",
        "error_context": {"status": "api_error", "http_status": None,
                          "retryable": True, "message": "x"},
    })
    assert store.get_task_by_job_id(job_id)["completed_chunks"] == 7
```

> **Chưa test được trong Phase 1 (ghi rõ để không tự lừa mình):** cancel một **recovery** task.
> `TranslationExecutor.recover_from_checkpoint` (executor.py:312-403) **không nhận `job_id`** và
> **không có** check `is_cancelled` trong vòng lặp ⇒ bấm Dừng trên recovery task chỉ đổi status trong
> DB, worker vẫn chạy tới hết. Đây là **L4**, xử lý ở Phase 4 Step 7. Không viết test
> `test_cancel_recovery_isolated` ở Phase 1 — một test luôn xanh vì không kiểm tra gì tệ hơn là
> không có test.

### Step 8: Test gate Phase 1

```bash
.venv/bin/python -m py_compile \
  backend/infrastructure/progress/runtime_state.py \
  backend/infrastructure/progress/task_registry.py \
  core/executor.py \
  backend/application/use_cases/translate_project_files_use_case.py \
  webui/routes/translation.py webui/routes/projects.py

.venv/bin/python -m pytest tests/unit/test_cancel_scoped.py \
  tests/unit/test_task_registry_persistence.py -q
# Kỳ vọng: PASS (12 test mới + 5 registry persistence cũ)
```

Nếu `test_task_registry_persistence.py` đỏ sau Step 2: nguyên nhân gần như chắc chắn là
`create_task` mới thêm keyword `checkpoint_key` — test cũ gọi positional
`create_task("translation", "Test", 1)`, vẫn tương thích vì tham số mới ở cuối và có default. Đỏ vì
lý do khác ⇒ dừng, đọc traceback, **đừng sửa test cũ để nó xanh**.

Negative: `RuntimeState().request_cancel()` không đổi state nào; `is_cancelled("X")` luôn False khi
không cancel X; event `"error"` không đổi status. Đã phủ trong test.

**Báo cáo phase:** `Files changed: runtime_state.py, task_registry.py, executor.py, use_case, translation.py, projects.py, test_cancel_scoped.py`. **Status: complete** chỉ khi Step 8 xanh.

---

## Phase 2 — Chuẩn hóa `resume_required` và frontend error handling (P0)

**Files:**
- Modify: `webui/routes/projects.py` (`_checkpoint_status_for`, route config `project_slug`)
- Modify: `webui/static/js/api-client.js`
- Modify: `webui/static/js/translation-worker.js`
- Test: `tests/unit/test_project_routes.py` (bổ sung test 409)

**Impact trước edit:** `_checkpoint_status_for` là helper nội bộ module, không có caller ngoài route translate. LOW.

### Step 1: `webui/routes/projects.py` — dùng comparator dùng chung của Phase 0.5

> **B12 — bug SỐNG ở HEAD, không phải rủi ro tương lai. Đọc trước khi sửa.**
>
> `_checkpoint_status_for` (dòng 1514-1548) so sánh `saved_ident != current_identity` trên **cả 13
> field**, trong đó `current_identity` được build từ `config` của route (dòng 1702-1717). Nhưng
> `config` đó **không có** `project_slug`, `provider_kind`, `provider_id`, `credential_mode`, và
> `base_url` là `""`. Trong khi executor build identity từ `worker_config` — nơi
> `worker_config["project_slug"] = slug` (dòng 1592) và 4 field provider đều là giá trị thật
> (dòng 1593-1601).
>
> Đối chiếu từng field, `current_identity` của route so với identity đã lưu trong checkpoint:
>
> | field | route tính | executor đã lưu | khớp? |
> |---|---|---|---|
> | `project_slug` | `""` | `slug` | ❌ |
> | `provider_kind` | `"unknown"` | vd `"native_openai"` | ❌ |
> | `provider_id` | `"unknown"` | id thật | ❌ |
> | `base_url` | `""` | url thật | ❌ |
> | `credential_mode` | `"default"` | mode thật | ❌ |
> | `model` | `data.get("model","")` | `model_from_req` (có fallback default_model) | ❌ khi client không gửi model |
>
> ⇒ `saved_ident != current_identity` **luôn** True ⇒ luôn trả `{"status": "stale_checkpoint"}` ⇒
> route **không bao giờ** trả 409 `resume_required` ⇒ **checkpoint không bao giờ được dùng lại** dù
> tồn tại và hợp lệ. Đây là lý do thật sự phía sau triệu chứng "bấm Dịch là dịch lại từ đầu".
> Không phải lỗi UI.
>
> Sửa bằng cách bỏ 6 field thực thi ra khỏi phép so sánh (Phase 0.5 đã tách sẵn) **và** bơm
> `project_slug` vào config route (Step 2). Thiếu một trong hai thì vẫn sai.

Thay toàn bộ block `_checkpoint_status_for` (dòng 1514-1548) bằng — **dùng lại**
`same_source_identity` / `execution_drift` của `services/checkpoint_service.py` (Phase 0.5 Step 2),
tuyệt đối không viết comparator thứ hai:

```python
def _current_checkpoint_identity(filename: str, source_text: str, config: dict) -> dict:
    """Build identity hiện tại theo ĐÚNG công thức của TranslationExecutor.

    Phải khớp từng ký tự với `TranslationExecutor._build_checkpoint_identity`
    (core/executor.py:72-93): cùng sha256, cùng `json.dumps(..., ensure_ascii=False,
    sort_keys=True, separators=(",", ":"))`. Đổi một bên mà không đổi bên kia là
    làm resume chết âm thầm — không có test nào bắt được ngoài Phase 5.
    """
    return {
        "project_file": filename,
        "project_slug": config.get("project_slug", ""),
        "source_hash": hashlib.sha256(source_text.encode()).hexdigest(),
        "chunker_version": "v2",
        "chunk_size": str(config.get("chunk_size", 22000)),
        "prompt_hash": hashlib.sha256(
            json.dumps(config.get("prompts", {}), ensure_ascii=False,
                       sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "schema_version": "1.0",
        # 6 field thực thi CỐ TÌNH không có ở đây: chúng không quyết định checkpoint
        # còn dùng được hay không, và route không biết giá trị thật của chúng
        # (worker mới điền — projects.py:1592-1601). Xem execution_drift().
    }


def _checkpoint_status_for(filename: str, source_text: str, config: dict) -> Optional[dict]:
    """Checkpoint có resume được không. So SOURCE identity, bỏ qua execution identity.

    Đổi provider/model KHÔNG làm mất khả năng resume — chỉ ghi nhận `mixed_provider`.
    """
    from services.checkpoint_service import same_source_identity

    ck_dir = _get_checkpoint_dir()
    ck = CheckpointService(ck_dir)
    info = ck.get_resume_info(filename)
    if not info or not info.get("can_resume"):
        return None

    saved = info.get("identity", {})
    current = _current_checkpoint_identity(filename, source_text, config)
    if not same_source_identity(saved, current):
        return {"status": "stale_checkpoint", "identity_mismatch": True}

    return {
        "status": "resume_available",
        "completed_chunks": info.get("translated_count", 0),
        "total_chunks": info.get("total_chunks", 0),
        "next_chunk": info.get("next_chunk_index", 0),
        # Tên VẬT LÝ. Task row lưu tên LOGIC (projects.py:1738 → filename).
        # Đừng so sánh 2 giá trị này bằng `==` ở bất kỳ đâu — dùng
        # CheckpointService.same_checkpoint_key (Phase 0.5). Đây là B4.
        "checkpoint_key": _checkpoint_key_for(filename),
    }
```

> `same_source_identity` ép `str()` mọi field trước khi so (Phase 0.5), nên `chunk_size` là int hay
> str đều khớp — chính chỗ này từng là nguồn lệch âm thầm.
>
> **Không xóa `_checkpoint_key_for`** (dòng 1510): còn caller khác trong file. Phase 4 mới thống nhất.

### Step 2: `webui/routes/projects.py` — ghi `project_slug` vào config ở 2 route translate

**Đây là nửa còn lại của B12 — bắt buộc, không phải "nên có".** `project_slug` nằm trong SOURCE
identity nên vẫn được so sánh sau Step 1; thiếu nó thì Step 1 chưa cứu được gì.

Trong `translate_project_file`: ngay sau dict `config = {...}` (kết thúc ở dòng 1717), **trước** khối
`if not force_retranslate:` (dòng 1720), thêm:

```python
    # BẮT BUỘC: identity của checkpoint chứa project_slug (executor đọc từ worker_config,
    # projects.py:1592). Nếu config của route thiếu nó, _checkpoint_status_for so lệch và
    # KHÔNG BAO GIỜ trả resume_available. Xem B12.
    config["project_slug"] = slug
```

Trong `confirm_resume_translate`: sau dict config (khoảng dòng 1800-1806), thêm cùng một dòng
`config["project_slug"] = slug`.

Trong `resume_task` (dòng 1906 `config["prompts"] = prompts`), thêm ngay sau:
```python
    config["project_slug"] = task["project_slug"]
```

> 3 chỗ, không phải 2. `resume_task` dựng config riêng và cũng đi qua `_build_translate_worker`;
> thiếu `project_slug` ở đây thì executor ghi lại identity với slug rỗng ở lần resume, phá vỡ
> checkpoint cho lần sau. Grep xác nhận: `config["prompts"] = prompts` xuất hiện ở dòng 1906
> (`resume_task`) và 2093 (`recover_from_checkpoint`) — dòng 2093 **không cần** vì recovery không
> gọi `translate_text`/`_build_checkpoint_identity`.


### Step 3: `webui/static/js/api-client.js` — helper fetch translate đọc JSON trước HTTP

Thêm method vào `ApiClient` (trước dòng đóng `};` của object, sau method `loadTasks`):

```js
    translateFiles(slug, files, opts = {}) {
        return fetch(`/api/projects/${slug}/translate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files, ...opts })
        }).then(async r => {
            const text = await r.text();
            let data = {};
            try { data = text ? JSON.parse(text) : {}; } catch { throw new Error(`Server không trả JSON (${r.status})`); }
            // 409 + {status: resume_required} là response nghiệp vụ, KHÔNG phải exception UI
            if (r.status === 409 && data.status === 'resume_required') return data;
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
            return data;
        });
    },
```

### Step 4: `webui/static/js/translation-worker.js` — dùng helper + `.catch` + lock modal

> **B14 — 2 crash SỐNG ở HEAD mà bản nháp đầu đã sao chép nguyên văn. Phải sửa, không được dán lại.**
>
> Grep toàn bộ `webui/templates/`: **không có** element nào có `id="force-retranslate"`,
> `id="pm-force-retranslate"`, hay `id="btn-translate-single"`. Hệ quả tại HEAD:
>
> | dòng | mã hiện tại | hậu quả thật |
> |---|---|---|
> | 39, 122, 141 | `getElementById('force-retranslate')` | luôn `null` → `forceRetranslate` **luôn false**. Ô tick "dịch lại từ đầu" không tồn tại; cờ này không bao giờ bật từ 3 flow này. |
> | 65 | `getElementById('btn-translate-single').click()` | **TypeError: Cannot read properties of null (reading 'click')** → bấm "Dịch lại từ đầu" trong modal resume là **văng lỗi JS**, không làm gì. |
> | 167 | `getElementById('pm-force-retranslate').checked = true` | **TypeError** tương tự ở flow dịch nhiều file đã chọn. |
>
> Đường "dịch lại từ đầu" thật sự đang hoạt động là `retranslateActiveFile()` (đã POST
> `force_retranslate: true`, gắn với `id="btn-retranslate-file"` trong `tab_projects.html:182`).
> Vì vậy nhánh `restart` phải **gửi thẳng `force_retranslate: true`**, không đi qua checkbox không
> tồn tại và không `.click()` vào button không tồn tại.

**4a. Thêm helper `_forceTranslate`** (chèn ngay trước `startTranslation`, dòng 25) — dùng chung cho
cả 3 flow, thay cho 3 biến thể checkbox/`.click()`:

```js
    // Nhánh "Dịch lại từ đầu" của modal resume. Gửi trực tiếp force_retranslate:true.
    // KHÔNG dùng checkbox #force-retranslate / #pm-force-retranslate (không tồn tại trong DOM)
    // và KHÔNG .click() vào #btn-translate-single (không tồn tại) — xem B14.
    _forceTranslate(slug, files, btn = null, isBatch = false) {
        return ApiClient.translateFiles(slug, files, { force_retranslate: true })
            .then(data => {
                if (data.status === 'started') {
                    ApiClient.loadTasks();
                    TranslationWorker.connectToProgress(btn, isBatch, data.job_id, data.files_count || files.length);
                } else {
                    UiHelpers.showToast(data.error || 'Không thể dịch lại từ đầu', 'error');
                    TranslationWorker.resetButton(btn, isBatch);
                }
            })
            .catch(e => {
                UiHelpers.showToast('Lỗi dịch lại: ' + e.message, 'error');
                TranslationWorker.resetButton(btn, isBatch);
            });
    },
```

> `force_retranslate: true` khiến route bỏ qua hoàn toàn khối check checkpoint (projects.py:1720)
> nên **không** lặp lại 409 → không có vòng lặp modal. Đây là lý do phải gửi cờ chứ không gọi lại
> hàm cũ.

**4b. `startTranslation` (nhánh project)** — thay block fetch (dòng 41-78) bằng:

```js
            UiHelpers.addLog('Bắt đầu dịch nội dung...', 'info');
            ApiClient.translateFiles(window.currentProject.slug, [window.currentProjectFile.name], {})
            .then(data => {
                clearTimeout(guardTimer);
                if (data.error) { UiHelpers.addLog(data.error, 'error'); TranslationWorker.resetButton(btn); }
                else if (data.status === 'resume_required') {
                    TranslationWorker.showResumeActionModal(data.checkpoints, (action) => {
                        if (action === 'continue') {
                            fetch(`/api/projects/${window.currentProject.slug}/translate/confirm-resume`, {
                                method: 'POST', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ files: [window.currentProjectFile.name] })
                            }).then(r => r.json()).then(resumeData => {
                                if (resumeData.status === 'started') {
                                    ApiClient.loadTasks();
                                    TranslationWorker.connectToProgress(btn, false, resumeData.job_id, resumeData.files_count || 1);
                                } else {
                                    UiHelpers.showToast(resumeData.error || 'Lỗi resume', 'error');
                                    TranslationWorker.resetButton(btn);
                                }
                            }).catch(e => { UiHelpers.showToast('Lỗi resume: ' + e.message, 'error'); TranslationWorker.resetButton(btn); });
                        } else if (action === 'restart') {
                            TranslationWorker._forceTranslate(window.currentProject.slug, [window.currentProjectFile.name], btn, false);
                        } else if (action === 'close_partial') {
                            TranslationWorker.handleClosePartialByCheckpoints(data.checkpoints, window.currentProject.slug);
                            TranslationWorker.resetButton(btn);
                        } else {
                            TranslationWorker.resetButton(btn);
                        }
                    });
                }
                else if (data.status === 'started') {
                    ApiClient.loadTasks();
                    TranslationWorker.connectToProgress(btn, false, data.job_id, data.files_count || 1);
                }
            }).catch(e => { clearTimeout(guardTimer); UiHelpers.addLog(e.message, 'error'); TranslationWorker.resetButton(btn); });
```

> Giữ nguyên khối `btn`/`guardTimer` ở dòng 28-36 — **không** dán lại chúng, chỉ thay từ
> `UiHelpers.addLog('Bắt đầu dịch nội dung...')` trở xuống. Bỏ 2 dòng đọc `#force-retranslate`.
>
> ⚠️ `guardTimer` 3000ms sẽ reset button **trong khi modal resume còn mở** (người dùng đọc modal
> lâu hơn 3s). Đó là hành vi có sẵn, không sửa trong P0 — nhưng đừng ngạc nhiên khi thấy button
> hồi trạng thái trước khi bấm.

**4c. `translateFileInProject`** — thay toàn bộ hàm (dòng 120-136) bằng:

```js
    translateFileInProject(filename) {
        if (!window.currentProject) return;
        ApiClient.translateFiles(window.currentProject.slug, [filename], {})
            .then(data => {
                if (data.status === 'started') {
                    ApiClient.loadTasks();
                    TranslationWorker.connectToProgress(null, false, data.job_id, data.files_count || 1);
                } else if (data.status === 'resume_required') {
                    TranslationWorker.showResumeActionModal(data.checkpoints, (action) => {
                        if (action === 'continue') {
                            fetch(`/api/projects/${window.currentProject.slug}/translate/confirm-resume`, {
                                method: 'POST', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ files: [filename] })
                            }).then(r => r.json()).then(resumeData => {
                                if (resumeData.status === 'started') {
                                    ApiClient.loadTasks();
                                    TranslationWorker.connectToProgress(null, false, resumeData.job_id, resumeData.files_count || 1);
                                } else UiHelpers.showToast(resumeData.error || 'Lỗi resume', 'error');
                            }).catch(e => UiHelpers.showToast('Lỗi resume: ' + e.message, 'error'));
                        } else if (action === 'restart') {
                            TranslationWorker._forceTranslate(window.currentProject.slug, [filename], null, false);
                        } else if (action === 'close_partial') {
                            TranslationWorker.handleClosePartialByCheckpoints(data.checkpoints, window.currentProject.slug);
                        }
                    });
                } else UiHelpers.showToast(data.error || 'Lỗi', 'error');
            })
            .catch(e => UiHelpers.showToast('Lỗi: ' + e.message, 'error'));
    },
```

**4d. `translateSelectedInProject`** — thay toàn bộ hàm (dòng 138-175) bằng:

```js
    translateSelectedInProject() {
        if (!window.currentProject || window.selectedFiles.size === 0) { UiHelpers.showToast('Chưa chọn file!', 'error'); return; }
        const files = Array.from(window.selectedFiles);
        const selBtn = document.getElementById('pm-btn-translate-selected');
        ApiClient.translateFiles(window.currentProject.slug, files, {})
            .then(data => {
                if (data.status === 'started') {
                    ApiClient.loadTasks();
                    TranslationWorker.connectToProgress(selBtn, true, data.job_id, data.files_count || files.length);
                } else if (data.status === 'resume_required') {
                    TranslationWorker.showResumeActionModal(data.checkpoints, (action) => {
                        const names = Object.keys(data.checkpoints || {});
                        if (action === 'continue') {
                            fetch(`/api/projects/${window.currentProject.slug}/translate/confirm-resume`, {
                                method: 'POST', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ files: names })
                            }).then(r => r.json()).then(resumeData => {
                                if (resumeData.status === 'started') {
                                    ApiClient.loadTasks();
                                    TranslationWorker.connectToProgress(selBtn, true, resumeData.job_id, resumeData.files_count || names.length);
                                } else {
                                    UiHelpers.showToast(resumeData.error || 'Lỗi resume', 'error');
                                    TranslationWorker.resetButton(selBtn, true);
                                }
                            }).catch(e => { UiHelpers.showToast('Lỗi resume: ' + e.message, 'error'); TranslationWorker.resetButton(selBtn, true); });
                        } else if (action === 'restart') {
                            // Dịch lại từ đầu CHỈ những file có checkpoint (names), không phải
                            // toàn bộ `files` — các file khác đã được server nhận ở lần POST đầu.
                            TranslationWorker._forceTranslate(window.currentProject.slug, names, selBtn, true);
                        } else if (action === 'close_partial') {
                            TranslationWorker.handleClosePartialByCheckpoints(data.checkpoints, window.currentProject.slug);
                            TranslationWorker.resetButton(selBtn, true);
                        } else {
                            TranslationWorker.resetButton(selBtn, true);
                        }
                    });
                } else UiHelpers.showToast(data.error || 'Lỗi', 'error');
            })
            .catch(e => {
                UiHelpers.showToast('Lỗi: ' + e.message, 'error');
                TranslationWorker.resetButton(selBtn, true);
            });
    },
```

> ⚠️ Về ngữ nghĩa `restart` ở flow nhiều file: server trả 409 **ngay khi có ≥1 file** có checkpoint
> (projects.py:1730) và **không** khởi động file nào. Nên `restart` gửi `names` là **chưa đủ**: các
> file trong `files` mà **không** có checkpoint vẫn chưa được dịch. Đây là khiếm khuyết ngữ nghĩa của
> contract 409 hiện tại, **không sửa trong P0** (sẽ phải cho phép resume theo từng file). Ghi vào
> handoff để P1 xử lý. Nếu muốn hành vi "không bỏ sót file nào" ngay, đổi thành
> `_forceTranslate(slug, files, ...)` — nhưng như vậy các file đã có tiến độ bị dịch lại từ đầu.
> Chọn `names` vì nó không phá dữ liệu; đánh đổi được ghi rõ ở đây thay vì im lặng.

**4e. `showResumeActionModal`** — khóa double-click (thay toàn bộ hàm dòng 177-200):

```js
    showResumeActionModal(checkpoints, onAction) {
        const preview = document.getElementById('resume-action-files-preview');
        if (!preview) return;
        const names = Object.keys(checkpoints || {});
        preview.innerHTML = names.map(n => `<div class="mb1 bb b--black-05 pb1"><strong>${n}</strong> <span class="gray">(Đã dịch: ${checkpoints[n].completed_chunks}/${checkpoints[n].total_chunks} chunk)</span></div>`).join('');

        const closePartialBtn = document.getElementById('btn-resume-action-close-partial');
        const continueBtn = document.getElementById('btn-resume-action-continue');
        const restartBtn = document.getElementById('btn-resume-action-restart');
        if (!closePartialBtn || !continueBtn || !restartBtn) return;

        const newClosePartial = closePartialBtn.cloneNode(true);
        const newContinue = continueBtn.cloneNode(true);
        const newRestart = restartBtn.cloneNode(true);

        closePartialBtn.parentNode.replaceChild(newClosePartial, closePartialBtn);
        continueBtn.parentNode.replaceChild(newContinue, continueBtn);
        restartBtn.parentNode.replaceChild(newRestart, restartBtn);

        let locked = false;
        const fire = (action) => {
            if (locked) return;
            locked = true;
            ModalManager.hide('resume-action-modal');
            onAction(action);
        };
        newClosePartial.addEventListener('click', () => fire('close_partial'));
        newContinue.addEventListener('click', () => fire('continue'));
        newRestart.addEventListener('click', () => fire('restart'));

        ModalManager.show('resume-action-modal');
    },
```

> 4 id trong hàm này **đã được xác nhận tồn tại** trong `webui/templates/partials/modals.html`
> (`resume-action-modal`, `resume-action-files-preview`, `btn-resume-action-close-partial`,
> `btn-resume-action-continue`, `btn-resume-action-restart`). Thêm guard `if (!...) return;` để
> đổi tên id trong tương lai không thành TypeError như B14.


### Step 5: Bổ sung test 409 vào `tests/unit/test_project_routes.py`

File này **đã có** helper `_setup_mocks()` / `_stop_mocks()` trong class
`TestTranslateProjectForceRetranslate` (dòng 78-133) và đã `from unittest.mock import MagicMock,
patch` ở dòng 7. **Dùng lại chúng** — không viết lại `__import__("unittest.mock", ...)`.

Thêm class sau class `TestTranslateProjectForceRetranslate`:

```python
class TestTranslateProjectResumeRequired409(TestTranslateProjectForceRetranslate):
    """Kế thừa để dùng lại _setup_mocks/_stop_mocks, không nhân bản 50 dòng mock."""

    def test_translate_returns_409_resume_required(self, client):
        mocks = self._setup_mocks()
        try:
            # File nguồn phải "tồn tại" để route đọc được source_text
            patch_read = patch(
                "pathlib.Path.read_text", return_value="nội dung nguồn"
            )
            mocks["ck_status"].stop()
            ck = patch(
                "webui.routes.projects._checkpoint_status_for",
                return_value={
                    "status": "resume_available",
                    "completed_chunks": 17,
                    "total_chunks": 24,
                    "next_chunk": 17,
                    "checkpoint_key": "abcd1234ef56.db",
                },
            )
            ck.start()
            mocks["ck_status"] = ck

            # _setup_mocks cho exists() = False; cần True để vào nhánh check checkpoint
            from pathlib import Path as _P
            mock_pdir = MagicMock(spec=_P)
            mock_file = MagicMock(spec=_P)
            mock_file.exists.return_value = True
            mock_file.read_text.return_value = "nội dung nguồn"
            mock_pdir.__truediv__ = lambda self, x: (
                mock_file if str(x) not in ("sources", "assets") else mock_pdir
            )
            mocks["dir"].stop()
            d = patch("webui.routes.projects._get_project_dir", return_value=mock_pdir)
            d.start()
            mocks["dir"] = d

            resp = client.post(
                "/api/projects/test-slug/translate",
                json={"files": ["book.txt"], "model": "gemini-flash"},
            )
            assert resp.status_code == 409
            data = resp.get_json()
            assert data["status"] == "resume_required"
            assert data["checkpoints"]["book.txt"]["completed_chunks"] == 17
            assert data["checkpoints"]["book.txt"]["total_chunks"] == 24
            assert data["checkpoints"]["book.txt"]["checkpoint_key"] == "abcd1234ef56.db"
        finally:
            self._stop_mocks(mocks)

    def test_translate_injects_project_slug_into_config(self, client):
        """B12: config truyền cho _checkpoint_status_for PHẢI có project_slug.

        Test này là cái duy nhất bắt được B12 ở mức unit. Mock _checkpoint_status_for
        rồi assert trên đối số nó nhận được — nếu ai xoá `config["project_slug"] = slug`
        thì test đỏ ngay, không phải đợi Phase 5.
        """
        mocks = self._setup_mocks()
        try:
            from pathlib import Path as _P
            mock_file = MagicMock(spec=_P)
            mock_file.exists.return_value = True
            mock_file.read_text.return_value = "nội dung nguồn"
            mock_pdir = MagicMock(spec=_P)
            mock_pdir.__truediv__ = lambda self, x: (
                mock_file if str(x) not in ("sources", "assets") else mock_pdir
            )
            mocks["dir"].stop()
            d = patch("webui.routes.projects._get_project_dir", return_value=mock_pdir)
            d.start()
            mocks["dir"] = d

            client.post(
                "/api/projects/test-slug/translate",
                json={"files": ["book.txt"], "model": "gemini-flash", "chunk_size": 2400},
            )

            import webui.routes.projects as _pj
            assert _pj._checkpoint_status_for.called, "route không gọi _checkpoint_status_for"
            cfg = _pj._checkpoint_status_for.call_args[0][2]
            assert cfg["project_slug"] == "test-slug", "B12: thiếu project_slug trong config"
            assert cfg["chunk_size"] == 2400
            assert "prompts" in cfg
        finally:
            self._stop_mocks(mocks)
```

> `_checkpoint_status_for` được gọi positional `(filename, source_text, config)` tại
> projects.py:1727 nên `call_args[0][2]` là `config`. Nếu bạn đổi sang keyword khi sửa Step 1 thì
> đổi assert thành `call_args.kwargs["config"]` — đừng để test đọc sai chỗ rồi kết luận sai.
>
> **Test source-identity thật (không mock) nằm ở Phase 0.5 Step 4** (`test_checkpoint_identity.py`)
> — chỗ đó mới có checkpoint thật trong `tmp_path`. Đừng dựng checkpoint thật trong
> `test_project_routes.py`: fixture `client` ở đây gọi `create_app()` thật, vốn đã quét
> `workspace/checkpoints` và `workspace/tasks.db` **thật** của người dùng (hành vi có sẵn của repo,
> Phase 4 Step 6 mới tách được). Thêm checkpoint thật vào đây là mời rắc rối vào dữ liệu thật.


### Step 6: Test gate Phase 2

```bash
.venv/bin/python -m pytest tests/unit/test_project_routes.py -q
# Kỳ vọng: PASS (9 test cũ + 2 test mới = 11)
```

> `TestTranslateProjectResumeRequired409` kế thừa `TestTranslateProjectForceRetranslate` nên pytest
> sẽ **chạy lại** 4 test của class cha dưới tên class con (tổng collected = 9 + 4 + 2 = 15). Đó là
> hành vi bình thường của inheritance trong pytest, không phải lỗi. Nếu không muốn chạy trùng, đổi
> thành composition: `class TestTranslateProjectResumeRequired409:` + gán
> `_setup_mocks = TestTranslateProjectForceRetranslate._setup_mocks` và
> `_stop_mocks = TestTranslateProjectForceRetranslate._stop_mocks`.

Negative: payload không phải contract → `.catch` hiện toast; selected-files rejection không tạo unhandled promise (có `.catch`). Kiểm chứng tĩnh: đảm bảo không còn `if (!r.ok) throw` ở 3 flow translate — grep:

```bash
grep -n "status === 'resume_required'" webui/static/js/translation-worker.js
# Kỳ vọng: 3 dòng (startTranslation, translateFileInProject, translateSelectedInProject)
grep -n "translateFiles" webui/static/js/translation-worker.js
# Kỳ vọng: 3 dòng
```

**Báo cáo phase:** `Contract changed: 409 payload giữ nguyên; frontend đọc JSON trước, throw chỉ khi lỗi thật.`

---

## Phase 3 — Canonical close-as-partial + cancel-and-wait (P0)

**Files:**
- Modify: `webui/routes/projects.py` (route `close_as_partial`, thêm `import time`, hằng số timeout)
- Modify: `backend/infrastructure/progress/task_registry.py` — **không đụng ở phase này**; `closed_partial` đã được thêm vào terminal list của `iter_events` + `update_status` tại **Phase 1 Step 2c/2d**. Nếu Phase 1 chưa xong, `close_as_partial` sẽ treo SSE stream vô hạn → làm Phase 1 trước.
- **Không** sửa `services/checkpoint_service.py` ở phase này: `resolve_checkpoint_key` đã tồn tại từ **Phase 0.5 Step 2**.

> **Thứ tự thực thi:** Phase 0.5 → Phase 1 → Phase 3. Không còn phụ thuộc ngược vào Phase 4
> (ghi chú "làm Phase 4 step 1 trước" của bản nháp đã lỗi thời — resolver được dời lên Phase 0.5
> chính vì vòng phụ thuộc đó).

**Impact trước edit:** `close_as_partial` d=1:0 LOW.

> **Đã xác thực trên nguồn (đọc `services/task_store.py`):**
> - `get_task(task_id)` tồn tại (dòng 264) — dùng được.
> - `task_id == job_id` ở **mọi** đường tạo task: `create_task` gán `task_id = job_id` (dòng 116),
>   `create_resumed_task` chèn `new_job_id` cho cả 2 cột (dòng 143-146). Vì vậy
>   `job_id = task.get("job_id") or task_id` luôn ra cùng giá trị — giữ dòng đó để phòng schema
>   tương lai, nhưng **không** dựa vào việc chúng khác nhau.
> - `TaskRegistry` là **singleton** (`__new__` giữ `_instance`, task_registry.py:70-77) và đã được
>   bind store thật khi `webui/routes/tasks.py:23` import. Nên `TaskRegistry()` trong route trả về
>   đúng instance đang chạy — an toàn.

### Step 1: Thêm `import time` + hằng số timeout vào đầu `webui/routes/projects.py`

Sau dòng `from datetime import datetime` (dòng 12), thêm:
```python
import time
```
Và sau `PROJECTS_DIR = Path("workspace/projects")` (dòng 32), thêm:
```python
CLOSE_WAIT_TIMEOUT_SECONDS = 6.0
```

### Step 2: Thay toàn bộ route `close_as_partial` (dòng ~2191)

```python
@projects_bp.route("/api/tasks/<task_id>/close-as-partial", methods=["POST"])
def close_as_partial(task_id: str):
    """Chốt task thành partial.

    Luồng bắt buộc: validate confirm → cancel scoped → chờ worker/lease hết hạn →
    resolve checkpoint (canonical resolver) → assemble partial + manifest atomic →
    persistent status `closed_partial` → registry mirror `closed_partial`.
    KHÔNG BAO GIỜ gọi status `completed` trong luồng này.
    """
    from services.task_store import TaskStore
    from services.checkpoint_service import CheckpointService
    from backend.infrastructure.progress.runtime_state import RuntimeState

    data = request.get_json(silent=True) or {}
    if not data.get("confirm"):
        return jsonify({"error": "Cần xác nhận: {\"confirm\": true}"}), 400

    task_store = TaskStore(_get_workspace_dir())
    checkpoint_service = CheckpointService(_get_checkpoint_dir())

    task = task_store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task không tồn tại"}), 404

    # Idempotent: đã chốt rồi thì trả lại kết quả cũ, không assemble lần hai.
    # Cần thiết vì frontend có thể retry sau khi nhận 202 close_pending.
    if task["status"] == "closed_partial" and task.get("partial_output_path"):
        existing = Path(task["partial_output_path"])
        if existing.is_file():
            return jsonify({
                "status": "closed_partial",
                "task_id": task_id,
                "partial_output": str(existing),
                "completed_chunks": task.get("completed_chunks", 0),
                "pending_chunks": max(0, (task.get("total_chunks") or 0) - (task.get("completed_chunks") or 0)),
                "idempotent": True,
            }), 200

    # `partial_completed` là status RÁC do route cũ ghi trước khi crash (B16) — chấp nhận ĐỌC
    # để người dùng chốt lại được, nhưng KHÔNG BAO GIỜ ghi lại giá trị này.
    if task["status"] not in ("running", "started", "queued", "resumable", "paused",
                              "interrupted", "failed", "partial_completed"):
        return jsonify({"error": f"Không thể chốt task ở trạng thái {task['status']}"}), 400

    job_id = task.get("job_id") or task_id
    _RUNNING = ("running", "started")

    # 1. Cancel scoped — chỉ khi worker có thể còn chạy
    if task["status"] in _RUNNING:
        RuntimeState().request_cancel(job_id)

    # 2. Chờ worker dừng / lease hết hạn. Quá timeout → close_pending, KHÔNG assemble
    if task["status"] in _RUNNING:
        deadline = time.monotonic() + CLOSE_WAIT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            current = task_store.get_task(task_id) or {}
            st = current.get("status")
            if st not in _RUNNING:
                task = current
                break
            time.sleep(0.2)
        else:
            return jsonify({"status": "close_pending", "task_id": task_id}), 202

    # 3. Resolve checkpoint bằng canonical resolver (logical | physical | stem)
    resolved = checkpoint_service.resolve_checkpoint_key(
        task.get("checkpoint_key") or task.get("filename") or task_id
    )
    if not resolved or not resolved.get("filename"):
        return jsonify({"error": "Không tìm thấy checkpoint cho task hoặc metadata hỏng"}), 400
    ck_logical = resolved["filename"]

    # 4. Đọc checkpoint trong transaction/read-safe boundary
    indices = checkpoint_service.get_done_pending_indices(ck_logical)
    if not indices or not indices["done_indices"]:
        return jsonify({"error": "Không có chunk nào đã dịch"}), 400

    slug = task.get("project_slug") or ""
    if not slug:
        # Task mồ côi: không biết ghi partial vào đâu. Ghi vào PROJECTS_DIR/"" sẽ rải file
        # rác ra workspace/projects/translated/ — chặn thẳng thay vì đoán.
        return jsonify({"error": "Task không có project_slug, không xác định được nơi ghi partial"}), 400
    project_dir = _get_project_dir(slug)
    partial_path = checkpoint_service.write_partial_file(
        ck_logical, project_dir / "translated" / ".recovery"
    )
    if not partial_path:
        return jsonify({"error": "Không thể tạo partial file"}), 500

    done_count = len(indices["done_indices"])
    pending_count = len(indices["pending_indices"])

    # 5. Registry mirror TRƯỚC (dọn cancel token qua update_status Phase 1).
    #    Phải chạy TRƯỚC bước 6, xem ghi chú thứ tự bên dưới.
    from backend.infrastructure.progress.task_registry import TaskRegistry
    registry = TaskRegistry()
    registry.update_status(job_id, "closed_partial")

    # 6. Persistent status closed_partial (terminal với worker, KHÔNG phải completed).
    #    Ghi SAU cùng để con số từ checkpoint (nguồn chân lý) là giá trị cuối trong DB.
    task_store.update_status(
        task_id,
        "closed_partial",
        partial_output_path=str(partial_path),
        completed_chunks=done_count,
        current_chunk=done_count,
        last_error=None,
    )

    return jsonify({
        "status": "closed_partial",
        "task_id": task_id,
        "partial_output": str(partial_path),
        "completed_chunks": done_count,
        "pending_chunks": pending_count,
    }), 200
```

> **Tại sao registry.update_status phải chạy TRƯỚC task_store.update_status** (bản nháp làm ngược):
> `TaskRegistry.update_status` (task_registry.py:178-194) tự gọi
> `self._store.update_status(job_id, status, completed_chunks=task.current)` khi `task.current > 0`.
> Nếu gọi nó SAU, `task.current` (đếm từ event `progress`) sẽ **ghi đè** `done_count` lấy từ
> checkpoint — đúng lúc ta vừa khẳng định checkpoint là nguồn chân lý duy nhất. Hai số này lệch
> nhau bất cứ khi nào một chunk emit `progress` rồi ghi checkpoint thất bại. Đảo thứ tự là fix
> 1 dòng, không cần sửa `TaskRegistry`.
>
> `get_done_pending_indices(ck_logical)` — nhận logical filename, tự hash đúng.
> `write_partial_file(ck_logical)` — cũng nhận logical. KHÔNG truyền tên `.db` vào 2 hàm này
> (tránh hash-of-hash, xem Phase 0.5).
>
> **Tại sao phải chấp nhận đọc `partial_completed`** (B16): route HEAD (dòng 2221-2229) ghi
> `update_recovery_task(task_id, status="partial_completed", partial_output_path=…)` **rồi mới**
> gọi `TaskRegistry()` — một `NameError` (xem bảng B16) làm request 500 **sau khi** đã ghi status.
> Nên mọi user từng bấm "Chốt bản dịch một phần" đang có hàng ở `partial_completed` trong
> `workspace/tasks.db` thật. Ta KHÔNG migrate dữ liệu (rule §4), nên phải đọc-dung-thứ giá trị này;
> lần chốt lại sẽ ghi đè bằng `closed_partial` đúng chuẩn.

### Step 3: Frontend `_closeAsPartial` (translation-worker.js, dòng 895-929)

> **B15 — 2 lỗi SỐNG ở HEAD trong hàm này; đây là lý do `closed_partial` chưa bao giờ tồn tại:**
>
> | dòng | mã hiện tại | hậu quả |
> |---|---|---|
> | 903 | `fetch(url, { method: 'POST' })` — **không có body** | Route mới yêu cầu `{"confirm": true}` → **400 "Cần xác nhận"** cho mọi lần bấm. Bản nháp đã thêm body, nhưng phải hiểu là *sửa lỗi*, không phải thêm tính năng. |
> | 921 | `fetch('/api/tasks/${jobId}/cancel')` gọi **SAU** khi close thành công | `cancel_task` (tasks.py:150-154) gọi `registry.update_status(job_id, "cancelled")` → **ghi đè** `closed_partial` vừa lưu thành `cancelled`, và xóa luôn `partial_output_path` khỏi ngữ nghĩa trạng thái. Route mới đã tự cancel scoped + chờ ở bước 1-2, nên lệnh cancel này vừa dư vừa phá dữ liệu. **Phải xóa.** |
>
> `taskState.taskId === taskState.jobId` ở frontend (gán tại dòng 322/331) và `task_id == job_id`
> trong DB, nên dùng trường nào cũng ra cùng giá trị. Giữ `taskId` cho URL task và `jobId` cho
> khóa Map/SSE đúng như hàm cũ.

Thay toàn bộ hàm bằng:

```js
    async _closeAsPartial(taskState) {
        const confirmed = await showConfirm(
            `Bạn có chắc muốn chia tách phần đã dịch và kết thúc task này?\n\n` +
            `Một file .partial.md sẽ được tạo ra với ${taskState.completedChunks} chunk đã dịch.`
        );
        if (!confirmed) return;

        try {
            const response = await fetch(`/api/tasks/${taskState.taskId}/close-as-partial`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ confirm: true, export_partial: true })
            });
            if (response.status === 202) {
                // close_pending: worker chưa dừng trong timeout. KHÔNG assemble, KHÔNG cancel thêm.
                await response.json();
                UiHelpers.showToast('Task đang chạy, chờ worker dừng hẳn rồi thử lại...', 'info');
                setTimeout(() => TranslationWorker.openTaskProgress(taskState.jobId), 3000);
                return;
            }
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Không thể chốt task');
            }
            const result = await response.json();
            UiHelpers.showToast(`Đã chốt file: ${result.partial_output}`, 'success');

            if (TranslationWorker._evtSource) {
                TranslationWorker._evtSource.close();
                TranslationWorker._evtSource = null;
            }
            TranslationWorker._taskStateByJob.delete(taskState.jobId);
            // KHÔNG gọi /cancel ở đây — xem B15. Route đã cancel scoped và đã chờ worker dừng.
            ApiClient.loadTasks();
        } catch (err) {
            UiHelpers.showToast('Lỗi: ' + err.message, 'error');
        }
    },
```

### Step 4: Frontend `_updateResumeButton` — thêm trạng thái `closed_partial`

Trong `_updateResumeButton` (dòng 636), thay (dòng 656):
```js
        } else if (status === 'completed' || status === 'cancelled') {
```
bằng:
```js
        } else if (status === 'completed' || status === 'cancelled' || status === 'closed_partial') {
```

> Không cần sửa 3 khối sau đó: `btnRecovery`/`btnExportPartial` dùng `status !== 'failed'` nên tự ẩn
> khi `closed_partial`; danh sách của `btnClosePartial` (dòng 669) không chứa `closed_partial` nên
> nút "Chốt file .partial" tự ẩn sau khi chốt — đúng ý muốn, không được thêm `closed_partial` vào
> danh sách đó.

### Step 5: Tạo `tests/unit/test_close_partial.py`

```python
# tests/unit/test_close_partial.py
import json
import threading
import time
from pathlib import Path

import pytest

from backend.infrastructure.progress.runtime_state import RuntimeState
from services.checkpoint_service import CheckpointService
from services.task_store import TaskStore


@pytest.fixture(autouse=True)
def _reset():
    RuntimeState.reset()
    from backend.infrastructure.progress.task_registry import TaskRegistry
    TaskRegistry._instance = None
    yield
    RuntimeState.reset()
    TaskRegistry._instance = None


def _seed_checkpoint(ck, filename="book.txt", total=3, done=(0, 1)):
    """3 chunk, mặc định done = {0,1}, còn index 2 pending → partial phải có marker."""
    ck.init_session(filename, total, ["a", "b", "c"])
    for i in done:
        ck.save_chunk(filename, i, "abc"[i], f"B{i}", status="done")


def _new_running_task(reg, store, filename="book.txt"):
    """Tạo task ở trạng thái running rõ ràng.

    `tasks.status` có DEFAULT 'running' (task_store.py:65) nên create_task đã ra 'running',
    nhưng set tường minh để test không phụ thuộc vào default của schema.
    """
    job = reg.create_task("translation", "T", 1, project_slug="p", filename=filename)
    store.update_status(job, "running")
    return job


def test_close_running_cancels_and_waits(sync_app):
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))

    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)
    job = _new_running_task(reg, store)
    _seed_checkpoint(ck)

    # Worker mô phỏng: chờ cancel token rồi tự kết thúc với status cancelled
    def worker():
        for _ in range(200):
            if RuntimeState().is_cancelled(job):
                break
            time.sleep(0.02)
        reg.append_event(job, {"type": "cancelled", "message": "dừng"})
        reg.update_status(job, "cancelled")

    t = threading.Thread(target=worker)
    t.start()

    resp = client.post(f"/api/tasks/{job}/close-as-partial",
                       json={"confirm": True, "export_partial": True})
    t.join(timeout=10)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "closed_partial"
    assert data["completed_chunks"] == 2
    assert data["pending_chunks"] == 1
    partial = Path(data["partial_output"])
    assert partial.exists()
    text = partial.read_text()
    assert "CHUNK 2 CHƯA DỊCH" in text  # index 2 (0-based) thiếu → marker
    assert partial.with_suffix(".manifest.json").exists()

    # Persistent + registry đều closed_partial, KHÔNG completed
    assert store.get_task(job)["status"] == "closed_partial"
    assert reg.get_task(job).status == "closed_partial"
    # Cancel token đã được dọn (update_status terminal)
    assert RuntimeState().is_cancelled(job) is False
    # completed_chunks trong DB phải là số từ checkpoint (2), KHÔNG bị registry ghi đè
    assert store.get_task(job)["completed_chunks"] == 2


def test_close_resumable_no_worker(sync_app):
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)
    job = reg.create_task("translation", "T", 1, project_slug="p", filename="book.txt")
    store.update_status(job, "resumable", completed_chunks=2, current_chunk=2)
    _seed_checkpoint(ck)

    resp = client.post(f"/api/tasks/{job}/close-as-partial", json={"confirm": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "closed_partial"
    assert data["pending_chunks"] == 1
    assert store.get_task(job)["status"] == "closed_partial"


def test_close_failed_no_worker(sync_app):
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)
    job = reg.create_task("translation", "T", 1, project_slug="p", filename="book.txt")
    store.update_status(job, "failed", error_class="censorship_blocked", http_status=451)
    _seed_checkpoint(ck)

    resp = client.post(f"/api/tasks/{job}/close-as-partial", json={"confirm": True})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "closed_partial"
    assert store.get_task(job)["status"] == "closed_partial"


def test_close_is_idempotent(sync_app):
    """Gọi lại sau khi đã chốt → 200 + cùng partial path, KHÔNG assemble lần hai."""
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)
    job = reg.create_task("translation", "T", 1, project_slug="p", filename="book.txt")
    store.update_status(job, "failed")
    _seed_checkpoint(ck)

    first = client.post(f"/api/tasks/{job}/close-as-partial", json={"confirm": True})
    assert first.status_code == 200
    second = client.post(f"/api/tasks/{job}/close-as-partial", json={"confirm": True})
    assert second.status_code == 200
    assert second.get_json()["idempotent"] is True
    assert second.get_json()["partial_output"] == first.get_json()["partial_output"]


def test_close_returns_202_when_worker_still_running(sync_app, monkeypatch):
    """Task vẫn 'running' trong DB suốt thời gian chờ → 202, KHÔNG assemble."""
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)
    job = _new_running_task(reg, store)
    _seed_checkpoint(ck)

    monkeypatch.setattr("webui.routes.projects.CLOSE_WAIT_TIMEOUT_SECONDS", 0.4)

    # KHÔNG cần thread: chỉ cần status trong DB không rời ("running") trong 0.4s.
    # Bản nháp dùng thread sleep(5.0) — vô nghĩa với route (route chỉ đọc DB) và làm
    # test chậm thêm 5 giây.
    resp = client.post(f"/api/tasks/{job}/close-as-partial", json={"confirm": True})
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["status"] == "close_pending"
    # KHÔNG assemble khi 202: không có partial nào được sinh ra
    out_dir = proj / "translated" / ".recovery"
    assert not out_dir.exists() or not list(out_dir.glob("*.partial.md"))
    # Status không đổi
    assert store.get_task(job)["status"] in ("running", "started")
    # Cancel token VẪN còn (worker chưa dừng) — không được dọn sớm
    assert RuntimeState().is_cancelled(job) is True


def test_close_requires_confirm(sync_app):
    client, store, ws, proj = sync_app
    resp = client.post("/api/tasks/nonexistent/close-as-partial", json={})
    assert resp.status_code == 400


def test_close_unknown_task_404(sync_app):
    client, store, ws, proj = sync_app
    resp = client.post("/api/tasks/nonexistent/close-as-partial", json={"confirm": True})
    assert resp.status_code == 404


def test_close_without_project_slug_400(sync_app):
    """Task mồ côi: không được ghi partial ra workspace/projects/translated/."""
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)
    job = reg.create_task("translation", "T", 1, project_slug="", filename="book.txt")
    store.update_status(job, "failed")
    _seed_checkpoint(ck)

    resp = client.post(f"/api/tasks/{job}/close-as-partial", json={"confirm": True})
    assert resp.status_code == 400
```

> `_seed_checkpoint` dùng `"abc"[i]` (3 ký tự cho 3 chunk). Bản nháp viết `"abcd"[i]` — không sai
> với `done=(0,1)` nhưng lệch với `chunks_text=["a","b","c"]`; sửa cho khớp để test không nói dối
> về nội dung chunk.
>
> Chữ ký đã xác thực trên nguồn: `init_session(filename, total_chunks, chunks_text=None,
> identity=None, reset=False)` (checkpoint_service.py:123), `save_chunk(filename, chunk_index,
> original_text, translated_text, api_key_used="", tokens_used=0, status='done')` (dòng 172).

### Step 6: Test gate Phase 3

```bash
.venv/bin/python -m pytest tests/unit/test_close_partial.py -q
# Kỳ vọng: PASS (8 test)
```

Negative đã phủ: 202 không assemble và không dọn cancel token sớm; worker race (join barrier) hoàn
tất trước khi đọc checkpoint; gọi lặp trả 200 `idempotent: true` cùng path; task mồ côi (không
`project_slug`) trả 400; thiếu `confirm` trả 400; task không tồn tại trả 404.

---

## Phase 4 — Một convention `checkpoint_key` + resolver dùng chung (P0)

**Files:**
- **KHÔNG** sửa `services/checkpoint_service.py` — `resolve_checkpoint_key` / `same_checkpoint_key` / `physical_checkpoint_key` đã có từ **Phase 0.5 Step 2**
- Modify: `webui/routes/projects.py` (**Step 1b: vá `NameError` B16**, `resume_task`, `recover_from_checkpoint`, `export_partial`)
- Modify: `webui/routes/tasks.py` (`_get_task_resume_info`, `get_task` completed fallback, `CheckpointService()` hardcoded, thêm route `by-checkpoint`)
- Modify: `webui/__init__.py` (tách `scan_and_recover` thành hàm testable)
- Modify: `webui/static/js/translation-worker.js` (`handleClosePartialByCheckpoints` + helper `resolveTaskForFile`)
- Test: `tests/unit/test_startup_scan.py` (resolver đã được test ở Phase 0.5 Step 4)

**Impact trước edit:** LOW trên mọi symbol bị đổi thân hàm đã xác nhận. Phase này **chỉ đổi call-site + thêm import thiếu**, không thêm API mới.

### Step 1: Kiểm tra tiền đề (KHÔNG viết code mới)

Bản nháp đặt `resolve_checkpoint_key` ở đây; nó đã được dời lên **Phase 0.5 Step 2** để phá vòng phụ
thuộc (B3). **Dán lại ở đây sẽ định nghĩa method trùng tên trong cùng một class** — Python lấy bản
sau và âm thầm bỏ bản trước, tức mất luôn guard path-traversal của Phase 0.5. Vì vậy step này chỉ
xác nhận:

```bash
.venv/bin/python - <<'PY'
from services.checkpoint_service import CheckpointService, same_source_identity
for name in ("resolve_checkpoint_key", "same_checkpoint_key", "physical_checkpoint_key", "_assert_safe_key"):
    assert hasattr(CheckpointService, name), f"THIẾU {name} — Phase 0.5 chưa xong"
import inspect, services.checkpoint_service as m
src = inspect.getsource(m)
assert src.count("def resolve_checkpoint_key") == 1, "ĐỊNH NGHĨA TRÙNG resolve_checkpoint_key"
assert src.count("def same_checkpoint_key") == 1, "ĐỊNH NGHĨA TRÙNG same_checkpoint_key"
print("OK: tiền đề Phase 4 đủ")
PY
```

Nếu script báo thiếu → quay lại làm Phase 0.5 trước, **không** vá tại chỗ.

### Step 1b: 🔴 B16 — vá `NameError` làm CHẾT 3 route lõi (làm TRƯỚC mọi step khác của Phase 4)

`webui/routes/projects.py` dùng 4 tên **không có trong scope nào** (không phải global của module, không
import trong hàm). Mọi request vào các route này raise `NameError` → `handle_all_exceptions` trả 500.
Kiểm chứng bằng `symtable` (per-scope, không phải grep):

| Hàm (route) | Dòng | Tên thiếu | Hậu quả tại HEAD |
|---|---|---|---|
| `resume_task` (`POST /api/tasks/<id>/resume`) | **1864** | `uuid` | **Resume chết hoàn toàn.** Nổ trước mọi lệnh ghi → không hỏng dữ liệu, nhưng nút "Tiếp tục dịch" không bao giờ chạy. |
| `resume_task` | 1900 | `PromptService` | (chưa với tới được vì 1864 nổ trước) |
| `resume_task` | 1913 | `TaskRegistry` | ” |
| `recover_from_checkpoint` | **2091** | `PromptService` | **Recovery chết, VÀ để lại rác.** Nổ *sau* `clone_namespace` (2026) + `create_recovery_task` (2036) + `write_partial_file` (2054) ⇒ mỗi lần bấm để lại 1 file `.db` mồ côi + 1 hàng task treo `running`. Lần bấm thứ 2 gặp `find_active_recovery_for_source` → **409 "Đã có recovery task đang chạy" vĩnh viễn**. |
| `close_as_partial` | 2228 | `TaskRegistry` | Nổ *sau* `update_recovery_task(status="partial_completed")` ⇒ hàng task mắc kẹt ở status rác (xem ghi chú Phase 3 Step 2). Route này **đã được thay toàn bộ** ở Phase 3 Step 2 (bản mới có import) → không cần sửa ở đây. |
| `summarize_project` | 1305 | `TaskRegistry` | Route AI project-info cũng 500. **Ngoài phạm vi P0** (không thuộc luồng checkpoint/resume) nhưng cùng một nguyên nhân; sửa 1 dòng nếu muốn, hoặc để P1 — ghi rõ lựa chọn vào báo cáo. |

**Vá `resume_task`** — thêm vào block import đầu hàm (dòng 1828), giữ nguyên thứ tự hiện có:

```python
def resume_task(task_id):
    import uuid
    from services.task_store import TaskStore
    from backend.infrastructure.config.prompt_service import PromptService
    from backend.infrastructure.progress.task_registry import TaskRegistry
```

**Vá `recover_from_checkpoint`** — thêm vào block import đầu hàm (dòng 1938-1941):

```python
def recover_from_checkpoint(task_id: str):
    from services.task_store import TaskStore
    from services.checkpoint_service import CheckpointService
    from backend.infrastructure.config.prompt_service import PromptService
    import uuid
    from pathlib import Path
```

> `PromptService` phải import từ **module nguồn** `backend.infrastructure.config.prompt_service`
> (giống dòng 1667/1760/2245) để test patch được đúng target — xem Phase 5 Step 1.
> `from pathlib import Path` ở dòng 1941 là dư (module đã import ở dòng 10) nhưng **đừng bỏ** ở step
> này: nó đang shadow đúng cùng một object, bỏ đi là thay đổi không cần thiết trong 1 hàm ta đang sửa
> vì lý do khác. Chỉ dọn ở `export_partial` (Step 4) nơi nó nằm giữa thân hàm.

**Cách phát hiện lại (chạy được ở bất kỳ thời điểm, KHÔNG cần pytest):**

```bash
.venv/bin/python - <<'PY'
import ast, symtable, builtins
path = "webui/routes/projects.py"
src = open(path, encoding="utf-8").read()
top = symtable.symtable(src, path, "exec")
mod = {s.get_name() for s in top.get_symbols() if s.is_assigned() or s.is_imported()} | set(dir(builtins))
tree = ast.parse(src)
scopes = {}
def collect(t):
    if t.get_type() == "function":
        scopes[(t.get_name(), t.get_lineno())] = {
            s.get_name() for s in t.get_symbols()
            if s.is_global() and not s.is_assigned() and s.get_name() not in mod
        }
    for c in t.get_children():
        collect(c)
collect(top)
bad = []
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        missing = scopes.get((node.name, node.lineno), set())
        if not missing:
            continue
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in missing:
                bad.append((n.lineno, node.name, n.id))
for ln, fn, nm in sorted(set(bad)):
    print(f"NameError tiềm ẩn: {path}:{ln} trong {fn}() → '{nm}'")
print("TỔNG:", len(set(bad)))
PY
# Trước khi vá: 6 dòng. Sau khi vá (kể cả summarize_project): 0 dòng.
# Nếu bỏ summarize_project cho P1 thì kỳ vọng đúng 1 dòng (projects.py:1305).
```

> ⚠️ Đây là loại lỗi **grep không bắt được** (`grep -n "import uuid" projects.py` không có kết quả nào
> cho biết hàm nào cần nó) và cũng **không** bị 301 test hiện tại phát hiện, vì không test nào gọi
> `/resume`, `/recover-from-checkpoint`, `/close-as-partial`. Vì vậy nó nằm ở Phase 4 Step 1b: bất kỳ
> assertion nào của Phase 5 về resume/recovery đều **không thể** xanh trước khi vá.

### Step 2: `webui/routes/projects.py` — `resume_task` dùng resolver

Thay block resolve trong `resume_task` (dòng ~1839-1854) bằng:

```python
    # A task row can outlive its SQLite checkpoint (for example after a
    # successful cleanup or manual file removal). Do not create a new resume
    # task when the source checkpoint is missing, unreadable, or complete.
    checkpoint_service = CheckpointService(_get_checkpoint_dir())
    resolved = checkpoint_service.resolve_checkpoint_key(task.get("checkpoint_key"))
    checkpoint_info = resolved["resume_info"] if resolved else None
    if not checkpoint_info or not checkpoint_info.get("can_resume"):
        return jsonify({
            "error": "Checkpoint không còn tồn tại, không đọc được hoặc đã hoàn tất; task không thể resume.",
            "task_id": task_id,
        }), 409
```
(bỏ biến `physical_checkpoint`/`checkpoint_key` cũ; giữ nguyên phần còn lại của hàm.)

> Ở đây **không** cần guard `resolved["filename"]`: hàm chỉ đọc `resume_info` rồi tạo task resume,
> không gọi API hash-based nào.

### Step 3: `webui/routes/projects.py` — `recover_from_checkpoint` dùng logical filename

Thay block từ `ck_key = source_task.get("checkpoint_key")` đến hết `indices = ...` (dòng ~1967-1977) bằng:

```python
    resolved = checkpoint_service.resolve_checkpoint_key(source_task.get("checkpoint_key"))
    if not resolved or not resolved.get("filename"):
        return jsonify({"error": "Không đọc được checkpoint hoặc metadata hỏng"}), 400
    ck_logical = resolved["filename"]

    indices = checkpoint_service.get_done_pending_indices(ck_logical)
    if not indices:
        return jsonify({"error": "Không đọc được checkpoint"}), 400
```

Sau đó thay dòng tạo recovery checkpoint (dòng ~2024):
```python
    recovery_ck_key = f"{ck_key}.{recovery_job_id[:8]}"
```
bằng:
```python
    recovery_ck_key = f"{ck_logical}.{recovery_job_id[:8]}"
```

Và thay lệnh clone (dòng ~2026):
```python
    if not checkpoint_service.clone_namespace(ck_logical, recovery_ck_key):
```
(trước đây là `clone_namespace(ck_key, recovery_ck_key)`.)

Cuối cùng thay dòng gọi worker recovery (dòng ~2132):
```python
    worker_thread = Thread(
        target=executor.recover_from_checkpoint,
        args=(ck_logical, recovery_ck_key, output_path, recovery_progress),
        daemon=True,
    )
```
(trước đây `args=(ck_key, ...)`.)

> Vì `ck_logical` là tên file gốc (vd `book.txt`) nên `clone_namespace`, `recover_from_checkpoint` hash nhất quán, không hash-of-hash. `recovery_ck_key` vẫn ghi vào task store như cũ.

### Step 4: `webui/routes/projects.py` — `export_partial` dùng resolver

Thay block resolve trong `export_partial` (dòng ~2167-2173) bằng:

```python
    resolved = checkpoint_service.resolve_checkpoint_key(task.get("checkpoint_key"))
    if not resolved or not resolved.get("filename"):
        return jsonify({"error": "Không đọc được checkpoint hoặc metadata hỏng"}), 400
    ck_logical = resolved["filename"]

    indices = checkpoint_service.get_done_pending_indices(ck_logical)
    if not indices or not indices["done_indices"]:
        return jsonify({"error": "Không có chunk nào đã dịch"}), 400

    partial_path = checkpoint_service.write_partial_file(
        ck_logical,
        project_dir / "translated" / ".recovery",
    )
```

> Bỏ dòng `from pathlib import Path` cục bộ của bản nháp: `projects.py` đã `from pathlib import Path`
> ở đầu file (dòng 6). Import lại trong hàm là vô hại nhưng làm người đọc tưởng `Path` chưa có, và
> nếu ai đó thêm `Path` vào tham số hàm thì shadow gây `UnboundLocalError`.

### Step 5: `webui/routes/tasks.py` — dùng resolver + thêm route lookup

**5a. Thêm factory checkpoint dir dùng chung** (sửa L9), chèn ngay sau `_get_task_store` (dòng 20),
trước `registry = TaskRegistry(...)`:

```python
def _get_checkpoint_service():
    """CheckpointService trỏ đúng workspace đang chạy.

    L9: `list_tasks` đã tự dựng đường dẫn từ `store.db_path` (dòng 50-52) nhưng `get_task`
    lại gọi `CheckpointService()` không tham số → dùng mặc định `workspace/checkpoints`
    theo CWD. Khi test set WORKSPACE_DIR sang tmp_path, hai hàm đọc HAI thư mục khác nhau:
    `list_tasks` archive task còn `get_task` vẫn thấy checkpoint (hoặc ngược lại).
    """
    from services.checkpoint_service import CheckpointService
    store = _get_task_store()
    return CheckpointService(str(Path(store.db_path).parent / "checkpoints"))
```

Rồi trong `list_tasks` (dòng 48-52) thay 4 dòng dựng `checkpoint_service` bằng:
```python
    checkpoint_service = _get_checkpoint_service()
```
(bỏ luôn `from services.checkpoint_service import CheckpointService` cục bộ ở dòng 48.)

**5b.** Thay `_get_task_resume_info` (dòng 26-35):
```python
def _get_task_resume_info(task: dict, checkpoint_service):
    """Read resume metadata qua resolver: logical | physical | stem — không hash lại."""
    resolved = checkpoint_service.resolve_checkpoint_key(task.get("checkpoint_key"))
    if not resolved:
        return None
    return resolved["resume_info"]
```

> Xóa `get_resume_info_from_path` / `get_resume_info` gọi tay ở đây: resolver đã bao cả 2 nhánh.
> `_is_valid_resumable_task` (dòng 38-41) không đổi — nó chỉ đọc dict trả về.

**5c.** Thay block fallback completed trong `get_task` (dòng 104-110):
```python
        if completed == 0 and task_row.get("status") in ("resumable", "paused", "failed", "interrupted") and task_row.get("checkpoint_key"):
            resolved = _get_checkpoint_service().resolve_checkpoint_key(task_row["checkpoint_key"])
            ck_info = resolved.get("resume_info") if resolved else None
            if ck_info:
                completed = ck_info.get("translated_count", 0)
                total = ck_info.get("total_chunks", total)
```

> Hai sửa lỗi so với bản nháp:
> 1. `CheckpointService()` **không tham số** là chính L9 — bản nháp giữ nguyên nó. Dùng
>    `_get_checkpoint_service()`.
> 2. `resolved["resume_info"]` có thể là `None` (checkpoint đã xong / metadata hỏng) → bản nháp
>    gọi `.get` trên `None` → `AttributeError` giữa request. Phải kiểm tra `ck_info` trước.
> 3. `translated_count` (số chunk done thật) thay cho `next_chunk_index` của mã cũ — `next_chunk_index`
>    là con trỏ, không phải số lượng, và bằng nhau chỉ khi phần done là tiền tố liền mạch.

**5d.** Thêm route lookup ở cuối `webui/routes/tasks.py` (sau `cancel_task`):

```python
_TERMINAL_TASK_STATUSES = ("completed", "cancelled", "closed_partial", "archived")


@tasks_bp.route("/api/tasks/by-checkpoint/<checkpoint_key>", methods=["GET"])
def task_by_checkpoint(checkpoint_key: str):
    """Resolve checkpoint (logical | physical | stem) về task duy nhất.

    Dùng cho luồng "close partial từ modal resume" — frontend có checkpoint_key
    từ payload 409 nhưng chưa có task_id.
    """
    store = _get_task_store()
    ck = _get_checkpoint_service()
    resolved = ck.resolve_checkpoint_key(checkpoint_key)
    if not resolved:
        return jsonify({"error": "Không tìm thấy checkpoint"}), 404

    physical = resolved["checkpoint_key"]

    # 1) Đường nhanh: cột checkpoint_key khớp đúng tên vật lý.
    match = store.get_task_by_checkpoint_key(physical)

    # 2) Task cũ lưu tên LOGIC (B4) → quét và so bằng comparator canonical.
    #    Ưu tiên task chưa terminal; nếu chỉ có terminal thì lấy bản mới nhất.
    if not match:
        candidates = [
            t for t in store.list_tasks()
            if t.get("checkpoint_key") and ck.same_checkpoint_key(t["checkpoint_key"], physical)
        ]
        alive = [t for t in candidates if t.get("status") not in _TERMINAL_TASK_STATUSES]
        pool = alive or candidates
        if pool:
            match = max(pool, key=lambda t: t.get("created_at") or "")

    if not match:
        return jsonify({
            "error": "Không tìm thấy task cho checkpoint",
            "checkpoint_key": physical,
        }), 404

    return jsonify({
        "task_id": match["task_id"],
        "job_id": match["job_id"],
        "status": match["status"],
        "checkpoint_key": physical,
        "filename": resolved["filename"],
    })
```

> Ba sửa lỗi so với bản nháp:
> 1. Bỏ `_same_ck` tự viết. `a.replace(".db", "")` thay **mọi** chỗ xuất hiện `.db` trong chuỗi, và
>    so 2 tên logic khác nhau vẫn ra False đúng nhưng so logic-vs-vật-lý thì luôn False — tức B9
>    vẫn còn. `ck.same_checkpoint_key` (Phase 0.5) mới là comparator canonical.
> 2. Dùng `store.get_task_by_checkpoint_key` (đã tồn tại, task_store.py:276) cho đường nhanh thay vì
>    luôn quét toàn bảng.
> 3. Một checkpoint có thể có **nhiều** task (task nguồn + task recovery/resume). Bản nháp lấy task
>    **đầu tiên** theo thứ tự `list_tasks()` — có thể là task đã `closed_partial`, khiến
>    close-as-partial trả về đường idempotent của task cũ thay vì chốt task đang sống. Chọn task chưa
>    terminal, mới nhất.
> 4. Dùng converter chuỗi mặc định thay `<path:...>`: key hợp lệ không bao giờ chứa `/`, và chặn ngay
>    ở tầng routing rẻ hơn là để `_assert_safe_key` từ chối sau.

### Step 6: `webui/__init__.py` — tách `scan_and_recover` testable

Thêm hàm module-level trước `create_app` (sau khối `translation_memory`) và thay block scan trong `create_app` (dòng ~97-139) bằng lời gọi:

```python
def scan_and_recover(store, ck_dir):
    """Startup reconciliation: running → interrupted; checkpoint mồ côi → resumable task.

    Tách ra để test. KHÔNG hash-of-hash: dùng get_resume_info_from_path cho file vật lý,
    fallback filename lấy từ metadata, không phải MD5 stem.
    Trả về số task mới tạo.
    """
    import uuid
    from services.checkpoint_service import CheckpointService

    created = 0
    for t in store.list_tasks():
        if t["status"] == "running":
            store.update_status(t["job_id"], "interrupted")

    if not ck_dir.exists():
        return created

    ck = CheckpointService(str(ck_dir))
    # Đọc bảng task MỘT lần rồi tự cập nhật danh sách khóa đã dùng: list_tasks() trong
    # vòng lặp là O(số checkpoint × số task) truy vấn SQLite mỗi lần khởi động.
    known_keys = [t.get("checkpoint_key") for t in store.list_tasks() if t.get("checkpoint_key")]

    for db_file in sorted(ck_dir.glob("*.db")):
        info = ck.get_resume_info_from_path(str(db_file))
        if not (info and info.get("can_resume")
                and info.get("translated_count", 0) < info.get("total_chunks", 0)):
            continue
        # B9: task cũ có thể lưu tên LOGIC ("book.txt") còn db_file.name là tên VẬT LÝ
        # ("f1ed388c8e76.db"). So thô bằng "==" không bao giờ khớp → mỗi lần khởi động lại
        # đẻ thêm một task resumable trùng trong workspace/tasks.db (dữ liệu thật của người dùng).
        if any(ck.same_checkpoint_key(k, db_file.name) for k in known_keys):
            continue
        job_id = str(uuid.uuid4())
        saved_identity = info.get("identity", {})
        logical = info.get("filename") or ""
        project_file = saved_identity.get("project_file") or logical
        project_slug = saved_identity.get("project_slug", "")
        store.create_task(
            job_id=job_id,
            kind="translation",
            title=f"Resume {project_file}",
            project_slug=project_slug,
            filename=project_file,
            total_chunks=info.get("total_chunks", 0),
            checkpoint_key=db_file.name,
            identity=saved_identity,
        )
        store.update_status(
            job_id, "resumable",
            completed_chunks=info.get("translated_count", 0),
            current_chunk=info.get("next_chunk_index", 0),
        )
        known_keys.append(db_file.name)
        created += 1
    return created
```

> **Đây là điểm nguy hiểm nhất của Phase 4**: hàm chạy trên `workspace/tasks.db` thật ở **mỗi lần
> khởi động server**. Bản nháp giữ nguyên `t.get("checkpoint_key") == db_file.name` — tức không sửa
> B9 dù bảng blocker nói là sửa ở Phase 4. Phải chạy `tests/unit/test_startup_scan.py` (Step 9,
> dùng `tmp_path`) TRƯỚC khi khởi động lại server thật.
>
> `create_task` không nhận `status`; cột có `DEFAULT 'running'` (task_store.py:65) nên task mới sinh
> ra là `running` trong khoảnh khắc giữa `create_task` và `update_status(...,"resumable")`. Đây là
> hành vi có sẵn, chấp nhận được vì cả hai lệnh chạy tuần tự trước khi Flask nhận request đầu tiên.

Trong `create_app`, thay toàn bộ block startup scan bằng:
```python
    # Scan resumable checkpoints on startup
    try:
        from services.task_store import TaskStore
        from pathlib import Path
        store = TaskStore()
        scan_and_recover(store, Path(store.db_path).parent / "checkpoints")
    except Exception as e:
        logger.warning(f"Startup checkpoint scan failed: {e}")
```

### Step 7: Frontend `handleClosePartialByCheckpoints` + `resolveTaskForFile`

> **B13 — hàm này ĐÃ TỒN TẠI (translation-worker.js:202-231) và đang 404 100% ở HEAD.**
> Dòng 208 gọi `POST /api/tasks/checkpoint/${ck.checkpoint_key}/close-as-partial`. Route đó
> **không tồn tại**: cả ứng dụng chỉ có `/api/tasks/<task_id>/close-as-partial`
> (projects.py:2191). Nên nút "Chốt file .partial" trong modal resume báo lỗi cho **mọi** file.
> Step này là **sửa lỗi sống**, không phải thêm tính năng — và nó phụ thuộc route
> `by-checkpoint` ở Step 5d, nên **không tách Step 7 ra làm trước Step 5**.

Thay toàn bộ hàm `handleClosePartialByCheckpoints` (dòng 202-231) bằng 2 hàm sau:

```js
    async resolveTaskForFile(filename, checkpointKey) {
        try {
            const res = await fetch('/api/tasks');
            if (!res.ok) return null;
            const data = await res.json();
            const tasks = data.tasks || [];
            let task = tasks.find(t => t.filename === filename);
            if (task) return task;
            if (checkpointKey) {
                const norm = String(checkpointKey).replace(/\.db$/, '');
                task = tasks.find(t => (t.checkpoint_key || '').replace(/\.db$/, '') === norm);
                if (task) return task;
                const r = await fetch(`/api/tasks/by-checkpoint/${encodeURIComponent(checkpointKey)}`);
                if (r.ok) {
                    const body = await r.json();
                    if (body.task_id) {
                        return tasks.find(t => t.task_id === body.task_id) ||
                               { task_id: body.task_id, job_id: body.job_id, status: body.status };
                    }
                }
            }
            return null;
        } catch (e) {
            console.error('resolveTaskForFile failed', e);
            return null;
        }
    },

    async handleClosePartialByCheckpoints(checkpoints, projectSlug) {
        let successCount = 0;
        let failCount = 0;
        let pendingCount = 0;
        for (const [name, ck] of Object.entries(checkpoints)) {
            try {
                const task = await TranslationWorker.resolveTaskForFile(name, ck.checkpoint_key);
                if (!task || !task.task_id) { failCount++; continue; }
                const res = await fetch(`/api/tasks/${task.task_id}/close-as-partial`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ confirm: true, export_partial: true })
                });
                if (res.status === 202) { pendingCount++; continue; }
                if (res.ok) { successCount++; }
                else { failCount++; }
            } catch (e) {
                console.error(e);
                failCount++;
            }
        }
        let msg = `Đã chia tách ${successCount} file thành công.`;
        if (pendingCount > 0) msg += ` ${pendingCount} file đang chờ worker dừng.`;
        if (failCount > 0) msg += ` Lỗi: ${failCount} file.`;
        UiHelpers.showToast(msg, successCount > 0 ? 'success' : (pendingCount > 0 ? 'info' : 'error'));
        if (typeof ProjectManager !== 'undefined' && ProjectManager.loadFiles) {
            ProjectManager.loadFiles(projectSlug);
        }
        ApiClient.loadTasks();
    },
```

### Step 8: (ĐÃ BỎ) — test resolver nằm ở Phase 0.5 Step 4

Bản nháp yêu cầu tạo `tests/unit/test_checkpoint_resolver.py` ở đây, nhưng **Phase 0.5 Step 4 đã tạo
đúng file đó** với bộ test rộng hơn (logical / physical / MD5 stem / namespace recovery
`<physical>.<8hex>` / `None` / rỗng / path-traversal / `same_checkpoint_key` / `same_source_identity`).
Làm lại ở đây sẽ **ghi đè file của Phase 0.5** — mất luôn 2 test bảo vệ path-traversal và
identity nguồn — hoặc, nếu người thực hiện dán thêm vào cuối file, sinh **hàm test trùng tên**
(`test_resolver_logical_key`, `test_resolver_md5_stem`, …) mà pytest chỉ chạy bản định nghĩa sau,
âm thầm bỏ bản trước. Cả hai kết cục đều là mất độ phủ mà không có cảnh báo nào.

Việc cần làm ở step này: chỉ chạy lại bộ test đã có.

```bash
.venv/bin/python -m pytest tests/unit/test_checkpoint_resolver.py -q
# Kỳ vọng: 9 passed (không tạo file mới, không thêm test mới)
```

### Step 9: Tạo `tests/unit/test_startup_scan.py`

```python
# tests/unit/test_startup_scan.py
"""scan_and_recover chạy trên workspace/tasks.db THẬT ở mỗi lần khởi động server.
Mọi test ở đây phải dùng tmp_path — không bao giờ TaskStore() không tham số.
"""
from services.checkpoint_service import CheckpointService
from services.task_store import TaskStore


def _seed(tmp_path, filename="book.txt", done=2, total=3, identity=None):
    ck = CheckpointService(str(tmp_path / "checkpoints"))
    ck.init_session(filename, total, ["a", "b", "c"][:total],
                    identity=identity or {"project_file": filename, "project_slug": "p"})
    for i in range(done):
        ck.save_chunk(filename, i, "abc"[i], f"B{i}")
    return ck


def test_scan_marks_running_interrupted(tmp_path):
    store = TaskStore(str(tmp_path))
    # Thứ tự positional: (job_id, kind, title, project_slug, filename, ...)
    store.create_task("j1", "translation", "T", "p", "f.txt", checkpoint_key="a.db")
    store.update_status("j1", "running")
    from webui import scan_and_recover
    assert scan_and_recover(store, tmp_path / "checkpoints") == 0
    assert store.get_task("j1")["status"] == "interrupted"


def test_scan_creates_resumable_for_orphan_checkpoint(tmp_path):
    store = TaskStore(str(tmp_path))
    ck = _seed(tmp_path)

    from webui import scan_and_recover
    created = scan_and_recover(store, tmp_path / "checkpoints")
    assert created == 1
    tasks = store.list_tasks()
    assert len(tasks) == 1
    t = tasks[0]
    assert t["status"] == "resumable"
    assert t["filename"] == "book.txt"
    assert t["project_slug"] == "p"
    assert t["checkpoint_key"] == ck._get_db_path("book.txt").name
    assert t["completed_chunks"] == 2

    # Idempotent: chạy lại không tạo thêm
    assert scan_and_recover(store, tmp_path / "checkpoints") == 0
    assert len(store.list_tasks()) == 1


def test_scan_does_not_duplicate_when_task_stores_logical_key(tmp_path):
    """B9 regression — test QUAN TRỌNG NHẤT của phase này.

    Task do executor tạo lưu checkpoint_key dạng LOGIC ("book.txt", từ
    emit(..., checkpoint_key=output_filename)), còn file trên đĩa mang tên VẬT LÝ
    ("f1ed388c8e76.db"). So thô bằng "==" không khớp → mỗi lần khởi động lại đẻ thêm
    một task resumable trùng trong tasks.db của người dùng.
    """
    store = TaskStore(str(tmp_path))
    _seed(tmp_path)
    store.create_task("j1", "translation", "T", "p", "book.txt", checkpoint_key="book.txt")
    store.update_status("j1", "interrupted")

    from webui import scan_and_recover
    assert scan_and_recover(store, tmp_path / "checkpoints") == 0
    assert len(store.list_tasks()) == 1

    # Và chạy 3 lần liên tiếp (mô phỏng 3 lần khởi động) vẫn đúng 1 row
    for _ in range(3):
        scan_and_recover(store, tmp_path / "checkpoints")
    assert len(store.list_tasks()) == 1


def test_scan_skips_completed_checkpoint(tmp_path):
    """Checkpoint đã dịch đủ → không sinh task resumable."""
    store = TaskStore(str(tmp_path))
    _seed(tmp_path, done=3, total=3)
    from webui import scan_and_recover
    assert scan_and_recover(store, tmp_path / "checkpoints") == 0
    assert store.list_tasks() == []


def test_scan_missing_dir_is_noop(tmp_path):
    store = TaskStore(str(tmp_path))
    from webui import scan_and_recover
    assert scan_and_recover(store, tmp_path / "khong-ton-tai") == 0
```

> `from webui import scan_and_recover` chạy module-level code của `webui/__init__.py`: tạo
> `workspace/logs/` + file log và khởi tạo `TranslationMemory` trỏ
> `workspace/projects/default-project/...` (dòng 14-64). Đây là hành vi có sẵn, chỉ ghi thêm log —
> **không** sửa trong P0. Chỉ cần biết rằng import này chạm `workspace/` thật, nên
> `scan_and_recover` bắt buộc nhận `store`/`ck_dir` qua tham số (đó là lý do Step 6 tách hàm) và
> test không bao giờ được gọi nó với `TaskStore()` mặc định.

### Step 10: Test gate Phase 4

```bash
.venv/bin/python -m pytest tests/unit/test_checkpoint_resolver.py tests/unit/test_startup_scan.py tests/unit/test_close_partial.py -q
# Kỳ vọng: PASS — 9 resolver (Phase 0.5) + 5 startup + 8 close = 22

# Bắt buộc: xác nhận không còn so sánh checkpoint_key thô ở các call-site đã sửa
grep -n 'checkpoint_key") ==\|checkpoint_key"\] ==' webui/__init__.py webui/routes/tasks.py
# Kỳ vọng: KHÔNG có dòng nào (mọi so sánh đi qua same_checkpoint_key)

grep -rn "tasks/checkpoint/" webui/static/js/
# Kỳ vọng: KHÔNG có dòng nào (route ảo /api/tasks/checkpoint/<key>/... đã bị xóa — B13)

# B16: chạy lại script symtable ở Step 1b
# Kỳ vọng: 0 dòng (hoặc đúng 1 dòng projects.py:1305 nếu cố ý để summarize_project cho P1)

.venv/bin/python -m pytest -q --ignore=test_debug.py
# Kỳ vọng: vẫn đúng 4 failed pre-existing, không thêm
```

Negative đã phủ: cùng một checkpoint resolve theo physical/stem/logical luôn về MỘT path
(`test_resolver_never_hashes_a_db_name_twice`); task lưu key logic không sinh bản trùng
(`test_scan_does_not_duplicate_when_task_stores_logical_key`); checkpoint đã hoàn tất không sinh task;
`by-checkpoint` chọn task chưa terminal khi một checkpoint có nhiều task; không còn `NameError`
tiềm ẩn trong `projects.py` (B16).

---

## Phase 5 — Integration gate P0 (release blocker)

**Files:**
- Create: `tests/integration/test_resume_recovery_e2e.py`

**Yêu cầu:** chạy từ đầu đến cuối trong tmp workspace, fake provider, worker chạy inline (patch `Thread`), checkpoint/executor trỏ tmp.

### Step 1: Tạo `tests/integration/test_resume_recovery_e2e.py`

```python
# tests/integration/test_resume_recovery_e2e.py
"""P0 integration gate: 24 chunk → commit 0..16 → 451 tại 17 →
close partial | recovery → chỉ gửi [17..23] → completed.

KHÔNG gọi mạng: robust_translate bị patch; worker chạy inline (SyncThread);
CheckpointService/ProviderService trỏ tmp.
"""
import re
from pathlib import Path

import pytest

from services.checkpoint_service import CheckpointService
from services.task_store import TaskStore

TOTAL = 24
CENSOR_AT = 17


@pytest.fixture(autouse=True)
def _reset():
    from backend.infrastructure.progress.runtime_state import RuntimeState
    from backend.infrastructure.progress.task_registry import TaskRegistry
    TaskRegistry._instance = None
    RuntimeState.reset()
    yield
    TaskRegistry._instance = None
    RuntimeState.reset()


def _source_text():
    return "\n\n".join(f"chunk {i}" for i in range(TOTAL))


def _fake_provider_config():
    return {
        "type": "openai",
        "api_key": "test-key",
        "gateway_api_key": "",
        "credential_mode": "default",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-test",
        "id": "openai-test",
    }


def _install_fakes(monkeypatch, ws, proj, sent_log, fail_at=CENSOR_AT):
    """Patch mọi thứ để luồng translate/recovery chạy offline trong tmp."""
    ck_dir = ws / "checkpoints"

    # CheckpointService chia sẻ 1 instance
    ck_service = CheckpointService(str(ck_dir))

    def _make_ck(*a, **k):
        return ck_service

    monkeypatch.setattr("core.executor.CheckpointService", _make_ck)
    monkeypatch.setattr("core.executor.ApiManager", lambda keys: None)

    # robust_translate giả: đếm lần gọi, fail censorship_blocked tại index fail_at.
    # Parse chunk_index từ original_text ("chunk N").
    state = {"calls": 0}

    def fake_rt(original_chunk, api_manager, prompts, config_params,
                previous_chunk_context="", normalizer=None):
        i = state["calls"]
        state["calls"] += 1
        m = re.search(r"chunk (\d+)", original_chunk or "")
        idx = int(m.group(1)) if m else i
        sent_log.append(idx)
        if idx == fail_at:
            return None, "censorship_blocked", "key-451"
        return f"[dịch {idx}]", "success", "key-ok"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    # Provider config giả
    from unittest.mock import MagicMock
    fake_provider_service = MagicMock()
    fake_provider_service.get_active_provider_config.return_value = _fake_provider_config()
    fake_provider_service.get_provider_by_id.return_value = _fake_provider_config()
    monkeypatch.setattr(
        "backend.infrastructure.providers.provider_service.ProviderService",
        lambda: fake_provider_service,
    )

    # Thread chạy inline
    from tests.conftest import SyncThread
    monkeypatch.setattr("webui.routes.projects.Thread", SyncThread)

    # Route helpers trỏ tmp
    monkeypatch.setattr("webui.routes.projects._get_checkpoint_dir", lambda: str(ck_dir))
    monkeypatch.setattr("webui.routes.projects._get_workspace_dir", lambda: str(ws))
    monkeypatch.setattr("webui.routes.projects._get_project_dir", lambda slug: proj)
    monkeypatch.setattr("webui.routes.projects._load_project_meta", lambda slug: {"book_title": "T", "slug": slug})

    # TaskRegistry singleton gắn store tmp
    from backend.infrastructure.progress.task_registry import TaskRegistry
    TaskRegistry._instance = None
    tmp_store = TaskStore(str(ws))
    TaskRegistry(store=tmp_store)
    monkeypatch.setattr("webui.routes.tasks._get_task_store", lambda: tmp_store)

    return ck_service, tmp_store


def _make_flask_client(monkeypatch, ws, proj):
    from flask import Flask
    from webui.routes.projects import projects_bp
    from webui.routes.tasks import tasks_bp
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)
    return app.test_client()


def _create_project_file(proj):
    src = proj / "sources" / "book.txt"
    src.write_text(_source_text(), encoding="utf-8")
    return src


def _run_translate(client):
    """POST translate (không force) → worker chạy inline → 451 tại 17."""
    resp = client.post("/api/projects/p/translate",
                       json={"files": ["book.txt"], "model": "gpt-test"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "started"
    return data["job_id"]


def test_full_451_close_partial_scenario(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    _create_project_file(proj)

    sent = []
    ck_service, store = _install_fakes(monkeypatch, ws, proj, sent)
    client = _make_flask_client(monkeypatch, ws, proj)

    # 1) Dịch → fail censorship_blocked tại 17
    job_id = _run_translate(client)
    task = store.get_task(job_id)
    assert task is not None
    assert task["status"] == "failed"
    assert task["error_class"] == "censorship_blocked"
    assert task["http_status"] == 451

    # Source checkpoint bất biến: 17 done
    resolved = ck_service.resolve_checkpoint_key(task["checkpoint_key"] or "book.txt")
    assert resolved is not None
    indices = ck_service.get_done_pending_indices(resolved["filename"])
    assert len(indices["done_indices"]) == 17
    assert indices["pending_indices"] == list(range(CENSOR_AT, TOTAL))

    # 2) Gọi translate lại → 409 resume_required (modal mở được)
    resp = client.post("/api/projects/p/translate", json={"files": ["book.txt"], "model": "gpt-test"})
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["status"] == "resume_required"
    ck_meta = data["checkpoints"]["book.txt"]
    assert ck_meta["completed_chunks"] == 17
    assert ck_meta["total_chunks"] == TOTAL

    # 3) Close partial qua resolver checkpoint→task
    r = client.get(f"/api/tasks/by-checkpoint/{ck_meta['checkpoint_key']}")
    assert r.status_code == 200
    task_meta = r.get_json()
    assert task_meta["task_id"] == job_id

    resp = client.post(f"/api/tasks/{task_meta['task_id']}/close-as-partial",
                       json={"confirm": True, "export_partial": True})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "closed_partial"
    assert body["completed_chunks"] == 17
    assert body["pending_chunks"] == 7

    partial = Path(body["partial_output"])
    assert partial.exists()
    text = partial.read_text()
    assert "CHUNK 17 CHƯA DỊCH" in text  # index 17 (0-based) thiếu → marker
    assert text.count("CHUNK") == 7  # đúng 7 marker
    manifest = partial.with_suffix(".manifest.json")
    import json as _json
    m = _json.loads(manifest.read_text())
    assert m["is_complete"] is False

    # 4) Task ở closed_partial, KHÔNG completed
    assert store.get_task(job_id)["status"] == "closed_partial"
    from backend.infrastructure.progress.task_registry import TaskRegistry
    assert TaskRegistry().get_task(job_id).status == "closed_partial"


def test_full_451_recovery_scenario(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    _create_project_file(proj)

    sent = []
    ck_service, store = _install_fakes(monkeypatch, ws, proj, sent)
    client = _make_flask_client(monkeypatch, ws, proj)

    job_id = _run_translate(client)
    task = store.get_task(job_id)
    assert task["status"] == "failed"
    assert task["http_status"] == 451

    # Recovery với provider khác (mixed_provider)
    resp = client.post(f"/api/tasks/{job_id}/recover-from-checkpoint",
                       json={"provider_id": "openai-test", "model": "gpt-other",
                             "export_partial": True})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["status"] == "recovery_started"
    recovery_job_id = body["job_id"]

    # Recovery task chain đúng
    rec_task = store.get_task(recovery_job_id)
    assert rec_task["source_task_id"] == job_id
    assert rec_task["recovery_of"] == job_id
    assert rec_task["mixed_provider"] == 1
    assert rec_task["status"] == "completed"  # worker inline đã chạy xong

    # Fake provider CHỈ nhận [17..23] ở lần recovery (đã lọc bỏ 0..16)
    # Lần dịch đầu đã gửi 0..17; recovery gửi 17..23 (lặp 17 do clone giữ pending).
    recovered = [i for i in sent if i >= CENSOR_AT]
    assert set(recovered) == set(range(CENSOR_AT, TOTAL))

    # Source checkpoint bất biến
    src_resolved = ck_service.resolve_checkpoint_key(task["checkpoint_key"] or "book.txt")
    assert len(ck_service.get_done_pending_indices(src_resolved["filename"])["done_indices"]) == 17

    # Recovery checkpoint còn nguyên (không cleanup trước verify)
    rec_resolved = ck_service.resolve_checkpoint_key(rec_task["recovery_checkpoint_key"])
    assert rec_resolved is not None

    # Output final không marker, verify thành công, task recovery completed
    final_path = Path(rec_task["final_output_path"])
    assert final_path.exists()
    out = final_path.read_text()
    assert "CHUNK" not in out
    assert "CHƯA DỊCH" not in out
    assert out.count("[dịch") == TOTAL


def test_cancel_recovery_isolated(tmp_path, monkeypatch):
    """Cancel recovery KHÔNG dừng job nguồn hoặc job khác; recovery checkpoint còn nguyên."""
    from backend.infrastructure.progress.runtime_state import RuntimeState

    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    _create_project_file(proj)

    sent = []
    ck_service, store = _install_fakes(monkeypatch, ws, proj, sent)
    client = _make_flask_client(monkeypatch, ws, proj)

    job_id = _run_translate(client)
    task = store.get_task(job_id)

    resp = client.post(f"/api/tasks/{job_id}/recover-from-checkpoint",
                       json={"provider_id": "openai-test", "model": "gpt-other"})
    assert resp.status_code == 200
    recovery_job_id = resp.get_json()["job_id"]

    # Cancel recovery (job mới, không phải job nguồn)
    client.post(f"/api/tasks/{recovery_job_id}/cancel")

    # Isolation: job nguồn + job khác không bị cancel
    assert RuntimeState().is_cancelled(job_id) is False
    assert RuntimeState().is_cancelled("some-other-job") is False
    # Job nguồn KHÔNG đổi status (vẫn failed)
    assert store.get_task(job_id)["status"] == "failed"
    # Recovery checkpoint còn nguyên
    rec_task = store.get_task(recovery_job_id)
    rec_resolved = ck_service.resolve_checkpoint_key(rec_task["recovery_checkpoint_key"])
    assert rec_resolved is not None
```

> **Lưu ý 2 test đầu:** recovery chạy inline nên `rec_task["status"]` là `completed` ngay sau POST. `sent` ghi cả lần dịch đầu (0..17) lẫn recovery (17..23); assertion chỉ kiểm tra phần `>= 17`. Đây là bằng chứng "recovery chỉ gửi pending indices, không gửi lại 0..16".

### Step 2: Test gate Phase 5

```bash
.venv/bin/python -m pytest tests/integration/test_resume_recovery_e2e.py -q
# Kỳ vọng: PASS (3 test)
```

### Step 3: Full gate P0

```bash
.venv/bin/python -m pytest tests/unit/test_checkpoint_resume.py tests/unit/test_endpoint_policy.py tests/unit/test_task_store.py tests/unit/test_cancel_scoped.py tests/unit/test_project_routes.py tests/unit/test_close_partial.py tests/unit/test_checkpoint_resolver.py tests/unit/test_startup_scan.py tests/unit/test_task_registry_persistence.py tests/integration/test_resume_recovery_e2e.py -q
# Kỳ vọng: toàn bộ PASS (28 cũ + 6 cancel + 1 route409 + 6 close + 6 resolver + 2 startup + 3 integration)
```

### Step 4: Negative cases bắt buộc (đã nằm trong suite)

- 202 không assemble (test_close_returns_202...).
- Worker race: cancel-and-wait hoàn tất trước khi đọc checkpoint (test_close_running_cancels_and_waits).
- Request lặp close: idempotent (test_close_resumable + failed).
- Cancel không lan sang job khác (test_cancel_* + test_cancel_recovery_isolated).
- Recovery chỉ gửi pending indices (assert set recovered).
- Source checkpoint bất biến sau recovery.

### Step 5: Diff check trước khi kết thúc P0

```bash
git status --short
# Chỉ được có: các file trong danh sách phase + tests/conftest.py + tests/integration/test_resume_recovery_e2e.py
git diff --stat
gitnexus_detect_changes(scope: "all")
# Nếu có file/symbol/flow ngoài dự kiến → DỪNG, review
```

---

## 2. Bảng trạng thái phase (cập nhật vào báo cáo, không tự đánh "complete" nếu test chưa xanh)

| Phase | Status | Required evidence |
|---|---|---|
| 0 Baseline/harness | `pending` | baseline 28 passed + conftest |
| 1 Cancel scoped | `pending` | test_cancel_scoped xanh |
| 2 Resume 409 UX | `pending` | test_project_routes 409 + JS grep |
| 3 Close partial | `pending` | test_close_partial xanh |
| 4 Key resolver | `pending` | resolver + startup scan xanh |
| 5 P0 integration | `pending` | 3 integration tests xanh |
| 6+ | `pending` | chưa được làm trong đợt này |

## 3. Mẫu handoff mỗi phase (bắt buộc ghi)

```text
Phase: <n>
Impact trước edit: <symbols, d=1, risk>
Files changed: <danh sách>
Contract changed: <trước/sau nếu có>
Tests added/updated: <danh sách>
Commands and result: <lệnh + kết quả>
Negative cases: <kết quả>
Remaining risks/blockers: <danh sách>
Status: complete | blocked | pending
```

## 4. Việc KHÔNG được làm trong đợt này

- Phase 6–9 (recovery orchestration sâu, durable restart/lease, auto-merge, in-flight, smart-batch) — thuộc P1/P2.
- Sửa 4 test fail pre-existing (`test_file_operations`, `test_provider_services`).
- Reset/checkout/stash/xóa `workspace/tasks.db` hoặc checkpoint.
- Đổi tên symbol bằng find/replace.
- Thêm dependency mới.

## 5. Kết quả cam kết sau khi hoàn tất P0

Phần này mô tả **đúng phạm vi P0 sau REV-C**, dùng để review acceptance sau khi model sinh mã. Chỉ đánh dấu đạt khi có test/evidence tương ứng; không suy ra từ việc endpoint tồn tại.

### Tính năng người dùng nhận được

- Khi file có checkpoint hợp lệ, bấm “Dịch” nhận response `409 resume_required` đúng contract và mở được modal lựa chọn.
- Người dùng có thể tiếp tục checkpoint bằng execution identity hiện tại hoặc identity provider/model khác mà không làm mất các chunk đã commit.
- Người dùng có thể xuất phần đã dịch thành partial artifact có marker và manifest `is_complete=false`.
- Người dùng có thể “Dừng và chốt phần đã dịch”; task chuyển sang `closed_partial`, không bị hiển thị như completed và checkpoint vẫn còn để recovery.
- Recovery tạo task/checkpoint namespace riêng, giữ nguyên checkpoint nguồn, ghi rõ quan hệ task nguồn → recovery task và chỉ gửi các index pending.
- HTTP 451 được lưu/display dưới dạng `censorship_blocked`, `http_status=451`, `retryable=false` và không bị coi là lỗi mạng thông thường.
- Cancel một job chỉ dừng job đó; cancel job A không dừng job B, job nguồn hoặc recovery job khác.
- Cancel recovery thật sự dừng worker đang chạy, không chỉ đổi trạng thái DB; checkpoint recovery còn đọc được sau khi dừng.
- Close partial đang chạy có cancel-and-wait/write barrier; nếu worker chưa dừng đúng hạn API trả `202 close_pending` và không assemble cạnh tranh.
- Startup scan không tạo task resumable trùng khi task lưu logical key còn file checkpoint dùng physical key.

### Lỗi/regression được giải quyết

- Cancel global qua `/api/translate/cancel` và cancel poisoning sau `reset_cancel`.
- `resume_required` bị frontend ném lỗi trước khi đọc payload 409.
- Endpoint frontend gọi sai `/api/tasks/checkpoint/<key>/close-as-partial`.
- `close_as_partial` ghi `partial_completed` rồi clobber thành `completed`.
- Ghi đè `completed_chunks` về 0 khi task lỗi giữa chừng.
- SSE đóng sớm ở event `error`, làm mất `task_failed`/HTTP 451 metadata.
- Hash-of-hash và lệch logical/physical `checkpoint_key`.
- Executor xóa chunk đã dịch khi chỉ provider/model thay đổi.
- Route recovery/export/close thiếu resolver hoặc đọc sai checkpoint directory.
- `NameError` trong route recovery/close và fallback đọc checkpoint hardcode workspace.
- E2E test giả xanh do source không đủ chunk hoặc fake provider fail vĩnh viễn.

### Những thứ P0 **không** được tuyên bố đã hoàn tất

- Recovery nhiều file đồng thời hoặc selected-files tự quyết định per-file.
- Durable restart/lease/heartbeat đầy đủ sau process crash.
- Auto-merge/retention lifecycle hoàn chỉnh sau recovery nếu chưa chạy Phase 6–8.
- Durable `in_flight`, attempt tracking và duplicate-cost accounting.
- Smart-batch nhiều file với manifest bất biến.

### Acceptance gate cuối P0

P0 chỉ được đánh `complete` khi đồng thời đạt tất cả điều kiện:

1. Baseline snapshot có `new failures = 0`.
2. Unit, route, cancel, resolver, startup và integration tests đều xanh theo đúng danh sách phase.
3. E2E chứng minh 24 chunk thật, initial `[0..17]`, recovery `[17..23]`, không có chunk 0–16 bị gửi lại.
4. E2E cancel recovery dùng thread/barrier thật và chứng minh worker đã dừng.
5. E2E close running chứng minh save barrier trước assemble.
6. `closed_partial` không xuất hiện trong completed list và source checkpoint không bị mutate/xóa.
7. GitNexus impact từng symbol đã sửa được lưu trong handoff; `gitnexus_detect_changes(scope="all")` không phát hiện file/flow ngoài phạm vi.
8. Selected-files có checkpoint hoặc bị chặn bằng contract rõ ràng, tuyệt đối không silently bỏ file.


---

## 9. Điều chỉnh Lộ trình & Báo Cáo Nghiệm Thu P0 (2026-08-19)

### 9.1 Đánh giá Hiện trạng & Tách tầng Kiến trúc

| Tầng | Phạm vi | Trọng tâm Triển khai | Trạng thái |
|---|---|---|:---:|
| **P0** | **Chốt Test Gate & Hermetic Smoke Test** | Mock matrix provider cho `/api/models` (Gemini, OpenAI, Error branch), loại bỏ triệt để network calls, xác nhận suite đạt **362 passed, 4 failed** (4 pre-existing waiver). | ✅ **HOÀN TẤT** |
| **P1.7** | **Lease An Toàn & Fencing Token** | Triển khai `LeaseKeepAlive` (daemon thread có `Event`, `join(1.0)`, cleanup `finally`) kết hợp bắt buộc với **Fencing Token (`lease_token`/`lease_epoch`)** và atomic CAS commit; worker mất lease phải abort ngay; test 6 kịch bản in-flight/revocation/zombie. | 📋 Sẵn sàng thực thi |
| **P2** | **Mở rộng Phân tán & Hardening** | DB-level Cross-process Idempotency, Auto-merge/Retention cleanup, `recovery_attempts`/`FAILED_POISON_PILL` (quarantine poison job), SSE reconnect hoàn chỉnh, Multi-process worker pool. | ⏳ Hậu P1.7 |

### 9.2 Chi tiết Kết quả Nghiệm thu P0
1. **Hermetic Mock `/api/models`:** Đã bổ sung mock matrix tại `tests/smoke/test_webui_app_factory.py` cho cả 2 provider active và các query parameters (`?provider=gemini`, `?provider=openai`), bảo đảm không có outbound socket call.
2. **Kiểm thử Toàn Suite (3 lần liên tiếp):**
   - Lần 1: `362 passed, 4 failed` (12.08s)
   - Lần 2: `362 passed, 4 failed` (11.99s)
   - Lần 3: `362 passed, 4 failed` (12.12s)
   - Tỉ lệ Flakiness: **0%**.
3. **Bốn (4) Pre-existing Failures (Documented Waiver):**
   - `tests/unit/test_file_operations.py::TestSplitFiles::test_splits_using_chunker`
   - `tests/unit/test_file_operations.py::TestSplitFiles::test_delete_source_after_success`
   - `tests/unit/test_provider_services.py::TestPromptServiceMethods::test_save_and_reset_project_prompts`
   - `tests/unit/test_provider_services.py::TestPromptServiceMethods::test_import_prompts_to_project`
