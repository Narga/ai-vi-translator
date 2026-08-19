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
    if _task_store is None:
        workspace = os.environ.get("WORKSPACE_DIR", os.path.join(os.getcwd(), "workspace"))
        _task_store = TaskStore(workspace)
    return _task_store


def _get_checkpoint_service():
    """CheckpointService trỏ đúng workspace đang chạy.

    L9: `list_tasks` đã tự dựng đường dẫn từ `store.db_path` (dòng 50-52) nhưng `get_task`
    lại gọi `CheckpointService()` không tham số → dùng mặc định `workspace/checkpoints`
    theo CWD. Khi test set WORKSPACE_DIR sang tmp_path, hai hàm đọc HAI thư mục khác nhau:
    `list_tasks` archive task còn `get_task` vẫn thấy checkpoint (hoặc ngược lại).
    """
    from services.checkpoint_service import CheckpointService
    store = _get_task_store()
    return CheckpointService(str(Path(store.db_path).parent / "checkpoints"))


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
    store = _get_task_store()
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
        for evt, cursor in task.iter_events(cursor):
            yield f"data: {json.dumps(evt)}\n\n"
        yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@tasks_bp.route("/api/tasks/<job_id>/cancel", methods=["POST"])
def cancel_task(job_id):
    registry.update_status(job_id, "cancelled")
    RuntimeState().request_cancel(job_id)
    return jsonify({"success": True})


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
