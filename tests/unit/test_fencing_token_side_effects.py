"""Unit tests cho Phase 7B: Fencing Token on All Side Effects & Zombie Worker Abort.

Kiểm tra:
- Fencing token & lease_epoch CAS guards trên mọi side-effect DB: update_status, append_event, update_recovery_task.
- Zombie Worker abort tại 5 điểm guard (trước provider, sau provider - drop response, trước save_chunk, trước assemble, trước terminal status).
- Không để lại dữ liệu rác hay làm hỏng checkpoint khi worker cũ (zombie) thức dậy muộn.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.executor import TranslationExecutor
from services.checkpoint_service import CheckpointService
from services.task_store import TaskStore


class FakeKeepAlive:
    """Mock LeaseKeepAlive cho unit testing các guard abort."""
    def __init__(self, abort_requested: bool = False):
        self.abort_requested = abort_requested


def test_db_side_effect_fencing_guards(tmp_path):
    """Kiểm tra CAS check trên update_status, append_event, update_recovery_task."""
    store = TaskStore(str(tmp_path))
    task_id = "test-fencing-task"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Test Task",
        project_slug="p",
        filename="book.txt",
        total_chunks=10,
    )
    token, epoch = store.acquire_lease(task_id)
    assert epoch == 1

    # 1. Update status với đúng epoch & token -> Thành công
    ok = store.update_status(
        task_id, status="running", lease_epoch=1, lease_token=token, completed_chunks=3
    )
    assert ok is True
    assert store.get_task(task_id)["completed_chunks"] == 3

    # 2. Update status với sai token -> Thất bại
    ok_wrong_tok = store.update_status(
        task_id, status="completed", lease_epoch=1, lease_token="wrong-token", completed_chunks=10
    )
    assert ok_wrong_tok is False
    assert store.get_task(task_id)["status"] == "running"

    # 3. Update status với stale epoch -> Thất bại, không ghi đè DB
    ok_stale = store.update_status(task_id, status="completed", lease_epoch=0, completed_chunks=10)
    assert ok_stale is False
    assert store.get_task(task_id)["status"] == "running"  # Không bị đổi thành completed
    assert store.get_task(task_id)["completed_chunks"] == 3

    # 4. Append event với đúng vs sai token/epoch
    evt_ok = store.append_event(
        task_id, {"type": "progress", "percent": 50}, lease_epoch=1, lease_token=token
    )
    assert evt_ok is True
    assert len(store.iter_events(task_id)) == 1

    evt_wrong_tok = store.append_event(
        task_id, {"type": "progress", "percent": 99}, lease_epoch=1, lease_token="wrong-token"
    )
    assert evt_wrong_tok is False
    assert len(store.iter_events(task_id)) == 1  # Không bị thêm event rác

    evt_stale = store.append_event(task_id, {"type": "progress", "percent": 99}, lease_epoch=0)
    assert evt_stale is False
    assert len(store.iter_events(task_id)) == 1

    # 5. Update recovery task với wrong token / stale epoch
    rec_ok = store.update_recovery_task(
        task_id, lease_epoch=1, lease_token=token, last_error="test-err"
    )
    assert rec_ok is True
    assert store.get_task(task_id)["last_error"] == "test-err"

    rec_wrong_tok = store.update_recovery_task(
        task_id, lease_epoch=1, lease_token="wrong-token", last_error="zombie-overwrite"
    )
    assert rec_wrong_tok is False
    assert store.get_task(task_id)["last_error"] == "test-err"

    rec_stale = store.update_recovery_task(task_id, lease_epoch=0, last_error="zombie-overwrite")
    assert rec_stale is False
    assert store.get_task(task_id)["last_error"] == "test-err"


def test_registry_ram_isolation_on_cas_rejection(tmp_path):
    """Kiểm tra TaskRegistry: Nếu persistent store CAS thất bại vì mất lease,

    không được cập nhật in-memory RAM event list hay status.
    """
    from backend.infrastructure.progress.task_registry import TaskRegistry

    store = TaskStore(str(tmp_path))
    registry = TaskRegistry(store=store)
    task_id = "reg-test-task"
    store.create_task(job_id=task_id, kind="translation", title="T", project_slug="p", filename="f.txt")
    token, epoch = store.acquire_lease(task_id)

    # 1. Append event với wrong epoch -> Bị store reject -> In-memory không thêm
    ok = registry.append_event(
        task_id, {"type": "info", "message": "zombie message"}, lease_epoch=epoch - 1
    )
    assert ok is False
    in_mem_task = registry.get_task(task_id)
    assert len(in_mem_task.events) == 0

    # 2. Append event với correct epoch -> Thành công -> In-memory có event
    ok_valid = registry.append_event(
        task_id, {"type": "info", "message": "valid message"}, lease_epoch=epoch, lease_token=token
    )
    assert ok_valid is True
    assert len(in_mem_task.events) == 1


def test_checkpoint_service_save_chunk_fencing_cas(tmp_path):
    """Kiểm tra CheckpointService.save_chunk atomic CAS:

    Worker có lease_epoch cũ hơn metadata checkpoint sẽ bị reject.
    """
    ck_service = CheckpointService(str(tmp_path))
    ck_name = "test_fencing_ck.txt"
    ck_service.init_session(filename=ck_name, total_chunks=3)

    # 1. Ghi chunk 0 với lease_epoch = 2 -> Thành công
    saved1 = ck_service.save_chunk(
        filename=ck_name,
        chunk_index=0,
        original_text="c0",
        translated_text="d0",
        lease_epoch=2,
        lease_token="token-epoch-2",
    )
    assert saved1 is True
    assert len(ck_service.get_translated_chunks(ck_name)) == 1

    # 2. Zombie worker với lease_epoch = 1 cố ghi đè chunk 0 -> Bị reject!
    saved_zombie = ck_service.save_chunk(
        filename=ck_name,
        chunk_index=0,
        original_text="c0",
        translated_text="zombie-d0",
        lease_epoch=1,
        lease_token="token-epoch-1",
    )
    assert saved_zombie is False
    # Checkpoint vẫn giữ bản dịch hợp lệ của epoch 2
    chunks = ck_service.get_translated_chunks(ck_name)
    assert chunks[0] == "d0"


def test_zombie_worker_guard_drop_response_after_network_call(tmp_path, monkeypatch):
    """Guard 2 & Guard 3: Worker mất lease trong lúc chờ mạng LLM ->

    Response trả về bị hủy (dropped), KHÔNG được ghi vào checkpoint database.
    """
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))
    ck_service.init_session(
        filename="test_zombie.txt",
        total_chunks=3,
        chunks_text=["chunk 0", "chunk 1", "chunk 2"],
    )

    keep_alive = FakeKeepAlive(abort_requested=False)
    call_log = []

    def fake_rt(original_chunk=None, *args, **kwargs):
        call_log.append(original_chunk)
        # Giả lập trong lúc LLM đang trả lời, lease bị thu hồi!
        keep_alive.abort_requested = True
        return "[kết quả dịch zombie]", "success", "key-ok"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    events = []
    executor = TranslationExecutor(api_keys=["test-key"], config={"chunk_size": 2400})
    executor.checkpoint_service = ck_service

    result = executor.translate_text(
        text="chunk 0\n\nchunk 1\n\nchunk 2",
        output_filename="test_zombie.txt",
        output_file_path=tmp_path / "out.txt",
        progress_callback=lambda e: events.append(e),
        lease_keep_alive=keep_alive,
    )

    # 1. Kết quả trả về phải là None (bị abort)
    assert result is None

    # 2. API call đã được gọi một lần
    assert len(call_log) == 1

    # 3. NHƯNG Guard 2 & Guard 3 đã chặn: checkpoint KHÔNG được lưu chunk nào!
    translated = ck_service.get_translated_chunks("test_zombie.txt")
    assert len(translated) == 0

    # 4. Event task_failed hoặc cancelled được emit
    failed_evts = [e for e in events if e.get("type") in ("task_failed", "cancelled")]
    assert len(failed_evts) > 0
    assert "lease_lost" in str(failed_evts[0])


from tests.conftest import E2E_CHUNK_SIZE, make_chunked_source


def test_zombie_worker_guard_aborts_before_assemble_and_output_write(tmp_path, monkeypatch):
    """Guard 4: Nếu lease bị mất trước khi assemble ->

    Không ghi file output cuối cùng ra đĩa.
    """
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    keep_alive = FakeKeepAlive(abort_requested=False)

    chunk_count = [0]

    def fake_rt(original_chunk=None, *args, **kwargs):
        chunk_count[0] += 1
        if chunk_count[0] == 2:
            # Mất lease ngay sau khi dịch xong chunk cuối nhưng trước khi ghi file
            keep_alive.abort_requested = True
        return f"[dịch chunk {chunk_count[0]}]", "success", "key-ok"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    out_file = tmp_path / "final_output.txt"
    executor = TranslationExecutor(api_keys=["test-key"], config={"chunk_size": E2E_CHUNK_SIZE})
    executor.checkpoint_service = ck_service

    result = executor.translate_text(
        text=make_chunked_source(2),
        output_filename="test_assemble.txt",
        output_file_path=out_file,
        lease_keep_alive=keep_alive,
    )

    # 1. translate_text thất bại và trả về None
    assert result is None

    # 2. File output cuối cùng KHÔNG được tạo
    assert not out_file.exists()


def test_executor_save_chunk_cas_failure_aborts_production_pipeline(tmp_path, monkeypatch):
    """Kiểm tra production path: save_chunk bị từ chối do lease mismatch ->

    TranslationExecutor dừng ngay lập tức với lỗi lease_lost, không emit complete và không ghi output.
    """
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    class MockKeepAlive:
        def __init__(self, epoch=1, token="tok-1"):
            self.lease_epoch = epoch
            self.lease_token = token
        def abort_reason(self):
            return None

    keep_alive = MockKeepAlive(epoch=1, token="tok-1")

    # Khi dịch chunk 1, một worker khác nhảy vào nâng epoch checkpoint lên 2
    def fake_rt(original_chunk=None, *args, **kwargs):
        if "SEG001" in (original_chunk or ""):
            # Worker 2 ghi đè metadata checkpoint với epoch 2
            ck_service.save_chunk(
                filename="test_prod_cas.txt",
                chunk_index=1,
                original_text="c1",
                translated_text="w2-trans",
                lease_epoch=2,
                lease_token="tok-2",
            )
        return "[dịch]", "success", "key-ok"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    out_file = tmp_path / "out_prod_cas.txt"
    events = []
    executor = TranslationExecutor(api_keys=["test-key"], config={"chunk_size": E2E_CHUNK_SIZE})
    executor.checkpoint_service = ck_service

    result = executor.translate_text(
        text=make_chunked_source(2),
        output_filename="test_prod_cas.txt",
        output_file_path=out_file,
        progress_callback=lambda e: events.append(e),
        lease_keep_alive=keep_alive,
    )

    assert result is None
    assert not out_file.exists()
    # Checkpoint chunk 1 vẫn là của worker 2
    assert ck_service.get_translated_chunks("test_prod_cas.txt")[1] == "w2-trans"
    # Event error lease_lost được phát sinh
    err_evts = [e for e in events if e.get("type") in ("error", "task_failed")]
    assert any(e.get("status") == "lease_lost" or "lease_lost" in str(e) for e in err_evts)


def test_atomic_write_pre_replace_check_and_manifest_cleanup(tmp_path):
    """Kiểm tra pre_replace_check và xóa sạch orphan file khi manifest generation fail."""
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    target_file = tmp_path / "protected_target.txt"

    # 1. pre_replace_check trả False -> atomic_write_file raise RuntimeError và không tạo target_file
    with pytest.raises(RuntimeError, match="Lease lost before atomic file replace"):
        ck_service.atomic_write_file(
            target_file,
            "Nội dung cần ghi",
            pre_replace_check=lambda: False,
        )
    assert not target_file.exists()

    # 2. pre_replace_check trả True -> Ghi thành công
    ck_service.atomic_write_file(
        target_file,
        "Nội dung cần ghi",
        pre_replace_check=lambda: True,
    )
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == "Nội dung cần ghi"


def test_save_chunk_durable_rejection_when_worker_b_steals_lease_before_checkpoint_touch(tmp_path):
    """Race condition 1: Worker B đã chiếm lease trong tasks.db (epoch 2) nhưng chưa kịp ghi checkpoint.

    Zombie Worker A (epoch 1) thức dậy gọi save_chunk() -> Bị CheckpointService từ chối thông qua
    durable lease validation từ tasks.db, không làm hỏng dữ liệu.
    """
    from backend.infrastructure.progress.lease_manager import LeaseKeepAlive

    store = TaskStore(str(tmp_path))
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    task_id = "task-race-durable-cas"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Durable Race",
        project_slug="p",
        filename="durable_race.txt",
        total_chunks=3,
    )
    ck_service.init_session("durable_race.txt", total_chunks=3)

    # 1. Worker A acquire lease (epoch 1, token A)
    leaseA = store.acquire_lease(task_id, lease_timeout_seconds=0.05)
    tokenA, epochA = leaseA
    assert epochA == 1

    keep_alive_A = LeaseKeepAlive(
        task_id=task_id,
        lease_token=tokenA,
        lease_epoch=epochA,
        task_store=store,
    )

    # Worker A lưu thành công chunk 0
    ok0 = ck_service.save_chunk(
        "durable_race.txt", 0, "c0", "trans0_A",
        lease_epoch=epochA, lease_token=tokenA,
        lease_validator=keep_alive_A.is_durable_valid,
    )
    assert ok0 is True
    assert len(ck_service.get_translated_chunks("durable_race.txt")) == 1

    # 2. Worker A ngủ quên; lease hết hạn; Worker B chiếm lease (epoch 2, token B)
    import time
    time.sleep(0.06)
    leaseB = store.acquire_lease(task_id, lease_timeout_seconds=0.05)
    assert leaseB is not None
    tokenB, epochB = leaseB
    assert epochB == 2

    # CHÚ Ý: Worker B CHƯA ghi bất kỳ chunk nào vào checkpoint SQLite!
    # Metadata trong checkpoint SQLite vẫn đang lưu epoch 1 / token A.

    # 3. Zombie Worker A thức dậy và cố ghi chunk 1 với epoch 1 và token A
    zombie_saved = ck_service.save_chunk(
        "durable_race.txt", 1, "c1", "zombie_trans1_A",
        lease_epoch=epochA, lease_token=tokenA,
        lease_validator=keep_alive_A.is_durable_valid,
    )

    # 4. Durable check PHẢI phát hiện tasks.db đã chuyển sang epoch 2 và REJECT Zombie Worker A!
    assert zombie_saved is False
    # Checkpoint SQLite không chứa chunk 1 của Zombie Worker A
    translated = ck_service.get_translated_chunks("durable_race.txt")
    assert 1 not in translated
    assert len(translated) == 1


def test_atomic_write_durable_lease_rejection_before_os_replace(tmp_path):
    """Race condition 2: Worker A dịch xong toàn bộ chunks, ghi xong file .tmp và fsync,

    nhưng ngay trước khi os.replace(), Worker B chiếm lease trong tasks.db.
    pre_replace_check kích hoạt durable check vào tasks.db -> Phát hiện mất lease ->
    Hủy bỏ os.replace(), xóa sạch file .tmp và raise RuntimeError.
    """
    from backend.infrastructure.progress.lease_manager import LeaseKeepAlive
    import time

    store = TaskStore(str(tmp_path))
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    task_id = "task-race-last-mile"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Last Mile Race",
        project_slug="p",
        filename="last_mile.txt",
        total_chunks=1,
    )

    leaseA = store.acquire_lease(task_id, lease_timeout_seconds=0.05)
    tokenA, epochA = leaseA

    keep_alive_A = LeaseKeepAlive(
        task_id=task_id,
        lease_token=tokenA,
        lease_epoch=epochA,
        task_store=store,
    )

    out_file = tmp_path / "final_output.txt"

    def pre_replace_hook():
        # Giả lập đúng lúc trước khi replace: Worker A bị trễ, Worker B chiếm lease trong tasks.db!
        time.sleep(0.06)
        stolen = store.acquire_lease(task_id, lease_timeout_seconds=0.05)
        assert stolen is not None
        # Worker A kiểm tra durable lease -> Phải trả False
        return keep_alive_A.is_durable_valid()

    # Thao tác atomic_write_file phải bị chặn
    with pytest.raises(RuntimeError, match="Lease lost before atomic file replace"):
        ck_service.atomic_write_file(
            out_file,
            "Nội dung dịch của Worker A",
            pre_replace_check=pre_replace_hook,
        )

    # Output file cuối cùng KHÔNG được tạo
    assert not out_file.exists()
    # File tạm .tmp cũng đã bị dọn sạch
    tmp_files = list(tmp_path.glob(".*tmp*"))
    assert len(tmp_files) == 0


def test_lease_keep_alive_fail_closed_on_db_exception():
    """Kiểm tra tính chất Fail-Closed của LeaseKeepAlive.is_durable_valid():
    Nếu tasks.db ném ngoại lệ (lỗi disk, lock timeout), hàm PHẢI trả về False
    và set abort_requested = True để bảo vệ an toàn dữ liệu.
    """
    import sqlite3
    from backend.infrastructure.progress.lease_manager import LeaseKeepAlive

    class BrokenStore:
        def is_lease_valid(self, *args, **kwargs):
            raise sqlite3.OperationalError("disk I/O error or database is locked")

    aborted = []
    keep_alive = LeaseKeepAlive(
        task_id="broken-task",
        lease_token="tok",
        lease_epoch=1,
        task_store=BrokenStore(),
        on_abort=lambda: aborted.append(True),
    )

    assert keep_alive.is_durable_valid() is False
    assert keep_alive.abort_requested is True
    assert len(aborted) == 1


def test_executor_translate_text_durable_abort_before_last_mile_replace(tmp_path, monkeypatch):
    """Kiểm tra TranslationExecutor.translate_text() cấp end-to-end với Last-mile Fencing:
    Worker A hoàn tất dịch tất cả các chunk thành công và bắt đầu bước assemble output.
    Trước khi os.replace() diễn ra, Worker B chiếm lease trong tasks.db (epoch 2).
    TranslationExecutor kích hoạt _durable_lease_guard() -> atomic_write_file raise RuntimeError ->
    TranslationExecutor dọn dẹp sạch file tạm, không tạo file output, không tạo manifest, và trả về None.
    """
    from backend.infrastructure.progress.lease_manager import LeaseKeepAlive
    import time

    store = TaskStore(str(tmp_path))
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    task_id = "task-executor-last-mile"
    store.create_task(
        job_id=task_id,
        kind="translation",
        title="Executor Last Mile",
        project_slug="p",
        filename="exec_last_mile.txt",
        total_chunks=2,
    )

    leaseA = store.acquire_lease(task_id, lease_timeout_seconds=0.05)
    assert leaseA is not None
    tokenA, epochA = leaseA

    keep_alive_A = LeaseKeepAlive(
        task_id=task_id,
        lease_token=tokenA,
        lease_epoch=epochA,
        task_store=store,
    )

    # Fake LLM translate: tại chunk cuối cùng, Worker B cướp lease trong tasks.db sau khi dịch xong
    def fake_rt(original_chunk=None, *args, **kwargs):
        if "SEG001" in (original_chunk or ""):
            # Ngay sau khi dịch chunk cuối, Worker A bị trễ và Worker B chiếm lease trong tasks.db
            time.sleep(0.06)
            stolen = store.acquire_lease(task_id, lease_timeout_seconds=0.05)
            assert stolen is not None
            assert stolen[1] == 2  # epoch 2
        return "[dịch]", "success", "key-ok"

    monkeypatch.setattr("core.executor.robust_translate", fake_rt)

    out_file = tmp_path / "final_exec_output.txt"
    manifest_file = out_file.with_suffix(".manifest.json")
    events = []

    executor = TranslationExecutor(api_keys=["test-key"], config={"chunk_size": E2E_CHUNK_SIZE})
    executor.checkpoint_service = ck_service

    result = executor.translate_text(
        text=make_chunked_source(2),
        output_filename="exec_last_mile.txt",
        output_file_path=out_file,
        progress_callback=lambda e: events.append(e),
        lease_keep_alive=keep_alive_A,
    )

    # 1. translate_text phải trả về None do lỗi last-mile replace
    assert result is None

    # 2. File output và Manifest sidecar KHÔNG được tạo
    assert not out_file.exists()
    assert not manifest_file.exists()

    # 3. Không còn file tạm .tmp nào còn sót lại trên filesystem
    tmp_files = list(tmp_path.glob(".*tmp*"))
    assert len(tmp_files) == 0


def test_lease_keep_alive_fail_closed_when_store_lacks_validator():
    """Kiểm tra Fail-Closed khi task_store thiếu method is_lease_valid:
    Hàm is_durable_valid PHẢI trả về False và đánh dấu abort_requested.
    """
    from backend.infrastructure.progress.lease_manager import LeaseKeepAlive

    class StoreWithoutValidator:
        pass

    aborted = []
    keep_alive = LeaseKeepAlive(
        task_id="no-validator-task",
        lease_token="tok",
        lease_epoch=1,
        task_store=StoreWithoutValidator(),
        on_abort=lambda: aborted.append(True),
    )

    assert keep_alive.is_durable_valid() is False
    assert keep_alive.abort_requested is True
    assert len(aborted) == 1


def test_checkpoint_save_chunk_rejects_when_metadata_token_is_missing_at_same_epoch(tmp_path):
    """Kiểm tra Checkpoint CAS từ chối ghi khi metadata checkpoint có epoch nhưng thiếu token:
    Nếu metadata có lease_epoch = '2' nhưng lease_token bị thiếu/hỏng -> Từ chối ghi.
    """
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))
    ck_service.init_session("corrupted_meta.txt", total_chunks=2)

    # Giả lập metadata hỏng: có lease_epoch nhưng không có lease_token
    conn = ck_service._get_connection("corrupted_meta.txt")
    conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('lease_epoch', '2')")
    conn.commit()

    # Ghi chunk với cùng epoch 2 nhưng metadata thiếu token -> PHẢI REJECT
    saved = ck_service.save_chunk(
        "corrupted_meta.txt",
        chunk_index=0,
        original_text="c0",
        translated_text="t0",
        lease_epoch=2,
        lease_token="valid-tok",
    )
    assert saved is False


def test_cross_task_resume_checkpoint_save_chunk_success(tmp_path):
    """Kiểm tra Task B resume checkpoint của Task A:
    Task A (epoch 1, token A) ghi chunk 0 thành công rồi dừng.
    Task B là một task mới (epoch 1, token B) resume checkpoint và ghi chunk 1 với lease_validator hợp lệ.
    Save chunk 1 PHẢI THÀNH CÔNG và cập nhật token của checkpoint sang token B.
    """
    from backend.infrastructure.progress.lease_manager import LeaseKeepAlive

    store = TaskStore(str(tmp_path))
    ck_dir = tmp_path / "checkpoints"
    ck_service = CheckpointService(str(ck_dir))

    # Task A tạo và ghi chunk 0
    task_id_A = "task-A"
    store.create_task(job_id=task_id_A, kind="translation", title="T1", project_slug="p", filename="book.txt", total_chunks=3)
    tokenA, epochA = store.acquire_lease(task_id_A)
    keep_alive_A = LeaseKeepAlive(task_id=task_id_A, lease_token=tokenA, lease_epoch=epochA, task_store=store)

    saved0 = ck_service.save_chunk(
        "book.txt", 0, "c0", "trans0",
        lease_epoch=epochA, lease_token=tokenA,
        lease_validator=keep_alive_A.is_durable_valid,
    )
    assert saved0 is True

    # Task A kết thúc / gián đoạn
    store.update_status(task_id_A, "interrupted")

    # Task B (task_id khác, epoch 1 mới, token B mới) resume checkpoint
    task_id_B = "task-B"
    store.create_task(job_id=task_id_B, kind="translation", title="T2", project_slug="p", filename="book.txt", total_chunks=3)
    tokenB, epochB = store.acquire_lease(task_id_B)
    assert epochB == 1
    assert tokenB != tokenA
    keep_alive_B = LeaseKeepAlive(task_id=task_id_B, lease_token=tokenB, lease_epoch=epochB, task_store=store)

    # Task B ghi chunk 1: PHẢI THÀNH CÔNG nhờ lease_validator xác nhận quyền sở hữu từ tasks.db
    saved1 = ck_service.save_chunk(
        "book.txt", 1, "c1", "trans1",
        lease_epoch=epochB, lease_token=tokenB,
        lease_validator=keep_alive_B.is_durable_valid,
    )
    assert saved1 is True

    # Kiểm tra cả 2 chunks đều có trong checkpoint
    chunks = ck_service.get_translated_chunks("book.txt")
    assert len(chunks) == 2
    assert chunks[0] == "trans0"
    assert chunks[1] == "trans1"





