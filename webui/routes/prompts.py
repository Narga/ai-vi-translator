# webui/routes/prompts.py
# Blueprint: Prompt Library + Project Prompts (thay thế genre-based)

import json
from pathlib import Path

from flask import Blueprint, request, jsonify

from backend.infrastructure.config.prompt_service import PromptService, PROMPT_KEY_FILE_MAP

prompts_bp = Blueprint("prompts", __name__)
_prompt_service = PromptService()


# ======================================================================
# Library API
# ======================================================================

@prompts_bp.route("/api/prompts/library")
def list_library():
    """Liệt kê tất cả bộ prompt trong thư viện."""
    sets = _prompt_service.list_library_sets()
    return jsonify(sets)


@prompts_bp.route("/api/prompts/library/<slug>")
def get_library(slug):
    """Lấy nội dung 1 bộ prompt trong thư viện."""
    try:
        data = _prompt_service.get_library_set(slug)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Bộ prompt không tồn tại"}), 404


@prompts_bp.route("/api/prompts/library", methods=["POST"])
def create_library():
    """Tạo bộ prompt mới trong thư viện."""
    data = request.json
    name = data.get("name", "").strip()
    slug = data.get("slug", "").strip().lower().replace(" ", "-")
    if not name or not slug:
        return jsonify({"error": "Thiếu name hoặc slug"}), 400

    # Kiểm tra trùng
    lib_dir = Path("workspace/prompts") / slug
    if lib_dir.exists():
        return jsonify({"error": "Bộ prompt đã tồn tại"}), 409

    prompts = data.get("prompts", {})
    _prompt_service.save_library_set(
        slug=slug, name=name, prompts=prompts,
        description=data.get("description", "")
    )
    return jsonify({"success": True, "slug": slug})


@prompts_bp.route("/api/prompts/library/<slug>", methods=["PUT"])
def update_library(slug):
    """Cập nhật bộ prompt trong thư viện."""
    data = request.json
    prompts = data.get("prompts", {})
    
    # Load existing metadata first
    existing = {}
    try:
        existing = _prompt_service.get_library_set(slug).get("meta", {})
    except Exception:
        pass
        
    name = data.get("name") or existing.get("name") or slug
    description = data.get("description") if "description" in data else (existing.get("description") or "")
    
    _prompt_service.save_library_set(
        slug=slug, name=name, prompts=prompts, description=description
    )
    return jsonify({"success": True})


@prompts_bp.route("/api/prompts/library/<slug>", methods=["DELETE"])
def delete_library(slug):
    """Xóa bộ prompt trong thư viện."""
    if slug == "default":
        return jsonify({"error": "Không thể xóa bộ mặc định"}), 400
    try:
        _prompt_service.delete_library_set(slug)
        return jsonify({"success": True})
    except FileNotFoundError:
        return jsonify({"error": "Bộ prompt không tồn tại"}), 404


# ======================================================================
# Project Prompts API
# ======================================================================

@prompts_bp.route("/api/projects/<slug>/prompts")
def get_project_prompts(slug):
    """Load prompt riêng của dự án, không nạp mặc định hệ thống vào form."""
    from webui.routes.projects import _get_project_dir
    pdir = _get_project_dir(slug)
    if not pdir or not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    project_prompts = _prompt_service.load_merged_prompts(pdir)
    status = _prompt_service.get_project_prompt_status(pdir)
    is_custom = any(status.values())
    return jsonify({**project_prompts, "is_custom": is_custom, "status": status})


@prompts_bp.route("/api/projects/<slug>/prompts", methods=["PUT"])
def save_project_prompts(slug):
    """Lưu prompts tùy chỉnh cho dự án."""
    from webui.routes.projects import _get_project_dir
    pdir = _get_project_dir(slug)
    if not pdir or not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json
    prompts = {}
    for key in PROMPT_KEY_FILE_MAP:
        if key in data:
            prompts[key] = data[key]

    _prompt_service.save_project_prompts(pdir, prompts)
    return jsonify({"success": True})


@prompts_bp.route("/api/projects/<slug>/prompts/import", methods=["POST"])
def import_from_library(slug):
    """Import 1 prompt cụ thể từ thư viện vào dự án."""
    from webui.routes.projects import _get_project_dir
    pdir = _get_project_dir(slug)
    if not pdir or not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json
    library_slug = data.get("library", "").strip()
    key = data.get("key", "").strip()

    if not library_slug or not key:
        return jsonify({"error": "Thiếu library hoặc key"}), 400
    if key not in PROMPT_KEY_FILE_MAP:
        return jsonify({"error": f"Key không hợp lệ: {key}"}), 400

    # Đọc prompt từ library
    try:
        lib_data = _prompt_service.get_library_set(library_slug)
    except FileNotFoundError:
        return jsonify({"error": f"Thư viện '{library_slug}' không tồn tại"}), 404

    content = lib_data["prompts"].get(key, "")
    if not content:
        return jsonify({"error": f"Bộ library không có prompt '{key}'"}), 404

    # Ghi vào project
    prompt_dir = pdir / "prompt"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / PROMPT_KEY_FILE_MAP[key]).write_text(content, encoding="utf-8")

    return jsonify({"success": True, "message": f"Đã nạp '{key}' từ '{library_slug}'"})


