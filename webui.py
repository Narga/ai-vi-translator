# webui.py - v4.0.6
# Tác giả: Narga
# Chức năng: Web UI tối giản cho Novel Translator với Flask

"""
Novel Translator Web UI
======================
Web interface đơn giản cho dịch thuật với Flask.

Usage:
    uv run python webui.py

Features:
- Real-time progress với Server-Sent Events (SSE)
- Form cấu hình đơn giản
- Hiển thị kết quả trực quan
- Không cần upload file (text nhập trực tiếp)
- Quản lý cache
- Prompt editor
- Batch translation với checkbox
- Auto-detect available models
- Detailed statistics
- Translation Memory với fuzzy matching
"""

import os
import sys
import json
import logging
import configparser
from pathlib import Path
from datetime import datetime
from threading import Thread
from queue import Queue

from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_file

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)

# Global queue for progress updates
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

# Translation Memory
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
    translation_memory = None

# Available Gemini models (dynamically updated)
AVAILABLE_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-3-pro",
    "gemini-3-flash",
]


def load_config():
    """Load configuration from config/app.ini."""
    config = configparser.ConfigParser()
    config_file = Path("config/app.ini")
    if config_file.exists():
        config.read(config_file)
    return config


def get_default_chunk_size():
    """Get default chunk size from config."""
    config = load_config()
    try:
        return config.getint("PROCESSING", "MAX_CHARS_PER_CHUNK", fallback=100000)
    except:
        return 100000


def get_default_model():
    """Get default model from config."""
    config = load_config()
    try:
        return config.get("MODEL", "MODEL", fallback="gemini-2.0-flash-exp")
    except:
        return "gemini-2.0-flash-exp"


def get_available_models():
    """Get list of available models - tries to detect from API if possible."""
    models = AVAILABLE_MODELS.copy()

    try:
        api_keys = load_api_keys()
        if api_keys:
            first_key = api_keys[0]
            try:
                from google import genai

                client = genai.Client(api_key=first_key)
                try:
                    for model in client.models.list():
                        if model and model.name:
                            model_name = model.name.replace("models/", "")
                            if "gemini" in model_name and model_name not in models:
                                models.insert(0, model_name)
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass

    default_model = get_default_model()
    if default_model not in models:
        models.insert(0, default_model)

    return list(dict.fromkeys(models))


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

    api_file = Path("config/API.txt")
    if api_file.exists():
        with open(api_file, "r") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return []


def get_input_files():
    """Lấy danh sách files trong input directory."""
    input_dir = Path("workspace/input")
    done_dir = Path("workspace/done")
    files = []
    done_names = set()

    if done_dir.exists():
        for f in done_dir.glob("*.txt"):
            done_names.add(f.stem)

    if input_dir.exists():
        for f in sorted(input_dir.rglob("*.txt")):
            if f.name.startswith("."):
                continue
            try:
                size = f.stat().st_size
                is_done = f.stem in done_names
                files.append(
                    {
                        "name": str(f.relative_to(input_dir)),
                        "path": str(f),
                        "size": size,
                        "size_display": f"{size / 1024:.1f} KB"
                        if size < 1024 * 1024
                        else f"{size / 1024 / 1024:.1f} MB",
                        "is_done": is_done,
                    }
                )
            except Exception:
                continue
    return files


def get_done_files():
    """Lấy danh sách files đã dịch từ cả done và output directories."""
    files = []

    # Helper function để scan một thư mục
    def scan_dir(dir_path, location):
        if not dir_path.exists():
            return
        for f in sorted(dir_path.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.name.startswith("."):
                continue
            try:
                size = f.stat().st_size
                with open(f, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    word_count = len(content.split())
                files.append(
                    {
                        "name": f.name,
                        "path": str(f),
                        "size": size,
                        "size_display": f"{size / 1024:.1f} KB"
                        if size < 1024 * 1024
                        else f"{size / 1024 / 1024:.1f} MB",
                        "word_count": word_count,
                        "location": location,  # 'done' hoặc 'output'
                    }
                )
            except Exception:
                continue

    # Scan cả 2 thư mục
    scan_dir(Path("workspace/done"), "done")
    scan_dir(Path("workspace/output"), "output")

    # Sắp xếp theo thờigian sửa đổi (mới nhất lên đầu)
    files.sort(key=lambda x: Path(x["path"]).stat().st_mtime, reverse=True)

    return files


def move_to_done(source_path):
    """Di chuyển file đã dịch vào thư mục done."""
    done_dir = Path("workspace/done")
    done_dir.mkdir(parents=True, exist_ok=True)

    source = Path(source_path)
    if not source.exists():
        return False

    dest = done_dir / source.name
    if dest.exists():
        dest.unlink()

    source.rename(dest)
    return True


def count_words_in_files(files):
    """Đếm số từ trong các file."""
    total = 0
    for f in files:
        try:
            path = Path(f["path"])
            if path.exists():
                with open(path, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    total += len(content.split())
        except Exception:
            continue
    return total


def calculate_stats():
    """Tính toán thống kê hệ thống."""
    global translation_stats

    input_files = get_input_files()
    pending_files = [f for f in input_files if not f.get("is_done", False)]
    done_files = get_done_files()
    output_dir = Path("workspace/output")
    output_files = list(output_dir.glob("*.txt")) if output_dir.exists() else []

    input_words = count_words_in_files(input_files)
    pending_words = count_words_in_files(pending_files)
    done_words = count_words_in_files(done_files)

    cache_dir = Path("workspace/cache")
    cache_files = list(cache_dir.glob("*.pkl*")) if cache_dir.exists() else []
    cache_size = sum(f.stat().st_size for f in cache_files) if cache_files else 0

    api_keys = load_api_keys()
    config = load_config()

    # Get TM stats
    tm_stats = {}
    if translation_memory:
        tm_stats = translation_memory.get_stats()

    translation_stats = {
        "translated_words": done_words,
        "pending_words": pending_words,
        "total_input_words": input_words,
        "total_done_words": done_words,
        "cache_files": len(cache_files),
        "cache_size_mb": round(cache_size / 1024 / 1024, 2),
        "output_files": len(output_files),
        "api_keys_count": len(api_keys),
        "input_files_count": len(input_files),
        "done_files_count": len(done_files),
        "default_model": get_default_model(),
        "default_chunk_size": get_default_chunk_size(),
        "tm_entries": tm_stats.get("total_entries", 0),
        "tm_size_mb": tm_stats.get("memory_size_mb", 0),
    }

    return translation_stats


def load_prompts(lang="CN"):
    """Load prompts theo ngôn ngữ."""
    prompts_dir = Path("prompts")
    prompts = {"main": "", "retranslate": "", "correction": ""}

    # Load default prompts
    for key, filename in [
        ("main", "01-main.txt"),
        ("retranslate", "02-retranslate.txt"),
        ("correction", "03-correction.txt"),
    ]:
        filepath = prompts_dir / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                prompts[key] = f.read()

    # Load language-specific prompts if exists
    lang_dir = prompts_dir / lang.lower()
    if lang_dir.exists():
        for key, filename in [
            ("main", "01-main.txt"),
            ("retranslate", "02-retranslate.txt"),
            ("correction", "03-correction.txt"),
        ]:
            filepath = lang_dir / filename
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    prompts[key] = f.read()

    return prompts


def save_prompts(prompts, lang="CN"):
    """Lưu prompts vào file."""
    prompts_dir = Path("prompts")
    lang_dir = prompts_dir / lang.lower()
    lang_dir.mkdir(parents=True, exist_ok=True)

    for key, filename in [
        ("main", "01-main.txt"),
        ("retranslate", "02-retranslate.txt"),
        ("correction", "03-correction.txt"),
    ]:
        filepath = lang_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(prompts.get(key, ""))


def translate_worker(text, config, output_filename="translated", input_file_path=None):
    """
    Worker thread để dịch và gửi progress updates.
    """
    global translation_result, translation_stats
    try:
        from plugins.translation.translator import robust_translate
        from services.api_service import ApiManager
        from services.cache_service import TranslationCache

        api_keys = load_api_keys()
        if not api_keys:
            progress_queue.put(
                {
                    "type": "error",
                    "message": "Không tìm thấy API keys. Vui lòng cấu hình .env hoặc config/API.txt",
                }
            )
            return

        api_manager = ApiManager(api_keys)
        cache = TranslationCache("workspace/cache", enabled=config.get("use_cache", True))

        prompts = config.get("prompts", {})
        if not prompts.get("main"):
            prompts = load_prompts(config.get("input_lang", "CN"))

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
            progress_queue.put(
                {
                    "type": "progress",
                    "current": i + 1,
                    "total": len(chunks),
                    "percent": int((i + 1) / len(chunks) * 100),
                    "message": f"Đang dịch chunk {i + 1}/{len(chunks)}...",
                }
            )

            cache_key = cache.build_key(chunk, prompts, config, prev_context)
            cached_result = cache.get(cache_key)

            if cached_result:
                cached_count += 1
                translated.append(cached_result)
                ctx_len = config.get("context_char_count", 500)
                prev_context = (
                    cached_result[-ctx_len:] if len(cached_result) > ctx_len else cached_result
                )
                progress_queue.put(
                    {
                        "type": "info",
                        "message": f"Chunk {i + 1}: Sử dụng cache ✅",
                    }
                )
                continue

            # Check Translation Memory for similar content
            tm_match = None
            if translation_memory:
                tm_match = translation_memory.find_match(chunk)

            if tm_match and tm_match.get("similarity", 0) >= 0.9:
                # High similarity - use TM translation
                tm_hits += 1
                result = tm_match["translation"]
                progress_queue.put(
                    {
                        "type": "info",
                        "message": f"Chunk {i + 1}: TM match {tm_match['similarity']:.0%} 📚",
                    }
                )
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
                    # Add to Translation Memory
                    if translation_memory:
                        translation_memory.add_translation(chunk, result, output_filename)
                    total_tokens += len(chunk) // 2
                else:
                    progress_queue.put(
                        {"type": "error", "message": f"Dịch thất bại tại chunk {i + 1}: {status}"}
                    )
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

        translation_result = {
            "text": full_translation,
            "filename": output_file.name,
            "path": str(output_file),
        }

        if input_file_path:
            move_to_done(input_file_path)

        calculate_stats()

        # Build completion message
        cache_info = f"{cached_count}/{len(chunks)} cache"
        tm_info = f", {tm_hits} TM" if tm_hits > 0 else ""

        progress_queue.put(
            {
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
            }
        )

    except Exception as e:
        logger.error(f"Translation error: {e}", exc_info=True)
        progress_queue.put({"type": "error", "message": f"Lỗi: {str(e)}"})


@app.route("/")
def index():
    """Render main page."""
    # Ensure workspace sub-directories exist
    for dir_name in ["input", "output", "done"]:
        Path(f"workspace/{dir_name}").mkdir(parents=True, exist_ok=True)

    default_model = get_default_model()
    available_models = get_available_models()

    if default_model not in available_models:
        available_models.insert(0, default_model)

    prompts = load_prompts("CN")

    return render_template(
        "index.html",
        default_chunk=get_default_chunk_size(),
        default_model=default_model,
        available_models=json.dumps(available_models),
        prompts_json=json.dumps(prompts),
        app_version="5.0.0",
    )


@app.route("/api/files")
def list_files():
    """Lấy danh sách files trong input."""
    return jsonify(get_input_files())


@app.route("/api/file/<path:filepath>")
def get_file(filepath):
    """Đọc nội dung file."""
    try:
        # Security: only allow files in workspace/input
        input_dir = Path("workspace/input").resolve()
        file_path = (input_dir / filepath).resolve()

        if not str(file_path).startswith(str(input_dir)):
            return jsonify({"error": "Invalid path"}), 403

        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return jsonify(
            {"content": content, "name": file_path.name, "size": file_path.stat().st_size}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/translate", methods=["POST"])
def start_translation():
    """Bắt đầu dịch thuật."""
    global translation_result
    data = request.json

    config = {
        "model_name": data.get("model", "gemini-3-flash-preview"),
        "qa_model": data.get("model", "gemini-3-flash-preview"),
        "temperature": float(data.get("temperature", 1.0)),
        "input_lang": data.get("input_lang", "CN"),
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

    # Save prompts if provided
    if data.get("prompts"):
        save_prompts(data["prompts"], config["input_lang"])

    # Clear queue
    while not progress_queue.empty():
        progress_queue.get()
    translation_result = {}

    thread = Thread(target=translate_worker, args=(text, config, output_filename))
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


@app.route("/api/models")
def get_models():
    """Lấy danh sách models khả dụng."""
    try:
        models = get_available_models()
        default_model = get_default_model()
        return jsonify({"models": models, "default": default_model})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/config")
def get_config():
    """Lấy cấu hình mặc định."""
    try:
        return jsonify(
            {
                "default_chunk_size": get_default_chunk_size(),
                "default_model": get_default_model(),
                "available_models": get_available_models(),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def get_stats():
    """Lấy thống kê hệ thống."""
    try:
        api_keys = load_api_keys()
        cache_dir = Path("workspace/cache")
        cache_files = list(cache_dir.glob("*.pkl*")) if cache_dir.exists() else []
        output_dir = Path("workspace/output")
        output_files = list(output_dir.glob("*.txt")) if output_dir.exists() else []

        stats = calculate_stats()

        return jsonify(
            {
                "api_keys": len(api_keys),
                "cache_files": stats.get("cache_files", len(cache_files)),
                "cache_size_mb": stats.get("cache_size_mb", 0),
                "output_files": len(output_files),
                "translated_words": stats.get("translated_words", 0),
                "pending_words": stats.get("pending_words", 0),
                "total_input_words": stats.get("total_input_words", 0),
                "total_done_words": stats.get("total_done_words", 0),
                "status": "ready",
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cache/clear", methods=["POST"])
def clear_cache():
    """Xóa cache."""
    try:
        cache_dir = Path("workspace/cache")
        if cache_dir.exists():
            count = 0
            for f in cache_dir.glob("*.pkl*"):
                f.unlink()
                count += 1
            return jsonify({"success": True, "deleted": count})
        return jsonify({"success": True, "deleted": 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/<filename>")
def download_file(filename):
    """Download translated file."""
    try:
        output_dir = Path("workspace/output")
        file_path = output_dir / filename

        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype="text/plain; charset=utf-8",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/prompts", methods=["GET", "POST"])
def handle_prompts():
    """Load or save prompts."""
    if request.method == "GET":
        lang = request.args.get("lang", "CN")
        return jsonify(load_prompts(lang))
    else:
        data = request.json
        lang = data.get("lang", "CN")
        prompts = data.get("prompts", {})
        try:
            save_prompts(prompts, lang)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@app.route("/api/output-files")
def list_output_files():
    """Lấy danh sách files đã dịch."""
    output_dir = Path("workspace/output")
    files = []
    if output_dir.exists():
        for f in sorted(output_dir.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
            files.append(
                {
                    "name": f.name,
                    "size": f.stat().st_size,
                    "mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                }
            )
    return jsonify(files)


@app.route("/api/done-files")
def list_done_files():
    """Lấy danh sách files trong thư mục done."""
    return jsonify(get_done_files())


@app.route("/api/done/<filename>")
def get_done_file(filename):
    """Đọc nội dung file đã dịch trong done hoặc output."""
    try:
        # Thử tìm trong done trước
        done_dir = Path("workspace/done")
        file_path = done_dir / filename

        # Nếu không có, thử tìm trong output
        if not file_path.exists():
            output_dir = Path("workspace/output")
            file_path = output_dir / filename

        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return jsonify(
            {"content": content, "name": file_path.name, "size": file_path.stat().st_size}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/output-file/<filename>")
def get_output_file(filename):
    """Đọc nội dung file trong output directory."""
    try:
        output_dir = Path("workspace/output")
        file_path = output_dir / filename

        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return jsonify(
            {"content": content, "name": file_path.name, "size": file_path.stat().st_size}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/translate-file", methods=["POST"])
def translate_single_file():
    """Dịch một file cụ thể."""
    data = request.json
    filepath = data.get("filepath")

    if not filepath:
        return jsonify({"error": "Thiếu filepath"}), 400

    file_path = Path(filepath)
    if not file_path.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        return jsonify({"error": f"Không thể đọc file: {str(e)}"}), 500

    config = {
        "model_name": data.get("model", "gemini-3-flash-preview"),
        "qa_model": data.get("model", "gemini-3-flash-preview"),
        "temperature": float(data.get("temperature", 1.0)),
        "input_lang": data.get("input_lang", "CN"),
        "chunk_size": int(data.get("chunk_size", 22000)),
        "use_cache": data.get("use_cache", True),
        "prompts": data.get("prompts", {}),
        "max_refinement_attempts": 2,
        "min_length_ratio": 0.5,
        "max_length_ratio": 5.0,
        "context_char_count": 500,
    }

    output_filename = file_path.stem

    while not progress_queue.empty():
        progress_queue.get()
    translation_result = {}

    thread = Thread(target=translate_worker, args=(text, config, output_filename, str(file_path)))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started", "file": file_path.name})


@app.route("/api/translate-batch", methods=["POST"])
def translate_batch():
    """Dịch nhiều file đã chọn."""
    data = request.json
    files = data.get("files", [])

    if not files:
        return jsonify({"error": "Không có file nào được chọn"}), 400

    results = []
    for filepath in files:
        file_path = Path(filepath)
        if not file_path.exists():
            results.append({"file": filepath, "status": "error", "message": "File không tồn tại"})
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            results.append({"file": filepath, "status": "error", "message": str(e)})
            continue

        config = {
            "model_name": data.get("model", "gemini-3-flash-preview"),
            "qa_model": data.get("model", "gemini-3-flash-preview"),
            "temperature": float(data.get("temperature", 1.0)),
            "input_lang": data.get("input_lang", "CN"),
            "chunk_size": int(data.get("chunk_size", 22000)),
            "use_cache": data.get("use_cache", True),
            "prompts": data.get("prompts", {}),
            "max_refinement_attempts": 2,
            "min_length_ratio": 0.5,
            "max_length_ratio": 5.0,
            "context_char_count": 500,
        }

        output_filename = file_path.stem

        while not progress_queue.empty():
            progress_queue.get()
        translation_result = {}

        thread = Thread(
            target=translate_worker, args=(text, config, output_filename, str(file_path))
        )
        thread.daemon = True
        thread.start()

        results.append({"file": file_path.name, "status": "started"})

        import time

        time.sleep(0.5)

    return jsonify({"status": "started", "results": results})


@app.route("/api/move-to-done", methods=["POST"])
def api_move_to_done():
    """Di chuyển file vào thư mục done."""
    data = request.json
    filepath = data.get("filepath")

    if not filepath:
        return jsonify({"error": "Thiếu filepath"}), 400

    if move_to_done(filepath):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Không thể di chuyển file"}), 500


@app.route("/api/move-back-to-input", methods=["POST"])
def move_back_to_input():
    """Di chuyển file từ done về input."""
    data = request.json
    filename = data.get("filename")

    if not filename:
        return jsonify({"error": "Thiếu filename"}), 400

    done_dir = Path("workspace/done")
    input_dir = Path("workspace/input")
    input_dir.mkdir(parents=True, exist_ok=True)

    source = done_dir / filename
    if not source.exists():
        return jsonify({"error": "File không tồn tại trong done"}), 404

    dest = input_dir / filename
    if dest.exists():
        dest.unlink()

    source.rename(dest)

    return jsonify({"success": True})


# ============================================================
# Prompt Sets (Genre-based Prompt Management) API
# ============================================================

GENRES_DIR = Path("prompts/genres")


@app.route("/api/prompt-sets")
def list_prompt_sets():
    """Liệt kê tất cả bộ prompt theo thể loại."""
    GENRES_DIR.mkdir(parents=True, exist_ok=True)
    sets = []
    
    # Inject Default System Prompts
    prompts_root = Path("prompts")
    sets.append({
        "name": "Mặc định (Hệ thống)",
        "slug": "default",
        "order": -1,
        "description": "Bộ prompt gốc nằm ở thư mục prompts, dùng chung cho mọi văn bản",
        "has_main": (prompts_root / "01-main.txt").exists(),
        "has_retranslate": (prompts_root / "02-retranslate.txt").exists(),
        "has_correction": (prompts_root / "03-correction.txt").exists()
    })
    
    for genre_dir in sorted(GENRES_DIR.iterdir()):
        if not genre_dir.is_dir():
            continue
        meta_file = genre_dir / "meta.json"
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        else:
            meta = {"name": genre_dir.name, "slug": genre_dir.name, "order": 99}
        meta["slug"] = genre_dir.name
        # Check which prompt files exist
        meta["has_main"] = (genre_dir / "main.txt").exists()
        meta["has_retranslate"] = (genre_dir / "retranslate.txt").exists()
        meta["has_correction"] = (genre_dir / "correction.txt").exists()
        sets.append(meta)
    sets.sort(key=lambda x: x.get("order", 99))
    return jsonify(sets)


@app.route("/api/prompt-sets/<genre>")
def get_prompt_set(genre):
    """Lấy nội dung 1 bộ prompt theo thể loại."""
    if genre == "default":
        prompts_root = Path("prompts")
        meta = {
            "name": "Mặc định (Hệ thống)",
            "slug": "default",
            "description": "Bộ prompt gốc dùng chung cho mọi văn bản"
        }
        prompts = {}
        mapping = [("main", "01-main.txt"), ("retranslate", "02-retranslate.txt"), ("correction", "03-correction.txt")]
        for key, fname in mapping:
            fpath = prompts_root / fname
            if fpath.exists():
                with open(fpath, "r", encoding="utf-8") as f:
                    prompts[key] = f.read()
            else:
                prompts[key] = ""
        return jsonify({"meta": meta, "prompts": prompts})
        
    genre_dir = GENRES_DIR / genre
    if not genre_dir.exists():
        return jsonify({"error": "Thể loại không tồn tại"}), 404

    meta_file = genre_dir / "meta.json"
    meta = {}
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

    prompts = {}
    for key, fname in [("main", "main.txt"), ("retranslate", "retranslate.txt"), ("correction", "correction.txt")]:
        fpath = genre_dir / fname
        if fpath.exists():
            with open(fpath, "r", encoding="utf-8") as f:
                prompts[key] = f.read()
        else:
            prompts[key] = ""

    return jsonify({"meta": meta, "prompts": prompts})


@app.route("/api/prompt-sets", methods=["POST"])
def create_prompt_set():
    """Tạo bộ prompt mới."""
    data = request.json
    name = data.get("name", "").strip()
    slug = data.get("slug", "").strip().lower().replace(" ", "-")

    if not name or not slug:
        return jsonify({"error": "Thiếu name hoặc slug"}), 400

    genre_dir = GENRES_DIR / slug
    if genre_dir.exists():
        return jsonify({"error": "Thể loại đã tồn tại"}), 409

    genre_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "name": name,
        "slug": slug,
        "order": data.get("order", 99),
        "description": data.get("description", ""),
    }
    with open(genre_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Save prompt content if provided
    prompts = data.get("prompts", {})
    for key, fname in [("main", "main.txt"), ("retranslate", "retranslate.txt"), ("correction", "correction.txt")]:
        content = prompts.get(key, "")
        with open(genre_dir / fname, "w", encoding="utf-8") as f:
            f.write(content)

    return jsonify({"success": True, "slug": slug})


@app.route("/api/prompt-sets/<genre>", methods=["PUT"])
def update_prompt_set(genre):
    """Cập nhật bộ prompt."""
    data = request.json
    prompts = data.get("prompts", {})
    
    if genre == "default":
        prompts_root = Path("prompts")
        mapping = [("main", "01-main.txt"), ("retranslate", "02-retranslate.txt"), ("correction", "03-correction.txt")]
        for key, fname in mapping:
            if key in prompts:
                with open(prompts_root / fname, "w", encoding="utf-8") as f:
                    f.write(prompts[key])
        return jsonify({"success": True})

    genre_dir = GENRES_DIR / genre
    if not genre_dir.exists():
        return jsonify({"error": "Thể loại không tồn tại"}), 404

    # Update meta if provided
    if "name" in data or "description" in data or "order" in data:
        meta_file = genre_dir / "meta.json"
        meta = {}
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        meta.update({k: v for k, v in data.items() if k in ("name", "description", "order")})
        meta["slug"] = genre
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    # Update prompts if provided
    for key, fname in [("main", "main.txt"), ("retranslate", "retranslate.txt"), ("correction", "correction.txt")]:
        if key in prompts:
            with open(genre_dir / fname, "w", encoding="utf-8") as f:
                f.write(prompts[key])

    return jsonify({"success": True})


@app.route("/api/prompt-sets/<genre>", methods=["DELETE"])
def delete_prompt_set(genre):
    """Xóa bộ prompt."""
    if genre == "default":
        return jsonify({"error": "Không thể xóa bộ prompt mặc định của hệ thống"}), 400
        
    genre_dir = GENRES_DIR / genre
    if not genre_dir.exists():
        return jsonify({"error": "Thể loại không tồn tại"}), 404

    import shutil
    shutil.rmtree(genre_dir)
    return jsonify({"success": True})


@app.route("/api/prompt-sets/<genre>/activate", methods=["POST"])
def activate_prompt_set(genre):
    """Nạp bộ prompt vào hệ thống đang chạy (copy vào prompts/ gốc)."""
    if genre == "default":
        return jsonify({"error": "Bộ prompt này đã là mặc định gốc, không cần nạp chép đè"}), 400
        
    genre_dir = GENRES_DIR / genre
    if not genre_dir.exists():
        return jsonify({"error": "Thể loại không tồn tại"}), 404

    prompts_root = Path("prompts")
    mapping = [("main.txt", "01-main.txt"), ("retranslate.txt", "02-retranslate.txt"), ("correction.txt", "03-correction.txt")]
    for src_name, dest_name in mapping:
        src = genre_dir / src_name
        if src.exists():
            import shutil
            shutil.copy2(src, prompts_root / dest_name)

    return jsonify({"success": True, "message": f"Đã nạp bộ prompt '{genre}' vào hệ thống"})


@app.route("/api/remove-done", methods=["POST"])
def remove_done_file():
    """Xóa file khỏi thư mục done."""
    data = request.json
    filename = data.get("filename")

    if not filename:
        return jsonify({"error": "Thiếu filename"}), 400

    done_dir = Path("workspace/done")
    file_path = done_dir / filename

    if not file_path.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    file_path.unlink()

    return jsonify({"success": True})


@app.route("/api/tm/stats")
def get_tm_stats():
    """Lấy thống kê Translation Memory."""
    try:
        if translation_memory:
            stats = translation_memory.get_stats()
            return jsonify(stats)
        return jsonify({"enabled": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tm/find", methods=["POST"])
def tm_find():
    """Tìm kiếm trong Translation Memory."""
    try:
        data = request.json
        text = data.get("text", "")

        if not translation_memory:
            return jsonify({"error": "Translation Memory not enabled"}), 400

        match = translation_memory.find_match(text)
        if match:
            return jsonify(match)
        return jsonify({"found": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tm/add", methods=["POST"])
def tm_add():
    """Thêm translation vào TM."""
    try:
        data = request.json
        source = data.get("source", "")
        target = data.get("target", "")
        context = data.get("context", "")

        if not translation_memory:
            return jsonify({"error": "Translation Memory not enabled"}), 400

        translation_memory.add_translation(source, target, context)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tm/clear", methods=["POST"])
def tm_clear():
    """Xóa toàn bộ TM."""
    try:
        if translation_memory:
            count = translation_memory.clear()
            return jsonify({"success": True, "deleted": count})
        return jsonify({"error": "Translation Memory not enabled"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tm/export", methods=["POST"])
def tm_export():
    """Export TM ra file."""
    try:
        data = request.json
        filepath = data.get("filepath", "workspace/translation_memory_export.json")

        if translation_memory:
            if translation_memory.export_tm(filepath):
                return jsonify({"success": True, "filepath": filepath})
        return jsonify({"error": "Export failed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tm/import", methods=["POST"])
def tm_import():
    """Import TM từ file."""
    try:
        data = request.json
        filepath = data.get("filepath", "")
        merge = data.get("merge", True)

        if not filepath:
            return jsonify({"error": "Thiếu filepath"}), 400

        if translation_memory:
            if translation_memory.import_tm(filepath, merge):
                return jsonify({"success": True})
        return jsonify({"error": "Import failed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/translate-text", methods=["POST"])
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
        input_lang = data.get("input_lang", "CN")

        if not text.strip():
            return jsonify({"error": "Vui lòng nhập văn bản"}), 400

        if not prompts:
            prompts = load_prompts(input_lang)

        prompt_key = mode if mode in prompts else "main"
        prompt = prompts.get(prompt_key, prompts.get("main", ""))

        if not prompt:
            prompt = load_prompts(input_lang).get("main", "")

        api_keys = load_api_keys()
        if not api_keys:
            return jsonify({"error": "Không tìm thấy API keys"}), 400

        api_manager = ApiManager(api_keys)
        cache = TranslationCache("workspace/cache", enabled=True)

        config_params = {
            "model_name": model,
            "qa_model": model,
            "temperature": temperature,
            "input_lang": input_lang,
            "chunk_size": 22000,
        }

        translated, stats, log = robust_translate(
            text, api_manager, cache, {"main": prompt}, config_params
        )

        return jsonify({"translated": translated, "mode": mode, "chars": len(text)})

    except Exception as e:
        logger.error(f"Translate text error: {e}")
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
