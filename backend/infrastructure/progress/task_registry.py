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

        self.percent = 0
        self.last_message = ""
        self.current = 0
        self.total = 0
        self.completed_files = 0
        self.error_count = 0
        self.finished_at = None
        self.checkpoint_key = None

    def append_event(self, event: Dict[str, Any]):
        with self._cond:
            self.events.append(event)
            if len(self.events) > 500:
                self.events = self.events[-500:]
            self.updated_at = time.time()

            if event.get("message"):
                self.last_message = event["message"]
            if event.get("checkpoint_key"):
                self.checkpoint_key = event["checkpoint_key"]

            evt_type = event.get("type", "")
            if evt_type == "progress":
                # Chunk-level progress: cập nhật current/total để completed_chunks không bị
                # ghi 0 khi task fail giữa file (B6). executor emit current=i+1, total=len(chunks).
                cur = event.get("current")
                tot = event.get("total")
                if isinstance(cur, int) and cur > self.current:
                    self.current = cur
                if isinstance(tot, int) and tot > 0:
                    self.total = tot
                if isinstance(event.get("percent"), int):
                    self.percent = event["percent"]
            elif evt_type == "file_complete":
                self.completed_files += 1
                if self.total_files > 0:
                    self.current = self.completed_files
                    self.total = self.total_files
                    self.percent = int((self.completed_files / self.total_files) * 100)
            elif evt_type in ("file_error", "batch_error", "error", "task_failed"):
                self.error_count += 1
            if evt_type in ("complete", "cancelled", "task_failed"):
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
            "finished_at": self.finished_at,
            "checkpoint_key": self.checkpoint_key,
        }

    def iter_events(self, cursor: int):
        with self._cond:
            while True:
                if cursor < len(self.events):
                    event = self.events[cursor]
                    cursor += 1
                    yield event, cursor
                else:
                    if self.status in ("completed", "failed", "cancelled", "resumable", "paused",
                                       "closed_partial", "interrupted"):
                        break
                    self._cond.wait(timeout=1.0)


class TaskRegistry:
    _instance = None
    _lock = Lock()

    def __new__(cls, store=None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TaskRegistry, cls).__new__(cls)
                cls._instance._tasks = {}
                cls._instance._store = store
            return cls._instance

    def __init__(self, store=None):
        pass

    @classmethod
    def bind_store(cls, store):
        if cls._instance is not None:
            cls._instance._store = store

    def create_task(
        self,
        kind: str,
        title: str,
        total_files: int = 0,
        project_slug: str = "",
        filename: str = "",
        checkpoint_key: Optional[str] = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        task = Task(job_id, kind, title, total_files)
        task.checkpoint_key = checkpoint_key
        with self._lock:
            self._tasks[job_id] = task
        if getattr(self, "_store", None):
            self._store.create_task(
                job_id=job_id,
                kind=kind,
                title=title,
                project_slug=project_slug,
                filename=filename,
                total_chunks=total_files,
                checkpoint_key=checkpoint_key,
            )
        return job_id

    def get_task(self, job_id: str) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(job_id)
        if task is None and getattr(self, "_store", None):
            row = self._store.get_task_by_job_id(job_id)
            if row:
                task = Task(
                    row["job_id"],
                    row["kind"],
                    row["title"],
                    row.get("total_chunks", 0),
                )
                task.status = row.get("status", "started")
                task.events = self._store.iter_events(row["task_id"])
                with self._lock:
                    self._tasks[job_id] = task
        return task

    # Chỉ những event này mới được phép chuyển task sang failed trong tasks.db.
    # "error" là lỗi cấp chunk/không terminal — KHÔNG persist failed (B7).
    _TERMINAL_FAILURE_EVENTS = ("task_failed",)

    @staticmethod
    def _error_context_of(event: Dict[str, Any]) -> Dict[str, Any]:
        """Chuẩn hóa 2 shape: task_failed (lồng error_context) và error (phẳng)."""
        ctx = event.get("error_context")
        if isinstance(ctx, dict) and ctx:
            return ctx
        return {
            "status": event.get("status"),
            "http_status": event.get("http_status"),
            "retryable": event.get("retryable"),
            "message": event.get("message"),
            "chunk_index": event.get("chunk_index"),
        }

    def append_event(
        self,
        job_id: str,
        event: Dict[str, Any],
        lease_epoch: Optional[int] = None,
        lease_token: Optional[str] = None,
    ) -> bool:
        if getattr(self, "_store", None):
            ok = self._store.append_event(
                job_id, event, lease_epoch=lease_epoch, lease_token=lease_token
            )
            if not ok:
                # CAS fencing reject: Không cập nhật in-memory hay SSE stream
                return False

        task = self.get_task(job_id)
        if task:
            task.append_event(event)

        if getattr(self, "_store", None) and event.get("type") in self._TERMINAL_FAILURE_EVENTS:
            ctx = self._error_context_of(event)
            kwargs = {
                "error_class": ctx.get("status"),
                "http_status": ctx.get("http_status"),
                "retryable": ctx.get("retryable"),
                "last_error": ctx.get("message") or event.get("message"),
            }
            if event.get("checkpoint_key"):
                kwargs["checkpoint_key"] = event["checkpoint_key"]

            # B6: chỉ ghi completed_chunks khi có số dương VÀ không nhỏ hơn số đã lưu.
            progress = task.current if task else 0
            if progress > 0:
                try:
                    row = self._store.get_task_by_job_id(job_id) or {}
                    if progress >= (row.get("completed_chunks") or 0):
                        kwargs["completed_chunks"] = progress
                except Exception:
                    kwargs["completed_chunks"] = progress

            self._store.update_status(
                job_id,
                status="failed",
                lease_epoch=lease_epoch,
                lease_token=lease_token,
                **kwargs,
            )

        return True

    def update_status(
        self,
        job_id: str,
        status: str,
        lease_epoch: Optional[int] = None,
        lease_token: Optional[str] = None,
    ) -> bool:
        task = self.get_task(job_id)
        if getattr(self, "_store", None):
            kwargs = {}
            if task:
                if task.current > 0:
                    kwargs["completed_chunks"] = task.current
                if task.checkpoint_key:
                    kwargs["checkpoint_key"] = task.checkpoint_key
            ok = self._store.update_status(
                job_id,
                status,
                lease_epoch=lease_epoch,
                lease_token=lease_token,
                **kwargs,
            )
            if not ok:
                return False

        if task:
            with task._cond:
                task.status = status
                task.updated_at = time.time()
                if status in ("completed", "failed", "cancelled", "closed_partial"):
                    task.finished_at = time.time()
                task._cond.notify_all()

        # Dọn cancel token sau khi task rời trạng thái đang chạy (chống poison job mới
        # cùng job_id). KHÔNG xóa token của job khác — reset_cancel chỉ discard đúng id.
        if status not in ("running", "started"):
            from backend.infrastructure.progress.runtime_state import RuntimeState
            RuntimeState().reset_cancel(job_id)

        return True

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [task.to_dict() for task in self._tasks.values()]

    def list_active_tasks(self) -> List[Dict[str, Any]]:
        if getattr(self, "_store", None):
            return self._store.list_tasks(["running", "resumable", "paused"])
        with self._lock:
            return [
                task.to_dict()
                for task in self._tasks.values()
                if task.status == "started"
            ]
