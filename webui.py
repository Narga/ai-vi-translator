# webui.py - v4.0.2
# Tác giả: Narga
# Chức năng: Web UI tối giản cho Novel Translator với Flask

"""
Novel Translator Web UI
========================
Web interface đơn giản cho dịch thuật với Flask.

Usage:
    uv run python webui.py

Hoặc:
    flask --app webui run

Features:
- Real-time progress với Server-Sent Events (SSE)
- Form cấu hình đơn giản
- Hiển thị kết quả trực quan
- Không cần upload file (text nhập trực tiếp)
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from threading import Thread
from queue import Queue

from flask import Flask, render_template, request, jsonify, Response, stream_with_context

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)

# Global queue for progress updates
progress_queue = Queue()


def load_api_keys():
    """Load API keys từ .env hoặc config."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
        env_value = os.environ.get("GEMINI_API_KEYS", "")
        if env_value:
            return [k.strip() for k in env_value.split(",") if k.strip()]
    except ImportError:
        pass

    # Fallback to file
    api_file = Path("config/API.txt")
    if api_file.exists():
        with open(api_file, "r") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return []


def translate_worker(text, config):
    """
    Worker thread để dịch và gửi progress updates.
    """
    try:
        from plugins.translation.translator import robust_translate
        from services.api_service import ApiManager
        from services.cache_service import TranslationCache

        # Load API keys
        api_keys = load_api_keys()
        if not api_keys:
            progress_queue.put(
                {
                    "type": "error",
                    "message": "Không tìm thấy API keys. Vui lòng cấu hình .env hoặc config/API.txt",
                }
            )
            return

        # Initialize services
        api_manager = ApiManager(api_keys)
        cache = TranslationCache("workspace/cache", enabled=config.get("use_cache", True))

        # Load prompts
        prompts_dir = Path("prompts")
        prompts = {"main": "", "retranslate": "", "correction": ""}
        for key, filename in [
            ("main", "01-main.txt"),
            ("retranslate", "02-retranslate.txt"),
            ("correction", "03-correction.txt"),
        ]:
            filepath = prompts_dir / filename
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    prompts[key] = f.read()

        # Chunk text
        from plugins.translation.chunker import process_text_for_chunking

        chunks = process_text_for_chunking(
            text,
            min_chars=config.get("chunk_size", 18000) - 2000,
            max_chars=config.get("chunk_size", 22000),
        )

        progress_queue.put({"type": "info", "message": f"Đã chia thành {len(chunks)} chunks"})

        # Translate each chunk
        translated = []
        prev_context = ""

        for i, chunk in enumerate(chunks):
            progress_queue.put(
                {
                    "type": "progress",
                    "current": i + 1,
                    "total": len(chunks),
                    "percent": int((i + 1) / len(chunks) * 100),
                    "message": f"Đang dịch chunk {i + 1}/{len(chunks)}...",
                }
            )

            context_data = {"prompts": prompts, "previous_context": prev_context, "chunk_index": i}

            result, status, api_key = robust_translate(
                original_chunk=chunk,
                api_manager=api_manager,
                cache=cache,
                prompts=prompts,
                config_params=config,
                previous_chunk_context=prev_context,
            )

            if status == "success" and result:
                translated.append(result)
                ctx_len = config.get("context_char_count", 500)
                prev_context = result[-ctx_len:] if len(result) > ctx_len else result
            else:
                progress_queue.put(
                    {"type": "error", "message": f"Dịch thất bại tại chunk {i + 1}: {status}"}
                )
                return

        # Send final result
        full_translation = "\n\n".join(translated)
        progress_queue.put(
            {
                "type": "complete",
                "message": "Dịch hoàn tất!",
                "result": full_translation,
                "chunks": len(chunks),
                "source_length": len(text),
                "translated_length": len(full_translation),
            }
        )

    except Exception as e:
        logger.error(f"Translation error: {e}", exc_info=True)
        progress_queue.put({"type": "error", "message": f"Lỗi: {str(e)}"})


@app.route("/")
def index():
    """Render main page."""
    # Đọc file input đầu tiên nếu có
    sample_text = ""
    input_dir = Path("workspace/input")
    if input_dir.exists():
        txt_files = list(input_dir.glob("*.txt"))
        if txt_files:
            try:
                with open(txt_files[0], "r", encoding="utf-8") as f:
                    sample_text = f.read()[:5000]  # Giới hạn 5000 chars
            except Exception:
                pass

    return render_template("index.html", sample_text=sample_text)


@app.route("/api/translate", methods=["POST"])
def start_translation():
    """Bắt đầu dịch thuật."""
    data = request.json

    config = {
        "model_name": data.get("model", "gemini-3-flash-preview"),
        "qa_model": data.get("model", "gemini-3-flash-preview"),
        "temperature": float(data.get("temperature", 1.0)),
        "input_lang": data.get("input_lang", "CN"),
        "chunk_size": int(data.get("chunk_size", 22000)),
        "use_cache": data.get("use_cache", True),
        "max_refinement_attempts": 2,
        "min_length_ratio": 0.5,
        "max_length_ratio": 5.0,
        "context_char_count": 500,
    }

    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "Vui lòng nhập văn bản cần dịch"}), 400

    # Clear queue
    while not progress_queue.empty():
        progress_queue.get()

    # Start translation in background thread
    thread = Thread(target=translate_worker, args=(text, config))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/progress")
def progress_stream():
    """SSE endpoint cho real-time progress."""

    def generate():
        while True:
            try:
                data = progress_queue.get(timeout=60)
                yield f"data: {json.dumps(data)}\n\n"

                if data["type"] in ["complete", "error"]:
                    break
            except:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/stats")
def get_stats():
    """Lấy thống kê hệ thống."""
    try:
        api_keys = load_api_keys()
        cache_dir = Path("workspace/cache")
        cache_files = list(cache_dir.glob("*.pkl*")) if cache_dir.exists() else []

        return jsonify(
            {"api_keys": len(api_keys), "cache_files": len(cache_files), "status": "ready"}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Novel Translator Web UI")
    parser.add_argument(
        "--port", "-p", type=int, default=7860, help="Port to run server (default: 7860)"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    args = parser.parse_args()

    print("=" * 60)
    print("📚 Novel Translator Web UI")
    print("=" * 60)
    print(f"\n🌐 Mở trình duyệt và truy cập: http://localhost:{args.port}")
    print("\nNhấn Ctrl+C để dừng\n")

    app.run(host=args.host, port=args.port, debug=False, threaded=True)
