"""Unit tests cho Phase 8: Auto-Merge, Standard Manifest Contract & Verification Gate.

Kiểm tra:
- Verification Gate: kiểm tra 100% chunk 0..total-1 trong SQLite & Zero-marker sanity check.
- Standard Manifest Contract v1.0: đầy đủ metadata, danh sách done_indices, sha256 output_hash.
- Atomic File Write: ghi an toàn qua tmp + fsync + atomic replace.
- Auto-merge / output generation sau recovery tạo đủ output file và manifest sidecar.
"""
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.executor import TranslationExecutor
from services.checkpoint_service import CheckpointService


def test_verification_gate_completeness_and_marker_check(tmp_path):
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    # 1. Tạo checkpoint 5 chunks, dịch đủ 5 chunks hợp lệ
    ck_service.init_session(
        filename="valid.txt",
        total_chunks=5,
        chunks_text=[f"chunk {i}" for i in range(5)],
    )
    for i in range(5):
        ck_service.save_chunk("valid.txt", i, f"chunk {i}", f"dịch {i}", "key-1")

    is_complete, details = ck_service.verify_checkpoint_completeness("valid.txt")
    assert is_complete is True
    assert details["total_chunks"] == 5
    assert details["done_count"] == 5
    assert len(details["missing_indices"]) == 0
    assert len(details["marker_violations"]) == 0

    # 2. Checkpoint thiếu chunk 3 -> Verification Gate phải FAIL
    ck_service.init_session(
        filename="missing.txt",
        total_chunks=5,
        chunks_text=[f"chunk {i}" for i in range(5)],
    )
    for i in [0, 1, 2, 4]:  # Bỏ qua chunk 3
        ck_service.save_chunk("missing.txt", i, f"chunk {i}", f"dịch {i}", "key-1")

    is_comp_miss, det_miss = ck_service.verify_checkpoint_completeness("missing.txt")
    assert is_comp_miss is False
    assert det_miss["missing_indices"] == [3]
    assert 3 in det_miss["pending_indices"]

    # 3. Checkpoint có marker placeholder "[CHUNK 2 CHƯA DỊCH...]" trong text -> Verification Gate phải FAIL
    ck_service.init_session(
        filename="marker_violation.txt",
        total_chunks=3,
        chunks_text=["c0", "c1", "c2"],
    )
    ck_service.save_chunk("marker_violation.txt", 0, "c0", "dịch 0", "key-1")
    ck_service.save_chunk("marker_violation.txt", 1, "c1", "[CHUNK 2 CHƯA DỊCH | nguồn: 10-20]", "key-1")
    ck_service.save_chunk("marker_violation.txt", 2, "c2", "dịch 2", "key-1")

    is_comp_mark, det_mark = ck_service.verify_checkpoint_completeness("marker_violation.txt")
    assert is_comp_mark is False
    assert len(det_mark["marker_violations"]) > 0
    assert det_mark["marker_violations"][0]["index"] == 1


def test_standard_manifest_contract_v1(tmp_path):
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    ck_service.init_session(
        filename="manifest_test.txt",
        total_chunks=3,
        chunks_text=["a", "b", "c"],
    )
    for i in range(3):
        ck_service.save_chunk("manifest_test.txt", i, f"source {i}", f"trans {i}", "key-1")

    output_text = "trans 0\n\ntrans 1\n\ntrans 2"
    expected_hash = f"sha256:{hashlib.sha256(output_text.encode('utf-8')).hexdigest()}"

    manifest = ck_service.create_manifest(
        checkpoint_key="manifest_test.txt",
        source_task_id="source-task-123",
        recovery_task_id="rec-task-456",
        provider_id="openai-test",
        model="test-model",
        output_text=output_text,
    )

    assert manifest["manifest_version"] == "1.0"
    assert manifest["source_task_id"] == "source-task-123"
    assert manifest["recovery_task_id"] == "rec-task-456"
    assert manifest["total_chunks"] == 3
    assert manifest["done_indices"] == [0, 1, 2]
    assert manifest["pending_indices"] == []
    assert manifest["output_hash"] == expected_hash
    assert manifest["provider_id"] == "openai-test"
    assert manifest["model"] == "test-model"
    assert manifest["is_complete"] is True
    assert "timestamp" in manifest


def test_atomic_write_file(tmp_path):
    ck_service = CheckpointService(str(tmp_path / "ck"))
    target = tmp_path / "subdir" / "output.txt"
    content = "Nội dung kiểm tra atomic write\nDòng 2"

    result_path = ck_service.atomic_write_file(target, content)
    assert result_path == target
    assert target.exists()
    assert target.read_text(encoding="utf-8") == content

    # Đảm bảo không để lại file rác .tmp trong thư mục
    tmp_files = list(target.parent.glob(".*.tmp.*"))
    assert len(tmp_files) == 0


def test_recovery_execution_generates_manifest_and_atomic_output(tmp_path, monkeypatch):
    """End-to-End recovery hoàn tất: tạo file output và manifest sidecar đồng bộ."""
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    # Checkpoint gốc có 4 chunks, chunk 0 và 1 đã xong, 2 và 3 pending
    ck_service.init_session(
        filename="source_ck.txt",
        total_chunks=4,
        chunks_text=["chunk 0", "chunk 1", "chunk 2", "chunk 3"],
    )
    ck_service.save_chunk("source_ck.txt", 0, "chunk 0", "dịch 0", "key-1")
    ck_service.save_chunk("source_ck.txt", 1, "chunk 1", "dịch 1", "key-1")

    # Checkpoint recovery (clone từ source)
    ck_service.clone_checkpoint("source_ck.txt", "rec_ck.txt")

    def fake_rt(original_chunk=None, *args, **kwargs):
        return f"[dịch tiếp {original_chunk}]", "success", "key-ok"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    out_file = tmp_path / "translated" / "book.recovery.12345678.txt"
    executor = TranslationExecutor(
        api_keys=["key"],
        config={"provider_id": "test-provider", "model_name": "test-model"},
    )
    executor.checkpoint_service = ck_service

    events = []
    res = executor.recover_from_checkpoint(
        source_checkpoint_key="source_ck.txt",
        recovery_checkpoint_key="rec_ck.txt",
        output_file_path=out_file,
        progress_callback=lambda e: events.append(e),
        job_id="rec-job-12345678",
    )

    assert res is not None
    assert out_file.exists()
    
    # Manifest sidecar được tạo bên cạnh file output
    manifest_file = out_file.with_suffix(".manifest.json")
    assert manifest_file.exists()

    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest_data["manifest_version"] == "1.0"
    assert manifest_data["is_complete"] is True
    assert manifest_data["total_chunks"] == 4
    assert manifest_data["done_indices"] == [0, 1, 2, 3]
    assert manifest_data["recovery_task_id"] == "rec-job-12345678"
    assert manifest_data["output_hash"] == f"sha256:{hashlib.sha256(res.encode('utf-8')).hexdigest()}"


def test_mandatory_manifest_failure_aborts_task(tmp_path, monkeypatch):
    """Phase 8: Nếu tạo/ghi manifest thất bại -> Không được hoàn tất task,

    không được xóa checkpoint, và phải emit task_failed status manifest_generation_failed.
    """
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))
    ck_service.init_session(
        filename="manifest_fail.txt",
        total_chunks=2,
        chunks_text=["chunk 0", "chunk 1"],
    )

    def fake_rt(original_chunk=None, *args, **kwargs):
        return f"[dịch {original_chunk}]", "success", "key-ok"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    # Giả lập lỗi khi create_manifest
    def fake_create_manifest(*args, **kwargs):
        raise RuntimeError("Disk I/O error on manifest creation")

    monkeypatch.setattr(ck_service, "create_manifest", fake_create_manifest)

    out_file = tmp_path / "output_fail.txt"
    executor = TranslationExecutor(api_keys=["key"], config={"chunk_size": 2400})
    executor.checkpoint_service = ck_service

    events = []
    res = executor.translate_text(
        text="chunk 0\n\nchunk 1",
        output_filename="manifest_fail.txt",
        output_file_path=out_file,
        progress_callback=lambda e: events.append(e),
    )

    # 1. translate_text trả về None
    assert res is None

    # 2. Không có event "complete"
    assert not any(e.get("type") == "complete" for e in events)

    # 3. Có event "task_failed" với status manifest_generation_failed
    failed_evts = [e for e in events if e.get("type") == "task_failed"]
    assert len(failed_evts) > 0
    # 4. Checkpoint database KHÔNG bị xóa (vẫn còn nguyên để retry/recovery)
    assert ck_service._get_db_path("manifest_fail.txt").exists() is True
