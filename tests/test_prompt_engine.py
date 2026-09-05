import pytest

from core.prompt_engine import PromptEngine


def test_unicode_preserved(tmp_path):
    eng = PromptEngine(tmp_path)
    out = eng.assemble_prompt("Tiếng Việt có dấu: ễ ộ ư đ.")
    assert "ễ" in out and "{{source_text}}" not in out


def test_missing_prompt_raises(tmp_path):
    eng = PromptEngine(tmp_path)
    with pytest.raises(FileNotFoundError):
        eng.load_prompt("khong_ton_tai.txt")


def test_glossary_terms_replaced(tmp_path):
    (tmp_path / "default_translation.txt").write_text(
        "Terms: {{glossary_terms}}\nText: {{source_text}}", encoding="utf-8"
    )
    eng = PromptEngine(tmp_path)
    out = eng.assemble_prompt("hi", glossary_terms="A -> B")
    assert "A -> B" in out


def test_rename_delete_prompt(tmp_path):
    eng = PromptEngine(tmp_path)
    (tmp_path / "a.txt").write_text("nội dung A", encoding="utf-8")
    assert eng.rename_prompt("a.txt", "b.txt") == "b.txt"
    assert (tmp_path / "b.txt").exists() and not (tmp_path / "a.txt").exists()
    eng.delete_prompt("b.txt")
    assert not (tmp_path / "b.txt").exists()
    with pytest.raises(FileNotFoundError):
        eng.delete_prompt("khongco.txt")
    with pytest.raises(ValueError):
        eng.rename_prompt("a.txt", "../evil.txt")
    with pytest.raises(ValueError):
        eng.rename_prompt("a.txt", "b.md")  # chỉ *.txt
    (tmp_path / "c.txt").write_text("C", encoding="utf-8")
    (tmp_path / "d.txt").write_text("D", encoding="utf-8")
    with pytest.raises(ValueError):
        eng.rename_prompt("c.txt", "d.txt")  # trùng tên
