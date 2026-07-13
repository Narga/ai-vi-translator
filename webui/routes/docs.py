# webui/routes/docs.py
# Blueprint: Project Documentation Reader API

import logging
from pathlib import Path

from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

docs_bp = Blueprint("docs", __name__)

ALLOWED_EXTENSIONS = {".txt", ".md", ".html"}


def _get_workspace_root() -> Path:
    """Trả về đường dẫn tuyệt đối đến thư mục gốc của dự án."""
    return Path(".").resolve()


def _get_docs_config():
    """Đọc cấu hình đường dẫn tài liệu từ AppConfigService."""
    from backend.infrastructure.config.app_config_service import AppConfigService
    config_service = AppConfigService()
    paths_str = config_service.get("DOCS", "INCLUDED_PATHS", fallback="docs, .agent, .agents, .cloud")
    include_root = config_service.get("DOCS", "INCLUDE_ROOT_FILES", fallback=True, value_type=bool)

    # Tách các đường dẫn
    paths = [p.strip() for p in paths_str.split(",") if p.strip()]
    return paths, include_root


@docs_bp.route("/api/docs/config", methods=["GET", "POST"])
def manage_docs_config():
    """Đọc hoặc ghi cấu hình đường dẫn tài liệu."""
    from backend.infrastructure.config.app_config_service import AppConfigService
    config_service = AppConfigService()

    if request.method == "POST":
        data = request.get_json() or {}
        paths = data.get("paths", "").strip()
        include_root = data.get("include_root", True)

        config_service.set_value("DOCS", "INCLUDED_PATHS", paths)
        config_service.set_value("DOCS", "INCLUDE_ROOT_FILES", str(include_root).lower())
        config_service.save()
        return jsonify({"success": True})

    # GET
    paths = config_service.get("DOCS", "INCLUDED_PATHS", fallback="docs, .agent, .agents, .cloud")
    include_root = config_service.get("DOCS", "INCLUDE_ROOT_FILES", fallback=True, value_type=bool)
    return jsonify({"paths": paths, "include_root": include_root})


@docs_bp.route("/api/docs")
def list_docs():
    """Liệt kê tất cả tài liệu trong các thư mục cấu hình và thư mục gốc."""
    workspace_root = _get_workspace_root()
    paths, include_root = _get_docs_config()

    files = []
    seen_paths = set()

    # 1. Quét các tập tin ở thư mục gốc (không đệ quy để tránh quét thư mục rác lớn như .venv, webui...)
    if include_root:
        for fp in sorted(workspace_root.iterdir()):
            if fp.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            if not fp.is_file():
                continue
            abs_path = fp.resolve()
            if abs_path in seen_paths:
                continue
            seen_paths.add(abs_path)
            files.append({
                "path": fp.name,
                "name": fp.name,
                "ext": fp.suffix.lower(),
                "dir": "",
            })

    # 2. Quét các thư mục được chỉ định trong cấu hình đệ quy
    for path_str in paths:
        if path_str == ".":
            continue

        dir_path = (workspace_root / path_str).resolve()
        # Đảm bảo đường dẫn hợp lệ và nằm trong thư mục gốc
        if not dir_path.exists() or not dir_path.is_dir():
            continue
        if not str(dir_path).startswith(str(workspace_root)):
            continue

        for fp in sorted(dir_path.rglob("*")):
            if fp.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            if not fp.is_file():
                continue
            abs_path = fp.resolve()
            if abs_path in seen_paths:
                continue
            seen_paths.add(abs_path)

            rel_to_workspace = fp.relative_to(workspace_root)
            files.append({
                "path": str(rel_to_workspace).replace("\\", "/"),
                "name": fp.name,
                "ext": fp.suffix.lower(),
                "dir": str(rel_to_workspace.parent).replace("\\", "/") if rel_to_workspace.parent != Path(".") else "",
            })

    return jsonify(files)


@docs_bp.route("/api/docs/content")
def get_doc_content():
    """Đọc nội dung một tài liệu. Có kiểm tra bảo mật path traversal và quyền truy cập."""
    rel_path = request.args.get("path", "").strip()
    if not rel_path:
        return jsonify({"error": "Thiếu tham số path"}), 400

    workspace_root = _get_workspace_root()
    # Kiểm tra bảo mật: resolve và xác nhận nằm trong workspace_root
    try:
        target = (workspace_root / rel_path).resolve()
    except Exception:
        return jsonify({"error": "Đường dẫn không hợp lệ"}), 400

    if not str(target).startswith(str(workspace_root)):
        logger.warning(f"Path traversal attempt: {rel_path}")
        return jsonify({"error": "Truy cập bị từ chối"}), 403

    # Kiểm tra phân quyền truy cập: tệp tin phải thuộc các đường dẫn được cấu hình
    paths, include_root = _get_docs_config()
    is_allowed = False

    # Nếu là tệp ở thư mục gốc trực tiếp
    if include_root and target.parent == workspace_root:
        is_allowed = True

    # Nếu thuộc các thư mục con được cấu hình
    if not is_allowed:
        for path_str in paths:
            if path_str == ".":
                continue
            dir_path = (workspace_root / path_str).resolve()
            if str(target).startswith(str(dir_path)):
                is_allowed = True
                break

    if not is_allowed:
        logger.warning(f"Unauthorized document access attempt: {rel_path}")
        return jsonify({"error": "Truy cập bị từ chối: Tệp tin không nằm trong vùng tài liệu được cấp quyền"}), 403

    if not target.exists() or not target.is_file():
        return jsonify({"error": "Tài liệu không tồn tại"}), 404

    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Định dạng tệp không được hỗ trợ"}), 400

    content = target.read_text(encoding="utf-8", errors="replace")
    return jsonify({"content": content, "ext": target.suffix.lower()})
