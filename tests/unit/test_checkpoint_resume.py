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


def test_get_done_pending_indices(tmp_path):
    service = CheckpointService(str(tmp_path))
    service.init_session("book", 5, ["a", "b", "c", "d", "e"])
    service.save_chunk("book", 0, "a", "A", status="done")
    service.save_chunk("book", 2, "c", "C", status="done")
    service.save_chunk("book", 3, "d", "D", status="failed")

    indices = service.get_done_pending_indices("book")
    assert indices["done_indices"] == [0, 2]
    assert 3 in indices["pending_indices"]
    assert 1 in indices["pending_indices"]
    assert 4 in indices["pending_indices"]
    assert indices["failed_indices"] == [3]


def test_clone_namespace(tmp_path):
    service = CheckpointService(str(tmp_path))
    service.init_session("src", 3, ["a", "b", "c"])
    service.save_chunk("src", 0, "a", "A", status="done")
    service.save_chunk("src", 1, "b", "B", status="done")

    assert service.clone_namespace("src", "dest") is True

    dest = service.get_translated_chunks("dest")
    assert dest == {0: "A", 1: "B"}

    src = service.get_translated_chunks("src")
    assert src == {0: "A", 1: "B"}


def test_assemble_partial(tmp_path):
    service = CheckpointService(str(tmp_path))
    service.init_session("book", 3, ["a", "b", "c"])
    service.save_chunk("book", 0, "a", "A", status="done")
    service.save_chunk("book", 2, "c", "C", status="done")

    text = service.assemble_partial("book", marker="[MISSING {idx}]")
    assert text == "A\n\n[MISSING 1]\n\nC"


def test_write_partial_file(tmp_path):
    service = CheckpointService(str(tmp_path / "checkpoints"))
    service.init_session("book", 3, ["a\nb", "c", "d\ne"])
    service.save_chunk("book", 0, "a\nb", "A", status="done")

    partial = service.write_partial_file("book", tmp_path / "out")
    assert partial.exists()
    assert ".partial" in partial.name
    assert partial.suffix == ".md"
    partial_text = partial.read_text()
    assert "CHUNK 1 CHƯA DỊCH" in partial_text
    assert "ký tự 5-6" in partial_text
    assert "dòng 3-3" in partial_text

    manifest = partial.with_suffix(".manifest.json")
    assert manifest.exists()
    import json
    data = json.loads(manifest.read_text())
    assert data["is_complete"] is False
    assert data["done_chunks"] == 1
    assert data["total_chunks"] == 3
    assert data["position_format"]["character_offsets"] == "0-based, end-exclusive"
    assert data["chunks"][0]["source_char_start"] == 0
    assert data["chunks"][0]["source_char_end"] == 3
    assert data["chunks"][0]["source_line_start"] == 1
    assert data["chunks"][0]["source_line_end"] == 2
    assert data["chunks"][1]["source_char_start"] == 5
    assert data["chunks"][1]["source_line_start"] == 3
    assert data["chunks"][1]["source_text"] == "c"
    assert data["chunks"][0]["source_text"] is None
