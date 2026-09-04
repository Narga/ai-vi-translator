"""SQLite index tối thiểu: projects/files/runs. Không checkpoint chunk."""

import datetime
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "workspace" / "app.db"


def get_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript((Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8"))
    return con


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
