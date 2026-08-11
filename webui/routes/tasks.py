from flask import Blueprint, jsonify, request, Response
import json
import os
import time
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


registry = TaskRegistry(store=_get_task_store())


@tasks_bp.route("/api/tasks", methods=["GET"])
def list_tasks():
    store = _get_task_store()
    tasks = store.list_tasks()
    running = sum(1 for t in tasks if t["status"] in ("running", "resumable", "paused"))
    resumable = sum(1 for t in tasks if t["status"] == "resumable")
    return jsonify({
        "tasks": [t for t in tasks if t["status"] not in ("completed", "archived")],
        "running_count": running,
        "resumable_count": resumable,
    })


@tasks_bp.route("/api/tasks/<job_id>", methods=["GET"])
def get_task(job_id):
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
    RuntimeState().request_cancel()
    return jsonify({"success": True})
