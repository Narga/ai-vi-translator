# webui/__init__.py - v6.8.0
# Flask App Factory cho Novel Translator Web UI

import os
import logging
from queue import Queue

from flask import Flask, request, jsonify

# Setup logging
from datetime import datetime
from pathlib import Path

log_dir = Path("workspace/logs")
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / (datetime.now().strftime("%Y-%m-%d_%H-%M") + "_webui.log")

from logging.handlers import RotatingFileHandler

_file_handler = RotatingFileHandler(
    log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[_file_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================
# Global State (shared across blueprints)
# NOTE: translation_result is replaced atomically via `import webui as _state;
# _state.translation_result = {...}` — safe under CPython GIL.
# If migrating to multiprocessing, add threading.Lock or use mp.Manager.
# ============================================================
progress_queue = Queue()
translation_result = {}
translation_stats = {
    "translated_words": 0,
    "pending_words": 0,
    "tokens_used": 0,
    "total_input_words": 0,
    "total_done_words": 0,
    "total_translation_time": 0,
    "total_chunks_translated": 0,
    "cache_hit_rate": 0,
    "tm_hits": 0,
}

# Translation Memory (singleton)
translation_memory = None
try:
    from services.translation_memory import TranslationMemory

    translation_memory = TranslationMemory(
        tm_dir="workspace/projects/default-project/profile/translation_memory",
        enabled=True,
        min_match_length=20,
        similarity_threshold=0.85,
    )
except Exception as e:
    logger.warning(f"Translation Memory init failed: {e}"    )


def scan_and_recover(store, ck_dir):
    """Startup reconciliation: running → interrupted; checkpoint mồ côi → resumable task.

    Tách ra để test. KHÔNG hash-of-hash: dùng get_resume_info_from_path cho file vật lý,
    fallback filename lấy từ metadata, không phải MD5 stem.
    Trả về số task mới tạo.
    """
    import uuid
    from services.checkpoint_service import CheckpointService

    created = 0
    # P1 Phase 7 lease: task `running` có worker crash (heartbeat stale/null) → interrupted.
    # KHÔNG convert mù mọi `running`: task đang chạy thật (heartbeat gần đây) được giữ.
    store.reconcile_lease_expired(lease_timeout_seconds=30.0)

    if not ck_dir.exists():
        return created

    ck = CheckpointService(str(ck_dir))
    # Đọc bảng task MỘT lần rồi tự cập nhật danh sách khóa đã dùng: list_tasks() trong
    # vòng lặp là O(số checkpoint × số task) truy vấn SQLite mỗi lần khởi động.
    known_keys = [t.get("checkpoint_key") for t in store.list_tasks() if t.get("checkpoint_key")]

    for db_file in sorted(ck_dir.glob("*.db")):
        info = ck.get_resume_info_from_path(str(db_file))
        if not (info and info.get("can_resume")
                and info.get("translated_count", 0) < info.get("total_chunks", 0)):
            continue
        # B9: task cũ có thể lưu tên LOGIC ("book.txt") còn db_file.name là tên VẬT LÝ
        # ("f1ed388c8e76.db"). So thô bằng "==" không bao giờ khớp → mỗi lần khởi động lại
        # đẻ thêm một task resumable trùng trong workspace/tasks.db (dữ liệu thật của người dùng).
        if any(ck.same_checkpoint_key(k, db_file.name) for k in known_keys):
            continue
        job_id = str(uuid.uuid4())
        saved_identity = info.get("identity", {})
        logical = info.get("filename") or ""
        project_file = saved_identity.get("project_file") or logical
        project_slug = saved_identity.get("project_slug", "")
        store.create_task(
            job_id=job_id,
            kind="translation",
            title=f"Resume {project_file}",
            project_slug=project_slug,
            filename=project_file,
            total_chunks=info.get("total_chunks", 0),
            checkpoint_key=db_file.name,
            identity=saved_identity,
        )
        store.update_status(
            job_id, "resumable",
            completed_chunks=info.get("translated_count", 0),
            current_chunk=info.get("next_chunk_index", 0),
        )
        known_keys.append(db_file.name)
        created += 1
    return created


def create_app():
    """Flask Application Factory."""
    import mimetypes
    mimetypes.add_type('text/css', '.css')
    mimetypes.add_type('application/javascript', '.js')
    
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.urandom(24)

    # Register blueprints
    from webui.routes.translation import translation_bp
    from webui.routes.settings import settings_bp
    from webui.routes.prompts import prompts_bp
    from webui.routes.projects import projects_bp
    from webui.routes.plugins import plugins_bp
    from webui.routes.docs import docs_bp
    from webui.routes.tasks import tasks_bp

    app.register_blueprint(translation_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(prompts_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(plugins_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(tasks_bp)

    # Đảm bảo dự án mặc định tồn tại
    from webui.helpers import ensure_default_project
    ensure_default_project()

    # Scan resumable checkpoints on startup
    try:
        from services.task_store import TaskStore
        from pathlib import Path
        store = TaskStore()
        scan_and_recover(store, Path(store.db_path).parent / "checkpoints")
    except Exception as e:
        logger.warning(f"Startup checkpoint scan failed: {e}")

    @app.after_request
    def force_static_mimetypes(response):
        # Force correct Content-Type for CSS/JS to prevent browser MIME-type blocking
        path = request.path.lower()
        if path.endswith('.css'):
            response.headers['Content-Type'] = 'text/css'
        elif path.endswith('.js'):
            response.headers['Content-Type'] = 'application/javascript'
        return response

    @app.errorhandler(Exception)
    def handle_all_exceptions(e):
        """Trả về JSON cho mọi lỗi không được catch ở route level."""
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"error": "Không tìm thấy tài nguyên"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return jsonify({"error": "Phương thức không hợp lệ"}), 405

    return app
