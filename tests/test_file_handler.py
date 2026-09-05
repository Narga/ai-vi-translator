import pytest

from core.file_handler import SafeFileHandler, atomic_write_text


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


def test_atomic_write_keeps_old_on_crash(tmp_path, monkeypatch):
    import os

    target = tmp_path / "out.md"
    target.write_text("bản dịch cũ", encoding="utf-8")
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("crash giả lập")))
    with pytest.raises(OSError):
        atomic_write_text(target, "bản dịch mới dở dang")
    assert target.read_text(encoding="utf-8") == "bản dịch cũ"  # output cũ còn nguyên
    assert list(tmp_path.glob("*.tmp")) == []  # không sót file tạm


def test_atomic_write_normal(tmp_path):
    target = tmp_path / "out.md"
    atomic_write_text(target, "bản dịch mới")
    assert target.read_text(encoding="utf-8") == "bản dịch mới"


def test_legacy_translated_migrated_to_results(tmp_path):
    handler = SafeFileHandler(tmp_path)
    proj = handler.get_project_dir("old_proj")
    (proj / "translated").mkdir(parents=True, exist_ok=True)
    (proj / "translated" / "cu.md").write_text("cũ", encoding="utf-8")
    handler.get_project_dir("old_proj")  # kích hoạt migration
    assert (proj / "results" / "cu.md").read_text(encoding="utf-8") == "cũ"
    assert handler.get_output_path("old_proj", "cu.md").exists()


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
