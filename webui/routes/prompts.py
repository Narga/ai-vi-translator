# webui/routes/prompts.py - v6.5.0
# Blueprint: Prompt Sets (Genre-based Prompt Management)

import json
import shutil
from pathlib import Path

from flask import Blueprint, request, jsonify

prompts_bp = Blueprint("prompts", __name__)

# Thống nhất: tất cả bộ prompt lưu tại workspace/prompts/
GENRES_DIR = Path("workspace/prompts")

# Chỉ giữ 1 prompt chính (main) - loại bỏ retranslate/correction theo yêu cầu v6.5.0
PROMPT_KEYS = ["main", "summary", "relationships", "glossary"]


@prompts_bp.route("/api/prompt-sets")
def list_prompt_sets():
    """Liệt kê tất cả bộ prompt."""
    GENRES_DIR.mkdir(parents=True, exist_ok=True)
    sets = []

    # Inject Default System Prompts
    default_dir = GENRES_DIR / "default"
    sets.append(
        {
            "name": "Mặc định (Hệ thống)",
            "slug": "default",
            "order": -1,
            "description": "Bộ prompt mặc định dùng cho dịch thuật và tạo nội dung",
            "has_main": (default_dir / "main_prompt.txt").exists(),
            "has_retranslate": False,
            "has_correction": False,
            "has_summary": (default_dir / "summary_prompt.txt").exists(),
            "has_relationships": (default_dir / "relationship_prompt.txt").exists(),
            "has_glossary": (default_dir / "glossary_prompt.txt").exists(),
        }
    )

    for genre_dir in sorted(GENRES_DIR.iterdir()):
        if not genre_dir.is_dir() or genre_dir.name == "default":
            continue
        meta_file = genre_dir / "meta.json"
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        else:
            meta = {"name": genre_dir.name, "slug": genre_dir.name, "order": 99}
        meta["slug"] = genre_dir.name
        meta["has_main"] = (genre_dir / "main_prompt.txt").exists()
        meta["has_retranslate"] = False
        meta["has_correction"] = False
        meta["has_summary"] = (genre_dir / "summary_prompt.txt").exists()
        meta["has_relationships"] = (genre_dir / "relationship_prompt.txt").exists()
        meta["has_glossary"] = (genre_dir / "glossary_prompt.txt").exists()
        sets.append(meta)
    sets.sort(key=lambda x: x.get("order", 99))
    return jsonify(sets)


@prompts_bp.route("/api/prompt-sets/<genre>")
def get_prompt_set(genre):
    """Lấy nội dung 1 bộ prompt."""
    if genre == "default":
        default_dir = GENRES_DIR / "default"
        meta = {
            "name": "Mặc định (Hệ thống)",
            "slug": "default",
            "description": "Bộ prompt mặc định dùng cho dịch thuật và tạo nội dung",
        }
        prompts = {}
        for key in PROMPT_KEYS:
            fname = f"{key}_prompt.txt" if key != "relationships" else "relationship_prompt.txt"
            fpath = default_dir / fname
            if fpath.exists():
                prompts[key] = fpath.read_text(encoding="utf-8")
            else:
                prompts[key] = ""
        # Giữ backward compat: retranslate/correction rỗng
        prompts.setdefault("retranslate", "")
        prompts.setdefault("correction", "")
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
    for key in PROMPT_KEYS:
        fname = f"{key}_prompt.txt" if key != "relationships" else "relationship_prompt.txt"
        fpath = genre_dir / fname
        if fpath.exists():
            prompts[key] = fpath.read_text(encoding="utf-8")
        else:
            prompts[key] = ""
    prompts.setdefault("retranslate", "")
    prompts.setdefault("correction", "")

    return jsonify({"meta": meta, "prompts": prompts})


@prompts_bp.route("/api/prompt-sets", methods=["POST"])
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

    prompts = data.get("prompts", {})
    for key in PROMPT_KEYS:
        fname = f"{key}_prompt.txt" if key != "relationships" else "relationship_prompt.txt"
        content = prompts.get(key, "")
        (genre_dir / fname).write_text(content, encoding="utf-8")

    return jsonify({"success": True, "slug": slug})


@prompts_bp.route("/api/prompt-sets/<genre>", methods=["PUT"])
def update_prompt_set(genre):
    """Cập nhật bộ prompt."""
    data = request.json
    prompts = data.get("prompts", {})

    if genre == "default":
        default_dir = GENRES_DIR / "default"
        default_dir.mkdir(parents=True, exist_ok=True)
        for key in PROMPT_KEYS:
            if key in prompts:
                fname = f"{key}_prompt.txt" if key != "relationships" else "relationship_prompt.txt"
                (default_dir / fname).write_text(prompts[key], encoding="utf-8")
        return jsonify({"success": True})

    genre_dir = GENRES_DIR / genre
    if not genre_dir.exists():
        return jsonify({"error": "Thể loại không tồn tại"}), 404

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

    for key in PROMPT_KEYS:
        if key in prompts:
            fname = f"{key}_prompt.txt" if key != "relationships" else "relationship_prompt.txt"
            (genre_dir / fname).write_text(prompts[key], encoding="utf-8")

    return jsonify({"success": True})


@prompts_bp.route("/api/prompt-sets/<genre>", methods=["DELETE"])
def delete_prompt_set(genre):
    """Xóa bộ prompt."""
    if genre == "default":
        return jsonify({"error": "Không thể xóa bộ prompt mặc định của hệ thống"}), 400

    genre_dir = GENRES_DIR / genre
    if not genre_dir.exists():
        return jsonify({"error": "Thể loại không tồn tại"}), 404

    shutil.rmtree(genre_dir)
    return jsonify({"success": True})


@prompts_bp.route("/api/prompt-sets/<genre>/use", methods=["POST"])
def use_prompt_set(genre):
    """Sử dụng bộ prompt này làm mặc định cho dịch thuật (copy vào default)."""
    if genre == "default":
        return jsonify({"success": True, "message": "Đã là bộ prompt mặc định"})

    genre_dir = GENRES_DIR / genre
    if not genre_dir.exists():
        return jsonify({"error": "Thể loại không tồn tại"}), 404

    default_dir = GENRES_DIR / "default"
    default_dir.mkdir(parents=True, exist_ok=True)

    # Copy tất cả prompt từ genre vào default
    for key in PROMPT_KEYS:
        fname = f"{key}_prompt.txt" if key != "relationships" else "relationship_prompt.txt"
        src = genre_dir / fname
        if src.exists():
            (default_dir / fname).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    return jsonify({"success": True, "message": f"Đã kích hoạt bộ prompt: {genre}"})
