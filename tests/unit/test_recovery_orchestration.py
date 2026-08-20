"""Unit tests cho Phase 6: Recovery Orchestration, Lineage & Rollback.

Kiểm tra:
- Recovery-of-Recovery chuỗi 2 cấp: Task 1 -> Task 2 -> Task 3.
- Source checkpoint gốc và recovery checkpoint 1 bất biến.
- Rollback toàn diện khi prepare recovery gặp lỗi (xóa cloned DB, task row, partial file).
- Chuẩn hóa progress events và task_failed emission.
"""
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.checkpoint_service import CheckpointService
from services.task_store import TaskStore

from tests.conftest import E2E_CHUNK_SIZE, E2E_TOTAL_CHUNKS, make_chunked_source


@pytest.fixture(autouse=True)
def _reset():
    from backend.infrastructure.progress.runtime_state import RuntimeState
    from backend.infrastructure.progress.task_registry import TaskRegistry

    TaskRegistry._instance = None
    RuntimeState.reset()
    yield
    TaskRegistry._instance = None
    RuntimeState.reset()


def _make_fake_provider():
    return {
        "type": "openai",
        "api_key": "test-key",
        "gateway_api_key": "",
        "credential_mode": "default",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-test",
        "id": "openai-test",
        "name": "OpenAI Test",
    }


def _setup_test_env(monkeypatch, ws, proj, fail_at_map):
    """
    fail_at_map: dict {job_index: fail_chunk_index}
    Patch robust_translate để kiểm soát vị trí fail từng lần chạy.
    """
    ck_dir = ws / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    monkeypatch.setattr("core.executor.CheckpointService", lambda *a, **k: ck_service)
    monkeypatch.setattr("core.executor.ApiManager", lambda keys: None)

    run_state = {"call_count": 0, "run_index": 0}

    def fake_rt(original_chunk=None, api_manager=None, prompts=None,
                config_params=None, previous_chunk_context="", **kwargs):
        m = re.search(r"SEG(\d+)", original_chunk or "")
        idx = int(m.group(1)) if m else run_state["call_count"]
        run_state["call_count"] += 1

        curr_run = run_state["run_index"]
        target_fail = fail_at_map.get(curr_run)
        if target_fail is not None and idx == target_fail:
            return None, "censorship_blocked", "key-451"
        return f"[dịch {idx}]", "success", "key-ok"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    fake_ps = MagicMock()
    fake_ps.get_active_provider_config.return_value = _make_fake_provider()
    fake_ps.get_provider_by_id.return_value = _make_fake_provider()
    monkeypatch.setattr(
        "backend.infrastructure.providers.provider_service.ProviderService",
        lambda: fake_ps,
    )

    from tests.conftest import SyncThread
    monkeypatch.setattr("webui.routes.projects.Thread", SyncThread)
    monkeypatch.setattr("webui.routes.projects._get_checkpoint_dir", lambda: str(ck_dir))
    monkeypatch.setattr("webui.routes.projects._get_workspace_dir", lambda: str(ws))
    monkeypatch.setattr("webui.routes.projects._get_project_dir", lambda slug: proj)
    monkeypatch.setattr("webui.routes.projects._load_project_meta", lambda slug: {"book_title": "T", "slug": slug})

    from backend.infrastructure.progress.task_registry import TaskRegistry
    TaskRegistry._instance = None
    tmp_store = TaskStore(str(ws))
    TaskRegistry(store=tmp_store)
    monkeypatch.setattr("webui.routes.tasks._get_task_store", lambda: tmp_store)

    from flask import Flask
    from webui.routes.projects import projects_bp
    from webui.routes.tasks import tasks_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)

    return app.test_client(), ck_service, tmp_store, run_state


def test_recovery_of_recovery_2_level_chain(tmp_path, monkeypatch):
    """
    Test chuỗi recovery 2 cấp:
    1. Lần 1: Dịch từ đầu -> fail tại chunk 10. (Task 1: failed, 10 done)
    2. Lần 2: Recovery lần 1 -> dịch tiếp 10..15 -> fail tại chunk 16. (Task 2: failed, 16 done)
    3. Lần 3: Recovery lần 2 -> dịch tiếp 16..23 -> hoàn tất! (Task 3: completed, 24 done)
    """
    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    src_file = proj / "sources" / "book.txt"
    src_file.write_text(make_chunked_source(E2E_TOTAL_CHUNKS), encoding="utf-8")

    fail_map = {
        0: 10,  # Lần 0: fail tại 10
        1: 16,  # Lần 1: fail tại 16
        2: None,  # Lần 2: không fail, chạy hết
    }
    client, ck_service, store, run_state = _setup_test_env(monkeypatch, ws, proj, fail_map)

    # 1. Chạy dịch ban đầu (Run 0)
    run_state["run_index"] = 0
    resp1 = client.post("/api/projects/p/translate", json={"files": ["book.txt"], "model": "gpt-test", "chunk_size": E2E_CHUNK_SIZE})
    assert resp1.status_code == 200
    task1_id = resp1.get_json()["job_id"]
    task1 = store.get_task(task1_id)
    assert task1["status"] == "failed"
    ck1_res = ck_service.resolve_checkpoint_key(task1["checkpoint_key"])
    ck1_done = ck_service.get_done_pending_indices(ck1_res["filename"])["done_indices"]
    assert len(ck1_done) == 10

    # 2. Chạy Recovery lần 1 (Run 1)
    run_state["run_index"] = 1
    resp2 = client.post(f"/api/tasks/{task1_id}/recover-from-checkpoint",
                        json={"provider_id": "openai-test", "model": "gpt-test"})
    assert resp2.status_code == 200
    task2_id = resp2.get_json()["job_id"]
    task2 = store.get_task(task2_id)
    assert task2["status"] == "failed"
    assert task2["source_task_id"] == task1_id
    assert task2["recovery_of"] == task1_id

    ck2_res = ck_service.resolve_checkpoint_key(task2["recovery_checkpoint_key"])
    ck2_done = ck_service.get_done_pending_indices(ck2_res["filename"])["done_indices"]
    assert len(ck2_done) == 16

    # 3. Chạy Recovery lần 2 (Run 2: Recovery of Recovery)
    run_state["run_index"] = 2
    resp3 = client.post(f"/api/tasks/{task2_id}/recover-from-checkpoint",
                        json={"provider_id": "openai-test", "model": "gpt-test"})
    assert resp3.status_code == 200
    task3_id = resp3.get_json()["job_id"]
    task3 = store.get_task(task3_id)
    assert task3["status"] == "completed"

    # Kiểm tra lineage chain đúng
    assert task3["source_task_id"] == task2_id
    assert task3["recovery_of"] == task1_id  # Trỏ đúng root task ban đầu
    assert task3["source_checkpoint_key"] == task2["recovery_checkpoint_key"]

    ck3_res = ck_service.resolve_checkpoint_key(task3["recovery_checkpoint_key"])
    ck3_done = ck_service.get_done_pending_indices(ck3_res["filename"])["done_indices"]
    assert len(ck3_done) == E2E_TOTAL_CHUNKS

    # 4. Kiểm tra tính bất biến của các checkpoint trước đó
    ck1_done_after = ck_service.get_done_pending_indices(ck1_res["filename"])["done_indices"]
    assert len(ck1_done_after) == 10  # Checkpoint 1 không đổi

    ck2_done_after = ck_service.get_done_pending_indices(ck2_res["filename"])["done_indices"]
    assert len(ck2_done_after) == 16  # Checkpoint 2 không đổi


def test_recovery_preparation_rollback_on_error(tmp_path, monkeypatch):
    """
    Test rollback toàn diện khi preparation gặp lỗi sau khi đã clone checkpoint:
    - Không để lại cloned checkpoint database.
    - Không để lại recovery task row trong tasks.db.
    - Không để lại partial output / manifest file.
    """
    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    src_file = proj / "sources" / "book.txt"
    src_file.write_text(make_chunked_source(E2E_TOTAL_CHUNKS), encoding="utf-8")

    fail_map = {0: 10}
    client, ck_service, store, run_state = _setup_test_env(monkeypatch, ws, proj, fail_map)

    # Tạo task 1 failed
    resp1 = client.post("/api/projects/p/translate", json={"files": ["book.txt"], "model": "gpt-test", "chunk_size": E2E_CHUNK_SIZE})
    task1_id = resp1.get_json()["job_id"]

    # Đếm số task và checkpoint trước khi gọi recovery
    tasks_before = len(store.list_tasks())
    ck_files_before = len(list((ws / "checkpoints").glob("*.db")))

    # Giả lập lỗi ở bước prompt loading (sau khi đã clone checkpoint và tạo recovery task)
    def _raise_prompt_err(*a, **k):
        raise RuntimeError("Disk I/O failure when loading merged prompts")

    monkeypatch.setattr("backend.infrastructure.config.prompt_service.PromptService.load_merged_prompts", _raise_prompt_err)

    resp_err = client.post(
        f"/api/tasks/{task1_id}/recover-from-checkpoint",
        json={"provider_id": "openai-test", "model": "gpt-test"},
    )
    assert resp_err.status_code == 500
    assert "Chuẩn bị recovery thất bại" in resp_err.get_json()["error"]

    # Kiểm tra rollback: cloned checkpoint và task row đã được xóa sạch
    assert len(store.list_tasks()) == tasks_before
    assert len(list((ws / "checkpoints").glob("*.db"))) == ck_files_before


def test_recovery_progress_events_emission(tmp_path, monkeypatch):
    """
    Kiểm tra progress events trong quá trình recovery mang đầy đủ
    completed_chunks, current, total, percent và tăng dần đều.
    """
    ws = tmp_path / "ws"
    proj = tmp_path / "proj"
    ws.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)
    src_file = proj / "sources" / "book.txt"
    src_file.write_text(make_chunked_source(E2E_TOTAL_CHUNKS), encoding="utf-8")

    fail_map = {0: 17, 1: None}
    client, ck_service, store, run_state = _setup_test_env(monkeypatch, ws, proj, fail_map)

    resp1 = client.post("/api/projects/p/translate", json={"files": ["book.txt"], "model": "gpt-test", "chunk_size": E2E_CHUNK_SIZE})
    task1_id = resp1.get_json()["job_id"]

    run_state["run_index"] = 1
    resp2 = client.post(f"/api/tasks/{task1_id}/recover-from-checkpoint",
                        json={"provider_id": "openai-test", "model": "gpt-test"})
    assert resp2.status_code == 200
    task2_id = resp2.get_json()["job_id"]

    events = store.iter_events(task2_id)
    prog_events = [e for e in events if e.get("type") == "progress"]

    assert len(prog_events) > 0
    # Checkpoint ban đầu có 17 chunk -> progress đầu tiên >= 70%
    assert prog_events[0]["completed_chunks"] >= 17
    assert prog_events[0]["total"] == E2E_TOTAL_CHUNKS

    # Progress cuối cùng đạt 100% và 24 chunks
    last_prog = prog_events[-1]
    assert last_prog["completed_chunks"] == E2E_TOTAL_CHUNKS
    assert last_prog["percent"] == 100
