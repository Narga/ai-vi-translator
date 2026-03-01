# webui/__init__.py - v5.0.0
# Flask App Factory cho Novel Translator Web UI

import os
import logging
from queue import Queue

from flask import Flask

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ============================================================
# Global State (shared across blueprints)
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
        tm_dir="workspace/translation_memory",
        enabled=True,
        min_match_length=20,
        similarity_threshold=0.85,
    )
except Exception as e:
    logger.warning(f"Translation Memory init failed: {e}")


def create_app():
    """Flask Application Factory."""
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
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

    return app
