import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional


class TaskStore:
    """
    Persistent SQLite-backed task store for translation/spellcheck jobs.
    Survives process restarts. Used as backing store for TaskRegistry.
    """

    def __init__(self, workspace_dir: str = "workspace"):
        self.db_path = os.path.join(workspace_dir, "tasks.db")
        os.makedirs(workspace_dir, exist_ok=True)
        self._lock = threading.RLock()
        self._connections: Dict[str, sqlite3.Connection] = {}
        self._get_connection()

    def _get_connection(self) -> sqlite3.Connection:
        with self._lock:
            if self.db_path not in self._connections:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        job_id TEXT UNIQUE NOT NULL,
                        kind TEXT NOT NULL,
                        title TEXT NOT NULL,
                        project_slug TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'running',
                        total_chunks INTEGER DEFAULT 0,
                        completed_chunks INTEGER DEFAULT 0,
                        current_chunk INTEGER DEFAULT 0,
                        phase TEXT,
                        checkpoint_key TEXT,
                        resume_of TEXT,
                        identity TEXT,
                        last_error TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS task_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        cursor INTEGER NOT NULL,
                        event_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id, cursor);
                    CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                    CREATE INDEX IF NOT EXISTS idx_tasks_checkpoint ON tasks(checkpoint_key);
                """)
                conn.commit()
                self._connections[self.db_path] = conn
            return self._connections[self.db_path]

    @contextmanager
    def _cursor(self):
        with self._lock:
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def create_task(
        self,
        job_id: str,
        kind: str,
        title: str,
        project_slug: str,
        filename: str,
        total_chunks: int = 0,
        identity: Optional[dict] = None,
        checkpoint_key: Optional[str] = None,
    ) -> str:
        task_id = job_id
        now = datetime.now().isoformat()
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO tasks (task_id, job_id, kind, title, project_slug, filename,
                   total_chunks, identity, checkpoint_key, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    job_id,
                    kind,
                    title,
                    project_slug,
                    filename,
                    total_chunks,
                    json.dumps(identity or {}, ensure_ascii=False),
                    checkpoint_key,
                    now,
                    now,
                ),
            )
        return task_id

    def create_resumed_task(self, original_task: dict, new_job_id: str) -> str:
        """Create a new task record linked to an existing task via resume_of."""
        now = datetime.now().isoformat()
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO tasks (task_id, job_id, kind, title, project_slug, filename,
                   status, total_chunks, completed_chunks, current_chunk, phase,
                   checkpoint_key, resume_of, identity, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_job_id,
                    new_job_id,
                    original_task["kind"],
                    original_task["title"],
                    original_task["project_slug"],
                    original_task["filename"],
                    original_task.get("total_chunks", 0),
                    original_task.get("completed_chunks", 0),
                    original_task.get("current_chunk", 0),
                    original_task.get("phase"),
                    original_task.get("checkpoint_key"),
                    original_task["task_id"],
                    json.dumps(original_task.get("identity") or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return new_job_id

    def get_task(self, task_id: str) -> Optional[dict]:
        row = self._get_connection().execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def get_task_by_job_id(self, job_id: str) -> Optional[dict]:
        row = self._get_connection().execute(
            "SELECT * FROM tasks WHERE job_id = ?", (job_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def update_status(self, task_id: str, status: str, **kwargs):
        sets = ["status = ?", "updated_at = ?"]
        vals: list = [status, datetime.now().isoformat()]
        for k, v in kwargs.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(task_id)
        with self._cursor() as cur:
            cur.execute(
                f"UPDATE tasks SET {', '.join(sets)} WHERE task_id = ?",
                vals,
            )

    def append_event(self, task_id: str, event: dict):
        with self._lock:
            conn = self._get_connection()
            cursor = (
                conn.execute(
                    "SELECT COALESCE(MAX(cursor), -1) FROM task_events WHERE task_id = ?",
                    (task_id,),
                ).fetchone()[0]
                + 1
            )
            conn.execute(
                """INSERT INTO task_events (task_id, cursor, event_json, created_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    task_id,
                    cursor,
                    json.dumps(event, ensure_ascii=False),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

    def iter_events(self, task_id: str, start_cursor: int = 0) -> List[dict]:
        rows = self._get_connection().execute(
            """SELECT event_json FROM task_events
               WHERE task_id = ? AND cursor >= ?
               ORDER BY cursor""",
            (task_id, start_cursor),
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def list_tasks(self, statuses: Optional[List[str]] = None) -> List[dict]:
        sql = "SELECT * FROM tasks"
        params: tuple = ()
        if statuses:
            placeholders = ",".join("?" * len(statuses))
            sql += f" WHERE status IN ({placeholders})"
            params = tuple(statuses)
        sql += " ORDER BY updated_at DESC"
        return [
            self._row_to_task(r)
            for r in self._get_connection().execute(sql, params)
        ]

    def find_running_by_checkpoint_key(self, checkpoint_key: str) -> Optional[dict]:
        row = self._get_connection().execute(
            """SELECT * FROM tasks WHERE checkpoint_key = ?
               AND status IN ('running', 'resumable')""",
            (checkpoint_key,),
        ).fetchone()
        return self._row_to_task(row) if row else None

    def close(self):
        conn = self._connections.pop(self.db_path, None)
        if conn:
            conn.close()

    def _row_to_task(self, row: tuple) -> dict:
        keys = [
            "task_id",
            "job_id",
            "kind",
            "title",
            "project_slug",
            "filename",
            "status",
            "total_chunks",
            "completed_chunks",
            "current_chunk",
            "phase",
            "checkpoint_key",
            "resume_of",
            "identity",
            "last_error",
            "created_at",
            "updated_at",
        ]
        d = dict(zip(keys, row))
        d["identity"] = json.loads(d["identity"] or "{}")
        return d
