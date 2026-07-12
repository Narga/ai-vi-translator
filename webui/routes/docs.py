# webui/routes/docs.py
# Blueprint: Project Documentation Reader API

import logging
from pathlib import Path

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

docs_bp = Blueprint("docs", __name__)

DOCS_ROOT = Path("docs")
ALLOWED_EXTENSIONS = {".txt", ".md", ".html"}


def _get_docs_root() -> Path:
    """Trả về đường dẫn tuyệt đối đến thư mục docs/, resolve từ CWD."""
    return DOCS_ROOT.resolve()


@docs_bp.route("/api/docs")
def list_docs():
    """Liệt kê tất cả tài liệu trong thư mục docs/ (đệ quy).

    Returns:
        JSON list các object: {"path": "relative/to/docs", "name": "filename.md", "ext": ".md"}
        Sắp xếp: thư mục con trước, sau đó theo tên alphabet.
    """
    docs_root = _get_docs_root()
    if not docs_root.exists():
        return jsonify([])

    files = []
    for fp in sorted(docs_root.rglob("*")):
        if fp.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if not fp.is_file():
            continue
        rel = fp.relative_to(docs_root)
        files.append({
            "path": str(rel).replace("\\", "/"),  # Windows-safe
            "name": fp.name,
            "ext": fp.suffix.lower(),
            "dir": str(rel.parent).replace("\\", "/") if rel.parent != Path(".") else "",
        })

    return jsonify(files)


@docs_bp.route("/api/docs/content")
def get_doc_content():
    """Đọc nội dung một tài liệu. Có kiểm tra bảo mật path traversal.

    Query params:
        path (str): Đường dẫn tương đối so với thư mục docs/ (ví dụ: "MANUAL.md").

    Returns:
        JSON: {"content": "...", "ext": ".md"}
    """
    rel_path = request.args.get("path", "").strip()
    if not rel_path:
        return jsonify({"error": "Thiếu tham số path"}), 400

    docs_root = _get_docs_root()
    # Kiểm tra bảo mật: resolve và xác nhận nằm trong docs_root
    try:
        target = (docs_root / rel_path).resolve()
    except Exception:
        return jsonify({"error": "Đường dẫn không hợp lệ"}), 400

    if not str(target).startswith(str(docs_root)):
        logger.warning(f"Path traversal attempt: {rel_path}")
        return jsonify({"error": "Truy cập bị từ chối"}), 403

    if not target.exists() or not target.is_file():
        return jsonify({"error": "Tài liệu không tồn tại"}), 404

    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Định dạng tệp không được hỗ trợ"}), 400

    content = target.read_text(encoding="utf-8", errors="replace")
    return jsonify({"content": content, "ext": target.suffix.lower()})
