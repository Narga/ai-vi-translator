"""SQLite index tối thiểu: projects/files/runs. Không checkpoint chunk."""

import contextlib
import datetime
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "workspace" / "app.db"


def get_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript((Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8"))
    cols = [r[1] for r in con.execute("PRAGMA table_info(projects)").fetchall()]
    for col in ("author", "description"):
        if col not in cols:
            con.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT DEFAULT ''")
    con.execute("CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at)")
    con.commit()
    return con


@contextlib.contextmanager
def db(db_path: Path = DB_PATH):
    """Context manager cho code mới: tự commit/close. Không rewrite hàng loạt code cũ."""
    con = get_db(db_path)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def file_id(project: str, filename: str, db_path: Path = DB_PATH) -> int | None:
    # Policy: chỉ bắt sqlite3.Error (schema/lock/path sai) + warning có trace;
    # KHÔNG nuốt mọi Exception — lỗi lập trình phải nổ to để thấy.
    try:
        with db() as con:
            row = con.execute("SELECT id FROM files WHERE project_slug=? AND filename=?",
                              (project, filename)).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        logger.warning("Cannot resolve file_id for %s/%s", project, filename, exc_info=True)
        return None


def log_run(provider: str, model: str, status: str, error: str = "",
            file_id: int | None = None, db_path: Path = DB_PATH) -> None:
    con = get_db(db_path)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    con.execute(
        "INSERT INTO runs(provider, model, started_at, finished_at, status, error, file_id)"
        " VALUES (?,?,?,?,?,?,?)",
        (provider, model, now, now, status, error, file_id),
    )
    con.commit()
    con.close()
