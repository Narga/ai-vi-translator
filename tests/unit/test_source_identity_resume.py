"""Đổi provider/model KHÔNG được xóa chunk đã dịch (B5)."""
import pytest

from core.executor import TranslationExecutor
from services.checkpoint_service import CheckpointService
from tests.conftest import E2E_CHUNK_SIZE, E2E_TOTAL_CHUNKS, make_chunked_source, make_fake_robust_translate


def _config(tmp_path, model="gpt-test"):
    return {
        "chunk_size": E2E_CHUNK_SIZE,
        "checkpoint_dir": str(tmp_path / "checkpoints"),
        "provider_kind": "native_openai",
        "provider_id": "openai-test",
        "base_url": "https://api.openai.com/v1",
        "model_name": model,
        "credential_mode": "default",
        "project_slug": "p",
        "prompts": {"main": "dịch đi"},
        "context_char_count": 200,
    }


def _run(monkeypatch, tmp_path, model, sent, fail_at):
    monkeypatch.setattr("core.executor.ApiManager", lambda keys: None)
    monkeypatch.setattr("core.executor.robust_translate",
                        make_fake_robust_translate(sent, fail_at=fail_at, fail_once=False))
    ex = TranslationExecutor(api_keys=["k"], config=_config(tmp_path, model))
    return ex.translate_text(
        text=make_chunked_source(),
        output_filename="book.txt",
        output_file_path=tmp_path / "out.txt",
        job_id="job-1",
    )


def test_doi_model_van_giu_chunk_da_dich(monkeypatch, tmp_path):
    sent = []
    assert _run(monkeypatch, tmp_path, "gpt-test", sent, fail_at=17) is None

    ck = CheckpointService(str(tmp_path / "checkpoints"))
    before = ck.get_done_pending_indices("book.txt")
    assert len(before["done_indices"]) == 17

    # Chỉ đổi model, nguồn giữ nguyên → resume được, không xóa chunk
    monkeypatch.setattr("core.executor.ApiManager", lambda keys: None)
    sent2 = []
    monkeypatch.setattr("core.executor.robust_translate",
                        make_fake_robust_translate(sent2, fail_at=None, fail_once=False))
    ex = TranslationExecutor(api_keys=["k"], config=_config(tmp_path, "gpt-other"))
    result = ex.translate_text(
        text=make_chunked_source(),
        output_filename="book.txt",
        output_file_path=tmp_path / "out2.txt",
        job_id="job-2",
    )
    assert result is not None
    assert result.count("[dịch") == E2E_TOTAL_CHUNKS
    # Chunk 0..16 không bị gửi lại
    assert all(i not in sent2 for i in range(17))
    # Chỉ gửi 17..23
    assert set(sent2) == set(range(17, E2E_TOTAL_CHUNKS))


def test_doi_noi_dung_nguon_thi_dich_lai_tu_dau(monkeypatch, tmp_path):
    sent = []
    _run(monkeypatch, tmp_path, "gpt-test", sent, fail_at=17)

    monkeypatch.setattr("core.executor.ApiManager", lambda keys: None)
    sent2 = []
    monkeypatch.setattr("core.executor.robust_translate",
                        make_fake_robust_translate(sent2, fail_at=None, fail_once=False))
    ex = TranslationExecutor(api_keys=["k"], config=_config(tmp_path, "gpt-test"))
    ex.translate_text(
        text=make_chunked_source(n=E2E_TOTAL_CHUNKS, body_chars=1500),
        output_filename="book.txt",
        output_file_path=tmp_path / "out2.txt",
        job_id="job-2",
    )
    assert 0 in sent2   # source_hash đổi → reset → dịch lại từ chunk 0
