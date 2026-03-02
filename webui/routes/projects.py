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
    load_api_keys, load_prompts, calculate_stats,
    get_default_model, get_default_chunk_size,
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
    sources = list((pdir / "sources").rglob("*.txt")) if (pdir / "sources").exists() else []
    translated = list((pdir / "translated").rglob("*.txt")) if (pdir / "translated").exists() else []
    return {
        "source_count": len(sources),
        "translated_count": len(translated),
        "source_words": sum(len(f.read_text(encoding="utf-8").split()) for f in sources if f.is_file()),
        "translated_words": sum(len(f.read_text(encoding="utf-8").split()) for f in translated if f.is_file()),
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

    slug = re.sub(r'[^\w\-]', '-', name.lower()).strip('-')
    slug = re.sub(r'-+', '-', slug)
    if not slug:
        slug = "project"

    pdir = _get_project_dir(slug)
    if pdir.exists():
        return jsonify({"error": f"Dự án '{slug}' đã tồn tại"}), 409

    for sub in ["sources", "translated", "prompt", "profile", "output"]:
        (pdir / sub).mkdir(parents=True, exist_ok=True)
    (pdir / "profile" / "translation_memory").mkdir(exist_ok=True)

    prompts_root = Path("prompts")
    for fname in ["01-main.txt", "02-retranslate.txt", "03-correction.txt"]:
        src = prompts_root / fname
        if src.exists():
            shutil.copy2(src, pdir / "prompt" / fname)

    meta = {
        "name": name,
        "slug": slug,
        "description": data.get("description", ""),
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _save_project_meta(slug, meta)

    for fname, content in [
        ("glossary.txt", "# Bảng thuật ngữ\n# Format: thuật ngữ gốc | thuật ngữ dịch | ghi chú\n"),
        ("characters.txt", "# Bảng nhân vật & quan hệ\n# Format: tên gốc | tên dịch | vai trò | quan hệ\n"),
        ("style_guide.txt", "# Hướng dẫn phong cách dịch\n# Mô tả tone, style, và các quy tắc dịch\n"),
    ]:
        fp = pdir / "profile" / fname
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
        source_files = [f for f in src_dir.rglob("*") if f.suffix in (".txt", ".md")]
        for f in sorted(source_files):
            if f.name.startswith("."):
                continue
            rel = str(f.relative_to(src_dir))
            size = f.stat().st_size
            has_translation = (pdir / "translated" / rel).exists()
            sources.append({
                "name": rel, "path": str(f), "size": size,
                "size_display": f"{size/1024:.1f} KB" if size < 1048576 else f"{size/1048576:.1f} MB",
                "has_translation": has_translation,
            })

    translated = []
    tr_dir = pdir / "translated"
    if tr_dir.exists():
        translated_files = [f for f in tr_dir.rglob("*") if f.suffix in (".txt", ".md")]
        for f in sorted(translated_files):
            if f.name.startswith("."):
                continue
            rel = str(f.relative_to(tr_dir))
            size = f.stat().st_size
            translated.append({
                "name": rel, "path": str(f), "size": size,
                "size_display": f"{size/1024:.1f} KB" if size < 1048576 else f"{size/1048576:.1f} MB",
            })

    profile_files = []
    prof_dir = pdir / "profile"
    if prof_dir.exists():
        for f in sorted(prof_dir.glob("*.txt")):
            profile_files.append({"name": f.name, "size": f.stat().st_size})

    return jsonify({
        **meta, "slug": slug, **stats,
        "sources": sources, "translated": translated, "profile_files": profile_files,
    })


@projects_bp.route("/api/projects/<slug>", methods=["PUT"])
def update_project(slug):
    """Cập nhật metadata dự án."""
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json
    for key in ["name", "description", "status"]:
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


@projects_bp.route("/api/projects/<slug>/archive", methods=["POST"])
def archive_project(slug):
    """Nén dự án thành file .zip."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    zip_path = PROJECTS_DIR / f"{slug}"
    shutil.make_archive(str(zip_path), 'zip', str(pdir))
    zip_file = f"{zip_path}.zip"

    return send_file(zip_file, as_attachment=True, download_name=f"{slug}.zip")


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

    # Chỉ cho phép .txt và .md
    if not (f.filename.lower().endswith(".txt") or f.filename.lower().endswith(".md")):
        return jsonify({"error": "Chỉ hỗ trợ file .txt và .md"}), 400

    safe_name = Path(f.filename).name  # sanitize
    src_dir = pdir / "sources"
    src_dir.mkdir(parents=True, exist_ok=True)
    dest = src_dir / safe_name
    f.save(str(dest))

    size = dest.stat().st_size
    return jsonify({
        "success": True,
        "filename": safe_name,
        "size": size,
        "size_display": f"{size/1024:.1f} KB" if size < 1048576 else f"{size/1048576:.1f} MB",
    })


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
            return jsonify({"success": True, "chunks": 1, "message": "File quá nhỏ, không cần chia chunk.", "files": [filename]})

        # Tạo tên chunk: filename_chunk_001.txt, _chunk_002.txt...
        stem = src_file.stem
        ext = src_file.suffix
        created_files = []
        for i, chunk in enumerate(chunks, 1):
            chunk_name = f"{stem}_chunk_{i:03d}{ext}"
            chunk_path = pdir / "sources" / chunk_name
            chunk_path.write_text(chunk, encoding="utf-8")
            created_files.append(chunk_name)

        return jsonify({
            "success": True,
            "chunks": len(chunks),
            "files": created_files,
            "message": f"Đã chia thành {len(chunks)} chunk.",
        })
    except Exception as e:
        logger.error(f"Chunk error: {e}")
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/<slug>/move-done", methods=["POST"])
def project_move_done(slug):
    """Chuyển file source sang translated."""
    data = request.json
    filename = data.get("filename", "")

    pdir = _get_project_dir(slug)
    src = pdir / "sources" / filename
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
    src = pdir / "translated" / filename
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
    """Load prompt dự án (fallback global)."""
    pdir = _get_project_dir(slug)
    prompts = {"main": "", "retranslate": "", "correction": ""}

    global_prompts = load_prompts()
    prompts.update(global_prompts)

    prompt_dir = pdir / "prompt"
    if prompt_dir.exists():
        for key, fname in [("main", "01-main.txt"), ("retranslate", "02-retranslate.txt"), ("correction", "03-correction.txt")]:
            fp = prompt_dir / fname
            if fp.exists():
                content = fp.read_text(encoding="utf-8").strip()
                if content:
                    prompts[key] = content

    return jsonify(prompts)


@projects_bp.route("/api/projects/<slug>/prompts", methods=["PUT"])
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
    prompts = {"main": "", "retranslate": "", "correction": ""}
    global_prompts = load_prompts()
    prompts.update(global_prompts)
    prompt_dir = pdir / "prompt"
    if prompt_dir.exists():
        for key, fname in [("main", "01-main.txt"), ("retranslate", "02-retranslate.txt"), ("correction", "03-correction.txt")]:
            fp = prompt_dir / fname
            if fp.exists():
                content = fp.read_text(encoding="utf-8").strip()
                if content:
                    prompts[key] = content

    # Load profile context (Static instructions)
    profile_context = ""
    for pfile in ["style_guide.txt"]:
        fp = pdir / "profile" / pfile
        if fp.exists():
            content = fp.read_text(encoding="utf-8").strip()
            if content and not content.startswith("#"):
                profile_context += f"\n\n# Hướng dẫn phong cách\n{content}"

    if profile_context.strip():
        prompts["main"] += profile_context

    # Glossary paths (Dynamic terms)
    glossary_filenames = ["glossary.txt", "characters.txt"]
    glossary_paths = [pdir / "profile" / gf for gf in glossary_filenames if (pdir / "profile" / gf).exists()]

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
        """Worker dịch trong project context sử dụng TranslationExecutor."""
        try:
            from core.executor import TranslationExecutor

            api_keys = load_api_keys()
            if not api_keys:
                progress_queue.put({"type": "error", "message": "Không tìm thấy API keys"})
                return

            from services.translation_memory import TranslationMemory
            project_tm = TranslationMemory(
                tm_dir=str(pdir / "profile" / "translation_memory"),
                enabled=True,
            )

            progress_queue.put({"type": "info", "message": f"📂 Dự án: {meta['name']} | File: {first_file}"})

            executor = TranslationExecutor(api_keys=api_keys, config=config, glossary_paths=glossary_paths)
            
            def cb(data):
                if data["type"] == "complete":
                    out_path = pdir / "translated" / first_file
                    
                    _state.translation_result = {
                        "text": data.get("result"), "filename": first_file, "path": str(out_path),
                    }
                    meta["updated_at"] = datetime.now().isoformat()
                    _save_project_meta(slug, meta)
                    calculate_stats()
                    
                    # Override message cho UI
                    data["message"] = f"✅ Hoàn tất: {first_file} → translated/{first_file}"
                    data["percent"] = 100

                progress_queue.put(data)

            executor.translate_text(
                text=text,
                output_filename=first_file,
                output_file_path=pdir / "translated" / first_file,
                progress_callback=cb,
                translation_memory=project_tm
            )

        except Exception as e:
            progress_queue.put({"type": "error", "message": f"❌ Lỗi: {str(e)}"})

    thread = Thread(target=_project_translate_worker, daemon=True)
    thread.start()
    return jsonify({"status": "started", "file": first_file})


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
