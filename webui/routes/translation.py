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
    """Worker thread để dịch và gửi progress updates."""
    from webui import progress_queue, translation_memory
    import webui as _state

    try:
        from plugins.translation.translator import robust_translate
        from services.api_service import ApiManager
        from services.cache_service import TranslationCache

        api_keys = load_api_keys()
        if not api_keys:
            progress_queue.put({
                "type": "error",
                "message": "Không tìm thấy API keys. Vui lòng cấu hình .env hoặc config/API.txt",
            })
            return

        api_manager = ApiManager(api_keys)
        cache = TranslationCache("workspace/cache", enabled=config.get("use_cache", True))

        prompts = config.get("prompts", {})
        if not prompts.get("main"):
            prompts = load_prompts()

        from plugins.translation.chunker import process_text_for_chunking

        min_chunk = config.get("chunk_size", 22000) - 2000
        max_chunk = config.get("chunk_size", 22000)
        chunks = process_text_for_chunking(text, min_chars=min_chunk, max_chars=max_chunk)

        progress_queue.put({"type": "info", "message": f"Đã chia thành {len(chunks)} chunks"})

        translated = []
        prev_context = ""
        cached_count = 0
        total_tokens = 0
        tm_hits = 0

        for i, chunk in enumerate(chunks):
            progress_queue.put({
                "type": "progress",
                "current": i + 1,
                "total": len(chunks),
                "percent": int((i + 1) / len(chunks) * 100),
                "message": f"Đang dịch chunk {i + 1}/{len(chunks)}...",
            })

            cache_key = cache.build_key(chunk, prompts, config, prev_context)
            cached_result = cache.get(cache_key)

            if cached_result:
                cached_count += 1
                translated.append(cached_result)
                ctx_len = config.get("context_char_count", 500)
                prev_context = cached_result[-ctx_len:] if len(cached_result) > ctx_len else cached_result
                progress_queue.put({"type": "info", "message": f"Chunk {i + 1}: Sử dụng cache ✅"})
                continue

            # Check Translation Memory
            tm_match = None
            if translation_memory:
                tm_match = translation_memory.find_match(chunk)

            if tm_match and tm_match.get("similarity", 0) >= 0.9:
                tm_hits += 1
                result = tm_match["translation"]
                progress_queue.put({
                    "type": "info",
                    "message": f"Chunk {i + 1}: TM match {tm_match['similarity']:.0%} 📚",
                })
            else:
                result, status, api_key = robust_translate(
                    original_chunk=chunk,
                    api_manager=api_manager,
                    cache=cache,
                    prompts=prompts,
                    config_params=config,
                    previous_chunk_context=prev_context,
                )

                if status == "success" and result:
                    if translation_memory:
                        translation_memory.add_translation(chunk, result, output_filename)
                    total_tokens += len(chunk) // 2
                else:
                    progress_queue.put({"type": "error", "message": f"Dịch thất bại tại chunk {i + 1}: {status}"})
                    return

            if result:
                translated.append(result)
                ctx_len = config.get("context_char_count", 500)
                prev_context = result[-ctx_len:] if len(result) > ctx_len else result

        full_translation = "\n\n".join(translated)

        output_dir = Path("workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{output_filename}_{timestamp}.txt"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(full_translation)

        _state.translation_result = {
            "text": full_translation,
            "filename": output_file.name,
            "path": str(output_file),
        }

        calculate_stats()

        cache_info = f"{cached_count}/{len(chunks)} cache"
        tm_info = f", {tm_hits} TM" if tm_hits > 0 else ""

        progress_queue.put({
            "type": "complete",
            "message": f"Dịch hoàn tất! ({cache_info}{tm_info})",
            "result": full_translation,
            "chunks": len(chunks),
            "cached": cached_count,
            "tm_hits": tm_hits,
            "source_length": len(text),
            "translated_length": len(full_translation),
            "output_file": str(output_file.name),
            "tokens_used": total_tokens,
        })

    except Exception as e:
        logger.error(f"Translation error: {e}", exc_info=True)
        from webui import progress_queue
        progress_queue.put({"type": "error", "message": f"Lỗi: {str(e)}"})


@translation_bp.route("/")
def index():
    """Render main page."""
    for dir_name in ["input", "output", "done"]:
        Path(f"workspace/{dir_name}").mkdir(parents=True, exist_ok=True)

    default_model = get_default_model()
    available_models = get_available_models()

    if default_model not in available_models:
        available_models.insert(0, default_model)

    prompts = load_prompts()

    return render_template(
        "index.html",
        default_chunk=get_default_chunk_size(),
        default_model=default_model,
        available_models=json.dumps(available_models),
        prompts_json=json.dumps(prompts),
        app_version="5.0.0",
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
        cache = TranslationCache("workspace/cache", enabled=True)

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
