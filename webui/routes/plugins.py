# webui/routes/plugins.py - v5.0.0
# Blueprint: Plugin Execution API (EPUB Converter, OCR)

import uuid
import logging
from pathlib import Path
from threading import Thread
import time
import json
from functools import wraps

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

plugins_bp = Blueprint("plugins", __name__)

plugin_progress = {}  # plugin_id -> {status, messages[], result, updated_at}
PLUGINS_JSON_PATH = Path("config/plugins.json")

def load_plugins_state():
    if not PLUGINS_JSON_PATH.exists():
        return {}
    try:
        with open(PLUGINS_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Lỗi đọc config/plugins.json: {e}")
        return {}

def save_plugins_state(state):
    try:
        PLUGINS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PLUGINS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logger.error(f"Lỗi ghi config/plugins.json: {e}")

def require_plugin_enabled(plugin_id):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            state = load_plugins_state()
            enabled = state.get(plugin_id, {}).get("enabled", True)
            if not enabled:
                return jsonify({"error": f"Plugin '{plugin_id}' đã bị tắt"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def cleanup_plugin_progress():
    now = time.time()
    to_delete = []
    for pid, info in plugin_progress.items():
        if info["status"] in ["done", "error"]:
            updated_at = info.get("updated_at", 0)
            if now - updated_at > 1800:  # 30 minutes
                to_delete.append(pid)
    for pid in to_delete:
        del plugin_progress[pid]


@plugins_bp.route("/api/projects/<slug>/plugins/epub-converter", methods=["POST"])
@require_plugin_enabled("epub_converter")
def run_epub_converter(slug):
    """Chạy EPUB Converter plugin."""
    cleanup_plugin_progress()
    data = request.json
    direction = data.get("direction", "epub_to_text")
    plugin_id = str(uuid.uuid4())[:8]

    plugin_progress[plugin_id] = {"status": "running", "messages": [], "result": None, "updated_at": time.time()}

    def _log(msg):
        plugin_progress[plugin_id]["messages"].append(msg)
        plugin_progress[plugin_id]["updated_at"] = time.time()

    def _run():
        try:
            from plugins.epub_converter.plugin import Plugin
            plugin = Plugin()
            plugin.initialize({"out_dir": f"workspace/projects/{slug}/output"})

            import io
            import contextlib
            buf = io.StringIO()

            if direction == "epub_to_text":
                input_path = Path(data.get("epub_path", ""))
                output_path = Path(data.get("out_dir", f"workspace/projects/{slug}/output"))
                
                if not input_path.exists():
                    _log(f"❌ Lỗi: Không tìm thấy file EPUB: {input_path}")
                    plugin_progress[plugin_id]["status"] = "error"
                    return

                options = {
                    "single_file": data.get("mode", "single") == "single",
                    "preserve_underline": data.get("underline", False),
                    "include_nonspine": data.get("include_nonspine", False)
                }

                _log(f"📖 Bắt đầu chuyển đổi EPUB → Text/MD: {input_path}")
                _log(f"📂 Thư mục đầu ra: {output_path}")

                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    success = plugin.convert(input_path, output_path, **options)

                for line in buf.getvalue().strip().split('\n'):
                    if line.strip():
                        _log(line.strip())

                if success:
                    _log("✅ Chuyển đổi EPUB thành công!")
                    plugin_progress[plugin_id]["status"] = "done"
                    plugin_progress[plugin_id]["result"] = {"output_dir": str(output_path)}
                else:
                    _log("❌ Chuyển đổi EPUB thất bại!")
                    plugin_progress[plugin_id]["status"] = "error"

            elif direction == "text_to_epub":
                input_path = Path(data.get("directory", f"workspace/projects/{slug}/translated"))
                output_path = Path(f"workspace/projects/{slug}/output")

                if not input_path.exists() or not input_path.is_dir():
                    _log(f"❌ Lỗi: Thư mục không tồn tại: {input_path}")
                    plugin_progress[plugin_id]["status"] = "error"
                    return

                options = {
                    "use_markdown": data.get("use_markdown", False),
                    "split_chapters": data.get("split_chapters", True)
                }

                _log(f"📝 Bắt đầu chuyển đổi Text → EPUB: {input_path}")

                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    success = plugin.convert(input_path, output_path, **options)

                for line in buf.getvalue().strip().split('\n'):
                    if line.strip():
                        _log(line.strip())

                if success:
                    _log("✅ Tạo EPUB thành công!")
                    plugin_progress[plugin_id]["status"] = "done"
                    plugin_progress[plugin_id]["result"] = {"output_dir": str(output_path)}
                else:
                    _log("❌ Tạo EPUB thất bại!")
                    plugin_progress[plugin_id]["status"] = "error"

            else:
                _log(f"❌ Hướng chuyển đổi không hợp lệ: {direction}")
                plugin_progress[plugin_id]["status"] = "error"

        except Exception as e:
            _log(f"❌ Lỗi: {str(e)}")
            plugin_progress[plugin_id]["status"] = "error"
        finally:
            plugin_progress[plugin_id]["updated_at"] = time.time()

    thread = Thread(target=_run, daemon=True)
    thread.start()
    return jsonify({"success": True, "plugin_id": plugin_id})


@plugins_bp.route("/api/projects/<slug>/plugins/ocr", methods=["POST"])
@require_plugin_enabled("ocr")
def run_ocr(slug):
    """Chạy OCR Reader plugin."""
    cleanup_plugin_progress()
    data = request.json
    plugin_id = str(uuid.uuid4())[:8]

    plugin_progress[plugin_id] = {"status": "running", "messages": [], "result": None, "updated_at": time.time()}

    def _log(msg):
        plugin_progress[plugin_id]["messages"].append(msg)
        plugin_progress[plugin_id]["updated_at"] = time.time()

    def _run():
        try:
            from plugins.ocr.plugin import Plugin
            plugin = Plugin()
            plugin.initialize({"out_dir": f"workspace/projects/{slug}/output"})

            input_path = data.get("input_path", "")
            output_path = data.get("output_path", f"workspace/projects/{slug}/output/ocr_result.txt")
            
            if not input_path or not Path(input_path).exists():
                _log(f"❌ Lỗi: Không tìm thấy file: {input_path}")
                plugin_progress[plugin_id]["status"] = "error"
                return

            if not output_path:
                inp = Path(input_path)
                output_path = str(inp.with_suffix('.txt'))

            options = {
                "pages": data.get("pages", None),
                "process_mode": data.get("process_mode", "process"),
                "skip_steps": data.get("skip_steps", None)
            }

            _log(f"🔍 Bắt đầu OCR: {input_path}")
            _log(f"📂 Đầu ra: {output_path}")
            _log(f"⚙️ Chế độ: {options['process_mode']}")

            import io
            import contextlib
            buf = io.StringIO()

            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                success = plugin.convert(Path(input_path), Path(output_path), **options)

            for line in buf.getvalue().strip().split('\n'):
                if line.strip():
                    _log(line.strip())

            if success:
                _log(f"✅ OCR hoàn tất! Đã xuất → {output_path}")
                plugin_progress[plugin_id]["status"] = "done"
                plugin_progress[plugin_id]["result"] = {
                    "output_path": output_path
                }
            else:
                _log("⚠️ OCR hoàn tất nhưng không trích xuất được text hoặc có lỗi.")
                plugin_progress[plugin_id]["status"] = "error"

        except Exception as e:
            _log(f"❌ Lỗi: {str(e)}")
            plugin_progress[plugin_id]["status"] = "error"
        finally:
            plugin_progress[plugin_id]["updated_at"] = time.time()

    thread = Thread(target=_run, daemon=True)
    thread.start()
    return jsonify({"success": True, "plugin_id": plugin_id})


@plugins_bp.route("/api/plugins/progress/<plugin_id>")
def get_plugin_progress(plugin_id):
    """Lấy tiến trình của plugin đang chạy."""
    cleanup_plugin_progress()
    info = plugin_progress.get(plugin_id)
    if not info:
        return jsonify({"error": "Plugin ID không tồn tại"}), 404

    return jsonify({
        "status": info["status"],
        "messages": info["messages"],
        "result": info["result"]
    })


@plugins_bp.route("/api/plugins/list")
def list_plugins():
    """Liệt kê các plugin khả dụng."""
    state = load_plugins_state()
    plugins_info = [
        {
            "id": "translation",
            "name": "Translation",
            "description": "Dịch thuật văn bản sử dụng AI (Gemini/OpenAI).",
            "version": "3.0.0",
            "author": "Novel Translator",
            "enabled": state.get("translation", {}).get("enabled", True),
            "is_core": True,
            "has_settings": False,
            "workspace_tab": None
        },
        {
            "id": "spellcheck",
            "name": "Spell Check",
            "description": "Kiểm tra chính tả và sửa lỗi bản dịch bằng AI.",
            "version": "3.0.0",
            "author": "Novel Translator",
            "enabled": state.get("spellcheck", {}).get("enabled", True),
            "is_core": True,
            "has_settings": False,
            "workspace_tab": None
        },
        {
            "id": "epub_converter",
            "workspace_tab": "ebook-kit",
            "name": "eBook Kit",
            "legacy_name": "EPUB Converter",
            "description": "Chuyển đổi EPUB sang Text/Markdown và đóng gói Text/Markdown thành EPUB.",
            "version": "3.0.0",
            "author": "Novel Translator",
            "enabled": state.get("epub_converter", {}).get("enabled", True),
            "is_core": False,
            "has_settings": False
        },
        {
            "id": "ocr",
            "workspace_tab": "ocr-toolbox",
            "name": "OCR Toolbox",
            "legacy_name": "OCR Reader",
            "description": "Nhận dạng ký tự từ PDF/ảnh, hỗ trợ cleanup và spell check bằng AI.",
            "version": "3.0.3",
            "author": "Novel Translator",
            "enabled": state.get("ocr", {}).get("enabled", True),
            "is_core": False,
            "has_settings": True
        }
    ]
    return jsonify(plugins_info)

@plugins_bp.route("/api/plugins/<plugin_id>", methods=["PATCH"])
def update_plugin(plugin_id):
    data = request.json
    enabled = data.get("enabled")
    
    if plugin_id in ["translation", "spellcheck"]:
        return jsonify({"error": "Không thể tắt core plugin"}), 400
        
    state = load_plugins_state()
    if plugin_id not in state:
        state[plugin_id] = {}
    
    if enabled is not None:
        state[plugin_id]["enabled"] = bool(enabled)
        save_plugins_state(state)
        
    # Return updated plugin info
    list_resp = list_plugins()
    plugins = json.loads(list_resp.get_data(as_text=True))
    plugin_info = next((p for p in plugins if p["id"] == plugin_id), None)
    
    return jsonify(plugin_info)

@plugins_bp.route("/api/plugins/<plugin_id>/settings", methods=["GET"])
def get_plugin_settings(plugin_id):
    # For phase 1, just return empty schema if supported
    return jsonify({"settings": {}})

@plugins_bp.route("/api/plugins/<plugin_id>/settings", methods=["PUT"])
def update_plugin_settings(plugin_id):
    # For phase 1, ignore
    return jsonify({"success": True})
