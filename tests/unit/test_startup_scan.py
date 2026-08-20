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


def test_scan_ignores_empty_and_non_schema_checkpoints(tmp_path):
    """File 0-byte hoặc DB rỗng không có bảng metadata không gây lỗi khi khởi động."""
    store = TaskStore(str(tmp_path))
    ck_dir = tmp_path / "checkpoints"
    ck_dir.mkdir(parents=True, exist_ok=True)

    # 1. 0-byte file
    (ck_dir / "empty.db").touch()

    # 2. SQLite db with no metadata table
    import sqlite3
    conn = sqlite3.connect(str(ck_dir / "dummy.db"))
    conn.execute("CREATE TABLE other_table (id INT)")
    conn.close()

    from webui import scan_and_recover
    assert scan_and_recover(store, ck_dir) == 0
    assert store.list_tasks() == []

