import pytest

from services.checkpoint_service import (
    CheckpointService,
    execution_drift,
    same_source_identity,
)


def _ident(**over):
    base = {
        "project_file": "book.txt", "project_slug": "p",
        "source_hash": "h" * 8, "chunker_version": "v2", "chunk_size": "2400",
        "prompt_hash": "p" * 8, "schema_version": "1.0",
        "provider_kind": "native_openai", "provider_id": "openai-test",
        "base_url": "https://api.openai.com/v1", "model": "gpt-test",
        "credential_mode": "default",
    }
    base.update({k: str(v) for k, v in over.items()})
    return base


@pytest.fixture
def ck(tmp_path):
    service = CheckpointService(str(tmp_path / "checkpoints"))
    service.init_session("book.txt", total_chunks=3, chunks_text=["a", "b", "c"],
                         identity=_ident())
    service.save_chunk("book.txt", 0, "a", "A", status="done")
    return service


def test_physical_key_khong_hash_lai(ck):
    physical = ck._get_db_path("book.txt").name
    assert ck.physical_checkpoint_key("book.txt") == physical
    assert ck.physical_checkpoint_key(physical) == physical          # đã vật lý
    assert ck.physical_checkpoint_key(physical[:-3]) == physical     # MD5 stem


def test_physical_key_khong_nhan_dam_file_nguon_ten_db(ck):
    # "notes.db" là tên file NGUỒN, không phải checkpoint vật lý → phải hash
    assert ck.physical_checkpoint_key("notes.db") == ck._get_db_path("notes.db").name


def test_same_checkpoint_key_logic_vs_vat_ly(ck):
    physical = ck._get_db_path("book.txt").name
    assert ck.same_checkpoint_key("book.txt", physical) is True
    assert ck.same_checkpoint_key(physical, physical[:-3]) is True
    assert ck.same_checkpoint_key("book.txt", "other.txt") is False
    assert ck.same_checkpoint_key(None, physical) is False


@pytest.mark.parametrize("key_kind", ["logical", "physical", "stem"])
def test_resolve_tra_ve_logical_filename(ck, key_kind):
    physical = ck._get_db_path("book.txt").name
    key = {"logical": "book.txt", "physical": physical, "stem": physical[:-3]}[key_kind]
    resolved = ck.resolve_checkpoint_key(key)
    assert resolved is not None
    assert resolved["checkpoint_key"] == physical
    assert resolved["filename"] == "book.txt"          # B2: KHÔNG được là tên vật lý
    assert resolved["resume_info"]["total_chunks"] == 3
    # filename dùng lại được ngay, không hash-of-hash
    idx = ck.get_done_pending_indices(resolved["filename"])
    assert idx["done_indices"] == [0]
    assert idx["pending_indices"] == [1, 2]


def test_resolve_khong_ton_tai_va_traversal(ck):
    assert ck.resolve_checkpoint_key("khong-co-file.txt") is None
    assert ck.resolve_checkpoint_key(None) is None
    assert ck.resolve_checkpoint_key("") is None
    for evil in ("../../etc/passwd", "..", "a/b.db", "\\\\srv\\x.db"):
        assert ck.resolve_checkpoint_key(evil) is None
        assert ck.physical_checkpoint_key(evil) is None


def test_resolve_namespace_recovery(ck):
    physical = ck._get_db_path("book.txt").name
    ck.clone_namespace("book.txt", f"{physical}.9a1b2c3d")
    resolved = ck.resolve_checkpoint_key(f"{physical}.9a1b2c3d")
    assert resolved is not None
    assert resolved["filename"] == f"{physical}.9a1b2c3d"
    assert resolved["checkpoint_key"] != physical      # namespace riêng, không đè nguồn


def test_identity_nguon_vs_thuc_thi():
    assert same_source_identity(_ident(), _ident(model="gpt-other")) is True
    assert same_source_identity(_ident(), _ident(source_hash="khac")) is False
    assert same_source_identity(_ident(), _ident(chunk_size=3000)) is False
    assert execution_drift(_ident(), _ident(model="gpt-other")) == ["model"]
    assert execution_drift(_ident(), _ident()) == []
