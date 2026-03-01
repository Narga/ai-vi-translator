# webui/routes/prompts.py - v5.0.0
# Blueprint: Prompt Sets (Genre-based Prompt Management)

import json
import shutil
from pathlib import Path

from flask import Blueprint, request, jsonify

prompts_bp = Blueprint("prompts", __name__)

GENRES_DIR = Path("prompts/genres")


@prompts_bp.route("/api/prompt-sets")
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
        meta["has_main"] = (genre_dir / "main.txt").exists()
        meta["has_retranslate"] = (genre_dir / "retranslate.txt").exists()
        meta["has_correction"] = (genre_dir / "correction.txt").exists()
        sets.append(meta)
    sets.sort(key=lambda x: x.get("order", 99))
    return jsonify(sets)


@prompts_bp.route("/api/prompt-sets/<genre>")
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
    for key, fname in [("main", "main.txt"), ("retranslate", "retranslate.txt"), ("correction", "correction.txt")]:
        content = prompts.get(key, "")
        with open(genre_dir / fname, "w", encoding="utf-8") as f:
            f.write(content)

    return jsonify({"success": True, "slug": slug})


@prompts_bp.route("/api/prompt-sets/<genre>", methods=["PUT"])
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

    for key, fname in [("main", "main.txt"), ("retranslate", "retranslate.txt"), ("correction", "correction.txt")]:
        if key in prompts:
            with open(genre_dir / fname, "w", encoding="utf-8") as f:
                f.write(prompts[key])

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


@prompts_bp.route("/api/prompt-sets/<genre>/activate", methods=["POST"])
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
            shutil.copy2(src, prompts_root / dest_name)

    return jsonify({"success": True, "message": f"Đã nạp bộ prompt '{genre}' vào hệ thống"})
