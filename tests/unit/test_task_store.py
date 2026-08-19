import os
import threading
import time
import pytest
from services.task_store import TaskStore


def test_create_and_get_task(tmp_path):
    store = TaskStore(str(tmp_path))
    task_id = store.create_task(
        job_id="job-1",
        kind="translation",
        title="Test",
        project_slug="proj",
        filename="book.txt",
        total_chunks=10,
        identity={"model": "gpt"},
        checkpoint_key="abc123",
    )
    task = store.get_task(task_id)
    assert task["status"] == "running"
    assert task["job_id"] == "job-1"
    assert task["resume_of"] is None
    assert task["identity"] == {"model": "gpt"}
    assert task["checkpoint_key"] == "abc123"


def test_get_task_by_job_id(tmp_path):
    store = TaskStore(str(tmp_path))
    store.create_task(
        job_id="job-1",
        kind="translation",
        title="Test",
        project_slug="proj",
        filename="book.txt",
    )
    task = store.get_task_by_job_id("job-1")
    assert task is not None
    assert task["task_id"] == "job-1"


def test_update_status(tmp_path):
    store = TaskStore(str(tmp_path))
    task_id = store.create_task(
        job_id="job-1",
        kind="translation",
        title="Test",
        project_slug="proj",
        filename="book.txt",
    )
    store.update_status(task_id, "resumable", completed_chunks=5, current_chunk=5)
    task = store.get_task(task_id)
    assert task["status"] == "resumable"
    assert task["completed_chunks"] == 5
    assert task["current_chunk"] == 5


def test_append_event_and_iter(tmp_path):
    store = TaskStore(str(tmp_path))
    task_id = store.create_task(
        job_id="job-1",
        kind="translation",
        title="Test",
        project_slug="proj",
        filename="book.txt",
    )
    store.append_event(task_id, {"type": "info", "message": "hello"})
    store.append_event(task_id, {"type": "progress", "percent": 50})
    events = store.iter_events(task_id)
    assert len(events) == 2
    assert events[0]["message"] == "hello"
    assert events[1]["percent"] == 50


def test_list_tasks_with_status_filter(tmp_path):
    store = TaskStore(str(tmp_path))
    store.create_task("j1", "translation", "T", "p", "f.txt", 10, {})
    store.create_task("j2", "translation", "T2", "p", "f2.txt", 5, {})
    store.update_status("j1", "resumable")
    store.update_status("j2", "completed")

    resumable = store.list_tasks(["resumable"])
    assert len(resumable) == 1
    assert resumable[0]["job_id"] == "j1"

    running = store.list_tasks(["running", "resumable"])
    assert len(running) == 1
    assert running[0]["job_id"] == "j1"


def test_persistence_across_instances(tmp_path):
    store1 = TaskStore(str(tmp_path))
    task_id = store1.create_task(
        job_id="job-1",
        kind="translation",
        title="Test",
        project_slug="proj",
        filename="book.txt",
        total_chunks=10,
    )
    store1.append_event(task_id, {"type": "info", "message": "persisted"})
    store1.update_status(task_id, "resumable", completed_chunks=3)
    store1.close()

    store2 = TaskStore(str(tmp_path))
    task = store2.get_task(task_id)
    assert task is not None
    assert task["status"] == "resumable"
    assert task["completed_chunks"] == 3
    events = store2.iter_events(task_id)
    assert len(events) == 1
    assert events[0]["message"] == "persisted"
    store2.close()


def test_concurrent_appends_no_corruption(tmp_path):
    store = TaskStore(str(tmp_path))
    task_id = store.create_task(
        job_id="job-1",
        kind="translation",
        title="Test",
        project_slug="proj",
        filename="book.txt",
    )

    errors = []

    def append_many(idx):
        try:
            for i in range(20):
                store.append_event(task_id, {"type": "info", "idx": idx, "seq": i})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=append_many, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"Concurrent append errors: {errors}"
    events = store.iter_events(task_id)
    assert len(events) == 100


def test_concurrent_creates_unique_job_ids(tmp_path):
    store = TaskStore(str(tmp_path))
    job_ids = []

    def create_task(idx):
        jid = f"job-{idx}-{threading.get_native_id()}"
        store.create_task(
            job_id=jid,
            kind="translation",
            title=f"Task {idx}",
            project_slug="proj",
            filename=f"file{idx}.txt",
        )
        job_ids.append(jid)

    threads = [threading.Thread(target=create_task, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(set(job_ids)) == 10
    tasks = store.list_tasks()
    assert len(tasks) == 10


def test_find_running_by_checkpoint_key(tmp_path):
    store = TaskStore(str(tmp_path))
    store.create_task(
        job_id="job-1",
        kind="translation",
        title="T1",
        project_slug="p",
        filename="f.txt",
        checkpoint_key="ck1",
    )
    store.update_status("job-1", "resumable")
    store.create_task(
        job_id="job-2",
        kind="translation",
        title="T2",
        project_slug="p",
        filename="f2.txt",
        checkpoint_key="ck2",
    )
    store.update_status("job-2", "completed")

    running = store.find_running_by_checkpoint_key("ck1")
    assert running is not None
    assert running["job_id"] == "job-1"

    none = store.find_running_by_checkpoint_key("ck2")
    assert none is None


def test_migration_adds_recovery_columns(tmp_path):
    store = TaskStore(str(tmp_path))
    conn = store._get_connection()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]

    required = [
        "recovery_of", "source_task_id", "source_checkpoint_key",
        "recovery_checkpoint_key", "partial_output_path", "final_output_path",
        "pending_chunks", "error_class", "http_status", "retryable", "mixed_provider",
        "heartbeat_at",
    ]
    for col in required:
        assert col in cols, f"Missing column: {col}"


def test_migration_adds_heartbeat_and_is_idempotent(tmp_path):
    """P1 Phase 7: migration thêm cột heartbeat_at trên DB cũ; chạy lần hai không lỗi."""
    import sqlite3 as _sqlite3
    db_path = str(tmp_path / "tasks.db")
    # Tạo DB CŨ chỉ có các cột recovery, KHÔNG có heartbeat_at
    conn = _sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY, job_id TEXT UNIQUE NOT NULL, kind TEXT NOT NULL,
        title TEXT NOT NULL, project_slug TEXT NOT NULL, filename TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'running', total_chunks INTEGER DEFAULT 0,
        completed_chunks INTEGER DEFAULT 0, current_chunk INTEGER DEFAULT 0,
        phase TEXT, checkpoint_key TEXT, resume_of TEXT, identity TEXT,
        last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()

    # Khởi tạo TaskStore chạy migration → thêm heartbeat_at
    store = TaskStore(str(tmp_path))
    cols = [r[1] for r in store._get_connection().execute("PRAGMA table_info(tasks)").fetchall()]
    assert "heartbeat_at" in cols, "Migration phải thêm heartbeat_at"

    # Chạy migration lần hai (khởi tạo store mới) không lỗi
    store2 = TaskStore(str(tmp_path))
    cols2 = [r[1] for r in store2._get_connection().execute("PRAGMA table_info(tasks)").fetchall()]
    assert "heartbeat_at" in cols2
    assert cols2.count("heartbeat_at") == 1

    # _row_to_task map đúng và heartbeat_at ban đầu NULL
    job_id = store.create_task(
        job_id="job-1", kind="translation", title="T",
        project_slug="p", filename="f.txt"
    )
    task = store.get_task(job_id)
    assert "heartbeat_at" in task
    assert task["heartbeat_at"] is None


def test_create_recovery_task(tmp_path):
    store = TaskStore(str(tmp_path))
    source_id = store.create_task(
        job_id="job-1",
        kind="translation",
        title="Test",
        project_slug="proj",
        filename="test.txt",
        total_chunks=10,
        checkpoint_key="src_ck",
    )
    source = store.get_task(source_id)

    recovery_id = store.create_recovery_task(
        source_task=source,
        recovery_job_id="job-2",
        recovery_checkpoint_key="rec_ck",
        provider_id="openai",
        model="gpt-4",
        mixed_provider=True,
    )

    recovery = store.get_task(recovery_id)
    assert recovery["recovery_of"] == source_id
    assert recovery["source_task_id"] == source_id
    assert recovery["recovery_checkpoint_key"] == "rec_ck"
    assert recovery["mixed_provider"] == 1
    assert recovery["status"] == "running"


def test_update_recovery_task(tmp_path):
    store = TaskStore(str(tmp_path))
    source_id = store.create_task(
        job_id="job-1", kind="translation", title="T",
        project_slug="p", filename="f.txt"
    )
    source = store.get_task(source_id)
    recovery_id = store.create_recovery_task(
        source_task=source, recovery_job_id="job-2",
        recovery_checkpoint_key="rec_ck", provider_id="openai",
        model="gpt-4", mixed_provider=False,
    )

    store.update_recovery_task(
        recovery_id,
        partial_output_path="/tmp/partial.md",
        pending_chunks=[5, 6, 7],
        completed_chunks=3,
    )

    task = store.get_task(recovery_id)
    assert task["partial_output_path"] == "/tmp/partial.md"
    assert task["pending_chunks"] == [5, 6, 7]
    assert task["completed_chunks"] == 3


def test_find_active_recovery_for_source(tmp_path):
    store = TaskStore(str(tmp_path))
    source_id = store.create_task(
        job_id="job-1", kind="translation", title="T",
        project_slug="p", filename="f.txt"
    )
    source = store.get_task(source_id)
    recovery_id = store.create_recovery_task(
        source_task=source, recovery_job_id="job-2",
        recovery_checkpoint_key="rec_ck", provider_id="openai",
        model="gpt-4", mixed_provider=False,
    )

    active = store.find_active_recovery_for_source(source_id)
    assert active is not None
    assert active["task_id"] == recovery_id

    store.update_status(recovery_id, "completed")
    assert store.find_active_recovery_for_source(source_id) is None


def test_touch_heartbeat_updates(tmp_path):
    """P1 Phase 7: `touch_heartbeat` cập nhật heartbeat_at của task."""
    store = TaskStore(str(tmp_path))
    job_id = store.create_task(
        job_id="job-1", kind="translation", title="T",
        project_slug="p", filename="f.txt"
    )
    # task vừa tạo: heartbeat NULL
    before = store.get_task(job_id)
    assert before["heartbeat_at"] is None

    store.update_status(job_id, "running")
    store.touch_heartbeat(job_id)
    after = store.get_task(job_id)
    assert after["heartbeat_at"] is not None


def test_reconcile_lease_expired_marks_stale_running(tmp_path):
    """P1 Phase 7: task `running` + heartbeat stale/null → interrupted.

    Lease timeout ngắn để task heartbeat-at cổ bị coi là hết hạn.
    """
    from datetime import datetime, timedelta
    store = TaskStore(str(tmp_path))
    # Task running, heartbeat NULL → coi là stale (không có worker thật)
    stale_job = store.create_task(
        job_id="job-stale", kind="translation", title="T",
        project_slug="p", filename="f.txt"
    )
    store.update_status(stale_job, "running")

    # Task running, heartbeat gần đây → giữ nguyên (worker còn sống)
    alive_job = store.create_task(
        job_id="job-alive", kind="translation", title="T",
        project_slug="p", filename="f.txt"
    )
    store.update_status(alive_job, "running")
    store.touch_heartbeat(alive_job)

    # Task running, heartbeat cổ 5 phút → bị chuyển interrupted
    old_job = store.create_task(
        job_id="job-old", kind="translation", title="T",
        project_slug="p", filename="f.txt"
    )
    store.update_status(old_job, "running")
    # ghi đè heartbeat_at thành 5 phút trước
    old_hb = (datetime.now() - timedelta(minutes=5)).isoformat()
    with store._cursor() as cur:
        cur.execute("UPDATE tasks SET heartbeat_at = ? WHERE task_id = ?", (old_hb, old_job))

    moved = store.reconcile_lease_expired(lease_timeout_seconds=120.0)
    assert moved == 2  # job-stale + job-old, KHÔNG phải job-alive
    assert store.get_task(stale_job)["status"] == "interrupted"
    assert store.get_task(old_job)["status"] == "interrupted"
    assert store.get_task(alive_job)["status"] == "running"
