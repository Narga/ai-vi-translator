# tests/unit/test_task_discard.py
import json
from pathlib import Path
import pytest
from services.checkpoint_service import CheckpointService
from services.task_store import TaskStore


def _seed_checkpoint(ck, filename="chapter1.md", total=5, done=(0, 1, 2)):
    ck.init_session(filename, total, ["a", "b", "c", "d", "e"])
    for i in done:
        ck.save_chunk(filename, i, f"source_{i}", f"translated_{i}", status="done")
    return ck.get_resume_info(filename)


def test_discard_non_existent_task(sync_app):
    client, store, ws, proj = sync_app
    resp = client.post("/api/tasks/non-existent-job-id/discard")
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_discard_running_task_rejected(sync_app):
    client, store, ws, proj = sync_app
    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)

    job_id = reg.create_task("translation", "Translate Test", 1, project_slug="proj-a", filename="chapter1.md")
    store.update_status(job_id, "running")

    resp = client.post(f"/api/tasks/{job_id}/discard")
    assert resp.status_code == 409
    data = resp.get_json()
    assert "error" in data
    assert "Task đang chạy" in data["error"]

    # Verify status unchanged
    task = store.get_task(job_id)
    assert task["status"] == "running"


def test_discard_resumable_task_soft_archives(sync_app):
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    _seed_checkpoint(ck, filename="chapter1.md")

    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)

    job_id = reg.create_task(
        "translation",
        "Translate Test",
        5,
        project_slug="proj-a",
        filename="chapter1.md",
        checkpoint_key="chapter1.md"
    )
    # Giả lập task có lease_token còn lại trước khi chuyển sang resumable
    with store._cursor() as cur:
        cur.execute("UPDATE tasks SET status = 'resumable', lease_token = 'leftover-token' WHERE task_id = ?", (job_id,))

    # Verify pre-condition: status is resumable and lease_token exists
    task_before = store.get_task(job_id)
    assert task_before["status"] == "resumable"
    assert task_before["lease_token"] == "leftover-token"

    expected_db_path = Path(ck.resolve_checkpoint_key("chapter1.md")["path"])
    assert expected_db_path.exists()

    resp = client.post(f"/api/tasks/{job_id}/discard")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["status"] == "archived"

    # Verify task updated to archived and lease_token cleared
    task_after = store.get_task(job_id)
    assert task_after["status"] == "archived"
    assert task_after["lease_token"] is None
    assert "Discarded" in task_after["last_error"]

    # Verify checkpoint db file was renamed with .archived suffix
    archived_db = expected_db_path.with_suffix(expected_db_path.suffix + ".archived")
    assert not expected_db_path.exists()
    assert archived_db.exists()


def test_discard_with_hard_delete_checkpoint(sync_app):
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    _seed_checkpoint(ck, filename="chapter2.md")

    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)

    job_id = reg.create_task(
        "translation",
        "Translate Test",
        5,
        project_slug="proj-b",
        filename="chapter2.md",
        checkpoint_key="chapter2.md"
    )
    store.update_status(job_id, "failed")

    expected_db_path = Path(ck.resolve_checkpoint_key("chapter2.md")["path"])
    assert expected_db_path.exists()

    resp = client.post(f"/api/tasks/{job_id}/discard", json={"delete_checkpoint": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["deleted_checkpoint"] is True

    # Verify both active and archived files are deleted
    archived_db = expected_db_path.with_suffix(expected_db_path.suffix + ".archived")
    assert not expected_db_path.exists()
    assert not archived_db.exists()


def test_discard_reduces_resumable_count_in_list_tasks(sync_app):
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    _seed_checkpoint(ck, filename="chapter3.md")

    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)

    job_id = reg.create_task(
        "translation",
        "Translate Test",
        5,
        project_slug="proj-c",
        filename="chapter3.md",
        checkpoint_key="chapter3.md"
    )
    store.update_status(job_id, "resumable", completed_chunks=3, total_chunks=5)

    # Check list before discard
    list_resp = client.get("/api/tasks")
    assert list_resp.status_code == 200
    list_data = list_resp.get_json()
    assert list_data["resumable_count"] >= 1

    # Discard task
    discard_resp = client.post(f"/api/tasks/{job_id}/discard")
    assert discard_resp.status_code == 200

    # Check list after discard
    list_resp2 = client.get("/api/tasks")
    assert list_resp2.status_code == 200
    list_data2 = list_resp2.get_json()
    # Task should not appear in active tasks list
    task_ids = [t["job_id"] for t in list_data2["tasks"]]
    assert job_id not in task_ids
    assert list_data2["resumable_count"] == 0


def test_bulk_discard_tasks_by_ids(sync_app):
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    _seed_checkpoint(ck, filename="bulk1.md")
    _seed_checkpoint(ck, filename="bulk2.md")

    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)

    j1 = reg.create_task("translation", "Task 1", 5, project_slug="p1", filename="bulk1.md", checkpoint_key="bulk1.md")
    j2 = reg.create_task("translation", "Task 2", 5, project_slug="p2", filename="bulk2.md", checkpoint_key="bulk2.md")
    store.update_status(j1, "resumable")
    store.update_status(j2, "failed")

    resp = client.post("/api/tasks/bulk-discard", json={"job_ids": [j1, j2]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["count"] == 2

    assert store.get_task(j1)["status"] == "archived"
    assert store.get_task(j2)["status"] == "archived"


def test_bulk_discard_all_resumable(sync_app):
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    _seed_checkpoint(ck, filename="bulk3.md")

    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)

    j1 = reg.create_task("translation", "Task 1", 5, project_slug="p1", filename="bulk3.md", checkpoint_key="bulk3.md")
    j_running = reg.create_task("translation", "Running Task", 5, project_slug="p1", filename="running.md")
    store.update_status(j1, "resumable")
    store.update_status(j_running, "running")
    store.touch_heartbeat(store.get_task(j_running)["task_id"])

    resp = client.post("/api/tasks/bulk-discard", json={"all_resumable": True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["count"] == 1

    # Running task should NOT be discarded
    assert store.get_task(j1)["status"] == "archived"
    assert store.get_task(j_running)["status"] == "running"


def test_bulk_discard_by_project_slug(sync_app):
    client, store, ws, proj = sync_app
    ck = CheckpointService(str(ws / "checkpoints"))
    _seed_checkpoint(ck, filename="p1_chap1.md")
    _seed_checkpoint(ck, filename="p2_chap1.md")

    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)

    j_p1 = reg.create_task("translation", "P1 Task", 5, project_slug="project-a", filename="p1_chap1.md", checkpoint_key="p1_chap1.md")
    j_p2 = reg.create_task("translation", "P2 Task", 5, project_slug="project-b", filename="p2_chap1.md", checkpoint_key="p2_chap1.md")
    store.update_status(j_p1, "resumable")
    store.update_status(j_p2, "resumable")

    # Discard only project-a tasks
    resp = client.post("/api/tasks/bulk-discard", json={"project_slug": "project-a"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["count"] == 1

    # Verify project-a is archived, project-b is still resumable
    assert store.get_task(j_p1)["status"] == "archived"
    assert store.get_task(j_p2)["status"] == "resumable"


def test_cleanup_stale_tasks(sync_app):
    client, store, ws, proj = sync_app
    from backend.infrastructure.progress.task_registry import TaskRegistry
    reg = TaskRegistry(store=store)

    # Create task with a checkpoint_key that does NOT exist physically
    j_orphan = reg.create_task("translation", "Orphan Task", 5, project_slug="project-x", filename="missing.md", checkpoint_key="non_existent_key_123")
    store.update_status(j_orphan, "resumable")

    resp = client.post("/api/tasks/cleanup-stale")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["cleaned_count"] >= 1

    # Task should now be archived
    assert store.get_task(j_orphan)["status"] == "archived"


