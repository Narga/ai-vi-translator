import pytest
from backend.infrastructure.progress.task_registry import TaskRegistry
from services.task_store import TaskStore


@pytest.fixture(autouse=True)
def _reset_task_registry():
    TaskRegistry._instance = None
    yield
    TaskRegistry._instance = None


def test_task_survives_registry_rebuild(tmp_path):
    store = TaskStore(str(tmp_path))
    registry1 = TaskRegistry(store=store)
    job_id = registry1.create_task("translation", "Test", 1)
    registry1.update_status(job_id, "resumable")

    registry2 = TaskRegistry(store=store)
    task = registry2.get_task(job_id)
    assert task is not None
    assert task.status == "resumable"


def test_list_active_tasks_uses_store_when_bound(tmp_path):
    store = TaskStore(str(tmp_path))
    registry = TaskRegistry(store=store)
    j1 = registry.create_task("translation", "T1", 1)
    j2 = registry.create_task("translation", "T2", 1)
    registry.update_status(j1, "resumable")
    registry.update_status(j2, "completed")

    active = registry.list_active_tasks()
    assert len(active) == 1
    assert active[0]["job_id"] == j1


def test_list_active_tasks_falls_back_to_ram_without_store():
    TaskRegistry._instance = None
    registry = TaskRegistry()
    j1 = registry.create_task("translation", "T1", 1)
    registry.update_status(j1, "started")

    active = registry.list_active_tasks()
    assert len(active) == 1
    assert active[0]["job_id"] == j1


def test_append_event_persists_to_store(tmp_path):
    store = TaskStore(str(tmp_path))
    registry = TaskRegistry(store=store)
    job_id = registry.create_task("translation", "T", 1)
    registry.append_event(job_id, {"type": "info", "message": "hello"})

    events = store.iter_events(job_id)
    assert len(events) == 1
    assert events[0]["message"] == "hello"


def test_get_task_loads_from_store_when_not_in_ram(tmp_path):
    store = TaskStore(str(tmp_path))
    # Pre-populate store directly
    store.create_task(
        job_id="job-1",
        kind="translation",
        title="Persisted",
        project_slug="p",
        filename="f.txt",
        total_chunks=5,
    )
    store.update_status("job-1", "resumable", completed_chunks=2)

    registry = TaskRegistry(store=store)
    task = registry.get_task("job-1")
    assert task is not None
    assert task.status == "resumable"
    assert task.total_files == 5
