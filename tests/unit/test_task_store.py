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
