import time
import uuid
from typing import Dict, Any, List, Optional
from threading import Lock, Condition
from queue import Queue

class Task:
    def __init__(self, job_id: str, kind: str, title: str, total_files: int):
        self.job_id = job_id
        self.kind = kind
        self.title = title
        self.total_files = total_files
        self.status = "started"
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.events: List[Dict[str, Any]] = []
        self._cond = Condition()
        
        # Summary fields for UI rehydration
        self.percent = 0
        self.last_message = ""
        self.current = 0
        self.total = 0
        self.completed_files = 0
        self.error_count = 0
        self.finished_at = None

    def append_event(self, event: Dict[str, Any]):
        with self._cond:
            self.events.append(event)
            if len(self.events) > 500:
                self.events = self.events[-500:]
            self.updated_at = time.time()

            if event.get("message"):
                self.last_message = event["message"]

            # Summary here is for whole-job state, not per-file chunk progress.
            evt_type = event.get("type", "")
            if evt_type == "file_complete":
                self.completed_files += 1
                if self.total_files > 0:
                    self.current = self.completed_files
                    self.total = self.total_files
                    self.percent = int((self.completed_files / self.total_files) * 100)
            elif evt_type in ("file_error", "batch_error", "error"):
                self.error_count += 1
            elif evt_type in ("complete", "cancelled"):
                self.finished_at = time.time()
                if evt_type == "complete":
                    self.current = self.total_files
                    self.total = self.total_files
                    self.percent = 100
                
            self._cond.notify_all()

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "title": self.title,
            "total_files": self.total_files,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "percent": self.percent,
            "last_message": self.last_message,
            "current": self.current,
            "total": self.total,
            "completed_files": self.completed_files,
            "error_count": self.error_count,
            "finished_at": self.finished_at
        }

    def iter_events(self, cursor: int):
        """Yield events starting from cursor index, then block for new events.
        Returns (event, new_cursor) tuples. Stops when task is terminal."""
        with self._cond:
            while True:
                if cursor < len(self.events):
                    event = self.events[cursor]
                    cursor += 1
                    yield event, cursor
                else:
                    if self.status in ("completed", "failed", "cancelled"):
                        break
                    self._cond.wait(timeout=1.0)

class TaskRegistry:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TaskRegistry, cls).__new__(cls)
                cls._instance._tasks = {}
            return cls._instance

    def create_task(self, kind: str, title: str, total_files: int = 0) -> str:
        job_id = str(uuid.uuid4())
        task = Task(job_id, kind, title, total_files)
        with self._lock:
            self._tasks[job_id] = task
        return job_id

    def get_task(self, job_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(job_id)

    def append_event(self, job_id: str, event: Dict[str, Any]):
        task = self.get_task(job_id)
        if task:
            task.append_event(event)

    def update_status(self, job_id: str, status: str):
        task = self.get_task(job_id)
        if task:
            with task._cond:
                task.status = status
                task.updated_at = time.time()
                if status in ("completed", "failed", "cancelled"):
                    task.finished_at = time.time()
                task._cond.notify_all()

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [task.to_dict() for task in self._tasks.values()]

    def list_active_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [task.to_dict() for task in self._tasks.values() if task.status == "started"]
