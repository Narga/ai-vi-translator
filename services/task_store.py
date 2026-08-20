import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


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

    def _migrate_schema(self, conn: sqlite3.Connection):
        """Migration an toàn: thêm cột nếu chưa có."""
        migrations = [
            ("recovery_of", "TEXT", "NULL"),
            ("source_task_id", "TEXT", "NULL"),
            ("source_checkpoint_key", "TEXT", "NULL"),
            ("recovery_checkpoint_key", "TEXT", "NULL"),
            ("partial_output_path", "TEXT", "NULL"),
            ("final_output_path", "TEXT", "NULL"),
            ("pending_chunks", "TEXT", "NULL"),
            ("error_class", "TEXT", "NULL"),
            ("http_status", "INTEGER", "NULL"),
            ("retryable", "INTEGER", "0"),
            ("mixed_provider", "INTEGER", "0"),
            # P1 Phase 7 lease: timestamp worker cập nhật để chứng minh còn sống.
            # NULL = task trước lease hoặc non-running. Startup dùng lease timeout để
            # chuyển running + stale heartbeat → interrupted (worker crash, không restart).
            ("heartbeat_at", "TEXT", "NULL"),
            # P1.7: Fencing token & epoch chống zombie worker ghi đè dữ liệu
            ("lease_token", "TEXT", "NULL"),
            ("lease_epoch", "INTEGER", "0"),
        ]

        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        missing = [item for item in migrations if item[0] not in existing]
        for col, col_type, default in missing:
            conn.execute(
                f"ALTER TABLE tasks ADD COLUMN {col} {col_type} DEFAULT {default}"
            )

        conn.commit()

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
                self._migrate_schema(conn)
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

    def create_recovery_task(
        self,
        source_task: dict,
        recovery_job_id: str,
        recovery_checkpoint_key: str,
        provider_id: str,
        model: str,
        mixed_provider: bool,
        source_checkpoint_key: Optional[str] = None,
        root_recovery_of: Optional[str] = None,
    ) -> str:
        """
        Tạo task recovery mới liên kết với task lỗi (hỗ trợ recovery lineage nhiều cấp).

        Args:
            source_task: Task bị lỗi (dict từ get_task)
            recovery_job_id: Job ID mới
            recovery_checkpoint_key: Checkpoint namespace mới
            provider_id: Provider mới
            model: Model mới
            mixed_provider: True nếu provider/model khác source
            source_checkpoint_key: Checkpoint của task nguồn trực tiếp
            root_recovery_of: Root task ID đầu tiên trong chuỗi lineage

        Returns:
            recovery_task_id
        """
        now = datetime.now().isoformat()
        src_ck_key = (
            source_checkpoint_key
            or source_task.get("recovery_checkpoint_key")
            or source_task.get("checkpoint_key")
        )
        root_rec_of = (
            root_recovery_of
            or source_task.get("recovery_of")
            or source_task["task_id"]
        )
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO tasks (
                    task_id, job_id, kind, title, project_slug, filename,
                    status, total_chunks, completed_chunks, current_chunk, phase,
                    checkpoint_key, resume_of, recovery_of, source_task_id,
                    source_checkpoint_key, recovery_checkpoint_key,
                    partial_output_path, final_output_path,
                    pending_chunks, identity,
                    last_error, error_class, http_status, retryable, mixed_provider,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    recovery_job_id,
                    recovery_job_id,
                    source_task["kind"],
                    source_task["title"],
                    source_task["project_slug"],
                    source_task["filename"],
                    source_task.get("total_chunks", 0),
                    source_task.get("completed_chunks", 0),
                    source_task.get("phase", "recovery"),
                    recovery_checkpoint_key,
                    source_task.get("resume_of"),
                    root_rec_of,
                    source_task["task_id"],
                    src_ck_key,
                    recovery_checkpoint_key,
                    None,
                    None,
                    json.dumps([], ensure_ascii=False),
                    json.dumps(source_task.get("identity") or {}, ensure_ascii=False),
                    None,
                    None,
                    None,
                    0,
                    1 if mixed_provider else 0,
                    now,
                    now,
                ),
            )
        return recovery_job_id

    def delete_task(self, task_id: str) -> bool:
        """Xóa task và các events liên quan (dùng cho rollback khi prepare thất bại)."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM task_events WHERE task_id = ?", (task_id,))
            cur.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            return cur.rowcount > 0

    def update_recovery_task(
        self,
        task_id: str,
        lease_epoch: Optional[int] = None,
        lease_token: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Cập nhật recovery task metadata.
        Kwargs có thể bao gồm: partial_output_path, final_output_path,
        pending_chunks (list), completed_chunks, status, v.v.
        """
        allowed = {
            "partial_output_path", "final_output_path", "pending_chunks",
            "completed_chunks", "current_chunk", "status", "last_error",
            "error_class", "http_status", "retryable", "heartbeat_at",
            "checkpoint_key",
        }
        sets = ["updated_at = ?"]
        vals: list = [datetime.now().isoformat()]

        for k, v in kwargs.items():
            if k not in allowed or v is None:
                continue
            if k == "pending_chunks" and isinstance(v, list):
                v = json.dumps(v, ensure_ascii=False)
            sets.append(f"{k} = ?")
            vals.append(v)

        vals.append(task_id)
        where_clause = "WHERE task_id = ?"
        if lease_epoch is not None:
            where_clause += " AND lease_epoch = ?"
            vals.append(lease_epoch)
        if lease_token is not None:
            where_clause += " AND lease_token = ?"
            vals.append(lease_token)

        with self._cursor() as cur:
            cur.execute(
                f"UPDATE tasks SET {', '.join(sets)} {where_clause}",
                vals,
            )
            return cur.rowcount > 0

    def get_task(self, task_id: str) -> Optional[dict]:
        row = self._get_connection().execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def get_task_by_job_id(self, job_id: str) -> Optional[dict]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            return self._row_to_task(row) if row else None

    def get_task_by_checkpoint_key(self, checkpoint_key: str) -> Optional[dict]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE checkpoint_key = ? ORDER BY created_at DESC LIMIT 1", (checkpoint_key,))
            row = cur.fetchone()
            return self._row_to_task(row) if row else None

    def update_status(
        self,
        task_id: str,
        status: str,
        lease_epoch: Optional[int] = None,
        lease_token: Optional[str] = None,
        **kwargs,
    ) -> bool:
        sets = ["status = ?", "updated_at = ?"]
        vals: list = [status, datetime.now().isoformat()]
        if status in ("completed", "failed", "cancelled", "closed_partial"):
            sets.append("lease_token = NULL")
        for k, v in kwargs.items():
            if v is not None:
                sets.append(f"{k} = ?")
                vals.append(v)
        vals.append(task_id)
        where_clause = "WHERE task_id = ?"
        if lease_epoch is not None:
            where_clause += " AND lease_epoch = ?"
            vals.append(lease_epoch)
        if lease_token is not None:
            where_clause += " AND lease_token = ?"
            vals.append(lease_token)

        with self._cursor() as cur:
            cur.execute(
                f"UPDATE tasks SET {', '.join(sets)} {where_clause}",
                vals,
            )
            return cur.rowcount > 0

    def acquire_lease(
        self, task_id: str, lease_timeout_seconds: float = 30.0
    ) -> Optional[tuple]:
        """
        Atomic claim lease trên task.
        Chỉ thành công nếu task ở trạng thái:
        - 'queued', 'interrupted', 'resumable'
        - hoặc 'running' nhưng heartbeat_at đã hết hạn quá lease_timeout_seconds (hoặc heartbeat_at IS NULL).
        Tuyệt đối KHÔNG acquire task ở trạng thái: 'completed', 'failed', 'cancelled', 'closed_partial'.
        Trả về (lease_token, lease_epoch) nếu thành công, None nếu thất bại.
        """
        import uuid
        from datetime import timedelta
        new_token = str(uuid.uuid4())
        now = datetime.now()
        now_iso = now.isoformat()
        stale_threshold = (now - timedelta(seconds=lease_timeout_seconds)).isoformat()

        with self._cursor() as cur:
            cur.execute(
                """UPDATE tasks
                   SET lease_token = ?,
                       lease_epoch = COALESCE(lease_epoch, 0) + 1,
                       heartbeat_at = ?,
                       status = 'running',
                       updated_at = ?
                   WHERE task_id = ?
                     AND (
                         status IN ('queued', 'interrupted', 'resumable')
                         OR (status = 'running' AND (heartbeat_at IS NULL OR heartbeat_at < ?))
                     )""",
                (new_token, now_iso, now_iso, task_id, stale_threshold),
            )
            if cur.rowcount == 0:
                return None

            cur.execute("SELECT lease_epoch FROM tasks WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            epoch = row[0] if row else 1
            return new_token, epoch

    def touch_lease(
        self, task_id: str, lease_epoch: int, lease_token: Optional[str] = None
    ) -> bool:
        """
        Cập nhật heartbeat_at có điều kiện (atomic CAS).
        Chỉ thành công nếu task đang 'running', lease_epoch khớp (và lease_token khớp nếu có).
        """
        now_iso = datetime.now().isoformat()
        query = (
            "UPDATE tasks SET heartbeat_at = ?, updated_at = ? "
            "WHERE task_id = ? AND lease_epoch = ? AND status = 'running'"
        )
        params = [now_iso, now_iso, task_id, lease_epoch]
        if lease_token is not None:
            query += " AND lease_token = ?"
            params.append(lease_token)
        with self._cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount > 0

    def is_lease_valid(
        self, task_id: str, lease_epoch: Optional[int], lease_token: Optional[str]
    ) -> bool:
        """
        Durable check trực tiếp vào SQLite tasks.db (Fail-Closed & Strict State):
        Chỉ trả về True khi:
        - task_id tồn tại,
        - status == 'running',
        - lease_epoch khớp chính xác,
        - lease_token khớp chính xác và không rỗng.
        """
        if not task_id or lease_epoch is None or not lease_token:
            return False
        with self._cursor() as cur:
            cur.execute(
                "SELECT lease_epoch, lease_token, status FROM tasks WHERE task_id = ?",
                (task_id,),
            )
            row = cur.fetchone()
            if not row:
                return False
            curr_epoch, curr_token, status = row
            if status != "running":
                return False
            if curr_epoch != lease_epoch or curr_token != lease_token:
                return False
            return True

    def touch_heartbeat(self, task_id: str) -> None:
        """Cập nhật heartbeat để chứng minh worker task đang còn sống (P1 Phase 7 lease)."""
        with self._cursor() as cur:
            cur.execute(
                "UPDATE tasks SET heartbeat_at = ?, updated_at = ? WHERE task_id = ?",
                (datetime.now().isoformat(), datetime.now().isoformat(), task_id),
            )

    def reconcile_lease_expired(self, lease_timeout_seconds: float = 30.0) -> int:
        """Chuyển task `running` + heartbeat cũ hơn lease_timeout → `interrupted` và thu hồi lease_token."""
        from datetime import timedelta
        now = datetime.now()
        stale_threshold = (now - timedelta(seconds=lease_timeout_seconds)).isoformat()
        now_iso = now.isoformat()
        with self._cursor() as cur:
            cur.execute(
                """UPDATE tasks
                   SET status = 'interrupted',
                       lease_token = NULL,
                       updated_at = ?
                   WHERE status = 'running'
                     AND (heartbeat_at IS NULL OR heartbeat_at < ?)""",
                (now_iso, stale_threshold),
            )
            return cur.rowcount

    def append_event(
        self,
        task_id: str,
        event: dict,
        lease_epoch: Optional[int] = None,
        lease_token: Optional[str] = None,
    ) -> bool:
        with self._lock:
            conn = self._get_connection()
            if lease_epoch is not None or lease_token is not None:
                query = "SELECT 1 FROM tasks WHERE task_id = ? AND status = 'running'"
                params = [task_id]
                if lease_epoch is not None:
                    query += " AND lease_epoch = ?"
                    params.append(lease_epoch)
                if lease_token is not None:
                    query += " AND lease_token = ?"
                    params.append(lease_token)
                row = conn.execute(query, params).fetchone()
                if not row:
                    return False

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
            return True

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

    def find_active_recovery_for_source(self, source_task_id: str) -> Optional[dict]:
        """
        Tìm recovery task đang chạy cho source task.
        Trả None nếu không có hoặc đã completed/failed.
        """
        row = self._get_connection().execute(
            """SELECT * FROM tasks WHERE source_task_id = ?
               AND status IN ('running', 'resumable')""",
            (source_task_id,),
        ).fetchone()
        return self._row_to_task(row) if row else None

    def close(self):
        conn = self._connections.pop(self.db_path, None)
        if conn:
            conn.close()

    def get_recovery_attempt_count(self, root_task_id: str) -> int:
        """Đếm số lần đã thử recovery cho root task ID (Phase 9: Poison Job Quarantine)."""
        if not root_task_id:
            return 0
        with self._cursor() as cur:
            row = cur.execute(
                "SELECT COUNT(*) FROM tasks WHERE recovery_of = ? AND task_id != ?",
                (root_task_id, root_task_id),
            ).fetchone()
            return row[0] if row else 0

    def quarantine_task(self, task_id: str, reason: str = "max_recovery_attempts") -> bool:
        """
        Đánh dấu canonical poison job quarantine (Phase 9).
        Tuân thủ quy tắc: status='failed', error_class='poison_job', không tạo status phi chuẩn.
        """
        now = datetime.now().isoformat()
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET status = 'failed',
                    error_class = 'poison_job',
                    last_error = ?,
                    lease_token = NULL,
                    updated_at = ?
                WHERE task_id = ? OR job_id = ?
                """,
                (f"Quarantined poison job: {reason}", now, task_id, task_id),
            )
            return cur.rowcount > 0

    def _row_to_task(self, row: Any) -> dict:
        if not row:
            return {}
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
            "recovery_of",
            "source_task_id",
            "source_checkpoint_key",
            "recovery_checkpoint_key",
            "partial_output_path",
            "final_output_path",
            "pending_chunks",
            "error_class",
            "http_status",
            "retryable",
            "mixed_provider",
            "heartbeat_at",
            "lease_token",
            "lease_epoch",
        ]
        if hasattr(row, "keys"):
            row_keys = set(row.keys())
            d = {k: row[k] if k in row_keys else None for k in keys}
        elif isinstance(row, dict):
            d = {k: row.get(k) for k in keys}
        else:
            d = dict(zip(keys, row))

        d["identity"] = json.loads(d.get("identity") or "{}") if isinstance(d.get("identity"), str) else (d.get("identity") or {})
        if d.get("pending_chunks"):
            if isinstance(d["pending_chunks"], str):
                try:
                    d["pending_chunks"] = json.loads(d["pending_chunks"])
                except Exception:
                    d["pending_chunks"] = []
        else:
            d["pending_chunks"] = []
        return d
