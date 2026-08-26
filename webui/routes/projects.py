# webui/routes/projects.py - v5.0.0
# Blueprint: Project-Based Workspace API + Translation Memory APIs

import json
import hashlib
import os
import re
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import time
from threading import Lock, Thread

from flask import Blueprint, request, jsonify, send_file

from services.task_store import TaskStore
from services.checkpoint_service import CheckpointService

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
CLOSE_WAIT_TIMEOUT_SECONDS = 6.0

# Phase 6 idempotency: khóa vòng "check active recovery → create recovery task" để chống
# hai request đồng thời tạo recovery worker kép trên cùng source task. Kiểm tra rồi tạo
# task nằm trong cùng một critical section; không atomic nếu chỉ dùng ORM/SQLite rời rạc.
_RECOVERY_CREATE_LOCK = Lock()


# ============================================================
# Spellcheck helpers
# ============================================================

def _is_spellcheck_info_file(path: Path) -> bool:
    """Kiểm tra file có phải là file log spellcheck (_info.txt) không."""
    return path.is_file() and path.name.endswith("_info.txt")


def _spellcheck_info_name(filename: str) -> str:
    """Tạo tên file log từ tên file nội dung.
    Quy tắc: stem + '_info.txt', tương đương backend filename.rsplit('.', 1)[0] + '_info.txt'
    """
    stem, _dot, _ext = filename.rpartition(".")
    return f"{stem or filename}_info.txt"


# ============================================================
# Project Info Helpers
# ============================================================


def _atomic_write_text(path: Path, content: str) -> None:
    """Ghi file an toàn bằng atomic write."""
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(str(tmp_path), str(path))


def _split_text_by_boundaries(text: str, max_chars: int) -> List[str]:
    """Chia văn bản thành các phần nhỏ hơn max_chars, ưu tiên boundary tự nhiên."""
    # Bước 1: chia theo heading/chapter
    raw_parts = re.split(r'\n(?=#{1,6}\s)', text)
    if len(raw_parts) == 1:
        raw_parts = re.split(r'\n(?=(chương|chapter)\s+\w+)', text, flags=re.IGNORECASE)

    # Bước 2: merge và chia theo paragraph rồi sentence
    parts = []
    current = ""

    for part in raw_parts:
        part = part.strip()
        if not part:
            continue

        if len(part) > max_chars:
            if current:
                parts.append(current)
                current = ""
            sub_parts = _split_large_part(part, max_chars)
            for sp in sub_parts[:-1]:
                parts.append(sp)
            current = sub_parts[-1] if sub_parts else ""
        elif len(current) + len(part) + 2 <= max_chars:
            current = current + "\n\n" + part if current else part
        else:
            if current:
                parts.append(current)
            current = part

    if current:
        parts.append(current)

    return parts if parts else [text]


def _split_large_part(text: str, max_chars: int) -> List[str]:
    """Chia một phần lớn theo đoạn rồi câu."""
    paragraphs = re.split(r'\n\n+', text)
    parts = []
    current = ""

    for para in paragraphs:
        if len(para) > max_chars:
            if current:
                parts.append(current)
                current = ""
            sentences = re.split(r'(?<=[.!?。])\s+', para)
            current = ""
            for sent in sentences:
                if len(current) + len(sent) + 1 <= max_chars:
                    current = current + " " + sent if current else sent
                else:
                    if current:
                        parts.append(current)
                    current = sent
            if current:
                parts.append(current)
                current = ""
        elif len(current) + len(para) + 2 <= max_chars:
            current = current + "\n\n" + para if current else para
        else:
            if current:
                parts.append(current)
            current = para

    if current:
        parts.append(current)

    return parts if parts else [text]


def _execute_single_request(job_id, registry, content, prompt_text, provider_type, api_keys, model, base_url, gateway_api_key, credential_mode, policy):
    """Thực hiện một request AI duy nhất với retry tối thiểu."""
    full_prompt = f"{prompt_text}\n{content}"
    max_retries = 2
    input_chars = len(content)
    prompt_chars = len(prompt_text)

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            registry.append_event(job_id, {
                "type": "info",
                "message": f"Thử lại lần {attempt}/{max_retries}...",
                "phase": "extracting",
                "attempt": attempt,
                "max_attempts": max_retries
            })

        try:
            # v8.29.0 (D3): dùng resolver/factory thay vì instantiate trực tiếp
            # GenAIClient/OpenAIClient. Đảm bảo runtime dùng provider_id đã
            # resolve từ đầu job (tránh race với active provider switch giữa job).
            from backend.infrastructure.providers.provider_resolver import (
                ProviderConfigResolver,
            )
            resolver = ProviderConfigResolver()
            try:
                resolved = resolver.resolve(provider_id_for_client) if 'provider_id_for_client' in dir() else resolver.resolve()
            except Exception:
                resolved = resolver.resolve()
            if not resolved.default_model:
                raise ValueError(
                    f"Provider '{resolved.id}' chưa cấu hình default_model. "
                    f"Cấu hình trong providers.json hoặc dùng endpoint /api/providers/<id>/models."
                )
            from services.ai_provider import create_provider as _create_provider_factory
            client = _create_provider_factory(
                resolved.type,
                api_key=(resolved.api_keys[0] if resolved.api_keys else resolved.api_key),
                default_model=resolved.default_model,
                base_url=resolved.base_url,
                gateway_api_key=resolved.gateway_api_key,
                credential_mode=resolved.credential_mode,
            )
            result, status = client.generate_content(full_prompt)

            if status == "success" and result:
                registry.append_event(job_id, {
                    "type": "info",
                    "message": f"Nhận kết quả: {len(result)} ký tự",
                    "phase": "extracting",
                    "output_chars": len(result),
                    "input_chars": input_chars,
                    "prompt_chars": prompt_chars,
                    "duration_ms": 0
                })
                return result
            elif status == "empty_response":
                if attempt < max_retries:
                    continue
                registry.append_event(job_id, {"type": "error", "message": "AI trả về kết quả rỗng", "retryable": True})
                return None
            else:
                registry.append_event(job_id, {"type": "error", "message": f"AI lỗi: {status}", "retryable": False})
                return None

        except Exception as e:
            retryable = _is_retryable_error(e)
            if retryable and attempt < max_retries:
                registry.append_event(job_id, {
                    "type": "info",
                    "message": f"Lỗi tạm thời, thử lại: {str(e)}",
                    "phase": "extracting",
                    "attempt": attempt,
                    "max_attempts": max_retries
                })
                continue
            registry.append_event(job_id, {"type": "error", "message": f"Lỗi gọi AI: {str(e)}", "retryable": retryable})
            return None

    return None


def _is_retryable_error(error: Exception) -> bool:
    """Kiểm tra lỗi có nên retry không."""
    error_str = str(error).lower()
    retryable_indicators = ["timeout", "timed out", "connection", "rate limit", "429", "quota", "503", "500"]
    non_retryable_indicators = ["api key", "invalid", "permission", "model", "context", "401", "403", "400"]

    for indicator in non_retryable_indicators:
        if indicator in error_str:
            return False
    for indicator in retryable_indicators:
        if indicator in error_str:
            return True
    return False


def _execute_map_reduce(job_id, registry, parts, prompt_text, content_type, provider_type, api_keys, model, base_url, gateway_api_key, credential_mode, policy):
    """Thực hiện phân tích nhiều phần: extraction -> merge -> synthesis."""
    total_parts = len(parts)
    registry.append_event(job_id, {
        "type": "info",
        "message": f"Bắt đầu phân tích {total_parts} phần...",
        "phase": "extracting",
        "current": 0,
        "total": total_parts
    })

    partials = []
    for idx, part in enumerate(parts, 1):
        # Kiểm tra cancel trước mỗi phần
        task = registry.get_task(job_id)
        if task and task.status == "cancelled":
            registry.append_event(job_id, {"type": "cancelled", "message": "Đã dừng theo yêu cầu"})
            return None

        registry.append_event(job_id, {
            "type": "progress",
            "message": f"Đang phân tích phần {idx}/{total_parts}",
            "phase": "extracting",
            "current": idx,
            "total": total_parts,
            "percent": int((idx / total_parts) * 50)
        })

        # Tạo prompt extraction cho phần này
        extraction_prompt = _build_extraction_prompt(prompt_text, part, idx, content_type)

        result = _execute_single_request(
            job_id, registry, part, extraction_prompt,
            provider_type, api_keys, model,
            base_url, gateway_api_key, credential_mode, policy
        )

        if result is None:
            return None

        partials.append({"part_id": f"part-{idx:03d}", "content": result})
        registry.append_event(job_id, {
            "type": "info",
            "message": f"Hoàn thành phần {idx}/{total_parts}",
            "phase": "extracting",
            "current": idx,
            "total": total_parts
        })

    # Phase: merging
    registry.append_event(job_id, {"type": "info", "message": "Đang hợp nhất kết quả...", "phase": "merging", "percent": 60})

    # Phase: synthesizing
    registry.append_event(job_id, {"type": "info", "message": "Đang tổng hợp toàn văn...", "phase": "synthesizing", "percent": 70})

    synthesis_prompt = _build_synthesis_prompt(prompt_text, partials, content_type)
    final_result = _execute_single_request(
        job_id, registry, "", synthesis_prompt,
        provider_type, api_keys, model,
        base_url, gateway_api_key, credential_mode, policy
    )

    return final_result


def _build_extraction_prompt(base_prompt: str, part_content: str, part_index: int, content_type: str) -> str:
    """Tạo prompt extraction cho một phần."""
    return (
        f"{base_prompt}\n\n"
        f"--- PHẦN {part_index} ---\n"
        f"Chỉ phân tích nội dung trong phần này. Giữ PART_ID nếu có.\n\n"
        f"{part_content}"
    )


def _build_synthesis_prompt(base_prompt: str, partials: List[dict], content_type: str) -> str:
    """Tạo prompt synthesis từ các partial đã trích xuất."""
    partials_text = "\n\n".join(
        f"--- {p['part_id']} ---\n{p['content']}"
        for p in partials
    )
    return (
        f"{base_prompt}\n\n"
        f"--- CÁC PHẦN ĐÃ TRÍCH XUẤT ---\n"
        f"Tổng hợp từ {len(partials)} phần. Hợp nhất, loại trùng, bao phủ toàn bộ nguồn.\n\n"
        f"{partials_text}"
    )


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
    """Lưu project.json an toàn bằng atomic write."""
    meta_file = _get_project_dir(slug) / "project.json"
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = meta_file.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    os.replace(str(tmp_path), str(meta_file))


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
    """Liệt kê tất cả dự án với thông tin đầy đủ cho card display."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    projects = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta = _load_project_meta(d.name)
        if not meta:
            continue
        stats = _project_stats(d.name)
        
        # Backward compatibility: parse book_title/author từ name cũ
        if "book_title" not in meta:
            parts = meta.get("name", "").split(" - ", 1)
            meta["book_title"] = parts[0] if parts else meta.get("name", "")
            meta["author"] = parts[1] if len(parts) > 1 else ""
        
        # Đọc danh sách tập tin nguồn thực tế để so sánh trạng thái
        src_dir = d / "sources"
        tr_dir = d / "translated"
        source_files = [f for f in src_dir.rglob("*") if f.is_file() and not f.name.startswith(".")] if src_dir.exists() else []
        file_status = meta.get("file_status", {})
        
        # Dự án được coi là Hoàn thành khi:
        # 1. Có file nguồn VÀ
        # 2. Toàn bộ file nguồn đều có translated tương ứng HOẶC có status "Xong"
        def is_file_done(f):
            rel = str(f.relative_to(src_dir))
            # Kiểm tra file_status trước
            if file_status.get(rel) == "Xong":
                return True
            # Kiểm tra file translated có tồn tại không
            trans_file = tr_dir / rel
            return trans_file.exists()
        
        all_done = len(source_files) > 0 and all(is_file_done(f) for f in source_files)
        status = "Hoàn thành" if all_done else "Đang thực hiện"
        
        # Tính progress percentage
        total_files = len(source_files)
        translated_files = stats.get("translated_count", 0)
        progress = (translated_files / total_files * 100) if total_files > 0 else 0
        
        projects.append({
            **meta, 
            "slug": d.name, 
            **stats,
            "progress": round(progress, 1),
            "status": status
        })
    return jsonify(projects)


@projects_bp.route("/api/projects", methods=["POST"])
def create_project():
    """Tạo dự án mới."""
    data = request.json
    book_title = data.get("book_title", "").strip()
    author = data.get("author", "").strip()
    name = data.get("name", "").strip()

    if book_title:
        author_display = author if author else "Vô danh"
        name = f"{book_title} - {author_display}"
    elif not name:
        return jsonify({"error": "Tên tác phẩm hoặc tên dự án không được trống"}), 400

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
        "book_title": book_title if book_title else (name.split(" - ", 1)[0] if " - " in name else name),
        "author": author if author else (name.split(" - ", 1)[1] if " - " in name else ""),
        "slug": slug,
        "description": data.get("description", ""),
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

    # Backward compatibility: parse book_title/author từ name cũ
    if "book_title" not in meta:
        parts = meta.get("name", "").split(" - ", 1)
        meta["book_title"] = parts[0] if parts else meta.get("name", "")
        meta["author"] = parts[1] if len(parts) > 1 else ""

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
            "file_status": meta.get("file_status", {}),
        }
    )


@projects_bp.route("/api/projects/<slug>", methods=["PUT"])
def update_project(slug):
    """Cập nhật metadata dự án."""
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json
    new_name = data.get("name", "").strip() if "name" in data else None
    
    if new_name is not None:
        if not new_name:
            return jsonify({"error": "Tên dự án không được trống"}), 400
        meta["name"] = new_name

    for key in ["description", "author", "status"]:
        if key in data:
            meta[key] = data[key]
            
    meta["updated_at"] = datetime.now().isoformat()

    new_slug = slug
    if new_name is not None:
        new_slug = re.sub(r"[^\w\-]", "-", new_name.lower()).strip("-")
        new_slug = re.sub(r"-+", "-", new_slug)
        if not new_slug:
            new_slug = "project"

    if new_slug != slug:
        new_dir = _get_project_dir(new_slug)
        if new_dir.exists():
            return jsonify({"error": f"Dự án với tên '{new_name}' (slug: '{new_slug}') đã tồn tại"}), 409
        
        old_dir = _get_project_dir(slug)
        try:
            old_dir.rename(new_dir)
        except Exception as e:
            logger.exception("Failed to rename project directory")
            return jsonify({"error": f"Không thể đổi tên thư mục dự án: {str(e)}"}), 500

    _save_project_meta(new_slug, meta)
    return jsonify({"success": True, "meta": meta, "slug": new_slug})


VALID_FILE_STATUSES = {"Chờ", "Xong"}

@projects_bp.route("/api/projects/<slug>/file-status", methods=["PUT"])
def update_project_file_status(slug):
    """Cập nhật trạng thái của một file (Chờ / Xong)."""
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json or {}
    filename = data.get("filename")
    status = data.get("status")

    if not filename or not status:
        return jsonify({"error": "Thiếu thông tin filename hoặc status"}), 400

    if status not in VALID_FILE_STATUSES:
        return jsonify({"error": f"Trạng thái không hợp lệ. Chỉ chấp nhận: {', '.join(VALID_FILE_STATUSES)}"}), 400

    if "file_status" not in meta:
        meta["file_status"] = {}

    meta["file_status"][filename] = status
    meta["updated_at"] = datetime.now().isoformat()

    _save_project_meta(slug, meta)
    return jsonify({"success": True, "file_status": meta["file_status"]})


@projects_bp.route("/api/projects/<slug>", methods=["DELETE"])
def delete_project(slug):
    """Xóa dự án."""
    try:
        pdir = _get_project_dir(slug)
        if not pdir.exists():
            return jsonify({"error": "Dự án không tồn tại"}), 404

        shutil.rmtree(pdir)
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Lỗi delete_project [{slug}]: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


ARCHIVE_DIR = Path("workspace/archive")


@projects_bp.route("/api/projects/<slug>/archive", methods=["POST"])
def archive_project(slug):
    """Nén dự án và di chuyển sang thư mục archive, sau đó xóa dự án gốc."""
    try:
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
    except Exception as e:
        logger.error(f"Lỗi archive_project [{slug}]: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


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


@projects_bp.route("/api/archive/<filename>/download", methods=["GET"])
def download_archive(filename):
    """Tải file lưu trữ."""
    archive_path = ARCHIVE_DIR / filename
    if not archive_path.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    # Prevent path traversal
    if archive_path.parent != ARCHIVE_DIR:
        return jsonify({"error": "Invalid path"}), 403

    return send_file(archive_path, as_attachment=True, download_name=filename)


# ============================================================
# Project Import/Export APIs
# ============================================================


@projects_bp.route("/api/projects/<slug>/export", methods=["GET"])
def export_project(slug):
    """Export dự án thành file zip để tải về."""
    try:
        pdir = _get_project_dir(slug)
        if not pdir.exists():
            return jsonify({"error": "Dự án không tồn tại"}), 404

        import zipfile
        from io import BytesIO

        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in pdir.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    arcname = file_path.relative_to(pdir.parent)
                    zf.write(file_path, arcname)

        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{slug}.zip"
        )
    except Exception as e:
        logger.error(f"Lỗi export_project [{slug}]: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/import", methods=["POST"])
def import_project():
    """Nhập dự án từ file zip."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "Không tìm thấy file"}), 400

        f = request.files["file"]
        if not f.filename or not f.filename.endswith('.zip'):
            return jsonify({"error": "File phải là định dạng .zip"}), 400

        import zipfile
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "import.zip"
            f.save(str(zip_path))

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)

            # Tìm thư mục dự án trong zip
            extracted_dirs = [d for d in Path(tmp_dir).iterdir() if d.is_dir()]
            if not extracted_dirs:
                return jsonify({"error": "File zip không hợp lệ"}), 400

            project_dir = extracted_dirs[0]
            slug = project_dir.name

            # Kiểm tra trùng lặp
            dest_dir = _get_project_dir(slug)
            if dest_dir.exists():
                return jsonify({"error": f"Dự án '{slug}' đã tồn tại"}), 409

            # Copy vào workspace
            shutil.copytree(project_dir, dest_dir)

            meta = _load_project_meta(slug)
            if meta:
                return jsonify({"success": True, "slug": slug, "meta": meta})
            else:
                return jsonify({"error": "Không tìm thấy project.json trong file"}), 400
    except Exception as e:
        logger.error(f"Lỗi import_project: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Project File APIs
# ============================================================


@projects_bp.route("/api/projects/<slug>/download/<path:filepath>")
def download_project_file(slug, filepath):
    """Tải file nhị phân (epub, zip, ...) trong dự án về máy."""
    pdir = _get_project_dir(slug)
    file_path = (pdir / filepath).resolve()
    if not str(file_path).startswith(str(pdir.resolve())):
        return jsonify({"error": "Invalid path"}), 403
    if not file_path.exists() or not file_path.is_file():
        return jsonify({"error": "File không tồn tại"}), 404
    return send_file(file_path, as_attachment=True, download_name=file_path.name)


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


@projects_bp.route("/api/projects/<slug>/files/spelling")
def get_project_spelling_files(slug):
    """Lấy danh sách file đã soát lỗi (chỉ file nội dung, không bao gồm file log _info.txt)."""
    pdir = _get_project_dir(slug)
    spelling_dir = pdir / "spelling"
    
    if not spelling_dir.exists():
        return jsonify([])
    
    files = []
    for f in sorted(spelling_dir.rglob("*")):
        if f.is_file() and not f.name.startswith('.') and not _is_spellcheck_info_file(f):
            rel = str(f.relative_to(spelling_dir))
            size = f.stat().st_size
            files.append({
                "name": rel,
                "path": str(f),
                "size": size,
                "size_display": f"{size / 1024:.1f} KB" if size < 1048576 else f"{size / 1048576:.1f} MB",
            })
    
    return jsonify(files)


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


@projects_bp.route("/api/projects/<slug>/rename-batch", methods=["POST"])
def rename_batch(slug):
    """Đổi tên hàng loạt file trong dự án."""
    data = request.json
    section = data.get("section", "sources")
    pattern = data.get("pattern", "")
    start = int(data.get("start", 1))
    zeropad = int(data.get("zeropad", 2))
    old_names = data.get("old_names", [])

    if not pattern or not old_names:
        return jsonify({"error": "Thiếu pattern hoặc danh sách file"}), 400

    pdir = _get_project_dir(slug)
    if not pdir:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    results = []
    for idx, old_name in enumerate(old_names):
        num = start + idx
        num_str = str(num).zfill(zeropad) if zeropad > 0 else str(num)

        # Tạo tên mới từ pattern
        new_name = pattern.replace("{N}", num_str)

        # Giữ đuôi file gốc nếu pattern không có đuôi
        if "." not in new_name and "." in old_name:
            ext = old_name.rsplit(".", 1)[-1]
            new_name = f"{new_name}.{ext}"

        old_path = (pdir / section / old_name).resolve()
        new_path = (pdir / section / new_name).resolve()

        # Validate paths
        if not str(old_path).startswith(str((pdir / section).resolve())):
            results.append({"old": old_name, "new": new_name, "error": "Invalid path"})
            continue
        if not str(new_path).startswith(str((pdir / section).resolve())):
            results.append({"old": old_name, "new": new_name, "error": "Invalid path"})
            continue
        if not old_path.exists():
            results.append({"old": old_name, "new": new_name, "error": "File không tồn tại"})
            continue
        if new_path.exists():
            results.append({"old": old_name, "new": new_name, "error": "Tên file đã tồn tại"})
            continue

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

            results.append({"old": old_name, "new": new_name, "success": True})
        except Exception as e:
            results.append({"old": old_name, "new": new_name, "error": str(e)})

    success_count = sum(1 for r in results if r.get("success"))
    return jsonify({"success": True, "results": results, "renamed": success_count})

@projects_bp.route("/api/projects/<slug>/move-done", methods=["POST"])
def project_move_done(slug):
    """Chuyển file source sang translated."""
    try:
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
    except Exception as e:
        logger.error(f"Lỗi project_move_done [{slug}]: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/<slug>/move-back", methods=["POST"])
def project_move_back(slug):
    """Chuyển file translated về sources."""
    try:
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
    except Exception as e:
        logger.error(f"Lỗi project_move_back [{slug}]: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# Project prompt APIs moved to webui/routes/prompts.py



# ============================================================
# Project Guidelines APIs (Phase 3)
# ============================================================


@projects_bp.route("/api/projects/<slug>/guidelines")
def get_project_guidelines(slug):
    """Load tất cả guidelines/profile của dự án."""
    try:
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
            try:
                result[key] = fp.read_text(encoding="utf-8") if fp.exists() else ""
            except UnicodeDecodeError as e:
                result[key] = ""
                logger.warning(f"Lỗi đọc guideline {fname}: {e}")

        return jsonify(result)
    except Exception as e:
        logger.error(f"Lỗi get_project_guidelines [{slug}]: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/<slug>/guidelines", methods=["PUT"])
def save_project_guidelines(slug):
    """Lưu guidelines/profile dự án."""
    try:
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
    except Exception as e:
        logger.error(f"Lỗi save_project_guidelines [{slug}]: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@projects_bp.route("/api/projects/<slug>/summarize", methods=["POST"])
def summarize_project(slug):
    """AI tạo nội dung theo loại (summary, glossary, relationship, style_guide)."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json
    source_file = data.get("source_file", "")
    content_type = data.get("content_type", "summary")

    CONTENT_MAP = {
        "summary": ("summary_prompt.txt", "summary.txt"),
        "relationship": ("relationship_prompt.txt", "relationship.txt"),
        "glossary": ("glossary_prompt.txt", "glossary.txt"),
        "style_guide": ("style_guide_prompt.txt", "style_guide.txt"),
    }

    if content_type not in CONTENT_MAP:
        return jsonify({"error": f"Loại nội dung không hợp lệ: {content_type}"}), 400

    prompt_filename, asset_filename = CONTENT_MAP[content_type]

    # Validate provider/model trước khi tạo task
    from backend.infrastructure.providers.provider_service import ProviderService
    from backend.infrastructure.providers.endpoint_policy import classify_endpoint

    provider_service = ProviderService()
    active_provider = provider_service.get_active_provider_config() or {}
    base_url = active_provider.get("base_url")
    policy = classify_endpoint(base_url)
    requested_model = data.get("model", "") or active_provider.get("default_model", "") or "gpt-4o-mini"
    requested_model = policy.normalize_model(requested_model)
    if not policy.validate_model(requested_model):
        return jsonify({"error": f"Model {requested_model} không hợp lệ với provider {policy.provider_kind}"}), 400

    # Tạo task và chạy worker nền
    registry = TaskRegistry()
    job_id = registry.create_task(
        kind="project_info",
        title=f"AI {content_type} cho {slug}",
        total_files=1,
        project_slug=slug,
        filename=""
    )

    def _project_info_worker(job_id):
        try:
            from backend.infrastructure.providers.provider_service import ProviderService
            from backend.infrastructure.providers.endpoint_policy import classify_endpoint

            provider_service = ProviderService()
            active_provider = provider_service.get_active_provider_config() or {}
            provider_type = active_provider.get("type", "gemini")
            base_url = active_provider.get("base_url")
            gateway_api_key = active_provider.get("gateway_api_key", "")
            credential_mode = active_provider.get("credential_mode", "default")

            policy = classify_endpoint(base_url)
            provider_kind = policy.provider_kind

            # Chuẩn bị API keys
            if provider_type == "gemini":
                api_keys = active_provider.get("api_keys", [])
            else:
                api_key = active_provider.get("api_key", "")
                api_keys = [api_key or gateway_api_key] if (api_key or gateway_api_key) else []

            if not api_keys or not api_keys[0]:
                registry.append_event(job_id, {"type": "error", "message": f"Chưa cấu hình API key cho provider {active_provider.get('name', provider_type)}", "retryable": False})
                registry.update_status(job_id, "failed")
                return

            # Phase: loading_source
            registry.append_event(job_id, {"type": "info", "message": "Đang đọc nguồn...", "phase": "loading_source"})

            src_path = pdir / "sources" / source_file
            if not src_path.is_file():
                src_dir = pdir / "sources"
                all_text = []
                if src_dir.exists():
                    for f in sorted(src_dir.rglob("*.txt")):
                        try:
                            all_text.append(f.read_text(encoding="utf-8"))
                        except UnicodeDecodeError as e:
                            registry.append_event(job_id, {"type": "error", "message": f"File lỗi encoding: {f.name}: {e}", "retryable": False})
                            registry.update_status(job_id, "failed")
                            return
                    for f in sorted(src_dir.rglob("*.md")):
                        try:
                            all_text.append(f.read_text(encoding="utf-8"))
                        except UnicodeDecodeError as e:
                            registry.append_event(job_id, {"type": "error", "message": f"File lỗi encoding: {f.name}: {e}", "retryable": False})
                            registry.update_status(job_id, "failed")
                            return
                content = "\n\n".join(all_text)
            else:
                try:
                    content = src_path.read_text(encoding="utf-8")
                except UnicodeDecodeError as e:
                    registry.append_event(job_id, {"type": "error", "message": f"File lỗi encoding: {source_file}: {e}", "retryable": False})
                    registry.update_status(job_id, "failed")
                    return

            input_chars = len(content)
            registry.append_event(job_id, {"type": "info", "message": f"Đã đọc nguồn: {input_chars} ký tự", "phase": "loading_source", "input_chars": input_chars})

            if not content.strip():
                registry.append_event(job_id, {"type": "error", "message": "Không có nội dung nguồn để phân tích", "retryable": False})
                registry.update_status(job_id, "failed")
                return

            # Phase: loading_prompt
            registry.append_event(job_id, {"type": "info", "message": "Đang nạp prompt...", "phase": "loading_prompt"})

            PROMPTS_DIR = Path("workspace/prompts")
            prompt_text = ""
            project_prompt = pdir / "prompt" / prompt_filename
            if project_prompt.exists():
                prompt_text = project_prompt.read_text(encoding="utf-8")

            if not prompt_text:
                default_prompt = PROMPTS_DIR / "default" / prompt_filename
                if default_prompt.exists():
                    prompt_text = default_prompt.read_text(encoding="utf-8")

            if not prompt_text:
                registry.append_event(job_id, {"type": "error", "message": "Không tìm thấy prompt", "retryable": False})
                registry.update_status(job_id, "failed")
                return

            prompt_chars = len(prompt_text)

            # Phase: planning
            registry.append_event(job_id, {"type": "info", "message": "Đang lập kế hoạch phân tích...", "phase": "planning"})

            # Quyết định strategy dựa trên kích thước input
            # Lấy context limit từ policy nếu có, không có thì dùng conservative
            context_limit = getattr(policy, 'context_window', 200000)
            safety_margin = 5000  # chừa cho output
            available_budget = context_limit - prompt_chars - safety_margin

            if input_chars <= available_budget:
                strategy = "single_request"
                parts = [content]
            else:
                strategy = "map_reduce"
                # Chia theo boundary: chapter/heading > paragraph > sentence
                parts = _split_text_by_boundaries(content, available_budget)

            registry.append_event(job_id, {
                "type": "info",
                "message": f"Chiến lược: {strategy}, {len(parts)} phần",
                "phase": "planning",
                "strategy": strategy,
                "part_count": len(parts)
            })

            # Thực thi AI
            if strategy == "single_request":
                result = _execute_single_request(
                    job_id, registry, content, prompt_text,
                    provider_type, api_keys, requested_model,
                    base_url, gateway_api_key, credential_mode, policy
                )
            else:
                result = _execute_map_reduce(
                    job_id, registry, parts, prompt_text, content_type,
                    provider_type, api_keys, requested_model,
                    base_url, gateway_api_key, credential_mode, policy
                )

            if result is None:
                registry.update_status(job_id, "failed")
                return

            # Phase: validating
            registry.append_event(job_id, {"type": "info", "message": "Đang kiểm tra kết quả...", "phase": "validating"})

            if not result or not result.strip():
                registry.append_event(job_id, {"type": "error", "message": "AI trả về kết quả rỗng", "retryable": True})
                registry.update_status(job_id, "failed")
                return

            # Phase: saving
            registry.append_event(job_id, {"type": "info", "message": f"Đang lưu {asset_filename}...", "phase": "saving"})

            assets_dir = pdir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            asset_path = assets_dir / asset_filename

            try:
                _atomic_write_text(asset_path, result)
            except Exception as e:
                registry.append_event(job_id, {"type": "error", "message": f"Lỗi ghi asset: {e}", "retryable": False})
                registry.update_status(job_id, "failed")
                return

            output_chars = len(result)
            registry.append_event(job_id, {
                "type": "complete",
                "message": "Hoàn tất",
                "phase": "complete",
                "asset_file": asset_filename,
                "output_chars": output_chars,
                "strategy": strategy,
                "input_chars": input_chars,
                "prompt_chars": prompt_chars
            })
            registry.update_status(job_id, "completed")

        except Exception as e:
            logger.error(f"Lỗi Project Info Worker [{content_type}]: {e}", exc_info=True)
            registry.append_event(job_id, {"type": "error", "message": f"❌ Lỗi hệ thống: {str(e)}", "retryable": False})
            registry.update_status(job_id, "failed")

    thread = Thread(target=_project_info_worker, args=(job_id,), daemon=True)
    thread.start()
    return jsonify({"status": "started", "job_id": job_id, "content_type": content_type, "source_file": source_file, "model": requested_model}), 202



# ============================================================

# ============================================================
# Project Translation API - Resume helpers and endpoints
# ============================================================


def _get_checkpoint_dir():
    from backend.infrastructure.config.app_config_service import AppConfigService
    return AppConfigService().get_checkpoints_dir()


def _get_workspace_dir():
    ck_dir = _get_checkpoint_dir()
    ck_path = Path(ck_dir)
    if ck_path.name == "checkpoints":
        return str(ck_path.parent)
    return str(ck_path.parent)


def _checkpoint_key_for(filename: str) -> str:
    return hashlib.md5(filename.encode()).hexdigest()[:12] + ".db"


def _current_checkpoint_identity(filename: str, source_text: str, config: dict) -> dict:
    """Build identity hiện tại theo ĐÚNG công thức của TranslationExecutor.

    Phải khớp từng ký tự với `TranslationExecutor._build_checkpoint_identity`
    (core/executor.py:72-93): cùng sha256, cùng `json.dumps(..., ensure_ascii=False,
    sort_keys=True, separators=(",", ":"))`. Đổi một bên mà không đổi bên kia là
    làm resume chết âm thầm — không có test nào bắt được ngoài Phase 5.
    """
    return {
        "project_file": filename,
        "project_slug": config.get("project_slug", ""),
        "source_hash": hashlib.sha256(source_text.encode()).hexdigest(),
        "chunker_version": "v2",
        "chunk_size": str(config.get("chunk_size", 22000)),
        "prompt_hash": hashlib.sha256(
            json.dumps(config.get("prompts", {}), ensure_ascii=False,
                       sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "schema_version": "1.0",
        # 6 field thực thi CỐ TÌNH không có ở đây: chúng không quyết định checkpoint
        # còn dùng được hay không, và route không biết giá trị thật của chúng
        # (worker mới điền — projects.py:1592-1601). Xem execution_drift().
    }


def _checkpoint_status_for(filename: str, source_text: str, config: dict) -> Optional[dict]:
    """Checkpoint có resume được không. So SOURCE identity, bỏ qua execution identity.

    Đổi provider/model KHÔNG làm mất khả năng resume — chỉ ghi nhận `mixed_provider`.
    """
    from services.checkpoint_service import same_source_identity

    ck_dir = _get_checkpoint_dir()
    ck = CheckpointService(ck_dir)
    info = ck.get_resume_info(filename)
    if not info or not info.get("can_resume"):
        return None

    saved = info.get("identity", {})
    current = _current_checkpoint_identity(filename, source_text, config)
    if not same_source_identity(saved, current):
        return {"status": "stale_checkpoint", "identity_mismatch": True}

    return {
        "status": "resume_available",
        "completed_chunks": info.get("translated_count", 0),
        "total_chunks": info.get("total_chunks", 0),
        "next_chunk": info.get("next_chunk_index", 0),
        # Tên VẬT LÝ. Task row lưu tên LOGIC (projects.py:1738 → filename).
        # Đừng so sánh 2 giá trị này bằng `==` ở bất kỳ đâu — dùng
        # CheckpointService.same_checkpoint_key (Phase 0.5). Đây là B4.
        "checkpoint_key": _checkpoint_key_for(filename),
    }


def _build_translate_worker(slug, pdir, meta, config, filenames, glossary_paths, registry):
    from services.translation_memory import TranslationMemory
    from backend.infrastructure.providers.provider_service import ProviderService
    from backend.infrastructure.providers.model_catalog_service import ModelCatalogService
    from backend.infrastructure.providers.endpoint_policy import classify_endpoint
    from backend.application.use_cases.translate_project_files_use_case import TranslateProjectFilesUseCase

    def worker(job_id):
        try:
            provider_service = ProviderService()
            active_provider = provider_service.get_active_provider_config() or {}
            provider_type = active_provider.get("type", "gemini")
            base_url = active_provider.get("base_url")
            gateway_api_key = active_provider.get("gateway_api_key", "")
            credential_mode = active_provider.get("credential_mode", "default")

            policy = classify_endpoint(base_url)
            provider_kind = policy.provider_kind

            model_from_req = config.get("model_name")
            if not model_from_req:
                model_from_req = active_provider.get("default_model") or "gpt-4o-mini"

            model_from_req = policy.normalize_model(model_from_req)
            if not policy.validate_model(model_from_req):
                registry.append_event(job_id, {"type": "error", "message": f"Model '{model_from_req}' không hợp lệ với provider '{provider_kind}'"})
                registry.update_status(job_id, "failed")
                return

            if provider_type == "gemini":
                api_keys = active_provider.get("api_keys", [])
            else:
                api_key = active_provider.get("api_key")
                api_keys = [api_key or gateway_api_key] if (api_key or gateway_api_key) else []

            if not api_keys or not api_keys[0]:
                registry.append_event(job_id, {"type": "error", "message": f"Chưa cấu hình API key cho provider {active_provider.get('name', provider_type)}"})
                registry.update_status(job_id, "failed")
                return

            worker_config = config.copy()
            worker_config["project_slug"] = slug
            worker_config["provider_type"] = provider_type
            worker_config["provider_kind"] = provider_kind
            worker_config["base_url"] = base_url
            worker_config["gateway_api_key"] = gateway_api_key
            worker_config["credential_mode"] = credential_mode
            worker_config["provider_api_key"] = active_provider.get("api_key", "")
            worker_config["provider_id"] = active_provider.get("id", "")
            worker_config["model_name"] = model_from_req
            worker_config["qa_model"] = model_from_req

            project_tm = TranslationMemory(
                tm_dir=str(pdir / "assets" / "translation_memory"),
                enabled=True,
            )

            use_case = TranslateProjectFilesUseCase(
                api_keys=api_keys,
                config=worker_config,
                glossary_paths=glossary_paths,
            )

            store = getattr(registry, "_store", None)
            lease = store.acquire_lease(job_id) if store else None
            if store and not lease:
                logger.error(f"Không thể acquire lease cho translate job {job_id}")
                registry.update_status(job_id, "failed")
                registry.append_event(job_id, {
                    "type": "task_failed",
                    "message": "Không thể acquire lease thực thi (task có thể đang được chạy bởi worker khác)",
                    "error_context": {
                        "status": "lease_acquisition_failed",
                        "http_status": 409,
                        "retryable": False,
                        "message": "Không thể acquire lease thực thi",
                    },
                })
                return
            lease_token, lease_epoch = lease if lease else (None, None)

            def emit_event(event):
                event_type = event.get("type", "info")
                # append_event TRƯỚC: nó là writer duy nhất của metadata failure, và phải chạy
                # khi task còn non-terminal để iter_events chưa break (B7).
                registry.append_event(job_id, event, lease_epoch=lease_epoch, lease_token=lease_token)
                if event_type == "complete":
                    registry.update_status(job_id, "completed", lease_epoch=lease_epoch, lease_token=lease_token)
                elif event_type == "task_failed":
                    registry.update_status(job_id, "failed", lease_epoch=lease_epoch, lease_token=lease_token)
                elif event_type == "cancelled":
                    registry.update_status(job_id, "cancelled", lease_epoch=lease_epoch, lease_token=lease_token)
                # "error" / "file_error" / "batch_error": KHÔNG terminal. Chỉ log vào stream.
                # Lỗi chunk lẻ không được đóng SSE trước khi task_failed kịp mang
                # http_status + checkpoint_key ra frontend.

            def save_meta():
                meta["updated_at"] = datetime.now().isoformat()
                _save_project_meta(slug, meta)
                calculate_stats()

            from backend.infrastructure.progress.lease_manager import LeaseKeepAlive
            with LeaseKeepAlive(
                task_id=job_id,
                lease_token=lease_token or "",
                lease_epoch=lease_epoch or 0,
                task_store=store,
                interval_seconds=5.0,
            ) as keep_alive:
                use_case.execute(
                    project_dir=pdir,
                    filenames=filenames,
                    progress_callback=emit_event,
                    translation_memory=project_tm,
                    save_meta_callback=save_meta,
                    job_id=job_id,
                    lease_keep_alive=keep_alive,
                )

        except Exception as e:
            logger.error(f"Lỗi Translate Worker: {str(e)}")
            registry.append_event(
                job_id,
                {
                    "type": "task_failed",
                    "message": f"❌ Lỗi hệ thống: {str(e)}",
                    "error_context": {
                        "status": "worker_exception",
                        "http_status": None,
                        "retryable": False,
                        "message": f"❌ Lỗi hệ thống: {str(e)}",
                    },
                },
                lease_epoch=lease_epoch,
                lease_token=lease_token,
            )
            registry.update_status(
                job_id,
                "failed",
                lease_epoch=lease_epoch,
                lease_token=lease_token,
            )

    return worker


# ============================================================
# Project Translation API
# ============================================================


# ============================================================


@projects_bp.route("/api/projects/<slug>/translate", methods=["POST"])
def translate_project_file(slug):
    """Dịch file(s) trong dự án - dùng backend use case."""
    import webui as _state
    from backend.application.use_cases.translate_project_files_use_case import TranslateProjectFilesUseCase
    from backend.infrastructure.config.api_key_service import ApiKeyService
    from backend.infrastructure.config.prompt_service import PromptService
    from backend.infrastructure.progress.task_registry import TaskRegistry

    data = request.json
    filenames = data.get("files", [])
    force_retranslate = bool(data.get("force_retranslate", False))

    pdir = _get_project_dir(slug)
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    if not filenames:
        return jsonify({"error": "Không có file nào được chọn"}), 400

    # Load prompts bằng PromptService
    prompt_service = PromptService()
    prompts = prompt_service.load_merged_prompts(pdir)

    # Dùng ProjectContextService thay vì đọc hardcode
    from backend.infrastructure.config.project_context_service import ProjectContextService
    context_service = ProjectContextService()
    context_data = context_service.load_context(pdir)
    prompts["main"] = context_service.render_prompt(prompts.get("main", ""), context_data)

    # Glossary paths
    glossary_filenames = ["glossary.txt", "relationship.txt"]
    glossary_paths = [
        pdir / "assets" / gf for gf in glossary_filenames if (pdir / "assets" / gf).exists()
    ]

    # Dùng AppConfigService để lấy cấu hình hệ thống
    from backend.infrastructure.config.app_config_service import AppConfigService
    config_service = AppConfigService()

    config = {
        "provider_type": "", # Sẽ được điền bên trong worker
        "base_url": "", # Sẽ được điền bên trong worker
        "model_name": data.get("model", ""), # Sẽ fallback về default_model nếu rỗng
        "qa_model": data.get("model", ""),
        "temperature": float(data.get("temperature", config_service.get_temperature())),
        "chunk_size": int(data.get("chunk_size", config_service.get_default_chunk_size())),
        "force_retranslate": force_retranslate,
        "thinking_level": data.get("thinking_level", config_service.get_thinking_level()),
        "request_delay": config_service.get("PROCESSING", "REQUEST_DELAY", fallback=0, value_type=float),
        "prompts": prompts,
        "max_refinement_attempts": 2,
        "min_length_ratio": 0.5,
        "max_length_ratio": 5.0,
        "context_char_count": config_service.get_context_char_count(),
    }

    # BẮT BUỘC: identity của checkpoint chứa project_slug (executor đọc từ worker_config,
    # projects.py:1592). Nếu config của route thiếu nó, _checkpoint_status_for so lệch và
    # KHÔNG BAO GIỜ trả resume_available. Xem B12.
    config["project_slug"] = slug

    # Check for existing checkpoints when not force retranslating
    if not force_retranslate:
        resume_required = {}
        files_without_checkpoint = []
        for filename in filenames:
            file_path = pdir / "sources" / filename
            if not file_path.exists():
                continue
            source_text = file_path.read_text(encoding="utf-8")
            ck_status = _checkpoint_status_for(filename, source_text, config)
            if ck_status and ck_status.get("status") == "resume_available":
                resume_required[filename] = ck_status
            else:
                files_without_checkpoint.append(filename)
        if resume_required:
            # REV-C C6: Nếu request nhiều file và chỉ một phần có checkpoint,
            # trả lỗi thay vì âm thầm bỏ qua file không có checkpoint.
            project_title = meta.get("book_title") or meta.get("name") or slug
            # Inject project_slug và project_name vào từng checkpoint entry
            for fn, ck in resume_required.items():
                ck["project_slug"] = slug
                ck["project_name"] = project_title
            if files_without_checkpoint and len(filenames) > 1:
                return jsonify({
                    "status": "multi_file_resume_requires_per_file_decision",
                    "error": "Một số file được chọn chưa có checkpoint. Vui lòng xử lý từng file hoặc chọn 'Dịch lại từ đầu' cho các file này.",
                    "project_slug": slug,
                    "project_name": project_title,
                    "files_with_checkpoint": list(resume_required.keys()),
                    "files_without_checkpoint": files_without_checkpoint,
                    "checkpoints": resume_required,
                }), 409
            return jsonify({
                "status": "resume_required",
                "project_slug": slug,
                "project_name": project_title,
                "checkpoints": resume_required,
            }), 409

    registry = TaskRegistry()
    main_filename = filenames[0] if filenames else ""
    job_id = registry.create_task(
        kind="translation",
        title=f"Translate {slug}",
        total_files=len(filenames),
        project_slug=slug,
        filename=main_filename
    )

    worker = _build_translate_worker(
        slug, pdir, meta, config, filenames, glossary_paths, registry
    )
    thread = Thread(target=worker, args=(job_id,), daemon=True)
    thread.start()
    return jsonify({"status": "started", "job_id": job_id, "files_count": len(filenames)})


@projects_bp.route("/api/projects/<slug>/translate/confirm-resume", methods=["POST"])
def confirm_resume_translate(slug):
    """Xác nhận resume cho các file có checkpoint."""
    import webui as _state
    from backend.application.use_cases.translate_project_files_use_case import TranslateProjectFilesUseCase
    from backend.infrastructure.config.api_key_service import ApiKeyService
    from backend.infrastructure.config.prompt_service import PromptService
    from backend.infrastructure.progress.task_registry import TaskRegistry

    data = request.json
    filenames = data.get("files", [])

    pdir = _get_project_dir(slug)
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    if not filenames:
        return jsonify({"error": "Không có file nào được chọn"}), 400

    prompt_service = PromptService()
    prompts = prompt_service.load_merged_prompts(pdir)

    from backend.infrastructure.config.project_context_service import ProjectContextService
    context_service = ProjectContextService()
    context_data = context_service.load_context(pdir)
    prompts["main"] = context_service.render_prompt(prompts.get("main", ""), context_data)

    glossary_filenames = ["glossary.txt", "relationship.txt"]
    glossary_paths = [
        pdir / "assets" / gf for gf in glossary_filenames if (pdir / "assets" / gf).exists()
    ]

    from backend.infrastructure.config.app_config_service import AppConfigService
    config_service = AppConfigService()

    config = {
        "provider_type": "",
        "base_url": "",
        "model_name": data.get("model", ""),
        "qa_model": data.get("model", ""),
        "temperature": float(data.get("temperature", config_service.get_temperature())),
        "chunk_size": int(data.get("chunk_size", config_service.get_default_chunk_size())),
        "force_retranslate": False,
        "thinking_level": data.get("thinking_level", config_service.get_thinking_level()),
        "request_delay": config_service.get("PROCESSING", "REQUEST_DELAY", fallback=0, value_type=float),
        "prompts": prompts,
        "max_refinement_attempts": 2,
        "min_length_ratio": 0.5,
        "max_length_ratio": 5.0,
        "context_char_count": config_service.get_context_char_count(),
    }
    config["project_slug"] = slug

    registry = TaskRegistry()
    # Ghi nhận project_slug và filename vào persistent store
    main_filename = filenames[0] if filenames else ""
    job_id = registry.create_task(
        kind="translation",
        title=f"Resume {slug}",
        total_files=len(filenames),
        project_slug=slug,
        filename=main_filename
    )

    worker = _build_translate_worker(
        slug, pdir, meta, config, filenames, glossary_paths, registry
    )
    thread = Thread(target=worker, args=(job_id,), daemon=True)
    thread.start()
    return jsonify({"status": "started", "job_id": job_id, "files_count": len(filenames)})


@projects_bp.route("/api/tasks/<task_id>/resume", methods=["POST"])
def resume_task(task_id):
    import uuid
    from services.task_store import TaskStore
    from backend.infrastructure.config.prompt_service import PromptService
    from backend.infrastructure.progress.task_registry import TaskRegistry
    store = TaskStore(_get_checkpoint_dir().replace("checkpoints", ""))
    task = store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if task["status"] not in ("resumable", "failed", "paused", "interrupted"):
        return jsonify({"error": f"Cannot resume task in status {task['status']}"}), 400

    # A task row can outlive its SQLite checkpoint (for example after a
    # successful cleanup or manual file removal). Do not create a new resume
    # task when the source checkpoint is missing, unreadable, or complete.
    checkpoint_service = CheckpointService(_get_checkpoint_dir())
    resolved = checkpoint_service.resolve_checkpoint_key(task.get("checkpoint_key"))
    checkpoint_info = resolved["resume_info"] if resolved else None
    if not checkpoint_info or not checkpoint_info.get("can_resume"):
        return jsonify({
            "error": "Checkpoint không còn tồn tại, không đọc được hoặc đã hoàn tất; task không thể resume.",
            "task_id": task_id,
        }), 409

    if task.get("checkpoint_key"):
        existing = store.find_running_by_checkpoint_key(task["checkpoint_key"])
        if existing and existing["task_id"] != task_id:
            return jsonify({
                "error": "Already resuming",
                "job_id": existing["job_id"],
            }), 409

    new_job_id = str(uuid.uuid4())
    store.create_resumed_task(task, new_job_id)

    if not task.get("project_slug"):
        return jsonify({
            "error": "Task không có project_slug — dùng /api/projects/<slug>/translate/confirm-resume để resume",
            "job_id": new_job_id,
            "filename": task["filename"],
            "checkpoint_key": task.get("checkpoint_key"),
        }), 400

    pdir = _get_project_dir(task["project_slug"])
    meta = _load_project_meta(task["project_slug"])
    filenames = [task["filename"]]

    # Restore config from saved identity to ensure chunk_size, model, etc.
    # match what was used when the checkpoint was created — prevents identity mismatch.
    saved_identity = task.get("identity") or {}
    from backend.infrastructure.config.app_config_service import AppConfigService
    config_service = AppConfigService()
    config = {
        "provider_type": "",
        "base_url": "",
        "model_name": saved_identity.get("model", ""),
        "qa_model": saved_identity.get("qa_model", ""),
        "temperature": config_service.get_temperature(),
        "chunk_size": int(saved_identity.get("chunk_size", config_service.get_default_chunk_size())),
        "force_retranslate": False,
        "thinking_level": config_service.get_thinking_level(),
        "request_delay": config_service.get("PROCESSING", "REQUEST_DELAY", fallback=0, value_type=float),
        "max_refinement_attempts": 2,
        "min_length_ratio": 0.5,
        "max_length_ratio": 5.0,
        "context_char_count": config_service.get_context_char_count(),
    }
    config["project_slug"] = task["project_slug"]

    prompt_service = PromptService()
    prompts = prompt_service.load_merged_prompts(pdir)
    from backend.infrastructure.config.project_context_service import ProjectContextService
    context_service = ProjectContextService()
    context_data = context_service.load_context(pdir)
    prompts["main"] = context_service.render_prompt(prompts.get("main", ""), context_data)
    config["prompts"] = prompts

    glossary_paths = [
        pdir / "assets" / gf for gf in ["glossary.txt", "relationship.txt"]
        if (pdir / "assets" / gf).exists()
    ]

    registry = TaskRegistry()
    worker = _build_translate_worker(
        task["project_slug"], pdir, meta, config, filenames, glossary_paths, registry
    )
    thread = Thread(target=worker, args=(new_job_id,), daemon=True)
    thread.start()

    return jsonify({
        "status": "resumed",
        "job_id": new_job_id,
        "resume_of": task_id,
        "checkpoint_key": task.get("checkpoint_key"),
        "snapshot": {
            "project_slug": task["project_slug"],
            "filename": task["filename"],
            "total_chunks": task.get("total_chunks", 0),
            "completed_chunks": task.get("completed_chunks", 0),
            "current_chunk": task.get("current_chunk", 0),
            "phase": task.get("phase"),
        },
    })


@projects_bp.route("/api/tasks/<task_id>/recover-from-checkpoint", methods=["POST"])
def recover_from_checkpoint(task_id: str):
    from services.task_store import TaskStore
    from services.checkpoint_service import CheckpointService
    from backend.infrastructure.config.prompt_service import PromptService
    import uuid
    from pathlib import Path

    task_store = TaskStore(_get_checkpoint_dir().replace("checkpoints", ""))
    checkpoint_service = CheckpointService(_get_checkpoint_dir())

    data = request.get_json(silent=True) or {}
    provider_id = data.get("provider_id")
    model = data.get("model")
    export_partial = data.get("export_partial", True)

    source_task = task_store.get_task(task_id)
    if not source_task:
        return jsonify({"error": "Task không tồn tại"}), 404

    project_dir = _get_project_dir(source_task["project_slug"])

    if source_task["status"] not in ("failed", "resumable"):
        return jsonify({"error": f"Task không ở trạng thái recovery: {source_task['status']}"}), 400

    recovery_job_id = None
    recovery_ck_key = None
    partial_output_path = None

    try:
        # CRITICAL SECTION — chống race tạo recovery worker kép:
        # Phải giữ lock từ lúc kiểm tra active recovery cho tới sau create_recovery_task,
        # nếu không hai request đồng thời có thể cùng vượt qua find_active_recovery_for_source.
        # `return` trong `with` vẫn tự nhả lock (context manager exit).
        with _RECOVERY_CREATE_LOCK:
            existing_recovery = task_store.find_active_recovery_for_source(task_id)
            if existing_recovery:
                return jsonify({
                    "error": "Đã có recovery task đang chạy",
                    "recovery_task_id": existing_recovery["task_id"],
                }), 409

            root_recovery_of = source_task.get("recovery_of") or source_task["task_id"]

            # Phase 9: Canonical Poison Job Quarantine (Tối đa 3 lần recovery)
            MAX_RECOVERY_ATTEMPTS = 3
            attempts = task_store.get_recovery_attempt_count(root_recovery_of)
            if attempts >= MAX_RECOVERY_ATTEMPTS:
                task_store.quarantine_task(
                    source_task["task_id"],
                    reason=f"Đạt giới hạn {MAX_RECOVERY_ATTEMPTS} lần recovery"
                )
                return jsonify({
                    "error": f"Task đã đạt tối đa {MAX_RECOVERY_ATTEMPTS} lần recovery (poison job quarantine). Cần can thiệp thủ công.",
                    "error_class": "poison_job",
                    "quarantine_reason": "max_recovery_attempts",
                    "recovery_attempts": attempts,
                }), 400

            immediate_ck_key = (
                source_task.get("recovery_checkpoint_key")
                or source_task.get("checkpoint_key")
            )
            resolved = checkpoint_service.resolve_checkpoint_key(immediate_ck_key)
            if not resolved or not resolved.get("filename"):
                return jsonify({"error": "Không đọc được checkpoint hoặc metadata hỏng"}), 400
            ck_logical = resolved["filename"]

            indices = checkpoint_service.get_done_pending_indices(ck_logical)
            if not indices:
                return jsonify({"error": "Không đọc được checkpoint"}), 400

            done_count = len(indices["done_indices"])
            pending_count = len(indices["pending_indices"])
            total_count = done_count + pending_count

            if pending_count == 0:
                return jsonify({"error": "Tất cả chunk đã dịch, không cần recovery"}), 400

            if done_count == 0:
                return jsonify({"error": "Không có chunk nào đã dịch, nên dùng resume thường"}), 400

            # Validate the selected provider before cloning the checkpoint or creating
            # the recovery task. Otherwise a missing credential can leave an orphaned
            # recovery DB/task behind after the API has already returned 400.
            from backend.infrastructure.providers.provider_service import ProviderService
            provider_service = ProviderService()
            if provider_id:
                active_provider = provider_service.get_provider_by_id(provider_id) or {}
                if not active_provider:
                    return jsonify({"error": f"Provider không tồn tại: {provider_id}"}), 400
            else:
                active_provider = provider_service.get_active_provider_config() or {}

            provider_type = active_provider.get("type", "gemini")
            if provider_type == "gemini":
                api_keys = active_provider.get("api_keys", [])
            else:
                api_key = active_provider.get("api_key")
                gateway_api_key = active_provider.get("gateway_api_key", "")
                api_keys = [api_key or gateway_api_key] if (api_key or gateway_api_key) else []

            if not api_keys or not api_keys[0]:
                return jsonify({"error": f"Chưa cấu hình API key cho provider {active_provider.get('name', provider_type)}"}), 400

            from backend.infrastructure.providers.endpoint_policy import classify_endpoint
            policy = classify_endpoint(active_provider.get("base_url"))
            selected_model = (
                model
                or (source_task.get("identity") or {}).get("model", "")
                or active_provider.get("default_model", "")
                or "gpt-4o-mini"
            )
            selected_model = policy.normalize_model(selected_model)
            if not policy.validate_model(selected_model):
                return jsonify({
                    "error": f"Model '{selected_model}' không hợp lệ với provider '{policy.provider_kind}'"
                }), 400
            model = selected_model

            recovery_job_id = str(uuid.uuid4())
            recovery_ck_key = f"{ck_logical}.{recovery_job_id[:8]}"

            if not checkpoint_service.clone_namespace(ck_logical, recovery_ck_key):
                return jsonify({"error": "Không thể clone checkpoint"}), 500

            saved_identity = source_task.get("identity") or {}
            mixed_provider = (
                provider_id and provider_id != saved_identity.get("provider_id")
            ) or (
                model and model != saved_identity.get("model")
            )

            root_recovery_of = source_task.get("recovery_of") or source_task["task_id"]

            task_store.create_recovery_task(
                source_task=source_task,
                recovery_job_id=recovery_job_id,
                recovery_checkpoint_key=recovery_ck_key,
                provider_id=provider_id or saved_identity.get("provider_id", ""),
                model=model or saved_identity.get("model", ""),
                mixed_provider=mixed_provider,
                source_checkpoint_key=immediate_ck_key,
                root_recovery_of=root_recovery_of,
            )

            task_store.update_recovery_task(
                recovery_job_id,
                pending_chunks=indices["pending_indices"],
                completed_chunks=done_count,
                checkpoint_key=recovery_ck_key,
            )

        if export_partial:
            partial_path = checkpoint_service.write_partial_file(
                recovery_ck_key,
                project_dir / "translated" / ".recovery",
            )
            if partial_path:
                partial_output_path = str(partial_path)
                task_store.update_recovery_task(recovery_job_id, partial_output_path=partial_output_path)

        from core.executor import TranslationExecutor
        from backend.infrastructure.progress.task_registry import TaskRegistry
        from services.api_service import ApiManager
        provider_type = active_provider.get("type", "gemini")
        base_url = active_provider.get("base_url")
        gateway_api_key = active_provider.get("gateway_api_key", "")
        credential_mode = active_provider.get("credential_mode", "default")

        config = {
            "provider_type": provider_type,
            "provider_kind": active_provider.get("type", provider_type),
            "base_url": base_url or "",
            "model_name": model or saved_identity.get("model", "") or active_provider.get("default_model", ""),
            "qa_model": saved_identity.get("qa_model", ""),
            "temperature": 1.0,
            "chunk_size": int(saved_identity.get("chunk_size", 22000)),
            "force_retranslate": False,
            "thinking_level": "MEDIUM",
            "request_delay": 0.0,
            "max_refinement_attempts": 2,
            "min_length_ratio": 0.5,
            "max_length_ratio": 5.0,
            "context_char_count": 500,
            "gateway_api_key": gateway_api_key,
            "credential_mode": credential_mode,
            "provider_api_key": active_provider.get("api_key", ""),
            "provider_id": active_provider.get("id", provider_id or ""),
        }

        prompt_service = PromptService()
        prompts = prompt_service.load_merged_prompts(_get_project_dir(source_task["project_slug"]))
        config["prompts"] = prompts

        executor = TranslationExecutor(api_keys=api_keys, config=config)

        registry = TaskRegistry()
        # create_recovery_task() already persisted the row. Hydrate the in-memory
        # registry entry instead of calling create_task(), which would generate a
        # different job id or duplicate the persistent primary key.
        if not registry.get_task(recovery_job_id):
            task_store.update_recovery_task(
                recovery_job_id,
                status="failed",
                last_error="Không thể đăng ký recovery task vào registry",
            )
            checkpoint_service.delete_by_key(recovery_ck_key)
            return jsonify({"error": "Không thể đăng ký recovery task"}), 500

        output_path = project_dir / "translated" / (
            f"{source_task['filename']}.recovery.{recovery_job_id[:8]}.txt"
        )
        lease = task_store.acquire_lease(recovery_job_id)
        if not lease:
            checkpoint_service.delete_by_key(recovery_ck_key)
            task_store.update_recovery_task(
                recovery_job_id,
                status="failed",
                last_error="Không thể acquire lease cho recovery task",
            )
            return jsonify({
                "error": "Không thể acquire lease cho recovery task",
                "status": "lease_acquisition_failed",
            }), 409

        lease_token, lease_epoch = lease

        def recovery_progress(event: dict):
            registry.append_event(recovery_job_id, event, lease_epoch=lease_epoch, lease_token=lease_token)
            evt_type = event.get("type")
            if evt_type == "complete":
                task_store.update_recovery_task(
                    recovery_job_id,
                    lease_epoch=lease_epoch,
                    lease_token=lease_token,
                    status="completed",
                    final_output_path=str(output_path),
                )
                registry.update_status(recovery_job_id, "completed", lease_epoch=lease_epoch, lease_token=lease_token)
            elif evt_type == "cancelled":
                task_store.update_recovery_task(
                    recovery_job_id,
                    lease_epoch=lease_epoch,
                    lease_token=lease_token,
                    status="cancelled",
                    last_error=event.get("message", ""),
                )
                registry.update_status(recovery_job_id, "cancelled", lease_epoch=lease_epoch, lease_token=lease_token)
            elif evt_type == "task_failed":
                err_ctx = event.get("error_context") if isinstance(event.get("error_context"), dict) else {}
                err_class = err_ctx.get("status") or event.get("error_class") or event.get("status")
                http_st = err_ctx.get("http_status") if "http_status" in err_ctx else event.get("http_status")
                ret = err_ctx.get("retryable") if "retryable" in err_ctx else event.get("retryable")
                chk_idx = err_ctx.get("chunk_index") if "chunk_index" in err_ctx else event.get("chunk_index")
                task_store.update_recovery_task(
                    recovery_job_id,
                    lease_epoch=lease_epoch,
                    lease_token=lease_token,
                    status="failed",
                    last_error=err_ctx.get("message") or event.get("message", ""),
                    error_class=err_class,
                    http_status=http_st,
                    retryable=1 if ret else 0,
                    current_chunk=chk_idx,
                )
                registry.update_status(recovery_job_id, "failed", lease_epoch=lease_epoch, lease_token=lease_token)
            elif evt_type == "error":
                err_ctx = event.get("error_context") if isinstance(event.get("error_context"), dict) else {}
                err_class = err_ctx.get("status") or event.get("error_class") or event.get("status")
                http_st = err_ctx.get("http_status") if "http_status" in err_ctx else event.get("http_status")
                ret = err_ctx.get("retryable") if "retryable" in err_ctx else event.get("retryable")
                chk_idx = err_ctx.get("chunk_index") if "chunk_index" in err_ctx else event.get("chunk_index")
                task_store.update_recovery_task(
                    recovery_job_id,
                    lease_epoch=lease_epoch,
                    lease_token=lease_token,
                    last_error=err_ctx.get("message") or event.get("message", ""),
                    error_class=err_class,
                    http_status=http_st,
                    retryable=1 if ret else 0,
                    current_chunk=chk_idx,
                )

        def _recovery_worker_wrapper():
            from backend.infrastructure.progress.lease_manager import LeaseKeepAlive
            with LeaseKeepAlive(
                task_id=recovery_job_id,
                lease_token=lease_token or "",
                lease_epoch=lease_epoch or 0,
                task_store=task_store,
                interval_seconds=5.0,
            ) as keep_alive:
                executor.recover_from_checkpoint(
                    source_checkpoint_key=ck_logical,
                    recovery_checkpoint_key=recovery_ck_key,
                    output_file_path=output_path,
                    progress_callback=recovery_progress,
                    job_id=recovery_job_id,
                    lease_keep_alive=keep_alive,
                )

        worker_thread = Thread(
            target=_recovery_worker_wrapper,
            daemon=True,
        )
        worker_thread.start()

        return jsonify({
            "status": "recovery_started",
            "job_id": recovery_job_id,
            "recovery_of": root_recovery_of,
            "source_task_id": source_task["task_id"],
            "partial_output": partial_output_path,
            "checkpoint": {
                "completed_chunks": done_count,
                "total_chunks": total_count,
                "done_indices": indices["done_indices"],
                "pending_indices": indices["pending_indices"],
            },
            "mixed_provider": mixed_provider,
        }), 200

    except Exception as prep_err:
        logger.error(f"Lỗi chuẩn bị recovery task {recovery_job_id}: {prep_err}", exc_info=True)
        # Rollback cloned checkpoint
        if recovery_ck_key:
            try:
                checkpoint_service.delete_by_key(recovery_ck_key)
            except Exception as e_ck:
                logger.warning(f"[ORPHAN_CLEANUP_FAILED] Không thể xóa checkpoint {recovery_ck_key}: {e_ck}")
        # Rollback recovery task row
        if recovery_job_id:
            try:
                task_store.delete_task(recovery_job_id)
            except Exception as e_ts:
                logger.warning(f"[ORPHAN_CLEANUP_FAILED] Không thể xóa recovery task {recovery_job_id}: {e_ts}")
        # Rollback partial output/manifest
        if partial_output_path and Path(partial_output_path).exists():
            try:
                Path(partial_output_path).unlink(missing_ok=True)
                Path(partial_output_path).with_suffix(".manifest.json").unlink(missing_ok=True)
            except Exception as e_p:
                logger.warning(f"[ORPHAN_CLEANUP_FAILED] Không thể xóa partial file {partial_output_path}: {e_p}")
        return jsonify({"error": f"Chuẩn bị recovery thất bại: {prep_err}"}), 500


@projects_bp.route("/api/tasks/<task_id>/export-partial", methods=["POST"])
def export_partial(task_id: str):
    from services.task_store import TaskStore
    from services.checkpoint_service import CheckpointService

    task_store = TaskStore(_get_checkpoint_dir().replace("checkpoints", ""))
    checkpoint_service = CheckpointService(_get_checkpoint_dir())

    task = task_store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task không tồn tại"}), 404

    project_dir = _get_project_dir(task["project_slug"])

    resolved = checkpoint_service.resolve_checkpoint_key(task.get("checkpoint_key"))
    if not resolved or not resolved.get("filename"):
        return jsonify({"error": "Không đọc được checkpoint hoặc metadata hỏng"}), 400
    ck_logical = resolved["filename"]

    indices = checkpoint_service.get_done_pending_indices(ck_logical)
    if not indices or not indices["done_indices"]:
        return jsonify({"error": "Không có chunk nào đã dịch"}), 400

    partial_path = checkpoint_service.write_partial_file(
        ck_logical,
        project_dir / "translated" / ".recovery",
    )

    if not partial_path:
        return jsonify({"error": "Không thể tạo partial file"}), 500

    return jsonify({
        "partial_output": str(partial_path),
        "done_chunks": len(indices["done_indices"]),
        "pending_chunks": len(indices["pending_indices"]),
    }), 200


@projects_bp.route("/api/tasks/<task_id>/close-as-partial", methods=["POST"])
def close_as_partial(task_id: str):
    """Chốt task thành partial.

    Luồng bắt buộc: validate confirm → cancel scoped → chờ worker/lease hết hạn →
    resolve checkpoint (canonical resolver) → assemble partial + manifest atomic →
    persistent status `closed_partial` → registry mirror `closed_partial`.
    KHÔNG BAO GIỜ gọi status `completed` trong luồng này.
    """
    from services.task_store import TaskStore
    from services.checkpoint_service import CheckpointService
    from backend.infrastructure.progress.runtime_state import RuntimeState

    data = request.get_json(silent=True) or {}
    if not data.get("confirm"):
        return jsonify({"error": "Cần xác nhận: {\"confirm\": true}"}), 400

    task_store = TaskStore(_get_workspace_dir())
    checkpoint_service = CheckpointService(_get_checkpoint_dir())

    task = task_store.get_task(task_id)
    if not task:
        return jsonify({"error": "Task không tồn tại"}), 404

    # Idempotent: đã chốt rồi thì trả lại kết quả cũ, không assemble lần hai.
    # Cần thiết vì frontend có thể retry sau khi nhận 202 close_pending.
    if task["status"] == "closed_partial" and task.get("partial_output_path"):
        existing = Path(task["partial_output_path"])
        if existing.is_file():
            return jsonify({
                "status": "closed_partial",
                "task_id": task_id,
                "partial_output": str(existing),
                "completed_chunks": task.get("completed_chunks", 0),
                "pending_chunks": max(0, (task.get("total_chunks") or 0) - (task.get("completed_chunks") or 0)),
                "idempotent": True,
            }), 200

    # `partial_completed` là status RÁC do route cũ ghi trước khi crash (B16) — chấp nhận ĐỌC
    # để người dùng chốt lại được, nhưng KHÔNG BAO GIỜ ghi lại giá trị này.
    if task["status"] not in ("running", "started", "queued", "resumable", "paused",
                              "interrupted", "failed", "partial_completed"):
        return jsonify({"error": f"Không thể chốt task ở trạng thái {task['status']}"}), 400

    job_id = task.get("job_id") or task_id
    _RUNNING = ("running", "started")

    # 1. Cancel scoped — chỉ khi worker có thể còn chạy
    if task["status"] in _RUNNING:
        RuntimeState().request_cancel(job_id)

    # 2. Chờ worker dừng / lease hết hạn. Quá timeout → close_pending, KHÔNG assemble
    if task["status"] in _RUNNING:
        deadline = time.monotonic() + CLOSE_WAIT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            current = task_store.get_task(task_id) or {}
            st = current.get("status")
            if st not in _RUNNING:
                task = current
                break
            time.sleep(0.2)
        else:
            return jsonify({"status": "close_pending", "task_id": task_id}), 202

    # 3. Resolve checkpoint bằng canonical resolver (logical | physical | stem)
    resolved = checkpoint_service.resolve_checkpoint_key(
        task.get("checkpoint_key") or task.get("filename") or task_id
    )
    if not resolved or not resolved.get("filename"):
        return jsonify({"error": "Không tìm thấy checkpoint cho task hoặc metadata hỏng"}), 400
    ck_logical = resolved["filename"]

    # 4. Đọc checkpoint trong transaction/read-safe boundary
    indices = checkpoint_service.get_done_pending_indices(ck_logical)
    if not indices or not indices["done_indices"]:
        return jsonify({"error": "Không có chunk nào đã dịch"}), 400

    slug = task.get("project_slug") or ""
    if not slug:
        # Task mồ côi: không biết ghi partial vào đâu. Ghi vào PROJECTS_DIR/"" sẽ rải file
        # rác ra workspace/projects/translated/ — chặn thẳng thay vì đoán.
        return jsonify({"error": "Task không có project_slug, không xác định được nơi ghi partial"}), 400
    project_dir = _get_project_dir(slug)
    partial_path = checkpoint_service.write_partial_file(
        ck_logical, project_dir / "translated" / ".recovery"
    )
    if not partial_path:
        return jsonify({"error": "Không thể tạo partial file"}), 500

    done_count = len(indices["done_indices"])
    pending_count = len(indices["pending_indices"])

    # 5. Registry mirror TRƯỚC (dọn cancel token qua update_status Phase 1).
    #    Phải chạy TRƯỚC bước 6, xem ghi chú thứ tự bên dưới.
    from backend.infrastructure.progress.task_registry import TaskRegistry
    registry = TaskRegistry()
    registry.update_status(job_id, "closed_partial")

    # 6. Persistent status closed_partial (terminal với worker, KHÔNG phải completed).
    #    Ghi SAU cùng để con số từ checkpoint (nguồn chân lý) là giá trị cuối trong DB.
    task_store.update_status(
        task_id,
        "closed_partial",
        partial_output_path=str(partial_path),
        completed_chunks=done_count,
        current_chunk=done_count,
        last_error=None,
    )

    return jsonify({
        "status": "closed_partial",
        "task_id": task_id,
        "partial_output": str(partial_path),
        "completed_chunks": done_count,
        "pending_chunks": pending_count,
    }), 200


# ============================================================
# Project Spell-check API
# ============================================================

@projects_bp.route("/api/projects/<slug>/spellcheck", methods=["POST"])
def spellcheck_project_file(slug):
    """Kiểm tra chính tả file(s) trong dự án - dùng backend use case."""
    from backend.application.use_cases.spellcheck_project_files_use_case import SpellcheckProjectFilesUseCase
    from backend.infrastructure.config.prompt_service import PromptService
    from backend.infrastructure.progress.task_registry import TaskRegistry

    data = request.json
    filenames = data.get("files", [])
    folder_type = data.get("folder_type", "sources")

    pdir = _get_project_dir(slug)
    meta = _load_project_meta(slug)
    if not meta:
        return jsonify({"error": "Dự án không tồn tại"}), 404

    if not filenames:
        return jsonify({"error": "Không có file nào được chọn"}), 400

    # Load spell-check prompt bằng PromptService
    prompt_service = PromptService()
    prompts = prompt_service.load_merged_prompts(pdir)

    sp_prompt = prompts.get("chinh_ta", "").strip()
    if not sp_prompt:
        sp_prompt = "Hãy soát lỗi chính tả cho văn bản sau, giữ nguyên định dạng. Trả về văn bản đã sửa, sau đó là dấu gạch ngang '---' và danh sách các lỗi đã sửa (nếu có)."

    # Load style guide for placeholder replacement
    style_guide_path = pdir / "assets" / "style-guide.txt"
    style_guide = style_guide_path.read_text(encoding="utf-8") if style_guide_path.exists() else ""
    sp_prompt = sp_prompt.replace("{translation_guidelines}", style_guide)

    # Dùng AppConfigService để lấy cấu hình hệ thống
    from backend.infrastructure.config.app_config_service import AppConfigService
    config_service = AppConfigService()

    config = {
        "provider_type": "", # Sẽ được điền bên trong worker
        "base_url": "", # Sẽ được điền bên trong worker
        "model_name": data.get("model", ""), # Sẽ fallback về default_model nếu rỗng
        "qa_model": data.get("model", ""),
        "temperature": float(data.get("temperature", config_service.get_temperature())),
        "chunk_size": int(data.get("chunk_size", config_service.get_default_chunk_size())),
        "prompts": {"main": sp_prompt, "chinh_ta": sp_prompt},
        "max_refinement_attempts": 2,
        "min_length_ratio": 0.5,
        "max_length_ratio": 5.0,
        "context_char_count": config_service.get_context_char_count(),
    }

    registry = TaskRegistry()
    main_filename = filenames[0] if filenames else ""
    job_id = registry.create_task(
        kind="spellcheck",
        title=f"Spellcheck {slug}",
        total_files=len(filenames),
        project_slug=slug,
        filename=main_filename
    )

    def _project_spellcheck_worker(job_id):
        """Worker dùng backend use case."""
        try:
            from backend.infrastructure.providers.provider_service import ProviderService
            from backend.infrastructure.providers.model_catalog_service import ModelCatalogService
            from backend.infrastructure.providers.endpoint_policy import classify_endpoint
            
            provider_service = ProviderService()
            active_provider = provider_service.get_active_provider_config() or {}
            provider_type = active_provider.get("type", "gemini")
            base_url = active_provider.get("base_url")
            gateway_api_key = active_provider.get("gateway_api_key", "")
            credential_mode = active_provider.get("credential_mode", "default")
            
            policy = classify_endpoint(base_url)
            provider_kind = policy.provider_kind
            
            model_from_req = config.get("model_name")
            if not model_from_req:
                model_from_req = active_provider.get("default_model") or "gpt-4o-mini"
                
            model_from_req = policy.normalize_model(model_from_req)
            if not policy.validate_model(model_from_req):
                registry.append_event(job_id, {"type": "error", "message": f"Model '{model_from_req}' không hợp lệ với provider '{provider_kind}'"})
                registry.update_status(job_id, "failed")
                return

            if provider_type == "gemini":
                api_keys = active_provider.get("api_keys", [])
            else:
                api_key = active_provider.get("api_key")
                api_keys = [api_key or gateway_api_key] if (api_key or gateway_api_key) else []

            if not api_keys or not api_keys[0]:
                registry.append_event(job_id, {"type": "error", "message": f"Chưa cấu hình API key cho provider {active_provider.get('name', provider_type)}"})
                registry.update_status(job_id, "failed")
                return

            worker_config = config.copy()
            worker_config["provider_type"] = provider_type
            worker_config["provider_kind"] = provider_kind
            worker_config["base_url"] = base_url
            worker_config["gateway_api_key"] = gateway_api_key
            worker_config["credential_mode"] = credential_mode
            worker_config["provider_api_key"] = active_provider.get("api_key", "")
            worker_config["provider_id"] = active_provider.get("id", "")
            worker_config["model_name"] = model_from_req
            worker_config["qa_model"] = model_from_req

            def emit_event(event):
                event_type = event.get("type", "info")
                if event_type == "complete":
                    registry.update_status(job_id, "completed")
                elif event_type == "error":
                    registry.update_status(job_id, "failed")
                registry.append_event(job_id, event)

            use_case = SpellcheckProjectFilesUseCase(api_keys=api_keys, config=worker_config)
            use_case.execute(
                project_dir=pdir,
                filenames=filenames,
                folder_type=folder_type,
                progress_callback=emit_event,
            )

        except Exception as e:
            logger.error(f"Lỗi Spellcheck Worker: {str(e)}")
            registry.append_event(job_id, {"type": "error", "message": f"❌ Lỗi hệ thống: {str(e)}"})
            registry.update_status(job_id, "failed")

    thread = Thread(target=_project_spellcheck_worker, args=(job_id,), daemon=True)
    thread.start()
    return jsonify({"status": "started", "job_id": job_id, "files_count": len(filenames)})

# ============================================================
# Portable Markdown Regex Helper (v1)
# ============================================================
# Profile: ECMAScript/Python Portable Regex v1
# Supported: (...), (?:...), a|b, *, +, ?, {m,n}, character class, ^, $, ., \n, \t, flags i, m, s
# Back-reference: $1, $2 in replacement strings (UI contract)
# Normalization: CRLF -> LF before matching.
# Note: Do not use \w, \d, \b for CJK-dependent logic.
# Python-specific adapter: Convert $1 to \g<1> for re.sub()

import re as _re

def _compile_portable_regex(pattern_str: str, search_mode: str) -> _re.Pattern:
    """Biên dịch pattern theo Portable Markdown Regex Profile."""
    normalized_search = pattern_str.replace("\r\n", "\n")
    if search_mode == "regex":
        # Default flags: MULTILINE (to match UI / JS behavior for ^ and $)
        return _re.compile(normalized_search, _re.MULTILINE)
    else:
        flags = 0 if search_mode == "case-sensitive" else _re.IGNORECASE
        return _re.compile(_re.escape(normalized_search), flags)

def _portable_replacement_adapter(replace_term: str) -> str:
    r"""Chuyển đổi cú pháp $1, $2 từ UI sang cú pháp \g<1>, \g<2> của Python re.sub."""
    # Chuyển $n thành \g<n>, cẩn thận bỏ qua trường hợp đã bị escape (\$n)
    # Tạm đơn giản: không xử lý escape sâu, chỉ map $1 -> \g<1>
    return _re.sub(r'(?<!\\)\$(\d+)', r'\\g<\1>', replace_term)

def _apply_portable_regex(content: str, pattern: _re.Pattern, replace_term: str = None) -> tuple[int, str]:
    """Áp dụng regex để đếm hoặc thay thế. Trả về (count, new_content)."""
    normalized_content = content.replace("\r\n", "\n")
    if replace_term is None:
        count = sum(1 for _ in pattern.finditer(normalized_content))
        return count, normalized_content
    
    adapted_replace = _portable_replacement_adapter(replace_term)
    new_content, count = pattern.subn(adapted_replace, normalized_content)
    return count, new_content

def _get_target_text_files(target_dir):
    ALLOWED_EXTS = {
        "", ".txt", ".md", ".markdown", ".html", ".htm", ".xhtml",
        ".xml", ".json", ".csv", ".tsv", ".srt", ".vtt", ".log"
    }
    return [
        f for f in target_dir.rglob("*")
        if f.is_file() and not f.name.startswith(".") and (f.suffix.lower() in ALLOWED_EXTS or not f.suffix)
    ]


@projects_bp.route("/api/projects/<slug>/replace-all", methods=["POST"])
def batch_replace_in_project(slug):
    """Tìm kiếm & Thay thế tất cả các tệp trong thư mục sources hoặc translated."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json or {}
    folder_type = data.get("folder_type", "sources")
    search_term = data.get("search_term", "")
    replace_term = data.get("replace_term", "")
    search_mode = data.get("search_mode", "normal")  # "normal" | "case-sensitive" | "regex"

    if not search_term:
        return jsonify({"error": "Chưa nhập từ khóa tìm kiếm"}), 400

    target_dir = pdir / ("translated" if folder_type == "translated" else "sources")
    if not target_dir.exists():
        return jsonify({"success": True, "replaced_files": 0, "total_occurrences": 0})

    try:
        pattern = _compile_portable_regex(search_term, search_mode)
    except _re.error as e:
        return jsonify({"error": f"Regex không hợp lệ: {str(e)}"}), 400

    total_occurrences = 0
    replaced_files = 0
    
    for fpath in sorted(_get_target_text_files(target_dir)):
        try:
            # Không bỏ qua byte lỗi: đọc thiếu rồi ghi đè sẽ làm mất nội dung.
            content = fpath.read_text(encoding="utf-8")
            count, new_content = _apply_portable_regex(content, pattern, replace_term)
            if count > 0:
                fpath.write_text(new_content, encoding="utf-8")
                total_occurrences += count
                replaced_files += 1
        except Exception as e:
            logger.error(f"Lỗi replace file {fpath.name}: {str(e)}")

    return jsonify({
        "success": True,
        "replaced_files": replaced_files,
        "total_occurrences": total_occurrences
    })


@projects_bp.route("/api/projects/<slug>/search-all", methods=["POST"])
def batch_search_in_project(slug):
    """Tìm kiếm đếm số lượt xuất hiện trong tất cả tệp nguồn hoặc dịch."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json or {}
    folder_type = data.get("folder_type", "sources")
    search_term = data.get("search_term", "")
    search_mode = data.get("search_mode", "normal")  # "normal" | "case-sensitive" | "regex"

    if not search_term:
        return jsonify({"error": "Chưa nhập từ khóa tìm kiếm"}), 400

    target_dir = pdir / ("translated" if folder_type == "translated" else "sources")
    if not target_dir.exists():
        return jsonify({"success": True, "matched_files": 0, "total_occurrences": 0})

    try:
        pattern = _compile_portable_regex(search_term, search_mode)
    except _re.error as e:
        return jsonify({"error": f"Regex không hợp lệ: {str(e)}"}), 400

    total_occurrences = 0
    matched_files = 0
    
    for fpath in sorted(_get_target_text_files(target_dir)):
        try:
            content = fpath.read_text(encoding="utf-8")
            count, _ = _apply_portable_regex(content, pattern, replace_term=None)
            if count > 0:
                total_occurrences += count
                matched_files += 1
        except Exception as e:
            logger.error(f"Lỗi search file {fpath.name}: {str(e)}")

    return jsonify({
        "success": True,
        "matched_files": matched_files,
        "total_occurrences": total_occurrences
    })

@projects_bp.route("/api/projects/<slug>/replace-preview", methods=["POST"])
def batch_replace_preview_in_project(slug):
    """Dry-run (chạy thử) thay thế để trả về số liệu đếm trước khi áp dụng thực sự."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    data = request.json or {}
    folder_type = data.get("folder_type", "sources")
    search_term = data.get("search_term", "")
    replace_term = data.get("replace_term", "")
    search_mode = data.get("search_mode", "normal")

    if not search_term:
        return jsonify({"error": "Chưa nhập từ khóa tìm kiếm"}), 400

    target_dir = pdir / ("translated" if folder_type == "translated" else "sources")
    if not target_dir.exists():
        return jsonify({"success": True, "matched_files": 0, "total_occurrences": 0, "scanned_files": 0})

    try:
        pattern = _compile_portable_regex(search_term, search_mode)
    except _re.error as e:
        return jsonify({"error": f"Regex không hợp lệ: {str(e)}"}), 400

    total_occurrences = 0
    matched_files = 0
    scanned_files = 0
    preview_samples = []
    
    for fpath in sorted(_get_target_text_files(target_dir)):
        scanned_files += 1
        try:
            content = fpath.read_text(encoding="utf-8")
            # We want to see how many matches, but we don't write
            count, _ = _apply_portable_regex(content, pattern, replace_term)
            if count > 0:
                total_occurrences += count
                matched_files += 1
                # Could add preview samples here in the future
        except Exception as e:
            logger.error(f"Lỗi preview file {fpath.name}: {str(e)}")

    return jsonify({
        "success": True,
        "matched_files": matched_files,
        "total_occurrences": total_occurrences,
        "scanned_files": scanned_files,
        "search_mode": search_mode
    })


# ============================================================
# Translation Memory APIs
# ============================================================


@projects_bp.route("/api/projects/<slug>/tm/clear", methods=["POST"])
def clear_project_tm(slug):
    """Xóa TM riêng của project (không phải global TM)."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404

    try:
        from services.translation_memory import TranslationMemory
        tm = TranslationMemory(
            tm_dir=str(pdir / "assets" / "translation_memory"),
            enabled=True,
        )
        count = tm.clear()
        return jsonify({"success": True, "deleted": count})
    except Exception as e:
        logger.error(f"Lỗi xóa TM project: {e}")
        return jsonify({"error": str(e)}), 500


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

        from backend.infrastructure.providers.provider_service import ProviderService
        from backend.infrastructure.providers.endpoint_policy import classify_endpoint
        
        provider_service = ProviderService()
        active_provider = provider_service.get_active_provider_config() or {}
        policy = classify_endpoint(active_provider.get("base_url"))
        
        match = translation_memory.find_match(text, provider_kind=policy.provider_kind)
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

        from backend.infrastructure.providers.provider_service import ProviderService
        from backend.infrastructure.providers.endpoint_policy import classify_endpoint
        
        provider_service = ProviderService()
        active_provider = provider_service.get_active_provider_config() or {}
        policy = classify_endpoint(active_provider.get("base_url"))

        translation_memory.add_translation(source, target, context, provider_kind=policy.provider_kind)
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
