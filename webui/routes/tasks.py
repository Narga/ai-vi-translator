from flask import Blueprint, jsonify, request, Response
import json
import os
import time
from pathlib import Path
from services.task_store import TaskStore
from backend.infrastructure.progress.task_registry import TaskRegistry
from backend.infrastructure.progress.runtime_state import RuntimeState

tasks_bp = Blueprint("tasks", __name__)

_task_store: TaskStore | None = None


def _get_task_store() -> TaskStore:
    global _task_store
    workspace = os.environ.get("WORKSPACE_DIR", os.path.join(os.getcwd(), "workspace"))
    if _task_store is None or str(Path(_task_store.db_path).parent) != str(Path(workspace)):
        _task_store = TaskStore(workspace)
    return _task_store


_checkpoint_service_cache = {}
_last_reconcile_time = 0.0


def _get_checkpoint_service():
    """CheckpointService trỏ đúng workspace đang chạy (cached theo workspace path)."""
    global _checkpoint_service_cache
    store = _get_task_store()
    ck_dir = str(Path(store.db_path).parent / "checkpoints")
    if ck_dir not in _checkpoint_service_cache:
        from services.checkpoint_service import CheckpointService
        _checkpoint_service_cache[ck_dir] = CheckpointService(ck_dir)
    return _checkpoint_service_cache[ck_dir]


registry = TaskRegistry(store=_get_task_store())


def _get_task_resume_info(task: dict, checkpoint_service):
    """Read resume metadata qua resolver: logical | physical | stem — không hash lại."""
    resolved = checkpoint_service.resolve_checkpoint_key(task.get("checkpoint_key"))
    if not resolved:
        return None
    return resolved["resume_info"]


def _is_valid_resumable_task(task: dict, checkpoint_service) -> bool:
    """A resumable task must still have an incomplete, readable checkpoint."""
    info = _get_task_resume_info(task, checkpoint_service)
    return bool(info and info.get("can_resume") and info.get("total_chunks", 0) > 0)


@tasks_bp.route("/api/tasks", methods=["GET"])
def list_tasks():
    global _last_reconcile_time
    store = _get_task_store()
    # Tự động thu hồi lease và đánh dấu interrupted cho các task running đã mất heartbeat (>60s)
    # Throttle để tránh ghi đĩa liên tục trên mỗi poll request
    now = time.time()
    if now - _last_reconcile_time > 60.0:
        store.reconcile_lease_expired(lease_timeout_seconds=60.0)
        _last_reconcile_time = now

    tasks = store.list_tasks()
    checkpoint_service = _get_checkpoint_service()

    # Lọc bỏ các task "mồ côi" (project_slug rỗng, filename rỗng) và dọn dẹp logic đếm
    valid_tasks = []
    running_count = 0
    resumable_count = 0

    for t in tasks:
        if t["status"] in ("completed", "archived"):
            continue

        # Task mồ côi (chưa có project/filename thực sự)
        if not t.get("project_slug") or not t.get("filename"):
            if t["status"] == "running":
                # Chuyển state sang interrupted để không tính vào running
                store.update_status(t["job_id"], "interrupted")
                t["status"] = "interrupted"

        if t["status"] == "resumable" and not _is_valid_resumable_task(
            t, checkpoint_service
        ):
            # Status trong tasks.db có thể còn lại sau khi checkpoint đã bị
            # cleanup hoặc bị xóa. Không để bản ghi mồ côi làm sai số đếm và
            # không để người dùng bấm resume vào một task không thể phục hồi.
            store.update_status(
                t["job_id"],
                "archived",
                last_error="Checkpoint không còn tồn tại hoặc đã hoàn tất; task đã được lưu trữ.",
            )
            continue

        valid_tasks.append(t)
        if t["status"] == "running":
            running_count += 1
        elif t["status"] == "resumable":
            resumable_count += 1

    return jsonify({
        "tasks": valid_tasks,
        "running_count": running_count,
        "resumable_count": resumable_count,
    })


@tasks_bp.route("/api/tasks/<job_id>", methods=["GET"])
def get_task(job_id):
    store = _get_task_store()
    task_row = store.get_task_by_job_id(job_id)
    if task_row:
        completed = task_row.get("completed_chunks", 0)
        total = task_row.get("total_chunks", 0)

        if completed == 0 and task_row.get("status") in ("resumable", "paused", "failed", "interrupted") and task_row.get("checkpoint_key"):
            resolved = _get_checkpoint_service().resolve_checkpoint_key(task_row["checkpoint_key"])
            ck_info = resolved.get("resume_info") if resolved else None
            if ck_info:
                completed = ck_info.get("translated_count", 0)
                total = ck_info.get("total_chunks", total)

        # Trả về snapshot trực tiếp từ TaskStore
        return jsonify({
            "task_id": task_row.get("task_id"),
            "job_id": task_row.get("job_id"),
            "status": task_row.get("status"),
            "project_slug": task_row.get("project_slug"),
            "filename": task_row.get("filename"),
            "checkpoint_key": task_row.get("checkpoint_key"),
            "completed_chunks": completed,
            "total_chunks": total,
            "current_chunk": task_row.get("current_chunk", 0),
            "last_error": task_row.get("last_error"),
            "recovery_available": task_row.get("recovery_available", True),
            "created_at": task_row.get("created_at"),
            "updated_at": task_row.get("updated_at")
        })

    # Fallback cho các task tạo tạm trong RAM nhưng chưa lưu persistent (nếu có)
    task = registry.get_task(job_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task.to_dict())


@tasks_bp.route("/api/tasks/<job_id>/events", methods=["GET"])
def task_events(job_id):
    task = registry.get_task(job_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    def generate():
        cursor = 0
        last_ping = time.time()
        with task._cond:
            while True:
                if cursor < len(task.events):
                    event = task.events[cursor]
                    cursor += 1
                    yield f"data: {json.dumps(event)}\n\n"
                    last_ping = time.time()
                else:
                    if task.status in ("completed", "failed", "cancelled", "resumable", "paused",
                                       "closed_partial", "interrupted"):
                        break
                    task._cond.wait(timeout=1.0)
                    now = time.time()
                    if now - last_ping >= 10.0:
                        yield ": ping\n\n"
                        last_ping = now
        yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@tasks_bp.route("/api/tasks/<job_id>/cancel", methods=["POST"])
def cancel_task(job_id):
    registry.update_status(job_id, "cancelled")
    RuntimeState().request_cancel(job_id)
    return jsonify({"success": True})


@tasks_bp.route("/api/tasks/<job_id>/discard", methods=["POST"])
def discard_task(job_id: str):
    """
    Hủy bỏ và lưu trữ một task dang dở (resumable/interrupted/failed/paused).
    Chuyển trạng thái sang 'archived' để không còn hiển thị trên Header Pill.
    Tùy chọn xóa hoặc đóng băng file checkpoint.
    """
    store = _get_task_store()
    task = store.get_task_by_job_id(job_id)
    if not task:
        # Fallback tìm theo task_id nếu job_id truyền vào là task_id
        task = store.get_task(job_id)

    if not task:
        return jsonify({"error": "Không tìm thấy thông tin task."}), 404

    # Bảo vệ: Không cho phép discard task đang trong quá trình thực thi thực tế
    if task.get("status") in ("running", "started"):
        return jsonify({
            "error": "Task đang chạy. Vui lòng nhấn 'Dừng' trước khi bỏ task."
        }), 409

    # Đọc tùy chọn từ request body (nếu muốn xóa triệt để checkpoint vật lý)
    data = request.get_json(silent=True) or {}
    delete_physical_checkpoint = data.get("delete_checkpoint", False)

    deleted_checkpoint = False
    ck_key = task.get("checkpoint_key")
    if ck_key:
        ck_service = _get_checkpoint_service()
        if delete_physical_checkpoint:
            deleted_checkpoint = ck_service.delete_by_key(ck_key)
        else:
            # Mặc định: Resolve và đổi tên file sang .archived để an toàn dữ liệu
            resolved = ck_service.resolve_checkpoint_key(ck_key)
            if resolved and resolved.get("path"):
                db_path = Path(resolved["path"])
                if db_path.exists():
                    archived_path = db_path.with_suffix(db_path.suffix + ".archived")
                    try:
                        db_path.rename(archived_path)
                        deleted_checkpoint = True
                    except Exception:
                        pass

    # Cập nhật trạng thái sang 'archived' (sẽ tự động clear lease_token)
    target_id = task.get("task_id") or task.get("job_id")
    store.update_status(
        task_id=target_id,
        status="archived",
        last_error="Task đã bị người dùng hủy bỏ (Discarded)"
    )

    return jsonify({
        "success": True,
        "job_id": job_id,
        "task_id": target_id,
        "status": "archived",
        "deleted_checkpoint": deleted_checkpoint,
        "message": "Đã loại bỏ task thành công."
    })


@tasks_bp.route("/api/tasks/bulk-discard", methods=["POST"])
def bulk_discard_tasks():
    """
    Hủy bỏ hàng loạt task theo danh sách job_ids, theo project_slug hoặc discard tất cả các task không running.
    """
    data = request.get_json(silent=True) or {}
    job_ids = data.get("job_ids")
    project_slug = data.get("project_slug")
    all_resumable = data.get("all_resumable", False)
    delete_checkpoint = data.get("delete_checkpoint", False)

    store = _get_task_store()
    ck_service = _get_checkpoint_service()

    # Reconcile lease để chuyển các task running chết heartbeat thành interrupted
    store.reconcile_lease_expired(lease_timeout_seconds=30.0)
    tasks = store.list_tasks()

    def _is_discardable(t: dict) -> bool:
        return t.get("status") not in ("running", "started", "completed", "archived")

    if project_slug:
        target_tasks = [
            t for t in tasks
            if (t.get("project_slug") or "uncategorized") == project_slug
            and _is_discardable(t)
        ]
    elif all_resumable or not job_ids:
        target_tasks = [t for t in tasks if _is_discardable(t)]
    else:
        target_tasks = []
        for jid in job_ids:
            t = store.get_task_by_job_id(jid) or store.get_task(jid)
            if t and _is_discardable(t):
                target_tasks.append(t)

    if not target_tasks:
        return jsonify({"success": True, "count": 0, "message": "Không có task nào để bỏ."})

    success_count = 0
    for task in target_tasks:
        jid = task.get("job_id")
        tid = task.get("task_id") or jid
        ck_key = task.get("checkpoint_key")
        if ck_key:
            if delete_checkpoint:
                ck_service.delete_by_key(ck_key)
            else:
                resolved = ck_service.resolve_checkpoint_key(ck_key)
                if resolved and resolved.get("path"):
                    db_path = Path(resolved["path"])
                    if db_path.exists():
                        try:
                            db_path.rename(db_path.with_suffix(db_path.suffix + ".archived"))
                        except Exception:
                            pass
        store.update_status(task_id=tid, status="archived", last_error="Task đã bị người dùng hủy bỏ (Bulk Discard)")
        success_count += 1

    return jsonify({
        "success": True,
        "count": success_count,
        "message": f"Đã bỏ thành công {success_count} tác vụ."
    })


@tasks_bp.route("/api/tasks/cleanup-stale", methods=["POST"])
def cleanup_stale_tasks():
    """Tự động quét dọn các bản ghi task mồ côi hoặc checkpoint đã mất file vật lý."""
    store = _get_task_store()
    ck_service = _get_checkpoint_service()
    cleaned_count = 0

    tasks = store.list_tasks()
    for t in tasks:
        if t.get("status") == "resumable" and not _is_valid_resumable_task(t, ck_service):
            tid = t.get("task_id") or t["job_id"]
            store.update_status(tid, "archived", last_error="Tự động dọn dẹp checkpoint mồ côi")
            cleaned_count += 1

    return jsonify({"success": True, "cleaned_count": cleaned_count})



_TERMINAL_TASK_STATUSES = ("completed", "cancelled", "closed_partial", "archived")


@tasks_bp.route("/api/tasks/by-checkpoint/<checkpoint_key>", methods=["GET"])
def task_by_checkpoint(checkpoint_key: str):
    """Resolve checkpoint (logical | physical | stem) về task duy nhất.

    Dùng cho luồng "close partial từ modal resume" — frontend có checkpoint_key
    từ payload 409 nhưng chưa có task_id.
    """
    store = _get_task_store()
    ck = _get_checkpoint_service()
    resolved = ck.resolve_checkpoint_key(checkpoint_key)
    if not resolved:
        return jsonify({"error": "Không tìm thấy checkpoint"}), 404

    physical = resolved["checkpoint_key"]

    # 1) Đường nhanh: cột checkpoint_key khớp đúng tên vật lý.
    match = store.get_task_by_checkpoint_key(physical)

    # 2) Task cũ lưu tên LOGIC (B4) → quét và so bằng comparator canonical.
    #    Ưu tiên task chưa terminal; nếu chỉ có terminal thì lấy bản mới nhất.
    if not match:
        candidates = [
            t for t in store.list_tasks()
            if t.get("checkpoint_key") and ck.same_checkpoint_key(t["checkpoint_key"], physical)
        ]
        alive = [t for t in candidates if t.get("status") not in _TERMINAL_TASK_STATUSES]
        pool = alive or candidates
        if pool:
            match = max(pool, key=lambda t: t.get("created_at") or "")

    if not match:
        return jsonify({
            "error": "Không tìm thấy task cho checkpoint",
            "checkpoint_key": physical,
        }), 404

    return jsonify({
        "task_id": match["task_id"],
        "job_id": match["job_id"],
        "status": match["status"],
        "checkpoint_key": physical,
        "filename": resolved["filename"],
    })
