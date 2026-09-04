import pytest

from core.file_handler import SafeFileHandler


def test_path_traversal_detection(tmp_path):
    handler = SafeFileHandler(tmp_path)
    with pytest.raises(ValueError):
        handler.get_project_dir("../evil_proj")
    with pytest.raises(ValueError):
        handler.get_source_path("my_proj", "../../../etc/passwd")
    with pytest.raises(ValueError):
        handler.get_source_path("my_proj", "sub/file.txt")


def test_valid_file_handling(tmp_path):
    handler = SafeFileHandler(tmp_path)
    p_dir = handler.get_project_dir("my_proj")
    assert (p_dir / "sources").exists()
    src_file = handler.get_source_path("my_proj", "ch01.md")
    src_file.write_text("Nội dung gốc", encoding="utf-8")
    assert handler.read_source("my_proj", "ch01.md") == "Nội dung gốc"


def test_cli_usage_error(monkeypatch):
    import asyncio

    class FakeMgr:
        def get_by_id(self, pid):
            return {"id": pid, "type": "gemini", "default_model": "m", "base_url": ""}
        def get_active(self):
            return {"id": "gemini-default", "type": "gemini", "default_model": "m", "base_url": ""}
        def get_keys(self, provider):
            return ["DUMMY"]

    monkeypatch.setattr("run.AIProviderManager", lambda: FakeMgr())
    from run import main

    assert asyncio.run(main(["--project", "X"])) == 1
