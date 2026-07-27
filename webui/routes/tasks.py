from flask import Blueprint, jsonify, request, Response
import json
import time
from backend.infrastructure.progress.task_registry import TaskRegistry
from backend.infrastructure.progress.runtime_state import RuntimeState

tasks_bp = Blueprint("tasks", __name__)
registry = TaskRegistry()

@tasks_bp.route("/api/tasks", methods=["GET"])
def list_tasks():
    return jsonify(registry.list_active_tasks())

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
        # Send stream_end when task is terminal
        yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
            
    return Response(generate(), mimetype="text/event-stream")

@tasks_bp.route("/api/tasks/<job_id>/cancel", methods=["POST"])
def cancel_task(job_id):
    registry.update_status(job_id, "cancelled")
    # For now, it also globally requests cancel to interrupt executors.
    RuntimeState().request_cancel()
    return jsonify({"success": True})
