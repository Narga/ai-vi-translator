# webui/__init__.py - v6.8.0
# Flask App Factory cho Novel Translator Web UI

import os
import logging
from queue import Queue

from flask import Flask

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
    logger.warning(f"Translation Memory init failed: {e}")


def create_app():
    """Flask Application Factory."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.urandom(24)

    # Register blueprints
    from webui.routes.translation import translation_bp
    from webui.routes.settings import settings_bp
    from webui.routes.prompts import prompts_bp
    from webui.routes.projects import projects_bp
    from webui.routes.plugins import plugins_bp

    app.register_blueprint(translation_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(prompts_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(plugins_bp)

    # Đảm bảo dự án mặc định tồn tại
    from webui.helpers import ensure_default_project
    ensure_default_project()

    return app
