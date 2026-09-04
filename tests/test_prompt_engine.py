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
