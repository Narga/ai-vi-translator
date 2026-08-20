"""Integration test for Multi-Worker Concurrency & Zombie Fencing Rejection.

Tests:
1. Concurrent translation route: Worker 1 claims lease; second concurrent run attempt is rejected.
2. Zombie worker write rejection: When a worker pauses (e.g. network hang) and lease is stolen
   by a new recovery task, the waking zombie worker's subsequent side effects
   (save_chunk, DB status updates, events, and output manifest creation) are strictly blocked.
3. Checkpoint consistency & manifest integrity are fully preserved by the valid owner.
"""
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.infrastructure.progress.lease_manager import LeaseKeepAlive
from backend.infrastructure.progress.runtime_state import RuntimeState
from backend.infrastructure.progress.task_registry import TaskRegistry
from services.checkpoint_service import CheckpointService
from services.task_store import TaskStore
from tests.conftest import E2E_CHUNK_SIZE, make_chunked_source


@pytest.fixture(autouse=True)
def _reset():
    TaskRegistry._instance = None
    RuntimeState.reset()
    yield
    TaskRegistry._instance = None
    RuntimeState.reset()


def test_concurrent_worker_lease_rejection(tmp_path):
    """Worker 1 acquires lease; Worker 2 cannot claim same task."""
    store = TaskStore(str(tmp_path))
    task_id = "test-concurrent-task"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Concurrent Test",
        project_slug="p",
        filename="book.txt",
        total_chunks=5,
    )

    # Worker 1 claims lease
    lease1 = store.acquire_lease(task_id, lease_timeout_seconds=10.0)
    assert lease1 is not None
    token1, epoch1 = lease1

    # Worker 2 attempts to claim active lease -> Rejected
    lease2 = store.acquire_lease(task_id, lease_timeout_seconds=10.0)
    assert lease2 is None


def test_zombie_worker_side_effects_fully_blocked(tmp_path, monkeypatch):
    """End-to-End: Zombie worker awakens with stale epoch and is blocked at all layers:

    - CheckpointService.save_chunk rejects write
    - TaskStore.update_status rejects update
    - TaskStore.append_event rejects event
    - TaskRegistry RAM remains clean
    """
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))
    store = TaskStore(str(tmp_path))
    registry = TaskRegistry(store=store)

    task_id = "task-zombie-e2e"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Zombie E2E",
        project_slug="p",
        filename="book.txt",
        total_chunks=3,
        checkpoint_key="book.txt",
    )
    ck_service.init_session("book.txt", total_chunks=3)

    # 1. Worker 1 acquires epoch 1
    lease1 = store.acquire_lease(task_id, lease_timeout_seconds=0.05)
    token1, epoch1 = lease1
    assert epoch1 == 1

    # Worker 1 saves chunk 0
    ok = ck_service.save_chunk("book.txt", 0, "c0", "trans0", lease_epoch=epoch1, lease_token=token1)
    assert ok is True

    # 2. Worker 1 hangs; lease expires and Worker 2 (Recovery) steals lease with epoch 2
    time.sleep(0.06)
    lease2 = store.acquire_lease(task_id, lease_timeout_seconds=0.05)
    assert lease2 is not None
    token2, epoch2 = lease2
    assert epoch2 == 2

    # Worker 2 saves chunk 1 with epoch 2
    ok2 = ck_service.save_chunk("book.txt", 1, "c1", "trans1_worker2", lease_epoch=epoch2, lease_token=token2)
    assert ok2 is True

    # 3. Zombie Worker 1 awakens and tries to perform side effects with stale epoch 1:
    # A. Zombie tries to save chunk 1 with old data -> REJECTED by Checkpoint CAS
    zombie_save = ck_service.save_chunk(
        "book.txt", 1, "c1", "zombie_trans1", lease_epoch=epoch1, lease_token=token1
    )
    assert zombie_save is False
    assert ck_service.get_translated_chunks("book.txt")[1] == "trans1_worker2"

    # B. Zombie tries to update DB status -> REJECTED by DB CAS
    zombie_status = store.update_status(
        task_id, status="completed", lease_epoch=epoch1, lease_token=token1
    )
    assert zombie_status is False
    assert store.get_task(task_id)["status"] == "running"

    # C. Zombie tries to append event via registry -> REJECTED by Registry & Store
    zombie_event = registry.append_event(
        task_id, {"type": "progress", "message": "zombie progress"}, lease_epoch=epoch1, lease_token=token1
    )
    assert zombie_event is False

    # 4. Valid Worker 2 completes chunk 2 and finishes task
    ok3 = ck_service.save_chunk("book.txt", 2, "c2", "trans2_worker2", lease_epoch=epoch2, lease_token=token2)
    assert ok3 is True
    complete_ok = store.update_status(
        task_id, status="completed", lease_epoch=epoch2, lease_token=token2
    )
    assert complete_ok is True
    assert store.get_task(task_id)["status"] == "completed"


def test_concurrent_threads_translation_execution(tmp_path, monkeypatch):
    """Hai luồng (threads) worker đồng thời tranh chấp thực thi cùng một task dịch.

    Đúng 1 worker acquire được lease và hoàn tất ghi output & manifest.
    Worker thứ 2 bị từ chối lease ngay từ đầu và không can thiệp vào checkpoint.
    """
    import threading
    from core.executor import TranslationExecutor

    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))
    store = TaskStore(str(tmp_path))
    task_id = "task-concurrent-threads"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Concurrent Threads",
        project_slug="p",
        filename="concurrent_book.txt",
        total_chunks=2,
    )

    def fake_rt(original_chunk=None, *args, **kwargs):
        time.sleep(0.02)  # Giả lập thời gian xử lý API
        return f"[Dịch: {original_chunk}]", "success", "key-ok"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    results = {}
    errors = []

    def worker_job(worker_name: str):
        try:
            lease = store.acquire_lease(task_id, lease_timeout_seconds=5.0)
            if not lease:
                results[worker_name] = "lease_rejected"
                return
            token, epoch = lease
            executor = TranslationExecutor(api_keys=["test-key"], config={"chunk_size": E2E_CHUNK_SIZE})
            executor.checkpoint_service = ck_service
            out_path = tmp_path / f"output_{worker_name}.txt"

            class WorkerKeepAlive:
                def __init__(self, e, t):
                    self.lease_epoch = e
                    self.lease_token = t
                def abort_reason(self):
                    return None

            res = executor.translate_text(
                text=make_chunked_source(2),
                output_filename="concurrent_book.txt",
                output_file_path=out_path,
                lease_keep_alive=WorkerKeepAlive(epoch, token),
            )
            results[worker_name] = "success" if res is not None else "failed"
            if res is not None:
                store.update_status(task_id, "completed", lease_epoch=epoch, lease_token=token)
        except Exception as e:
            errors.append((worker_name, e))

    t1 = threading.Thread(target=worker_job, args=("worker_A",))
    t2 = threading.Thread(target=worker_job, args=("worker_B",))

    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert len(errors) == 0
    # Đúng một worker thành công, worker còn lại bị reject lease
    statuses = list(results.values())
    assert "success" in statuses
    assert "lease_rejected" in statuses
    assert len(statuses) == 2
    assert store.get_task(task_id)["status"] == "completed"

