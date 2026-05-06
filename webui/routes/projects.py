# webui/routes/projects.py - v5.0.0
# Blueprint: Project-Based Workspace API + Translation Memory APIs

import json
import re
import shutil
import logging
from pathlib import Path
from datetime import datetime
from threading import Thread

from flask import Blueprint, request, jsonify, send_file

from webui.helpers import (
    load_api_keys,
    load_prompts,
    calculate_stats,
    get_default_model,
    get_default_chunk_size,
)

logger = logging.getLogger(__name__)

projects_bp = Blueprint("projects", __name__)

PROJECTS_DIR = Path("workspace/projects")


# ============================================================
# Project Helpers
# ============================================================


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
    
    def get_files(folder):
        d = pdir / folder
        return [f for f in d.rglob("*") if f.is_file() and not f.name.startswith(".")] if d.exists() else []
        
    sources = get_files("sources")
    translated = get_files("translated")
    
    def count_words(files):
        total = 0
        for f in files:
            try:
                total += len(f.read_text(encoding="utf-8").split())
            except Exception:
                pass
        return total

    return {
        "source_count": len(sources),
        "translated_count": len(translated),
        "source_words": count_words(sources),
        "translated_words": count_words(translated),
    }


# ============================================================
# Project CRUD
# ============================================================


@projects_bp.route("/api/projects")
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


@projects_bp.route("/api/projects", methods=["POST"])
def create_project():
    """Tạo dự án mới."""
    data = request.json
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Tên dự án không được trống"}), 400

    slug = re.sub(r"[^\w\-]", "-", name.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if not slug:
        slug = "project"

    pdir = _get_project_dir(slug)
    if pdir.exists():
        return jsonify({"error": f"Dự án '{slug}' đã tồn tại"}), 409

    for sub in ["sources", "translated", "prompt", "assets", "output"]:
        (pdir / sub).mkdir(parents=True, exist_ok=True)
    (pdir / "assets" / "translation_memory").mkdir(exist_ok=True)

    prompts_root = Path("workspace/prompts/default")
    for key, fname in [
        ("main", "main_prompt.txt"),
        ("summary", "summary_prompt.txt"),
        ("relationships", "relationship_prompt.txt"),
        ("glossary", "glossary_prompt.txt"),
        ("chinh_ta", "chinh_ta_prompt.txt"),
    ]:
        src = prompts_root / fname
        if src.exists():
            shutil.copy2(src, pdir / "prompt" / fname)
        else:
            # Nếu không có file mặc định, lấy từ load_prompts() (vừa update có DEFAULTS)
            from webui.helpers import load_prompts
            dprompts = load_prompts()
            if key in dprompts:
                (pdir / "prompt" / fname).write_text(dprompts[key], encoding="utf-8")

    meta = {
        "name": name,
        "slug": slug,
        "description": data.get("description", ""),
        "genre": data.get("genre", ""),
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _save_project_meta(slug, meta)

    for fname, content in [
        ("glossary.txt", "# Bảng thuật ngữ\n# Format: thuật ngữ gốc | thuật ngữ dịch | ghi chú\n"),
        (
            "relationship.txt",
            "# Bảng nhân vật & quan hệ\n# Format: tên gốc | tên dịch | vai trò | quan hệ\n",
        ),
        (
            "style_guide.txt",
            "# Hướng dẫn phong cách dịch\n# Mô tả tone, style, và các quy tắc dịch\n",
        ),
        (
            "summary.txt",
            "# Tóm tắt cốt truyện\n# Ghi chú diễn biến chính\n",
        ),
    ]:
        fp = pdir / "assets" / fname
        if not fp.exists():
            fp.write_text(content, encoding="utf-8")

    return jsonify({"success": True, "slug": slug, "meta": meta}), 201


@projects_bp.route("/api/projects/<slug>")
def get_project(slug):
    """Chi tiết dự án + danh sách file."""
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    pdir = _get_project_dir(slug)
    stats = _project_stats(slug)

    sources = []
    src_dir = pdir / "sources"
    if src_dir.exists():
        # Cho phép mọi định dạng, loại bỏ filter .txt .md
        source_files = [f for f in src_dir.rglob("*") if f.is_file()]
        for f in sorted(source_files):
            if f.name.startswith("."):
                continue
            rel = str(f.relative_to(src_dir))
            size = f.stat().st_size
            has_translation = (pdir / "translated" / rel).exists()
            sources.append(
                {
                    "name": rel,
                    "path": str(f),
                    "size": size,
                    "size_display": f"{size / 1024:.1f} KB"
                    if size < 1048576
                    else f"{size / 1048576:.1f} MB",
                    "has_translation": has_translation,
                }
            )

    translated = []
    tr_dir = pdir / "translated"
    if tr_dir.exists():
        # Cho phép mọi định dạng
        translated_files = [f for f in tr_dir.rglob("*") if f.is_file()]
        for f in sorted(translated_files):
            if f.name.startswith("."):
                continue
            rel = str(f.relative_to(tr_dir))
            size = f.stat().st_size
            translated.append(
                {
                    "name": rel,
                    "path": str(f),
                    "size": size,
                    "size_display": f"{size / 1024:.1f} KB"
                    if size < 1048576
                    else f"{size / 1048576:.1f} MB",
                }
            )

    profile_files = []
    prof_dir = pdir / "profile"
    if prof_dir.exists():
        for f in sorted(prof_dir.glob("*.txt")):
            profile_files.append({"name": f.name, "size": f.stat().st_size})

    return jsonify(
        {
            **meta,
            "slug": slug,
            **stats,
            "sources": sources,
            "translated": translated,
            "profile_files": profile_files,
        }
    )


@projects_bp.route("/api/projects/<slug>", methods=["PUT"])
def update_project(slug):
    """Cập nhật metadata dự án."""
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json
    for key in ["name", "description", "genre", "status"]:
        if key in data:
            meta[key] = data[key]
    meta["updated_at"] = datetime.now().isoformat()
    _save_project_meta(slug, meta)
    return jsonify({"success": True, "meta": meta})


@projects_bp.route("/api/projects/<slug>", methods=["DELETE"])
def delete_project(slug):
    """Xóa dự án."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    shutil.rmtree(pdir)
    return jsonify({"success": True})


ARCHIVE_DIR = Path("workspace/archive")


@projects_bp.route("/api/projects/<slug>/archive", methods=["POST"])
def archive_project(slug):
    """Nén dự án và di chuyển sang thư mục archive, sau đó xóa dự án gốc."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    data = request.json or {}
    strategy = data.get("strategy", "check")  # "check", "overwrite", "copy"

    # Target zip names
    base_zip_name = f"{slug}.zip"
    target_zip = ARCHIVE_DIR / base_zip_name

    if strategy == "check":
        return jsonify({"exists": target_zip.exists()})

    final_zip_path = target_zip

    if target_zip.exists() and strategy == "copy":
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_zip_path = ARCHIVE_DIR / f"{slug}_{stamp}.zip"

    # Nén vào thư mục temp hoặc trực tiếp
    temp_zip = PROJECTS_DIR / f"temp_{slug}"
    shutil.make_archive(str(temp_zip), "zip", str(pdir))

    # Di chuyển file zip tới archive
    shutil.move(f"{temp_zip}.zip", final_zip_path)

    # Xóa dự án gốc
    shutil.rmtree(pdir)

    return jsonify({"success": True, "message": f"Đã nén thành công vào {final_zip_path.name}"})


@projects_bp.route("/api/archive", methods=["GET"])
def list_archives():
    """Liệt kê các server đã lưu trữ."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archives = []

    for f in sorted(ARCHIVE_DIR.glob("*.zip")):
        size = f.stat().st_size
        archives.append(
            {
                "filename": f.name,
                "size": size,
                "size_display": f"{size / 1024:.1f} KB"
                if size < 1048576
                else f"{size / 1048576:.1f} MB",
                "mtime": f.stat().st_mtime,
            }
        )

    return jsonify(archives)


@projects_bp.route("/api/archive/restore", methods=["POST"])
def restore_archive():
    """Khôi phục dự án từ archive."""
    data = request.json or {}
    filename = data.get("filename", "")
    if not filename:
        return jsonify({"error": "Chưa chọn file"}), 400

    archive_path = ARCHIVE_DIR / filename
    if not archive_path.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    # Lấy slug từ filename (xóa .zip và suffix ngày tháng nếu có)
    base_slug = filename.replace(".zip", "")
    # Thử check nếu có suffix _YYYYMMDD_HHMMSS
    base_slug = re.sub(r"_\d{8}_\d{6}$", "", base_slug)

    pdir = _get_project_dir(base_slug)

    # Nếu thư mục dự án đã tồn tại
    if pdir.exists():
        # Xử lý tự động đổi tên dự án nếu cần thiết
        return jsonify(
            {
                "error": f"Dự án '{base_slug}' đang tồn tại, vui lòng xóa hoặc đổi tên dự án đó trước."
            }
        ), 409

    # Giải nén
    import zipfile

    try:
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(pdir)

        return jsonify({"success": True, "slug": base_slug})
    except Exception as e:
        if pdir.exists():
            shutil.rmtree(pdir)
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/archive/<filename>", methods=["DELETE"])
def delete_archive(filename):
    """Xóa file lưu trữ."""
    archive_path = ARCHIVE_DIR / filename
    if not archive_path.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    # Prevent path traversal
    if archive_path.parent != ARCHIVE_DIR:
        return jsonify({"error": "Invalid path"}), 403

    archive_path.unlink()
    return jsonify({"success": True})


# ============================================================
# Project File APIs
# ============================================================


@projects_bp.route("/api/projects/<slug>/file/<path:filepath>")
def get_project_file(slug, filepath):
    """Đọc nội dung file trong dự án."""
    pdir = _get_project_dir(slug)
    file_path = (pdir / filepath).resolve()

    if not str(file_path).startswith(str(pdir.resolve())):
        return jsonify({"error": "Invalid path"}), 403

    if not file_path.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    try:
        content = file_path.read_text(encoding="utf-8")
        return jsonify({"content": content, "name": file_path.name, "path": str(file_path)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/<slug>/file/<path:filepath>", methods=["PUT"])
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


@projects_bp.route("/api/projects/<slug>/merge", methods=["POST"])
def merge_project_files(slug):
    """Ghép danh sách các file (thường ở translated/) thành 1 file duy nhất trong thư mục translated."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json
    filenames = data.get("files", [])
    if not filenames or not isinstance(filenames, list):
        return jsonify({"error": "Danh sách file không hợp lệ"}), 400

    # Use project name as the merged file name, placed in translated/
    out_name = f"{slug}.txt"
    out_name = re.sub(r"[^\w\-\.]", "_", out_name)  # Sanitize

    out_path = pdir / "translated" / out_name
    # Ensure translated directory exists
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(out_path, "w", encoding="utf-8") as out_f:
            for fname in filenames:
                # Only allow merging from translated/ or sources/ (prefer translated)
                fpath = pdir / "translated" / fname
                if not fpath.exists():
                    fpath = pdir / "sources" / fname

                if fpath.exists() and fpath.is_file():
                    content = fpath.read_text(encoding="utf-8").strip()
                    if content:
                        out_f.write(content + "\n\n")

        size = out_path.stat().st_size
        return jsonify(
            {
                "success": True,
                "file": out_name,
                "path": str(out_path.relative_to(pdir)),
                "size": size,
            }
        )
    except Exception as e:
        logger.error(f"Error merging files: {e}")
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/<slug>/file/<path:filepath>", methods=["DELETE"])
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


@projects_bp.route("/api/projects/<slug>/upload", methods=["POST"])
def upload_project_file(slug):
    """Upload file text vào thư mục sources/ của dự án."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    if "file" not in request.files:
        return jsonify({"error": "Không tìm thấy file"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Tên file rỗng"}), 400

    # Cho phép mọi định dạng
    safe_name = Path(f.filename).name  # sanitize
    src_dir = pdir / "sources"
    src_dir.mkdir(parents=True, exist_ok=True)
    dest = src_dir / safe_name
    f.save(str(dest))

    size = dest.stat().st_size
    return jsonify(
        {
            "success": True,
            "filename": safe_name,
            "size": size,
            "size_display": f"{size / 1024:.1f} KB"
            if size < 1048576
            else f"{size / 1048576:.1f} MB",
        }
    )


@projects_bp.route("/api/projects/<slug>/chunk/<filename>", methods=["POST"])
def chunk_project_file(slug, filename):
    """Chia file nguồn thành nhiều chunk nhỏ."""
    pdir = _get_project_dir(slug)
    src_file = pdir / "sources" / filename

    if not src_file.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    # Đọc cấu hình chunk size
    data = request.json or {}
    max_chars = data.get("max_chars", 100000)
    min_chars = max(5000, max_chars // 2)

    try:
        from plugins.translation.chunker import process_text_for_chunking

        text = src_file.read_text(encoding="utf-8")
        chunks = process_text_for_chunking(text, min_chars, max_chars)

        if len(chunks) <= 1:
            return jsonify(
                {
                    "success": True,
                    "chunks": 1,
                    "message": "File quá nhỏ, không cần chia chunk.",
                    "files": [filename],
                }
            )

        # Tạo tên chunk: filename_chunk_001.txt, _chunk_002.txt...
        stem = src_file.stem
        ext = src_file.suffix
        created_files = []
        for i, chunk in enumerate(chunks, 1):
            chunk_name = f"{stem}_chunk_{i:03d}{ext}"
            chunk_path = pdir / "sources" / chunk_name
            chunk_path.write_text(chunk, encoding="utf-8")
            created_files.append(chunk_name)

        return jsonify(
            {
                "success": True,
                "chunks": len(chunks),
                "files": created_files,
                "message": f"Đã chia thành {len(chunks)} chunk.",
            }
        )
    except Exception as e:
        logger.error(f"Chunk error: {e}")
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/<slug>/rename", methods=["POST"])
def rename_project_file(slug):
    """Đổi tên file trong dự án."""
    data = request.json
    old_name = data.get("old_name")
    new_name = data.get("new_name")
    section = data.get("section", "sources")  # sources or translated

    if not old_name or not new_name:
        return jsonify({"error": "Thiếu tên file"}), 400

    pdir = _get_project_dir(slug)
    old_path = (pdir / section / old_name).resolve()
    new_path = (pdir / section / new_name).resolve()

    if not str(old_path).startswith(str((pdir / section).resolve())):
        return jsonify({"error": "Invalid path"}), 403
    if not str(new_path).startswith(str((pdir / section).resolve())):
        return jsonify({"error": "Invalid path"}), 403

    if not old_path.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    if new_path.exists():
        return jsonify({"error": f"Tên file '{new_name}' đã tồn tại"}), 409

    try:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)

        # Nếu đổi tên ở sources, tự động đổi tên ở translated nếu có
        if section == "sources":
            old_trans = pdir / "translated" / old_name
            new_trans = pdir / "translated" / new_name
            if old_trans.exists() and not new_trans.exists():
                new_trans.parent.mkdir(parents=True, exist_ok=True)
                old_trans.rename(new_trans)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/<slug>/move-done", methods=["POST"])
def project_move_done(slug):
    """Chuyển file source sang translated."""
    data = request.json
    filename = data.get("filename", "")

    pdir = _get_project_dir(slug)

    # Path traversal check
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Tên file không hợp lệ"}), 403
    src = (pdir / "sources" / filename).resolve()
    if not str(src).startswith(str((pdir / "sources").resolve())):
        return jsonify({"error": "Invalid path"}), 403

    if not src.exists():
        return jsonify({"error": "File nguồn không tồn tại"}), 404

    dest = pdir / "translated" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    shutil.move(str(src), str(dest))
    return jsonify({"success": True})


@projects_bp.route("/api/projects/<slug>/move-back", methods=["POST"])
def project_move_back(slug):
    """Chuyển file translated về sources."""
    data = request.json
    filename = data.get("filename", "")

    pdir = _get_project_dir(slug)

    # Path traversal check
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Tên file không hợp lệ"}), 403
    src = (pdir / "translated" / filename).resolve()
    if not str(src).startswith(str((pdir / "translated").resolve())):
        return jsonify({"error": "Invalid path"}), 403

    if not src.exists():
        return jsonify({"error": "File dịch không tồn tại"}), 404

    dest = pdir / "sources" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()

    src.rename(dest)
    return jsonify({"success": True})


# ============================================================
# Project Prompt APIs
# ============================================================


@projects_bp.route("/api/projects/<slug>/prompts")
def get_project_prompts(slug):
    """Load prompt dự án. CHỈ trả về nếu có prompt riêng của dự án, không nạp mặc định hệ thống vào form."""
    pdir = _get_project_dir(slug)
    prompts = {
        "main": "",
        "summary": "",
        "relationships": "",
        "glossary": "",
        "chinh_ta": "",
        "is_custom": False,
    }

    prompt_dir = pdir / "prompt"
    has_any_custom = False
    if prompt_dir.exists():
        for key, fname in [
            ("main", "main_prompt.txt"),
            ("summary", "summary_prompt.txt"),
            ("relationships", "relationship_prompt.txt"),
            ("glossary", "glossary_prompt.txt"),
            ("chinh_ta", "chinh_ta_prompt.txt"),
        ]:
            fp = prompt_dir / fname
            if fp.exists():
                content = fp.read_text(encoding="utf-8").strip()
                if content:
                    prompts[key] = content
                    has_any_custom = True

    prompts["is_custom"] = has_any_custom
    return jsonify(prompts)


@projects_bp.route("/api/projects/<slug>/prompts", methods=["PUT"])
def save_project_prompts(slug):
    """Lưu prompt dự án."""
    pdir = _get_project_dir(slug)
    prompt_dir = pdir / "prompt"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    data = request.json

    key_fname_map = {
        "main": "main_prompt.txt",
        "summary": "summary_prompt.txt",
        "relationships": "relationship_prompt.txt",
        "glossary": "glossary_prompt.txt",
        "chinh_ta": "chinh_ta_prompt.txt",
    }

    for key, fname in key_fname_map.items():
        if key in data and data[key] is not None:
            fp = prompt_dir / fname
            with open(fp, "w", encoding="utf-8") as f:
                f.write(str(data[key]))

    return jsonify({"success": True})


@projects_bp.route("/api/projects/<slug>/prompts", methods=["DELETE"])
def reset_project_prompts(slug):
    """Xóa tất cả prompt tùy chỉnh của dự án, khôi phục về mặc định hệ thống."""
    import shutil as _shutil
    pdir = _get_project_dir(slug)
    prompt_dir = pdir / "prompt"
    if prompt_dir.exists():
        _shutil.rmtree(prompt_dir)
    return jsonify({"success": True, "message": "Đã khôi phục chỉ dẫn hệ thống"})


@projects_bp.route("/api/projects/<slug>/prompts/import", methods=["POST"])
def import_project_prompts(slug):
    """Copy bộ prompt từ thư viện hệ thống vào thư mục riêng của dự án."""
    import shutil as _shutil
    data = request.json or {}
    genre_slug = data.get("genre", "default")

    pdir = _get_project_dir(slug)
    dest_dir = pdir / "prompt"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Xác định nguồn prompt
    src_dir = Path("workspace/prompts") / genre_slug
    if not src_dir.exists():
        src_dir = Path("workspace/prompts/default")

    if not src_dir.exists():
        # Fallback: ghi từ load_prompts() DEFAULTS
        global_prompts = load_prompts()
        key_fname_map = {
            "main": "main_prompt.txt",
            "summary": "summary_prompt.txt",
            "relationships": "relationship_prompt.txt",
            "glossary": "glossary_prompt.txt",
            "chinh_ta": "chinh_ta_prompt.txt",
        }
        for key, fname in key_fname_map.items():
            if key in global_prompts and global_prompts[key]:
                (dest_dir / fname).write_text(global_prompts[key], encoding="utf-8")
        return jsonify({"success": True, "message": f"Đã nạp chỉ dẫn mặc định hệ thống"})

    # Copy tất cả file .txt từ thư viện vào dự án
    copied = 0
    for f in src_dir.glob("*.txt"):
        _shutil.copy2(f, dest_dir / f.name)
        copied += 1

    display_name = genre_slug if genre_slug != "default" else "Mặc định (Hệ thống)"
    return jsonify({"success": True, "message": f"Đã nạp chỉ dẫn \"{display_name}\" ({copied} file)", "count": copied})


# ============================================================
# Project Guidelines APIs (Phase 3)
# ============================================================


@projects_bp.route("/api/projects/<slug>/guidelines")
def get_project_guidelines(slug):
    """Load tất cả guidelines/profile của dự án."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    assets_dir = pdir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    fields = {
        "summary": "summary.txt",
        "characters": "relationship.txt",
        "glossary": "glossary.txt",
        "style_guide": "style_guide.txt",
        "additional_notes": "additional_notes.txt",
    }

    result = {}
    for key, fname in fields.items():
        fp = assets_dir / fname
        result[key] = fp.read_text(encoding="utf-8") if fp.exists() else ""

    return jsonify(result)


@projects_bp.route("/api/projects/<slug>/guidelines", methods=["PUT"])
def save_project_guidelines(slug):
    """Lưu guidelines/profile dự án."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    assets_dir = pdir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    data = request.json
    fields = {
        "summary": "summary.txt",
        "characters": "relationship.txt",
        "glossary": "glossary.txt",
        "style_guide": "style_guide.txt",
        "additional_notes": "additional_notes.txt",
    }

    saved = []
    for key, fname in fields.items():
        if key in data:
            (assets_dir / fname).write_text(data[key], encoding="utf-8")
            saved.append(key)

    return jsonify({"success": True, "saved": saved})


@projects_bp.route("/api/projects/<slug>/summarize", methods=["POST"])
def summarize_project(slug):
    """AI tạo nội dung theo loại (summary, glossary, relationship, style_guide)."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json
    source_file = data.get("source_file", "")
    content_type = data.get("content_type", "summary")

    # Map content_type -> (prompt_filename, asset_filename, fallback_prompt)
    CONTENT_MAP = {
        "summary": (
            "summary_prompt.txt",
            "summary.txt",
            (
                "Đọc nội dung sau và viết bản TÓM TẮT NGẮN GỌN bằng tiếng Việt, "
                "bao gồm: thể loại, bối cảnh, nhân vật chính, cốt truyện chính (3-5 câu), tone văn.\n\n"
                "--- NỘI DUNG ---\n"
            ),
        ),
        "relationship": (
            "relationship_prompt.txt",
            "relationship.txt",
            (
                "Đọc nội dung sau và liệt kê các NHÂN VẬT quan trọng theo định dạng:\n"
                "tên_gốc | tên_tiếng_việt | vai_trò | quan_hệ\n\n"
                "--- NỘI DUNG ---\n"
            ),
        ),
        "glossary": (
            "glossary_prompt.txt",
            "glossary.txt",
            (
                "Đọc nội dung sau và trích xuất THUẬT NGỮ quan trọng theo định dạng:\n"
                "thuật_ngữ_gốc | thuật_ngữ_tiếng_việt | ghi_chú\n\n"
                "--- NỘI DUNG ---\n"
            ),
        ),
        "style_guide": (
            "style_guide_prompt.txt",
            "style_guide.txt",
            (
                "Đọc nội dung sau và tạo CHỈ DẪN PHONG CÁCH DỊCH bao gồm: "
                "tone văn, cách xưng hô, quy tắc dịch tên riêng, các lưu ý văn phong.\n\n"
                "--- NỘI DUNG ---\n"
            ),
        ),
    }

    if content_type not in CONTENT_MAP:
        return jsonify({"error": f"Loại nội dung không hợp lệ: {content_type}"}), 400

    prompt_filename, asset_filename, fallback_prompt = CONTENT_MAP[content_type]

    # Tìm file nguồn
    src_path = pdir / "sources" / source_file
    if not src_path.is_file():
        src_dir = pdir / "sources"
        all_text = []
        if src_dir.exists():
            for f in sorted(src_dir.rglob("*.txt")):
                all_text.append(f.read_text(encoding="utf-8", errors="ignore"))
            for f in sorted(src_dir.rglob("*.md")):
                all_text.append(f.read_text(encoding="utf-8", errors="ignore"))
        content = "\n\n".join(all_text)
    else:
        content = src_path.read_text(encoding="utf-8", errors="ignore")

    if not content.strip():
        return jsonify({"error": "Không có nội dung nguồn để phân tích"}), 400

    # Giới hạn nội dung
    max_chars = 50000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[... nội dung tiếp theo bị cắt ...]"

    # Nạp prompt chuyên biệt từ thư viện
    PROMPTS_DIR = Path("workspace/prompts")
    meta = _load_project_meta(slug) or {}
    genre = (meta.get("genre") or "").strip()

    prompt_text = ""
    # Thử tìm prompt theo thể loại dự án trước
    if genre:
        genre_prompt = PROMPTS_DIR / genre / prompt_filename
        if genre_prompt.exists():
            prompt_text = genre_prompt.read_text(encoding="utf-8")

    # Fallback về bộ default
    if not prompt_text:
        default_prompt = PROMPTS_DIR / "default" / prompt_filename
        if default_prompt.exists():
            prompt_text = default_prompt.read_text(encoding="utf-8")

    # Fallback hardcoded nếu không có file prompt nào
    if not prompt_text:
        prompt_text = fallback_prompt

    # Ghép prompt + nội dung
    full_prompt = f"{prompt_text}\n{content}"

    try:
        from webui.helpers import get_active_provider

        provider = get_active_provider()
        requested_model = data.get("model", "")

        if provider == "gemini":
            from webui.helpers import load_api_keys, get_default_model

            keys = load_api_keys()
            model = requested_model or get_default_model()
            if not keys:
                return jsonify({"error": "Chưa cấu hình API Key Gemini"}), 400
            from services.genai_client import GenAIClient

            client = GenAIClient(api_key=keys[0])
            result, status = client.generate_content(full_prompt, model=model)
        else:
            from webui.helpers import load_openai_key, get_openai_base_url, get_openai_model

            api_key = load_openai_key()
            if not api_key:
                return jsonify({"error": "Chưa cấu hình API Key OpenAI"}), 400
            from services.openai_client import OpenAIClient

            client = OpenAIClient(
                api_key=api_key,
                base_url=get_openai_base_url(),
                default_model=requested_model or get_openai_model(),
            )
            result, status = client.generate_content(full_prompt)

        if status == "success" and result:
            # Lưu vào đúng file asset tương ứng với content_type
            assets_dir = pdir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            (assets_dir / asset_filename).write_text(result, encoding="utf-8")
            return jsonify({"success": True, "summary": result})
        else:
            return jsonify({"error": f"AI trả về lỗi: {result or status}"}), 500

    except Exception as e:
        logging.getLogger(__name__).error(f"AI Generate error [{content_type}]: {e}")
        return jsonify({"error": str(e)}), 500



# ============================================================

# Project Translation API
# ============================================================


@projects_bp.route("/api/projects/<slug>/translate", methods=["POST"])
def translate_project_file(slug):
    """Dịch file(s) trong dự án."""
    from webui import progress_queue
    import webui as _state

    data = request.json
    filenames = data.get("files", [])

    pdir = _get_project_dir(slug)
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    if not filenames:
        return jsonify({"error": "Không có file nào được chọn"}), 400

    # Load project prompts
    prompts = {"main": ""}
    global_prompts = load_prompts()
    prompts.update(global_prompts)
    prompt_dir = pdir / "prompt"
    if prompt_dir.exists():
        for key, fname in [
            ("main", "main_prompt.txt"),
        ]:
            fp = prompt_dir / fname
            if fp.exists():
                content = fp.read_text(encoding="utf-8").strip()
                if content:
                    prompts[key] = content

    # Load assets context (Static instructions)
    assets_context = ""
    for pfile in ["style_guide.txt"]:
        fp = pdir / "assets" / pfile
        if fp.exists():
            content = fp.read_text(encoding="utf-8").strip()
            if content and not content.startswith("#"):
                assets_context += f"\n\n# Hướng dẫn phong cách\n{content}"

    if assets_context.strip():
        prompts["main"] += assets_context

    # Glossary paths (Dynamic terms)
    glossary_filenames = ["glossary.txt", "relationship.txt"]
    glossary_paths = [
        pdir / "assets" / gf for gf in glossary_filenames if (pdir / "assets" / gf).exists()
    ]

    config = {
        "model_name": data.get("model", get_default_model()),
        "qa_model": data.get("model", get_default_model()),
        "temperature": float(data.get("temperature", 1.0)),
        "chunk_size": int(data.get("chunk_size", get_default_chunk_size())),
        "use_cache": data.get("use_cache", True),
        "prompts": prompts,
        "max_refinement_attempts": 2,
        "min_length_ratio": 0.5,
        "max_length_ratio": 5.0,
        "context_char_count": 500,
    }

    while not progress_queue.empty():
        progress_queue.get()

    def _project_translate_worker():
        """Worker dịch trong project context sử dụng TranslationExecutor."""
        try:
            from core.executor import TranslationExecutor
            from services.translation_memory import TranslationMemory

            api_keys = load_api_keys()
            if not api_keys:
                progress_queue.put({"type": "error", "message": "Không tìm thấy API keys"})
                return

            project_tm = TranslationMemory(
                tm_dir=str(pdir / "assets" / "translation_memory"),
                enabled=True,
            )

            total_files = len(filenames)
            for idx, filename in enumerate(filenames, 1):
                file_path = pdir / "sources" / filename
                if not file_path.exists():
                    progress_queue.put(
                        {"type": "info", "message": f"⚠️ File không tồn tại: {filename}"}
                    )
                    continue

                try:
                    text = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    progress_queue.put(
                        {"type": "info", "message": f"❌ Lỗi đọc file {filename}: {str(e)}"}
                    )
                    continue

                progress_queue.put(
                    {"type": "info", "message": f"📂 [{idx}/{total_files}] Đang dịch: {filename}"}
                )

                executor = TranslationExecutor(
                    api_keys=api_keys, config=config, glossary_paths=glossary_paths
                )

                def cb(data):
                    if data["type"] == "complete":
                        out_path = pdir / "translated" / filename

                        _state.translation_result = {
                            "text": data.get("result"),
                            "filename": filename,
                            "path": str(out_path),
                        }
                        # Override message cho UI
                        data["message"] = f"✅ Đã dịch xong file {idx}/{total_files}: {filename}"

                        # Chỉ gửi complete thật sự nếu là file cuối cùng
                        if idx < total_files:
                            data["type"] = "file_complete"

                    progress_queue.put(data)

                executor.translate_text(
                    text=text,
                    output_filename=filename,
                    output_file_path=pdir / "translated" / filename,
                    progress_callback=cb,
                    translation_memory=project_tm,
                )

            # Gửi thông báo hoàn tất tất cả sau khi loop xong
            meta["updated_at"] = datetime.now().isoformat()
            _save_project_meta(slug, meta)
            calculate_stats()
            progress_queue.put(
                {"type": "complete", "message": f"🚀 Đã hoàn tất {total_files} file!"}
            )

        except Exception as e:
            progress_queue.put({"type": "error", "message": f"❌ Lỗi hệ thống: {str(e)}"})

    thread = Thread(target=_project_translate_worker, daemon=True)
    thread.start()
    return jsonify({"status": "started", "files_count": len(filenames)})


# ============================================================
# Project Spell-check API
# ============================================================

@projects_bp.route("/api/projects/<slug>/spellcheck", methods=["POST"])
def spellcheck_project_file(slug):
    """Kiểm tra chính tả file(s) trong dự án."""
    from webui import progress_queue
    import webui as _state

    data = request.json
    filenames = data.get("files", [])

    pdir = _get_project_dir(slug)
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    if not filenames:
        return jsonify({"error": "Không có file nào được chọn"}), 400

    # Load spell-check prompt
    prompts = {"main": "", "chinh_ta": ""}
    global_prompts = load_prompts()
    prompts.update(global_prompts)
    prompt_dir = pdir / "prompt"
    if prompt_dir.exists():
        for key, fname in [
            ("chinh_ta", "chinh_ta_prompt.txt"),
        ]:
            fp = prompt_dir / fname
            if fp.exists():
                content = fp.read_text(encoding="utf-8").strip()
                if content:
                    prompts[key] = content
            elif key == "chinh_ta":
                # Fallback to system default
                default_fp = Path("workspace/prompts/default") / fname
                if default_fp.exists():
                    prompts[key] = default_fp.read_text(encoding="utf-8").strip()

    # Glossary paths (Dynamic terms)
    glossary_filenames = ["glossary.txt", "relationship.txt"]
    glossary_paths = [
        pdir / "assets" / gf for gf in glossary_filenames if (pdir / "assets" / gf).exists()
    ]

    # Ensure we have a default instruction for spell-check if prompt is empty
    sp_prompt = prompts.get("chinh_ta", "").strip()
    if not sp_prompt:
        sp_prompt = "Hãy soát lỗi chính tả cho văn bản sau, giữ nguyên định dạng. Trả về văn bản đã sửa, sau đó là dấu gạch ngang '---' và danh sách các lỗi đã sửa (nếu có)."
    
    # Load style guide for placeholder replacement
    style_guide_path = pdir / "assets" / "style-guide.txt"
    style_guide = style_guide_path.read_text(encoding="utf-8") if style_guide_path.exists() else ""

    # Replace placeholders
    sp_prompt = sp_prompt.replace("{translation_guidelines}", style_guide)

    executor_prompts = {
        "main": sp_prompt,
        "chinh_ta": sp_prompt
    }

    config = {
        "model_name": data.get("model", get_default_model()),
        "qa_model": data.get("model", get_default_model()),
        "temperature": float(data.get("temperature", 1.0)),
        "chunk_size": int(data.get("chunk_size", get_default_chunk_size())),
        "use_cache": data.get("use_cache", True),
        "prompts": executor_prompts,
        "max_refinement_attempts": 2,
        "min_length_ratio": 0.5,
        "max_length_ratio": 5.0,
        "context_char_count": 500,
    }

    while not progress_queue.empty():
        progress_queue.get()

    def _project_spellcheck_worker():
        """Worker spell-check độc lập sử dụng SpellcheckExecutor."""
        try:
            from core.spellcheck_executor import SpellcheckExecutor

            api_keys = load_api_keys()
            if not api_keys:
                progress_queue.put({"type": "error", "message": "Không tìm thấy API keys"})
                return

            total_files = len(filenames)
            for idx, filename in enumerate(filenames, 1):
                # Ưu tiên tìm trong sources, sau đó là translated
                file_path = pdir / "sources" / filename
                if not file_path.exists():
                    file_path = pdir / "translated" / filename
                
                if not file_path.exists():
                    progress_queue.put(
                        {"type": "info", "message": f"⚠️ Tệp không tồn tại: {filename}"}
                    )
                    continue

                try:
                    text = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    progress_queue.put(
                        {"type": "info", "message": f"❌ Lỗi đọc file {filename}: {str(e)}"}
                    )
                    continue

                progress_queue.put(
                    {"type": "info", "message": f"📂 [{idx}/{total_files}] Đang soát lỗi: {filename}"}
                )

                executor = SpellcheckExecutor(api_keys=api_keys, config=config)

                def cb(data):
                    # SpellcheckExecutor uses "progress" type
                    progress_queue.put(data)

                # Thực thi soát lỗi
                clean_text, error_log = executor.execute(
                    text=text,
                    progress_callback=cb
                )

                # Lưu kết quả
                out_path = pdir / "spelling" / filename
                info_path = pdir / "spelling" / f"{filename.rsplit('.', 1)[0]}_info.txt"
                out_path.parent.mkdir(parents=True, exist_ok=True)

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(clean_text)

                with open(info_path, "w", encoding="utf-8") as f:
                    f.write(error_log)

                # Gửi thông báo hoàn tất file
                _state.translation_result = {
                    "text": clean_text,
                    "filename": filename,
                    "path": str(out_path),
                }
                
                msg = f"✅ Đã soát lỗi xong {idx}/{total_files}: {filename}"
                if idx == total_files:
                    progress_queue.put({"type": "complete", "message": msg})
                else:
                    progress_queue.put({"type": "file_complete", "message": msg})

        except Exception as e:
            logger.error(f"Lỗi Spellcheck Worker: {str(e)}")
            progress_queue.put({"type": "error", "message": f"❌ Lỗi hệ thống: {str(e)}"})

    thread = Thread(target=_project_spellcheck_worker, daemon=True)
    thread.start()
    return jsonify({"status": "started", "files_count": len(filenames)})


# ============================================================
# Translation Memory APIs
# ============================================================


@projects_bp.route("/api/tm/stats")
def get_tm_stats():
    """Lấy thống kê Translation Memory."""
    from webui import translation_memory

    try:
        if translation_memory:
            stats = translation_memory.get_stats()
            return jsonify(stats)
        return jsonify({"enabled": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/tm/find", methods=["POST"])
def tm_find():
    """Tìm kiếm trong Translation Memory."""
    from webui import translation_memory

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


@projects_bp.route("/api/tm/add", methods=["POST"])
def tm_add():
    """Thêm translation vào TM."""
    from webui import translation_memory

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


@projects_bp.route("/api/tm/clear", methods=["POST"])
def tm_clear():
    """Xóa toàn bộ TM."""
    from webui import translation_memory

    try:
        if translation_memory:
            count = translation_memory.clear()
            return jsonify({"success": True, "deleted": count})
        return jsonify({"error": "Translation Memory not enabled"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/tm/export", methods=["POST"])
def tm_export():
    """Export TM ra file."""
    from webui import translation_memory

    try:
        data = request.json
        filepath = data.get("filepath", "workspace/translation_memory_export.json")

        if translation_memory:
            if translation_memory.export_tm(filepath):
                return jsonify({"success": True, "filepath": filepath})
        return jsonify({"error": "Export failed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/tm/import", methods=["POST"])
def tm_import():
    """Import TM từ file."""
    from webui import translation_memory

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
