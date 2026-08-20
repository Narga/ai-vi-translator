"""Unit tests cho Phase 9: Hardening, Canonical Poison Job Quarantine & Row Mapping.

Kiểm tra:
- Named Row Mapping: _row_to_task hỗ trợ sqlite3.Row, dict, tuple và deserialization an toàn.
- Canonical Poison Job Quarantine: status='failed', error_class='poison_job', không tạo status phi chuẩn.
- Giới hạn 3 lần recovery (max recovery attempts threshold): từ chối tạo recovery thứ 4 và quarantine source task.
"""
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.task_store import TaskStore


def test_named_row_mapping_robustness(tmp_path):
    store = TaskStore(str(tmp_path))
    task_id = "row-map-task"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Test Title",
        project_slug="p",
        filename="novel.txt",
        total_chunks=10,
        identity={"model": "gpt-4o", "chunk_size": 2000},
    )

    # 1. get_task trả về dict hoàn chỉnh qua named mapping
    task = store.get_task(task_id)
    assert task["task_id"] == task_id
    assert task["filename"] == "novel.txt"
    assert task["identity"]["model"] == "gpt-4o"
    assert isinstance(task["pending_chunks"], list)

    # 2. Test trực tiếp _row_to_task với sqlite3.Row
    conn = sqlite3.connect(store.db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    mapped = store._row_to_task(row)
    assert mapped["task_id"] == task_id
    assert mapped["status"] == "running"
    conn.close()

    # 3. Test với dictionary hoặc object khuyết thiếu
    partial_dict = {"task_id": "custom-id", "filename": "custom.txt"}
    mapped_dict = store._row_to_task(partial_dict)
    assert mapped_dict["task_id"] == "custom-id"
    assert mapped_dict["status"] is None
    assert mapped_dict["identity"] == {}

    # 4. Test với row rỗng
    assert store._row_to_task(None) == {}


def test_canonical_poison_job_quarantine(tmp_path):
    """Quy tắc bắt buộc: status='failed', error_class='poison_job', lease_token=NULL."""
    store = TaskStore(str(tmp_path))
    task_id = "poison-task-1"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Poison Task",
        project_slug="p",
        filename="novel.txt",
        total_chunks=10,
    )
    store.acquire_lease(task_id)
    assert store.get_task(task_id)["lease_token"] is not None

    ok = store.quarantine_task(task_id, reason="Repeated crash at chunk 4")
    assert ok is True

    task = store.get_task(task_id)
    # Tuân thủ Canonical status: 'failed', KHÔNG ĐƯỢC 'quarantined'
    assert task["status"] == "failed"
    assert task["error_class"] == "poison_job"
    assert "Repeated crash at chunk 4" in task["last_error"]
    assert task["lease_token"] is None


def test_max_recovery_attempts_quarantine_enforcement(tmp_path, monkeypatch):
    """Khi một task nguồn đã có 3 recovery task con, lần recovery thứ 4 bị từ chối và quarantine."""
    from backend.infrastructure.progress.task_registry import TaskRegistry
    from services.checkpoint_service import CheckpointService
    from flask import Flask
    from webui.routes.projects import projects_bp

    app = Flask(__name__)
    app.register_blueprint(projects_bp)

    ws = tmp_path / "ws"
    proj_dir = ws / "projects" / "test-proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "sources").mkdir(parents=True, exist_ok=True)
    (proj_dir / "sources" / "chapter.txt").write_text("Source content", encoding="utf-8")

    ck_dir = ws / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))
    store = TaskStore(str(ws))
    registry = TaskRegistry(store=store)

    monkeypatch.setattr("webui.routes.projects._get_checkpoint_dir", lambda: str(ck_dir))
    monkeypatch.setattr("webui.routes.projects._get_workspace_dir", lambda: str(ws))
    monkeypatch.setattr("webui.routes.projects._get_project_dir", lambda slug: proj_dir)
    monkeypatch.setattr("webui.routes.projects._load_project_meta", lambda slug: {"book_title": "T", "slug": slug})

    TaskRegistry._instance = None
    TaskRegistry(store=store)

    # 1. Tạo source task đã failed
    root_task_id = "root-task-fail"
    ck_service.init_session("chapter.txt", total_chunks=5, chunks_text=["1", "2", "3", "4", "5"])
    ck_service.save_chunk("chapter.txt", 0, "1", "d1", "key")
    store.create_task(
        job_id=root_task_id,
        kind="translation",
        title="Root Failed Task",
        project_slug="test-proj",
        filename="chapter.txt",
        total_chunks=5,
        checkpoint_key="chapter.txt",
    )
    store.update_status(root_task_id, "failed")

    # 2. Tạo 3 lần recovery đã thử trước đó và đều failed
    source_task_dict = store.get_task(root_task_id)
    for i in range(1, 4):
        rec_id = f"rec-attempt-{i}"
        ck_name = f"rec_ck_{i}.txt"
        ck_service.clone_checkpoint("chapter.txt", ck_name)
        store.create_recovery_task(
            source_task=source_task_dict,
            recovery_job_id=rec_id,
            recovery_checkpoint_key=ck_name,
            provider_id="test-provider",
            model="test-model",
            mixed_provider=False,
        )
        store.update_status(rec_id, "failed")

    # Xác nhận đếm đủ 3 attempts
    assert store.get_recovery_attempt_count(root_task_id) == 3

    # 3. Yêu cầu recovery lần thứ 4 -> Phải trả về HTTP 400 + error_class="poison_job"
    client = app.test_client()
    resp = client.post(f"/api/tasks/{root_task_id}/recover-from-checkpoint", json={})
    assert resp.status_code == 400
    resp_data = resp.get_json()
    assert resp_data["error_class"] == "poison_job"
    assert resp_data["quarantine_reason"] == "max_recovery_attempts"

    # 4. Kiểm tra root task đã được quarantine với canonical status
    root_task = store.get_task(root_task_id)
    assert root_task["status"] == "failed"
    assert root_task["error_class"] == "poison_job"
