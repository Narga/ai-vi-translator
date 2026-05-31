# webui/routes/translation.py - v5.0.0
# Blueprint: Translation Worker, SSE Progress, Direct Translate

import json
import logging
from pathlib import Path
from datetime import datetime
from threading import Thread

from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context

from webui.helpers import (
    load_api_keys, load_prompts, save_prompts, calculate_stats,
    get_default_chunk_size, get_default_model, get_available_models,
)

logger = logging.getLogger(__name__)

translation_bp = Blueprint("translation", __name__)


def translate_worker(text, config, output_filename="translated", input_file_path=None):
    """Worker thread để dịch - dùng backend use case."""
    from webui import progress_queue, translation_memory
    import webui as _state
    from backend.infrastructure.progress.webui_progress_bridge import WebUIProgressBridge
    from backend.application.use_cases.translate_text_use_case import TranslateTextUseCase
    from backend.application.dto.translation_request import TranslationRequest
    from backend.infrastructure.config.api_key_service import ApiKeyService
    from backend.infrastructure.workspace.workspace_service import WorkspaceService

    try:
        key_service = ApiKeyService()
        ws_service = WorkspaceService()

        api_keys = key_service.load_gemini_keys()
        if not api_keys:
            progress_queue.put({
                "type": "error",
                "message": "Không tìm thấy API keys. Vui lòng cấu hình .env hoặc config/API.txt",
            })
            return

        pdir = ws_service.get_project_dir("default-project")
        out_path = pdir / "translated" / output_filename

        bridge = WebUIProgressBridge(progress_queue)

        use_case = TranslateTextUseCase(
            api_keys=api_keys,
            config=config,
        )

        request = TranslationRequest(
            text=text,
            output_filename=output_filename,
            output_file_path=out_path,
            translation_memory=translation_memory,
        )

        result = use_case.execute(request, progress_callback=bridge.create_callback())

        if result.success and result.output_path:
            _state.translation_result = {
                "text": result.translated_text,
                "filename": output_filename,
                "path": result.output_path,
            }

    except Exception as e:
        logger.error(f"Translation error: {e}", exc_info=True)
        from webui import progress_queue
        progress_queue.put({"type": "error", "message": f"Lỗi: {str(e)}"})


@translation_bp.route("/")
def index():
    """Render main page."""
    default_model = get_default_model()
    available_models = get_available_models()

    if default_model not in available_models:
        available_models.insert(0, default_model)

    prompts = load_prompts()

    from webui.helpers import get_app_version
    app_version = get_app_version()

    return render_template(
        "index.html",
        default_chunk=get_default_chunk_size(),
        default_model=default_model,
        available_models=json.dumps(available_models),
        prompts_json=json.dumps(prompts),
        app_version=app_version,
    )


@translation_bp.route("/api/translate", methods=["POST"])
def start_translation():
    """Bắt đầu dịch thuật."""
    from webui import progress_queue
    import webui as _state

    data = request.json

    config = {
        "model_name": data.get("model", "gemini-3-flash-preview"),
        "qa_model": data.get("model", "gemini-3-flash-preview"),
        "temperature": float(data.get("temperature", 1.0)),
        "chunk_size": int(data.get("chunk_size", 22000)),
        "use_cache": data.get("use_cache", True),
        "prompts": data.get("prompts", {}),
        "max_refinement_attempts": 2,
        "min_length_ratio": 0.5,
        "max_length_ratio": 5.0,
        "context_char_count": 500,
    }

    text = data.get("text", "")
    output_filename = data.get("filename", "translated")

    if not text.strip():
        return jsonify({"error": "Vui lòng nhập văn bản cần dịch"}), 400

    if data.get("prompts"):
        save_prompts(data["prompts"])

    while not progress_queue.empty():
        progress_queue.get()
    _state.translation_result = {}

    thread = Thread(target=translate_worker, args=(text, config, output_filename))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started"})


@translation_bp.route("/api/progress")
def progress_stream():
    """SSE endpoint cho real-time progress."""
    from webui import progress_queue

    def generate():
        while True:
            try:
                data = progress_queue.get(timeout=60)
                yield f"data: {json.dumps(data)}\n\n"

                if data["type"] in ["complete", "error"]:
                    break
            except Exception:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@translation_bp.route("/api/translate-text", methods=["POST"])
def translate_text():
    """Dịch text trực tiếp (cho Retranslate/Correction)."""
    try:
        from plugins.translation.translator import robust_translate
        from services.api_service import ApiManager
        from services.cache_service import TranslationCache

        data = request.json
        text = data.get("text", "")
        mode = data.get("mode", "main")
        prompts = data.get("prompts", {})
        model = data.get("model", "gemini-3-flash-preview")
        temperature = float(data.get("temperature", 1.0))

        if not text.strip():
            return jsonify({"error": "Vui lòng nhập văn bản"}), 400

        if not prompts:
            prompts = load_prompts()

        prompt_key = mode if mode in prompts else "main"
        prompt = prompts.get(prompt_key, prompts.get("main", ""))

        if not prompt:
            prompt = load_prompts().get("main", "")

        api_keys = load_api_keys()
        if not api_keys:
            return jsonify({"error": "Không tìm thấy API keys"}), 400

        api_manager = ApiManager(api_keys)
        
        from webui.helpers import load_config
        app_config = load_config()
        cache_dir = app_config.get("DIRECTORIES", "CACHE_DIR", fallback="workspace/cache")
        cache = TranslationCache(cache_dir, enabled=True)

        config_params = {
            "model_name": model,
            "qa_model": model,
            "temperature": temperature,
            "chunk_size": 22000,
        }

        translated, stats, log = robust_translate(
            text, api_manager, cache, {"main": prompt}, config_params
        )

        return jsonify({"translated": translated, "mode": mode, "chars": len(text)})

    except Exception as e:
        logger.error(f"Translate text error: {e}")
        return jsonify({"error": str(e)}), 500
