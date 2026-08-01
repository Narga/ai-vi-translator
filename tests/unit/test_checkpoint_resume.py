from services.checkpoint_service import CheckpointService


def test_resume_returns_first_pending_chunk(tmp_path):
    service = CheckpointService(str(tmp_path))
    service.init_session("book", 3, ["a", "b", "c"], identity={"model": "one"})
    service.save_chunk("book", 0, "a", "A")
    service.save_chunk("book", 2, "c", "C")

    info = service.get_resume_info("book")
    assert info["translated_count"] == 2
    assert info["next_chunk_index"] == 1


def test_reset_session_removes_old_done_rows(tmp_path):
    service = CheckpointService(str(tmp_path))
    service.init_session("book", 2, ["a", "b"], identity={"model": "old"})
    service.save_chunk("book", 0, "a", "A")

    service.init_session(
        "book", 2, ["a-new", "b-new"], identity={"model": "new"}, reset=True
    )

    assert service.get_resume_info("book")["translated_count"] == 0
    assert service.get_translated_chunks("book") == {}

