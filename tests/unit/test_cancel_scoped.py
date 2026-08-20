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


def test_cancel_before_translate_text_is_preserved(tmp_path, monkeypatch):
    """Kiểm tra: Cancel request được gửi ngay trước khi executor.translate_text()

    bắt đầu chạy thì KHÔNG bị xóa mù bởi reset_cancel.
    """
    from core.executor import TranslationExecutor
    from services.checkpoint_service import CheckpointService

    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    # Đặt cancel request trước khi chạy translate_text
    job_id = "test-early-cancel"
    RuntimeState().request_cancel(job_id)

    api_called = [False]

    def fake_rt(*args, **kwargs):
        api_called[0] = True
        return "translation", "success", "k"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    executor = TranslationExecutor(api_keys=["test-key"], config={"chunk_size": 2400})
    executor.checkpoint_service = ck_service

    events = []
    res = executor.translate_text(
        text="chunk 0\n\nchunk 1",
        output_filename="test_cancel_preserved.txt",
        job_id=job_id,
        progress_callback=lambda e: events.append(e),
    )

    # 1. translate_text trả về None
    assert res is None

    # 2. Không gọi API vì đã nhận diện cancel ngay từ Guard 1
    assert api_called[0] is False

    # 3. Emit event cancelled
    assert any(e.get("type") == "cancelled" for e in events)
