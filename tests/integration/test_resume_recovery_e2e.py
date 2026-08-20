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
from tests.conftest import E2E_CHUNK_SIZE, E2E_TOTAL_CHUNKS, make_chunked_source, make_fake_robust_translate

TOTAL = E2E_TOTAL_CHUNKS
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

    # Fake provider config
    from unittest.mock import MagicMock
    fake_provider_service = MagicMock()
    fake_provider_service.get_active_provider_config.return_value = _fake_provider_config()
    fake_provider_service.get_provider_by_id.return_value = _fake_provider_config()
    monkeypatch.setattr(
        "backend.infrastructure.providers.provider_service.ProviderService",
        lambda: fake_provider_service,
    )

    # Recovery control: chỉ block khi test yêu cầu (cho test cancel).
    # Dùng Event để đồng bộ worker chính xác, không dùng sleep:
    #  - blocked_event: worker đang chờ allow_next (đã thực sự bị block)
    #  - allow_next:   test release để worker tiến
    from threading import Event
    recovery_control = {
        "is_recovery": False,
        "block_chunks": False,  # chỉ block khi test cancel bật cờ này
        "blocked_event": Event(),
        "blocked_event_unset": Event(),  # báo test rằng worker vừa clear blocked (đã chuyển trạng thái)
        "allow_next": Event(),
        "fail_status": "censorship_blocked",  # status robust_translate trả khi fail (test override)
    }
    # Mặc định: allow_next set để worker không block nếu test không bật block_chunks
    recovery_control["allow_next"].set()

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

    # robust_translate giả: dùng SEG label, fail censorship_blocked tại index fail_at.
    # Khi block_chunks=True và is_recovery=True, block tại allow_next event để test cancel.
    sent_log = sent_log

    state = {"failed": False}
    recovery_control["state"] = state  # cho test reset/hold state giữa translate & recovery

    def fake_rt(original_chunk=None, api_manager=None, prompts=None,
                config_params=None, previous_chunk_context="", normalizer=None, **kwargs):
        m = re.search(r"SEG(\d+)", original_chunk or "")
        idx = int(m.group(1)) if m else -1
        sent_log.append(idx)
        
        # Chỉ block khi test cancel bật block_chunks
        if recovery_control["block_chunks"] and recovery_control["is_recovery"] and idx >= CENSOR_AT:
            recovery_control["allow_next"].clear()
            # Báo worker thực sự đang block rồi chờ test release
            recovery_control["blocked_event"].set()
            recovery_control["allow_next"].wait(timeout=5)
            recovery_control["blocked_event"].clear()
        
        if idx == fail_at and not state["failed"]:
            state["failed"] = True
            fail_status = recovery_control.get("fail_status", "censorship_blocked")
            return None, fail_status, "key-451"
        return f"[dịch {idx}]", "success", "key-ok"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    return ck_service, tmp_store, recovery_control


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
    src.write_text(make_chunked_source(), encoding="utf-8")
    return src


def _run_translate(client, store=None):
    """POST translate (không force) → worker chạy inline → 451 tại 17."""
    resp = client.post("/api/projects/p/translate",
                       json={"files": ["book.txt"], "model": "gpt-test", "chunk_size": E2E_CHUNK_SIZE})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "started"
    job_id = data["job_id"]

    # Bounded wait for task to complete (failed or completed)
    import time
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if store is not None:
            row = store.get_task(job_id)
            if row and row.get("status") in ("failed", "completed", "cancelled"):
                break
        time.sleep(0.02)
    return job_id


def test_full_451_close_partial_scenario(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    _create_project_file(proj)

    sent = []
    ck_service, store, recovery_control = _install_fakes(monkeypatch, ws, proj, sent)
    client = _make_flask_client(monkeypatch, ws, proj)

    # 1) Dịch → fail censorship_blocked tại 17
    job_id = _run_translate(client, store)
    task = store.get_task(job_id)
    assert task is not None
    assert task["status"] == "failed"
    assert task["error_class"] == "censorship_blocked"
    assert task["http_status"] == 451

    # Source checkpoint bất biến: 17 done
    resolved = ck_service.resolve_checkpoint_key(task["checkpoint_key"] or "book.txt")
    assert resolved is not None
    indices = ck_service.get_done_pending_indices(resolved["filename"])
    assert len(indices["done_indices"]) == CENSOR_AT
    assert indices["pending_indices"] == list(range(CENSOR_AT, TOTAL))

    # 2) Gọi translate lại → 409 resume_required (modal mở được)
    resp = client.post("/api/projects/p/translate", json={"files": ["book.txt"], "model": "gpt-test", "chunk_size": E2E_CHUNK_SIZE})
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["status"] == "resume_required"
    ck_meta = data["checkpoints"]["book.txt"]
    assert ck_meta["completed_chunks"] == CENSOR_AT
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
    assert body["completed_chunks"] == CENSOR_AT
    assert body["pending_chunks"] == TOTAL - CENSOR_AT

    partial = Path(body["partial_output"])
    assert partial.exists()
    text = partial.read_text()
    assert f"CHUNK {CENSOR_AT} CHƯA DỊCH" in text  # index 17 (0-based) thiếu → marker
    assert text.count("CHUNK") == TOTAL - CENSOR_AT
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
    ck_service, store, recovery_control = _install_fakes(monkeypatch, ws, proj, sent)
    client = _make_flask_client(monkeypatch, ws, proj)

    job_id = _run_translate(client, store)
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

    # Recovery chạy hết (KHÔNG block) -> task sẽ completed
    import time
    for _ in range(20):  # wait up to 2 seconds
        time.sleep(0.1)
        rec_task = store.get_task(recovery_job_id)
        if rec_task["status"] in ("completed", "failed"):
            break
    
    assert rec_task["status"] == "completed"  # worker đã chạy xong

    # Fake provider CHỈ nhận [17..23] ở lần recovery (đã lọc bỏ 0..16)
    recovered = [i for i in sent if i >= CENSOR_AT]
    assert set(recovered) == set(range(CENSOR_AT, TOTAL))

    # Source checkpoint bất biến
    src_resolved = ck_service.resolve_checkpoint_key(task["checkpoint_key"] or "book.txt")
    assert len(ck_service.get_done_pending_indices(src_resolved["filename"])["done_indices"]) == CENSOR_AT

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


def _wait_status(store, job_id, expected, timeout=5.0):
    """Poll store cho đến khi task đạt status expected (bounded, không gây flaky sleep)."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = store.get_task(job_id)
        if row and row["status"] == expected:
            return True
        time.sleep(0.02)
    return False


def test_cancel_recovery_isolated(tmp_path, monkeypatch):
    """Cancel recovery KHÔNG dừng job nguồn hoặc job khác; recovery task phải đạt `cancelled`.

    Dùng Event synchronization (blocked_event) để biết worker thực sự block, không dùng sleep.
    """
    from backend.infrastructure.progress.runtime_state import RuntimeState
    import time

    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    _create_project_file(proj)

    sent = []
    ck_service, store, recovery_control = _install_fakes(monkeypatch, ws, proj, sent)
    client = _make_flask_client(monkeypatch, ws, proj)

    job_id = _run_translate(client, store)
    task = store.get_task(job_id)

    resp = client.post(f"/api/tasks/{job_id}/recover-from-checkpoint",
                       json={"provider_id": "openai-test", "model": "gpt-other"})
    assert resp.status_code == 200
    recovery_job_id = resp.get_json()["job_id"]

    # Bật block cho test cancel: recovery sẽ block tại mỗi chunk pending
    recovery_control["block_chunks"] = True
    recovery_control["is_recovery"] = True

    # Đợi (bounded) cho đến khi worker thực sự block tại chunk đầu tiên — KHÔNG sleep.
    assert recovery_control["blocked_event"].wait(5.0), "Recovery worker không block như dự kiến"

    # Cancel recovery (job mới, không phải job nguồn)
    client.post(f"/api/tasks/{recovery_job_id}/cancel")
    assert RuntimeState().is_cancelled(recovery_job_id) is True

    # Release block để worker tiến tới vòng lặp kiểm tra cancel → emit "cancelled" → terminal
    recovery_control["allow_next"].set()

    # Bounded wait: recovery phải đạt terminal `cancelled` trong tasks.db
    assert _wait_status(store, recovery_job_id, "cancelled", timeout=5.0), (
        f"Recovery task không đạt 'cancelled' sau cancel"
    )

    # Isolation: job nguồn + job khác không bị cancel
    assert RuntimeState().is_cancelled(job_id) is False
    assert RuntimeState().is_cancelled("some-other-job") is False
    # Job nguồn KHÔNG đổi status (vẫn failed)
    assert store.get_task(job_id)["status"] == "failed"
    # Recovery checkpoint còn nguyên
    rec_task = store.get_task(recovery_job_id)
    rec_resolved = ck_service.resolve_checkpoint_key(rec_task["recovery_checkpoint_key"])
    assert rec_resolved is not None
    # Persistent strict: bắt buộc `cancelled`, không chấp nhận failed/interrupted
    assert store.get_task(recovery_job_id)["status"] == "cancelled"


@pytest.mark.parametrize("fail_status,http_status,retryable", [
    ("all_keys_exhausted", None, True),   # retryable: hết key, thử lại được
    ("auth_error", 401, False),           # 401: key sai, KHÔNG retryable
    ("censorship_blocked", 451, False),   # 451: nội dung bị chặn, KHÔNG retryable
])
def test_recovery_provider_failure_marks_failed(tmp_path, monkeypatch, fail_status, http_status, retryable):
    """Recovery gặp lỗi provider → task recovery `failed` + metadata lỗi persist đúng.

    Phase 6: recovery phải stable khi provider lỗi, không treo task, không đổi source task,
    item checkpoint recovery vẫn còn để chạy lại, trạng thái error_class/http_status/retryable
    được persist vào tasks.db.
    """
    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    _create_project_file(proj)

    sent = []
    ck_service, store, recovery_control = _install_fakes(monkeypatch, ws, proj, sent)
    client = _make_flask_client(monkeypatch, ws, proj)

    job_id = _run_translate(client, store)
    task = store.get_task(job_id)
    assert task["status"] == "failed"
    source_ck_key = task["checkpoint_key"]

    # Recovery với provider khác (mixed_provider) — fake fail tại chunk 17 với status đã chọn
    recovery_control["fail_status"] = fail_status
    recovery_control["state"]["failed"] = False  # để recovery cũng fail tại chunk 17
    resp = client.post(f"/api/tasks/{job_id}/recover-from-checkpoint",
                       json={"provider_id": "openai-test", "model": "gpt-other"})
    assert resp.status_code == 200
    recovery_job_id = resp.get_json()["job_id"]

    # Recovery phải kết thúc ở failed (không treo running), vì chunk đầu tiên fail
    assert _wait_status(store, recovery_job_id, "failed", timeout=5.0), (
        f"Recovery task không đạt 'failed' sau provider error, got {store.get_task(recovery_job_id)['status']}"
    )
    rec_task = store.get_task(recovery_job_id)
    assert rec_task["error_class"] == fail_status
    assert rec_task["http_status"] == http_status
    assert rec_task["retryable"] == retryable
    # chunk_index (0-based) vị trí fail được ghi đúng
    assert rec_task["current_chunk"] == CENSOR_AT
    # Source task KHÔNG bị đổi bởi recovery fail
    assert store.get_task(job_id)["status"] == "failed"
    assert store.get_task(job_id)["checkpoint_key"] == source_ck_key
    # Recovery checkpoint vẫn còn để chạy lại (không bị cleanup) và vẫn có pending chunk 17
    rec_resolved = ck_service.resolve_checkpoint_key(rec_task["recovery_checkpoint_key"])
    assert rec_resolved is not None
    rec_indices = ck_service.get_done_pending_indices(rec_resolved["filename"])
    assert rec_indices is not None
    assert CENSOR_AT in rec_indices["pending_indices"], "Chunk fail vẫn pending (resume được)"


def test_double_recovery_rejected_while_running(tmp_path, monkeypatch):
    """Phase 6 idempotency: recovery thứ hai trên cùng source task bị từ chối 409 khi
    recovery đầu đang chạy. `find_active_recovery_for_source` chống tạo worker kép."""
    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    _create_project_file(proj)

    sent = []
    ck_service, store, recovery_control = _install_fakes(monkeypatch, ws, proj, sent)
    client = _make_flask_client(monkeypatch, ws, proj)

    job_id = _run_translate(client, store)
    task = store.get_task(job_id)
    assert task["status"] == "failed"

    # Bật block để giữ recovery đầu ở trạng thái running (chưa hoàn tất)
    recovery_control["block_chunks"] = True
    recovery_control["is_recovery"] = True

    resp = client.post(f"/api/tasks/{job_id}/recover-from-checkpoint",
                       json={"provider_id": "openai-test", "model": "gpt-other"})
    assert resp.status_code == 200
    recovery_job_id = resp.get_json()["job_id"]

    # Chờ recovery block (đang chạy, chưa hoàn tất)
    assert recovery_control["blocked_event"].wait(5.0), "Recovery đầu không block"

    # Tấn công double recovery: phải bị từ chối (task recovery đang active trên source)
    resp2 = client.post(f"/api/tasks/{job_id}/recover-from-checkpoint",
                        json={"provider_id": "openai-test", "model": "gpt-other"})
    assert resp2.status_code == 409, f"Double recovery phải 409, got {resp2.status_code}"
    data2 = resp2.get_json()
    assert "recovery_task_id" in data2
    assert data2["recovery_task_id"] == recovery_job_id

    # Dọn dẹp: release block để worker hoàn tất, tránh thread leak
    recovery_control["allow_next"].set()
    recovery_control["block_chunks"] = False
    recovery_control["is_recovery"] = False
    assert _wait_status(store, recovery_job_id, "completed", timeout=5.0) or \
        _wait_status(store, recovery_job_id, "failed", timeout=5.0) or \
        _wait_status(store, recovery_job_id, "cancelled", timeout=5.0), "Recovery đầu không kết thúc"


def test_concurrent_double_recovery_race(tmp_path, monkeypatch):
    """Phase 6 atomic idempotency: hai request recovery đồng thời trên cùng source task.

    Chỉ MỘT request được tạo recovery task; request kia phải 409. Không có worker kép.
    Dùng thread thật + barrier để đẩy cả hai vào critical section cùng lúc.
    """
    import threading

    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    _create_project_file(proj)

    sent = []
    ck_service, store, recovery_control = _install_fakes(monkeypatch, ws, proj, sent)
    client = _make_flask_client(monkeypatch, ws, proj)

    job_id = _run_translate(client, store)
    task = store.get_task(job_id)
    assert task["status"] == "failed"

    # Bật block để recovery worker giữ task ở trạng thái running → active recovery visible
    recovery_control["block_chunks"] = True
    recovery_control["is_recovery"] = True

    start_barrier = threading.Barrier(2)  # cả 2 request cùng bắt đầu
    results = {}

    def _fire(tag):
        start_barrier.wait()
        try:
            r = client.post(f"/api/tasks/{job_id}/recover-from-checkpoint",
                            json={"provider_id": "openai-test", "model": "gpt-other"})
            results[tag] = r.status_code
        except Exception as e:  # barrier/có thể deadlock nếu lock chết
            results[tag] = f"EXC:{e}"

    t1 = threading.Thread(target=_fire, args=("a",))
    t2 = threading.Thread(target=_fire, args=("b",))
    t1.start(); t2.start(); t1.join(timeout=10); t2.join(timeout=10)

    codes = [results.get("a"), results.get("b")]
    # Phải có đúng 1 request 200, request còn lại 409
    assert codes.count(200) == 1, f"Phải đúng 1 recovery tạo thành công, got codes={codes}"
    assert codes.count(409) == 1, f"Request còn lại phải 409, got codes={codes}"

    # Chỉ 1 recovery task được tạo cho source này
    recoveries = [
        t for t in store.list_tasks() if t.get("source_task_id") == job_id
    ]
    assert len(recoveries) == 1, f"Phải đúng 1 recovery task, got {len(recoveries)}"
    rec_job_id = recoveries[0]["job_id"]

    # Dọn dẹp: release block để worker hoàn tất, tránh thread leak
    recovery_control["allow_next"].set()
    recovery_control["block_chunks"] = False
    recovery_control["is_recovery"] = False
    assert _wait_status(store, rec_job_id, "completed", timeout=5.0) or \
        _wait_status(store, rec_job_id, "failed", timeout=5.0) or \
        _wait_status(store, rec_job_id, "cancelled", timeout=5.0), "Recovery không kết thúc"
