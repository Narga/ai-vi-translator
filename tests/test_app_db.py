from core.app_db import get_db, log_run


def test_tables_created(tmp_path, monkeypatch):
    import core.app_db as m

    monkeypatch.setattr(m, "DB_PATH", tmp_path / "app.db")
    con = m.get_db()
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"projects", "files", "runs"} <= tables
    con.close()


def test_log_run(tmp_path, monkeypatch):
    import core.app_db as m

    monkeypatch.setattr(m, "DB_PATH", tmp_path / "app.db")
    m.log_run("gemini", "gemini-2.5-flash", "ok", db_path=tmp_path / "app.db")
    con = get_db(tmp_path / "app.db")
    rows = con.execute("SELECT provider, model, status FROM runs").fetchall()
    assert rows == [("gemini", "gemini-2.5-flash", "ok")]
    con.close()
