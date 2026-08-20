"""Unit tests cho Phase 7A: Safe Lease Lifecycle & Atomic Acquisition.

Kiểm tra:
- Atomic acquire_lease conditional update (2 worker tranh chấp task -> đúng 1 worker thành công).
- Atomic touch_lease CAS check với lease_epoch và lease_token.
- Reconcile lease expired thu hồi lease của task có heartbeat cũ.
- LeaseKeepAlive background daemon thread tự động gia hạn heartbeat và phát hiện mất lease.
- LeaseKeepAlive dừng sạch sẽ khi exit context manager.
"""
import time
from services.task_store import TaskStore
from backend.infrastructure.progress.lease_manager import LeaseKeepAlive


def test_atomic_acquire_lease_and_concurrency(tmp_path):
    store = TaskStore(str(tmp_path))
    task_id = "test-lease-task-1"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Test Task",
        project_slug="p",
        filename="book.txt",
        total_chunks=10,
    )
    store.update_status(task_id, "queued")

    # 1. Worker 1 claim lease
    lease1 = store.acquire_lease(task_id, lease_timeout_seconds=5.0)
    assert lease1 is not None
    token1, epoch1 = lease1
    assert epoch1 == 1

    task = store.get_task(task_id)
    assert task["status"] == "running"
    assert task["lease_token"] == token1
    assert task["lease_epoch"] == 1
    assert task["heartbeat_at"] is not None

    # 2. Worker 2 cố claim task khi lease1 còn hạn -> Phải thất bại
    lease2 = store.acquire_lease(task_id, lease_timeout_seconds=5.0)
    assert lease2 is None  # Bị chặn vì lease1 đang active

    # 3. Giả lập lease1 hết hạn sau timeout
    time.sleep(0.15)
    lease3 = store.acquire_lease(task_id, lease_timeout_seconds=0.1)
    assert lease3 is not None
    token3, epoch3 = lease3
    assert epoch3 == 2
    assert token3 != token1

    # Task bây giờ thuộc về Worker 3 với epoch 2
    task_after = store.get_task(task_id)
    assert task_after["lease_token"] == token3
    assert task_after["lease_epoch"] == 2


def test_acquire_lease_status_restrictions(tmp_path):
    """Kiểm tra điều kiện trạng thái của acquire_lease:
    - KHÔNG ĐƯỢC PHÉP acquire task ở trạng thái terminal: completed, failed, cancelled, closed_partial.
    - ĐƯỢC PHÉP acquire task ở trạng thái: queued, interrupted, resumable.
    - ĐƯỢC PHÉP acquire task ở trạng thái running CHỈ KHI heartbeat đã hết hạn.
    """
    store = TaskStore(str(tmp_path))

    # 1. Terminal states -> BỊ TỪ CHỐI
    for term_status in ["completed", "failed", "cancelled", "closed_partial"]:
        tid = f"task-{term_status}"
        store.create_task(job_id=tid, kind="translation", title="T", project_slug="p", filename="f.txt")
        store.update_status(tid, term_status)
        lease = store.acquire_lease(tid, lease_timeout_seconds=0.0)
        assert lease is None, f"Status '{term_status}' tuyệt đối không được phép acquire lease!"

    # 2. Resumable / Interrupted / Queued -> ĐƯỢC PHÉP
    for valid_status in ["queued", "interrupted", "resumable"]:
        tid = f"task-{valid_status}"
        store.create_task(job_id=tid, kind="translation", title="T", project_slug="p", filename="f.txt")
        store.update_status(tid, valid_status)
        lease = store.acquire_lease(tid, lease_timeout_seconds=10.0)
        assert lease is not None, f"Status '{valid_status}' phải acquire lease thành công!"
        assert store.get_task(tid)["status"] == "running"

    # 3. Running còn hạn -> BỊ TỪ CHỐI, Running hết hạn -> ĐƯỢC PHÉP
    tid_running = "task-running"
    store.create_task(job_id=tid_running, kind="translation", title="T", project_slug="p", filename="f.txt")
    lease1 = store.acquire_lease(tid_running, lease_timeout_seconds=10.0)
    assert lease1 is not None

    # Còn hạn -> Không acquire được
    assert store.acquire_lease(tid_running, lease_timeout_seconds=10.0) is None

    # Hết hạn -> Acquire được
    time.sleep(0.05)
    lease2 = store.acquire_lease(tid_running, lease_timeout_seconds=0.01)
    assert lease2 is not None
    assert lease2[1] == lease1[1] + 1


def test_atomic_touch_lease_cas_guards(tmp_path):
    store = TaskStore(str(tmp_path))
    task_id = "test-touch-task"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Test Task",
        project_slug="p",
        filename="book.txt",
        total_chunks=10,
    )
    lease = store.acquire_lease(task_id, lease_timeout_seconds=10.0)
    token, epoch = lease

    # 1. Touch đúng epoch & token -> Thành công
    assert store.touch_lease(task_id, lease_epoch=epoch, lease_token=token) is True

    # 2. Touch sai epoch (epoch cũ) -> Thất bại
    assert store.touch_lease(task_id, lease_epoch=epoch - 1, lease_token=token) is False

    # 3. Touch sai token -> Thất bại
    assert store.touch_lease(task_id, lease_epoch=epoch, lease_token="wrong-token") is False

    # 4. Khi task không còn 'running' (ví dụ đã bị chuyển sang interrupted) -> Touch thất bại
    store.update_status(task_id, "interrupted")
    assert store.touch_lease(task_id, lease_epoch=epoch, lease_token=token) is False


def test_reconcile_lease_expired_revokes_token(tmp_path):
    store = TaskStore(str(tmp_path))
    task_id = "test-reconcile-task"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Test Task",
        project_slug="p",
        filename="book.txt",
        total_chunks=10,
    )
    token, epoch = store.acquire_lease(task_id, lease_timeout_seconds=10.0)

    time.sleep(0.15)
    # Reconcile với timeout 0.1s -> Task bị chuyển sang interrupted và xóa lease_token
    revoked_count = store.reconcile_lease_expired(lease_timeout_seconds=0.1)
    assert revoked_count == 1

    task = store.get_task(task_id)
    assert task["status"] == "interrupted"
    assert task["lease_token"] is None


def test_lease_keep_alive_daemon_lifecycle(tmp_path):
    store = TaskStore(str(tmp_path))
    task_id = "test-keepalive-task"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Test Task",
        project_slug="p",
        filename="book.txt",
        total_chunks=10,
    )
    token, epoch = store.acquire_lease(task_id, lease_timeout_seconds=10.0)

    abort_called = [False]

    def _on_abort():
        abort_called[0] = True

    # 1. Chạy LeaseKeepAlive và kiểm tra heartbeat được cập nhật
    with LeaseKeepAlive(
        task_id=task_id,
        lease_token=token,
        lease_epoch=epoch,
        task_store=store,
        interval_seconds=0.05,
        on_abort=_on_abort,
    ) as keep_alive:
        assert keep_alive.is_alive()
        hb1 = store.get_task(task_id)["heartbeat_at"]
        time.sleep(0.12)
        hb2 = store.get_task(task_id)["heartbeat_at"]
        assert hb2 > hb1
        assert not keep_alive.abort_requested

    # 2. Sau khi ra khỏi context manager, thread phải dừng và join() thành công
    assert not keep_alive.is_alive()

    # 3. Khi lease bị thu hồi trong lúc chạy -> LeaseKeepAlive phát hiện và kích hoạt abort
    with LeaseKeepAlive(
        task_id=task_id,
        lease_token=token,
        lease_epoch=epoch,
        task_store=store,
        interval_seconds=0.05,
        on_abort=_on_abort,
    ) as keep_alive:
        # Giả lập Reconciler thu hồi lease / worker khác claim
        store.acquire_lease(task_id, lease_timeout_seconds=0.0)
        time.sleep(0.12)
        assert keep_alive.abort_requested is True
        assert abort_called[0] is True
