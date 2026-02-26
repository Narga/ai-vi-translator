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
            {"content": content, "name": file_path.name, "path": str(file_path), "size": file_path.stat().st_size}
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


@app.route("/api/model-info/<path:model_name>")
def get_model_info(model_name):
    """Lấy thông tin chi tiết của model (token limits, rate limits, availability)."""
    try:
        api_keys = load_api_keys()
        if not api_keys:
            return jsonify({"error": "Không tìm thấy API key"}), 400

        from google import genai

        client = genai.Client(api_key=api_keys[0])

        # Ensure model name has prefix
        full_name = model_name if model_name.startswith("models/") else f"models/{model_name}"

        try:
            model = client.models.get(model=full_name)
        except Exception as e:
            return jsonify({"error": f"Không tìm thấy model: {model_name}", "detail": str(e)}), 404

        # Extract info from model object
        info = {
            "name": getattr(model, "name", model_name),
            "display_name": getattr(model, "display_name", model_name),
            "description": getattr(model, "description", ""),
            "input_token_limit": getattr(model, "input_token_limit", None),
            "output_token_limit": getattr(model, "output_token_limit", None),
        }

        # Format limits for display
        if info["input_token_limit"]:
            info["input_token_display"] = f"{info['input_token_limit']:,}"
        if info["output_token_limit"]:
            info["output_token_display"] = f"{info['output_token_limit']:,}"

        return jsonify(info)

    except Exception as e:
        logger.error(f"Model info error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/estimate-tokens", methods=["POST"])
def estimate_tokens():
    """Ước tính token từ số ký tự văn bản.

    Quy tắc ước tính:
    - Tiếng Trung/Nhật/Hàn: ~1 token per 1.5 ký tự
    - Tiếng Anh/Việt: ~1 token per 4 ký tự
    - Hỗn hợp: trung bình ~1 token per 2.5 ký tự
    """
    data = request.json
    text = data.get("text", "")
    char_count = data.get("char_count", len(text))
    lang = data.get("lang", "CN").upper()

    # Detect CJK ratio if text provided
    if text:
        import re
        cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', text))
        total = len(text.strip())
        cjk_ratio = cjk_chars / total if total > 0 else 0
    else:
        cjk_ratio = 1.0 if lang in ("CN", "JP", "KR") else 0.0

    # Token estimation
    if cjk_ratio > 0.5:
        tokens_per_char = 1 / 1.5  # CJK-heavy
        lang_label = "CJK"
    elif cjk_ratio > 0.2:
        tokens_per_char = 1 / 2.5  # Mixed
        lang_label = "Hỗn hợp"
    else:
        tokens_per_char = 1 / 4.0  # Latin-heavy
        lang_label = "Latin"

    estimated_tokens = int(char_count * tokens_per_char)

    # Estimate cost (rough: prompt tokens)
    # For prompt overhead (~2000 tokens for prompts + context)
    prompt_overhead = 2000
    total_input_tokens = estimated_tokens + prompt_overhead

    return jsonify({
        "char_count": char_count,
        "estimated_tokens": estimated_tokens,
        "total_input_tokens": total_input_tokens,
        "prompt_overhead": prompt_overhead,
        "tokens_per_char": round(tokens_per_char, 3),
        "lang_type": lang_label,
        "cjk_ratio": round(cjk_ratio, 2),
        "display": f"~{estimated_tokens:,} tokens ({char_count:,} ký tự, {lang_label})",
    })


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


@app.route("/api/files", methods=["PUT"])
def save_file():
    """Lưu nội dung file đã chỉnh sửa."""
    data = request.json
    filepath = data.get("filepath", "")
    content = data.get("content", "")

    if not filepath:
        return jsonify({"error": "Thiếu filepath"}), 400

    fp = Path(filepath)
    if not fp.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    try:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/files", methods=["DELETE"])
def delete_file():
    """Xóa file khỏi workspace/input."""
    data = request.json
    filepath = data.get("filepath", "")

    if not filepath:
        return jsonify({"error": "Thiếu filepath"}), 400

    fp = Path(filepath)
    if not fp.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    try:
        fp.unlink()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/done-files", methods=["DELETE"])
def delete_done_file():
    """Xóa file khỏi done hoặc output."""
    data = request.json
    filename = data.get("filename", "")
    location = data.get("location", "done")

    if not filename:
        return jsonify({"error": "Thiếu filename"}), 400

    if location == "done":
        fp = Path("workspace/done") / filename
    else:
        fp = Path("workspace/output") / filename

    if not fp.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    try:
        fp.unlink()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cache-files")
def list_cache_files():
    """Liệt kê các file cache."""
    cache_dir = Path("workspace/cache")
    files = []
    if cache_dir.exists():
        for f in sorted(cache_dir.glob("*.pkl*")):
            try:
                size = f.stat().st_size
                files.append({
                    "name": f.name,
                    "size": size,
                    "size_display": f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB",
                })
            except Exception:
                continue
    return jsonify(files)


@app.route("/api/cache-files", methods=["DELETE"])
def delete_cache_file():
    """Xóa file cache cụ thể."""
    data = request.json
    filename = data.get("filename", "")

    if not filename:
        return jsonify({"error": "Thiếu filename"}), 400

    fp = Path("workspace/cache") / filename
    if not fp.exists():
        return jsonify({"error": "Cache file không tồn tại"}), 404

    try:
        fp.unlink()
        return jsonify({"success": True})
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


# ============================================================
# Project-Based Workspace API
# ============================================================

PROJECTS_DIR = Path("workspace/projects")


def _get_project_dir(slug):
    """Trả về Path thư mục dự án, đảm bảo an toàn."""
    return PROJECTS_DIR / slug


def _load_project_meta(slug):
    """Đọc project.json."""
    meta_file = _get_project_dir(slug) / "project.json"
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_project_meta(slug, meta):
    """Lưu project.json."""
    meta_file = _get_project_dir(slug) / "project.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _project_stats(slug):
    """Tính nhanh stats cho dự án."""
    pdir = _get_project_dir(slug)
    sources = list((pdir / "sources").rglob("*.txt")) if (pdir / "sources").exists() else []
    translated = list((pdir / "translated").rglob("*.txt")) if (pdir / "translated").exists() else []
    return {
        "source_count": len(sources),
        "translated_count": len(translated),
        "source_words": sum(len(f.read_text(encoding="utf-8").split()) for f in sources if f.is_file()),
        "translated_words": sum(len(f.read_text(encoding="utf-8").split()) for f in translated if f.is_file()),
    }


@app.route("/api/projects")
def list_projects():
    """Liệt kê tất cả dự án."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    projects = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta = _load_project_meta(d.name)
        if not meta:
            continue
        stats = _project_stats(d.name)
        projects.append({**meta, "slug": d.name, **stats})
    return jsonify(projects)


@app.route("/api/projects", methods=["POST"])
def create_project():
    """Tạo dự án mới."""
    data = request.json
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Tên dự án không được trống"}), 400

    # Tạo slug từ tên
    import re
    slug = re.sub(r'[^\w\-]', '-', name.lower()).strip('-')
    slug = re.sub(r'-+', '-', slug)
    if not slug:
        slug = "project"

    pdir = _get_project_dir(slug)
    if pdir.exists():
        return jsonify({"error": f"Dự án '{slug}' đã tồn tại"}), 409

    # Tạo cấu trúc thư mục
    for sub in ["sources", "translated", "prompt", "profile", "output"]:
        (pdir / sub).mkdir(parents=True, exist_ok=True)
    (pdir / "profile" / "translation_memory").mkdir(exist_ok=True)

    # Copy prompt mặc định
    prompts_root = Path("prompts")
    for fname in ["01-main.txt", "02-retranslate.txt", "03-correction.txt"]:
        src = prompts_root / fname
        if src.exists():
            import shutil
            shutil.copy2(src, pdir / "prompt" / fname)

    # Tạo project.json
    meta = {
        "name": name,
        "slug": slug,
        "input_lang": data.get("input_lang", "CN"),
        "description": data.get("description", ""),
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _save_project_meta(slug, meta)

    # Tạo template profile files
    for fname, content in [
        ("glossary.txt", "# Bảng thuật ngữ\n# Format: thuật ngữ gốc | thuật ngữ dịch | ghi chú\n"),
        ("characters.txt", "# Bảng nhân vật & quan hệ\n# Format: tên gốc | tên dịch | vai trò | quan hệ\n"),
        ("style_guide.txt", "# Hướng dẫn phong cách dịch\n# Mô tả tone, style, và các quy tắc dịch\n"),
    ]:
        fp = pdir / "profile" / fname
        if not fp.exists():
            fp.write_text(content, encoding="utf-8")

    return jsonify({"success": True, "slug": slug, "meta": meta}), 201


@app.route("/api/projects/<slug>")
def get_project(slug):
    """Chi tiết dự án + danh sách file."""
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    pdir = _get_project_dir(slug)
    stats = _project_stats(slug)

    # Danh sách sources
    sources = []
    src_dir = pdir / "sources"
    if src_dir.exists():
        for f in sorted(src_dir.rglob("*.txt")):
            if f.name.startswith("."):
                continue
            rel = str(f.relative_to(src_dir))
            size = f.stat().st_size
            # Check if translated version exists
            has_translation = (pdir / "translated" / rel).exists()
            sources.append({
                "name": rel,
                "path": str(f),
                "size": size,
                "size_display": f"{size/1024:.1f} KB" if size < 1048576 else f"{size/1048576:.1f} MB",
                "has_translation": has_translation,
            })

    # Danh sách translated
    translated = []
    tr_dir = pdir / "translated"
    if tr_dir.exists():
        for f in sorted(tr_dir.rglob("*.txt")):
            if f.name.startswith("."):
                continue
            rel = str(f.relative_to(tr_dir))
            size = f.stat().st_size
            translated.append({
                "name": rel,
                "path": str(f),
                "size": size,
                "size_display": f"{size/1024:.1f} KB" if size < 1048576 else f"{size/1048576:.1f} MB",
            })

    # Profile files
    profile_files = []
    prof_dir = pdir / "profile"
    if prof_dir.exists():
        for f in sorted(prof_dir.glob("*.txt")):
            profile_files.append({"name": f.name, "size": f.stat().st_size})

    return jsonify({
        **meta,
        "slug": slug,
        **stats,
        "sources": sources,
        "translated": translated,
        "profile_files": profile_files,
    })


@app.route("/api/projects/<slug>", methods=["PUT"])
def update_project(slug):
    """Cập nhật metadata dự án."""
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json
    for key in ["name", "description", "input_lang", "status"]:
        if key in data:
            meta[key] = data[key]
    meta["updated_at"] = datetime.now().isoformat()
    _save_project_meta(slug, meta)
    return jsonify({"success": True, "meta": meta})


@app.route("/api/projects/<slug>", methods=["DELETE"])
def delete_project(slug):
    """Xóa dự án."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    import shutil
    shutil.rmtree(pdir)
    return jsonify({"success": True})


@app.route("/api/projects/<slug>/archive", methods=["POST"])
def archive_project(slug):
    """Nén dự án thành file .zip."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    import shutil
    zip_path = PROJECTS_DIR / f"{slug}"
    shutil.make_archive(str(zip_path), 'zip', str(pdir))
    zip_file = f"{zip_path}.zip"

    return send_file(zip_file, as_attachment=True, download_name=f"{slug}.zip")


# --- Project File APIs ---

@app.route("/api/projects/<slug>/file/<path:filepath>")
def get_project_file(slug, filepath):
    """Đọc nội dung file trong dự án."""
    pdir = _get_project_dir(slug)
    # filepath có thể là sources/xxx hoặc translated/xxx hoặc profile/xxx
    file_path = (pdir / filepath).resolve()

    # Security check
    if not str(file_path).startswith(str(pdir.resolve())):
        return jsonify({"error": "Invalid path"}), 403

    if not file_path.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    try:
        content = file_path.read_text(encoding="utf-8")
        return jsonify({"content": content, "name": file_path.name, "path": str(file_path)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/projects/<slug>/file/<path:filepath>", methods=["PUT"])
def save_project_file(slug, filepath):
    """Lưu nội dung file trong dự án."""
    pdir = _get_project_dir(slug)
    file_path = (pdir / filepath).resolve()

    if not str(file_path).startswith(str(pdir.resolve())):
        return jsonify({"error": "Invalid path"}), 403

    data = request.json
    content = data.get("content", "")

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/projects/<slug>/file/<path:filepath>", methods=["DELETE"])
def delete_project_file(slug, filepath):
    """Xóa file trong dự án."""
    pdir = _get_project_dir(slug)
    file_path = (pdir / filepath).resolve()

    if not str(file_path).startswith(str(pdir.resolve())):
        return jsonify({"error": "Invalid path"}), 403

    if not file_path.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    file_path.unlink()
    return jsonify({"success": True})


@app.route("/api/projects/<slug>/move-done", methods=["POST"])
def project_move_done(slug):
    """Chuyển file source sang translated (đánh dấu dịch xong)."""
    data = request.json
    filename = data.get("filename", "")

    pdir = _get_project_dir(slug)
    src = pdir / "sources" / filename
    if not src.exists():
        return jsonify({"error": "File nguồn không tồn tại"}), 404

    dest = pdir / "translated" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    import shutil
    shutil.move(str(src), str(dest))
    return jsonify({"success": True})


@app.route("/api/projects/<slug>/move-back", methods=["POST"])
def project_move_back(slug):
    """Chuyển file translated về sources."""
    data = request.json
    filename = data.get("filename", "")

    pdir = _get_project_dir(slug)
    src = pdir / "translated" / filename
    if not src.exists():
        return jsonify({"error": "File dịch không tồn tại"}), 404

    dest = pdir / "sources" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()

    src.rename(dest)
    return jsonify({"success": True})


# --- Project Prompt APIs ---

@app.route("/api/projects/<slug>/prompts")
def get_project_prompts(slug):
    """Load prompt dự án (fallback global)."""
    pdir = _get_project_dir(slug)
    prompts = {"main": "", "retranslate": "", "correction": ""}

    # Load global defaults first
    global_prompts = load_prompts("CN")
    prompts.update(global_prompts)

    # Override with project prompts
    prompt_dir = pdir / "prompt"
    if prompt_dir.exists():
        for key, fname in [("main", "01-main.txt"), ("retranslate", "02-retranslate.txt"), ("correction", "03-correction.txt")]:
            fp = prompt_dir / fname
            if fp.exists():
                content = fp.read_text(encoding="utf-8").strip()
                if content:
                    prompts[key] = content

    return jsonify(prompts)


@app.route("/api/projects/<slug>/prompts", methods=["PUT"])
def save_project_prompts(slug):
    """Lưu prompt dự án."""
    pdir = _get_project_dir(slug)
    prompt_dir = pdir / "prompt"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    data = request.json
    for key, fname in [("main", "01-main.txt"), ("retranslate", "02-retranslate.txt"), ("correction", "03-correction.txt")]:
        if key in data:
            (prompt_dir / fname).write_text(data[key], encoding="utf-8")

    return jsonify({"success": True})


# --- Project Translation API ---

@app.route("/api/projects/<slug>/translate", methods=["POST"])
def translate_project_file(slug):
    """Dịch file(s) trong dự án."""
    data = request.json
    filenames = data.get("files", [])

    pdir = _get_project_dir(slug)
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    if not filenames:
        return jsonify({"error": "Không có file nào được chọn"}), 400

    # Load project prompts
    prompts = {"main": "", "retranslate": "", "correction": ""}
    global_prompts = load_prompts(meta.get("input_lang", "CN"))
    prompts.update(global_prompts)
    prompt_dir = pdir / "prompt"
    if prompt_dir.exists():
        for key, fname in [("main", "01-main.txt"), ("retranslate", "02-retranslate.txt"), ("correction", "03-correction.txt")]:
            fp = prompt_dir / fname
            if fp.exists():
                content = fp.read_text(encoding="utf-8").strip()
                if content:
                    prompts[key] = content

    # Load profile context (glossary + characters)
    profile_context = ""
    for pfile in ["glossary.txt", "characters.txt", "style_guide.txt"]:
        fp = pdir / "profile" / pfile
        if fp.exists():
            content = fp.read_text(encoding="utf-8").strip()
            if content and not content.startswith("#"):
                profile_context += f"\n\n--- {pfile} ---\n{content}"

    # If profile context, append to main prompt
    if profile_context.strip():
        prompts["main"] += f"\n\n# Thông tin bổ sung dự án\n{profile_context}"

    config = {
        "model_name": data.get("model", get_default_model()),
        "qa_model": data.get("model", get_default_model()),
        "temperature": float(data.get("temperature", 1.0)),
        "input_lang": meta.get("input_lang", "CN"),
        "chunk_size": int(data.get("chunk_size", get_default_chunk_size())),
        "use_cache": data.get("use_cache", True),
        "prompts": prompts,
        "max_refinement_attempts": 2,
        "min_length_ratio": 0.5,
        "max_length_ratio": 5.0,
        "context_char_count": 500,
    }

    # Dịch file đầu tiên (sequential qua SSE)
    first_file = filenames[0]
    file_path = pdir / "sources" / first_file
    if not file_path.exists():
        return jsonify({"error": f"File không tồn tại: {first_file}"}), 404

    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    output_filename = file_path.stem

    while not progress_queue.empty():
        progress_queue.get()

    def _project_translate_worker():
        """Worker dịch trong project context."""
        global translation_result
        try:
            from plugins.translation.translator import robust_translate
            from services.api_service import ApiManager
            from services.cache_service import TranslationCache

            api_keys = load_api_keys()
            if not api_keys:
                progress_queue.put({"type": "error", "message": "Không tìm thấy API keys"})
                return

            api_manager = ApiManager(api_keys)
            cache = TranslationCache("workspace/cache", enabled=config.get("use_cache", True))

            # Use project TM
            from services.translation_memory import TranslationMemory
            project_tm = TranslationMemory(
                tm_dir=str(pdir / "profile" / "translation_memory"),
                enabled=True,
            )

            from plugins.translation.chunker import process_text_for_chunking
            min_chunk = config["chunk_size"] - 2000
            max_chunk = config["chunk_size"]
            chunks = process_text_for_chunking(text, min_chars=min_chunk, max_chars=max_chunk)

            progress_queue.put({"type": "info", "message": f"📂 Dự án: {meta['name']} | File: {first_file}"})
            progress_queue.put({"type": "info", "message": f"Đã chia thành {len(chunks)} chunks"})

            translated_chunks = []
            prev_context = ""

            for i, chunk in enumerate(chunks):
                progress_queue.put({
                    "type": "progress",
                    "current": i + 1,
                    "total": len(chunks),
                    "percent": int((i + 1) / len(chunks) * 100),
                    "message": f"Đang dịch chunk {i+1}/{len(chunks)}...",
                })

                # Check cache
                cache_key = cache.build_key(chunk, prompts, config, prev_context)
                cached_result = cache.get(cache_key)
                if cached_result:
                    translated_chunks.append(cached_result)
                    ctx_len = config.get("context_char_count", 500)
                    prev_context = cached_result[-ctx_len:] if len(cached_result) > ctx_len else cached_result
                    progress_queue.put({"type": "info", "message": f"Chunk {i+1}: Cache ✅"})
                    continue

                # Check TM
                tm_match = project_tm.find_match(chunk)
                if tm_match and tm_match.get("similarity", 0) >= 0.9:
                    result = tm_match["translation"]
                    progress_queue.put({"type": "info", "message": f"Chunk {i+1}: TM {tm_match['similarity']:.0%} 📚"})
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
                        project_tm.add_translation(chunk, result, output_filename)
                    else:
                        progress_queue.put({"type": "error", "message": f"Dịch thất bại chunk {i+1}: {status}"})
                        return

                if result:
                    translated_chunks.append(result)
                    ctx_len = config.get("context_char_count", 500)
                    prev_context = result[-ctx_len:] if len(result) > ctx_len else result

            full_translation = "\n\n".join(translated_chunks)

            # Lưu vào translated/ (giữ nguyên tên file)
            out_file = pdir / "translated" / first_file
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(full_translation, encoding="utf-8")

            translation_result = {
                "text": full_translation,
                "filename": first_file,
                "path": str(out_file),
            }

            # Update project meta
            meta["updated_at"] = datetime.now().isoformat()
            _save_project_meta(slug, meta)

            calculate_stats()
            progress_queue.put({
                "type": "complete",
                "message": f"✅ Hoàn tất: {first_file} → translated/{first_file}",
                "percent": 100,
            })
        except Exception as e:
            progress_queue.put({"type": "error", "message": f"❌ Lỗi: {str(e)}"})

    thread = Thread(target=_project_translate_worker, daemon=True)
    thread.start()
    return jsonify({"status": "started", "file": first_file})


# ============================================================
# Plugin Execution API
# ============================================================

plugin_progress = {}  # plugin_id -> {status, messages[], result}


@app.route("/api/plugins/epub-converter", methods=["POST"])
def run_epub_converter():
    """Chạy EPUB Converter plugin."""
    import uuid
    data = request.json
    direction = data.get("direction", "epub_to_text")  # epub_to_text | text_to_epub
    plugin_id = str(uuid.uuid4())[:8]

    plugin_progress[plugin_id] = {"status": "running", "messages": [], "result": None}

    def _log(msg):
        plugin_progress[plugin_id]["messages"].append(msg)

    def _run():
        try:
            if direction == "epub_to_text":
                from plugins.epub_converter.epub_to_text.epub2text import convert_epub

                class Args:
                    pass
                args = Args()
                args.epub_path = data.get("epub_path", "")
                args.out_dir = data.get("out_dir", "workspace/input")
                args.mode = data.get("mode", "single")
                args.ext = data.get("ext", "txt")
                args.underline = data.get("underline", False)
                args.include_nonspine = data.get("include_nonspine", False)
                args.preserve_dirs = data.get("preserve_dirs", False)
                args.prefix_index = data.get("prefix_index", True)

                if not args.epub_path or not Path(args.epub_path).exists():
                    _log(f"❌ Lỗi: Không tìm thấy file EPUB: {args.epub_path}")
                    plugin_progress[plugin_id]["status"] = "error"
                    return

                _log(f"📖 Bắt đầu chuyển đổi EPUB → {args.ext.upper()}: {args.epub_path}")
                _log(f"📂 Thư mục đầu ra: {args.out_dir}")
                _log(f"⚙️ Chế độ: {args.mode} | Giữ underline: {args.underline}")

                # Redirect stdout to capture progress
                import io
                import contextlib
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    convert_epub(args)

                for line in buf.getvalue().strip().split('\n'):
                    if line.strip():
                        _log(line.strip())

                _log("✅ Chuyển đổi EPUB thành công!")
                plugin_progress[plugin_id]["status"] = "done"
                plugin_progress[plugin_id]["result"] = {"output_dir": args.out_dir}

            elif direction == "text_to_epub":
                from plugins.epub_converter.text_to_epub.main import process_book_directory

                directory = Path(data.get("directory", ""))
                use_markdown = data.get("use_markdown", False)
                split_chapters = data.get("split_chapters", True)

                if not directory.exists() or not directory.is_dir():
                    _log(f"❌ Lỗi: Thư mục không tồn tại: {directory}")
                    plugin_progress[plugin_id]["status"] = "error"
                    return

                _log(f"📝 Bắt đầu chuyển đổi Text → EPUB: {directory}")
                _log(f"⚙️ Markdown: {use_markdown} | Tách chương: {split_chapters}")

                import io
                import contextlib
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    process_book_directory(directory, use_markdown, split_chapters)

                for line in buf.getvalue().strip().split('\n'):
                    if line.strip():
                        _log(line.strip())

                _log("✅ Tạo EPUB thành công!")
                plugin_progress[plugin_id]["status"] = "done"
                plugin_progress[plugin_id]["result"] = {"output_dir": str(directory)}

            else:
                _log(f"❌ Hướng chuyển đổi không hợp lệ: {direction}")
                plugin_progress[plugin_id]["status"] = "error"

        except Exception as e:
            _log(f"❌ Lỗi: {str(e)}")
            plugin_progress[plugin_id]["status"] = "error"

    thread = Thread(target=_run, daemon=True)
    thread.start()
    return jsonify({"success": True, "plugin_id": plugin_id})


@app.route("/api/plugins/ocr", methods=["POST"])
def run_ocr():
    """Chạy OCR Reader plugin."""
    import uuid
    data = request.json
    plugin_id = str(uuid.uuid4())[:8]

    plugin_progress[plugin_id] = {"status": "running", "messages": [], "result": None}

    def _log(msg):
        plugin_progress[plugin_id]["messages"].append(msg)

    def _run():
        try:
            input_path = data.get("input_path", "")
            output_path = data.get("output_path", "")
            pages = data.get("pages", None)
            process_mode = data.get("process_mode", "process")
            skip_steps = data.get("skip_steps", None)

            if not input_path or not Path(input_path).exists():
                _log(f"❌ Lỗi: Không tìm thấy file: {input_path}")
                plugin_progress[plugin_id]["status"] = "error"
                return

            if not output_path:
                # Auto-generate output path
                inp = Path(input_path)
                output_path = str(inp.with_suffix('.txt'))

            _log(f"🔍 Bắt đầu OCR: {input_path}")
            _log(f"📂 Đầu ra: {output_path}")
            _log(f"⚙️ Chế độ: {process_mode}")

            from plugins.ocr.ocr_engine import ocr_file

            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = ocr_file(
                    input_path,
                    pages=pages,
                    output_path=output_path,
                    skip_steps=skip_steps,
                    process_mode=process_mode
                )

            for line in buf.getvalue().strip().split('\n'):
                if line.strip():
                    _log(line.strip())

            if result and result.get('text'):
                _log(f"✅ OCR hoàn tất! Đã xuất → {output_path}")
                plugin_progress[plugin_id]["status"] = "done"
                plugin_progress[plugin_id]["result"] = {
                    "output_path": output_path,
                    "char_count": len(result.get('text', ''))
                }
            else:
                _log("⚠️ OCR hoàn tất nhưng không trích xuất được text.")
                plugin_progress[plugin_id]["status"] = "done"

        except Exception as e:
            _log(f"❌ Lỗi: {str(e)}")
            plugin_progress[plugin_id]["status"] = "error"

    thread = Thread(target=_run, daemon=True)
    thread.start()
    return jsonify({"success": True, "plugin_id": plugin_id})


@app.route("/api/plugins/progress/<plugin_id>")
def get_plugin_progress(plugin_id):
    """Lấy tiến trình của plugin đang chạy."""
    info = plugin_progress.get(plugin_id)
    if not info:
        return jsonify({"error": "Plugin ID không tồn tại"}), 404

    return jsonify({
        "status": info["status"],
        "messages": info["messages"],
        "result": info["result"]
    })


@app.route("/api/plugins/list")
def list_plugins():
    """Liệt kê các plugin khả dụng."""
    plugins_info = [
        {
            "id": "epub_converter",
            "name": "EPUB Converter",
            "icon": "📚",
            "description": "Chuyển đổi EPUB ↔ Text/Markdown",
            "sub_tools": [
                {"id": "epub_to_text", "name": "EPUB → Text", "description": "Trích xuất nội dung EPUB sang text/markdown"},
                {"id": "text_to_epub", "name": "Text → EPUB", "description": "Đóng gói text/markdown thành EPUB3"}
            ]
        },
        {
            "id": "ocr",
            "name": "OCR Reader",
            "icon": "🔍",
            "description": "Nhận dạng ký tự từ PDF/Ảnh",
            "sub_tools": [
                {"id": "ocr", "name": "PDF/Ảnh → Text", "description": "OCR hỗ trợ đa ngôn ngữ sử dụng Tesseract + AI cleanup"}
            ]
        }
    ]
    return jsonify(plugins_info)


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
