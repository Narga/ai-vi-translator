# webui/routes/plugins.py - v5.0.0
# Blueprint: Plugin Execution API (EPUB Converter, OCR)

import uuid
import logging
from pathlib import Path
from threading import Thread

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

plugins_bp = Blueprint("plugins", __name__)

plugin_progress = {}  # plugin_id -> {status, messages[], result}


@plugins_bp.route("/api/plugins/epub-converter", methods=["POST"])
def run_epub_converter():
    """Chạy EPUB Converter plugin."""
    data = request.json
    direction = data.get("direction", "epub_to_text")
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


@plugins_bp.route("/api/plugins/ocr", methods=["POST"])
def run_ocr():
    """Chạy OCR Reader plugin."""
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


@plugins_bp.route("/api/plugins/progress/<plugin_id>")
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


@plugins_bp.route("/api/plugins/list")
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
