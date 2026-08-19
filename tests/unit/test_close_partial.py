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
