"""Integration test CLI run.main(): mock AI, filesystem + db tạm."""

import asyncio
from pathlib import Path

import run


class FakeMgr:
    THINKING_BUDGETS = {}

    @staticmethod
    def get_by_id(pid):
        return {"id": pid, "type": "gemini", "default_model": "m", "base_url": ""}

    @staticmethod
    def get_active():
        return {"id": "gemini-default", "type": "gemini", "default_model": "m", "base_url": ""}

    @staticmethod
    def get_keys(provider):
        return ["DUMMY"]


async def _fake_ok(self, prompt):
    return "DỊCH:" + prompt[:10]


def _patch_common(monkeypatch):
    from core import app_db
    monkeypatch.setattr("run.AIProviderManager", FakeMgr)
    monkeypatch.setattr("run.log_run", lambda *a, **k: None)
    monkeypatch.setattr(app_db, "DB_PATH", Path("/tmp/nonexistent-xyz/app.db"))
    monkeypatch.setattr("core.ai_client.GeminiClient.translate_chunk", _fake_ok)


def test_cli_direct_saves_output(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    src = tmp_path / "in.txt"
    src.write_text("Nội dung nguồn. " * 200, encoding="utf-8")
    out = tmp_path / "out.txt"
    assert asyncio.run(run.main([str(src), str(out)])) == 0
    assert out.exists() and "DỊCH:" in out.read_text(encoding="utf-8")


def test_cli_chunk2_error_no_output(tmp_path, monkeypatch):
    from core import app_db
    monkeypatch.setattr("run.AIProviderManager", FakeMgr)
    monkeypatch.setattr("run.log_run", lambda *a, **k: None)
    monkeypatch.setattr(app_db, "DB_PATH", Path("/tmp/nonexistent-xyz/app.db"))

    async def flaky(self, prompt):
        flaky.n += 1
        if flaky.n >= 2:
            raise TimeoutError("hết giờ")
        return "DỊCH:" + prompt[:10]
    flaky.n = 0
    monkeypatch.setattr("core.ai_client.GeminiClient.translate_chunk", flaky)
    src = tmp_path / "in.txt"
    src.write_text("Nội dung nguồn. " * 20000, encoding="utf-8")  # chắc chắn nhiều chunk
    out = tmp_path / "out.txt"
    assert asyncio.run(run.main([str(src), str(out)])) == 1
    assert not out.exists()  # lỗi chunk 2 -> không ghi output mới


def test_cli_project_mode_unicode(tmp_path, monkeypatch):
    from core import app_db
    from core.file_handler import SafeFileHandler as RealHandler
    monkeypatch.setattr("run.AIProviderManager", FakeMgr)
    monkeypatch.setattr("run.log_run", lambda *a, **k: None)
    monkeypatch.setattr(app_db, "DB_PATH", Path("/tmp/nonexistent-xyz/app.db"))
    monkeypatch.setattr("run.SafeFileHandler", lambda: RealHandler(tmp_path / "ws"))
    monkeypatch.setattr("core.ai_client.GeminiClient.translate_chunk", _fake_ok)
    fh = RealHandler(tmp_path / "ws")
    proj = fh.get_project_dir("Truyện_Tiêu")
    (proj / "sources" / "chương_01.md").write_text("Nội dung ễ ộ ư đ. " * 100, encoding="utf-8")
    assert asyncio.run(run.main(["--project", "Truyện_Tiêu", "--file", "chương_01.md"])) == 0
    out = proj / "results" / "chương_01.md"
    assert out.exists() and "DỊCH:" in out.read_text(encoding="utf-8")
