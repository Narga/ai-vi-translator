# plugins/epub_converter/services/file_operations.py
# split_files / merge_files cho Converter Tool plugin.

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from plugins.translation.chunker import process_text_for_chunking

SUPPORTED_SUFFIXES = {".md", ".txt", ".html", ".htm", ".xhtml", ".json", ".csv"}
VALID_SECTIONS = {"sources", "translated", "spelling"}


def _safe_project_file(project_dir: Path, section: str, filename: str) -> Path | None:
    if section not in VALID_SECTIONS or not isinstance(filename, str) or not filename:
        return None
    base_dir = (project_dir / section).resolve()
    target = (base_dir / filename).resolve()
    if not target.is_relative_to(base_dir):
        return None
    return target if target.is_file() else None


def _write_new_text(path: Path, content: str) -> None:
    """Atomically create a new file without replacing an existing path."""
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.link(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    else:
        os.unlink(tmp_name)


def split_files(
    project_dir: Path,
    section: str,
    filenames: list[str],
    delete_source: bool,
    max_chars: int,
    log: Callable[[str], None],
) -> dict[str, Any]:
    min_chars = max(100, max_chars // 2) if max_chars <= 10000 else max(5000, max_chars // 2)
    output_paths: list[str] = []
    processed_count = 0
    failed_files: list[dict[str, str]] = []
    deleted_files: list[str] = []
    skipped_files: list[dict[str, str]] = []

    for filename in filenames:
        safe_path = _safe_project_file(project_dir, section, filename)
        if safe_path is None:
            failed_files.append({"filename": filename, "reason": "Đường dẫn không hợp lệ"})
            log(f"❌ {filename}: đường dẫn không hợp lệ")
            continue
        if safe_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            skipped_files.append({"filename": filename, "reason": f"Định dạng {safe_path.suffix} không hỗ trợ"})
            log(f"⚠️ {filename}: bỏ qua định dạng {safe_path.suffix}")
            continue
        try:
            text = safe_path.read_text(encoding="utf-8")
        except Exception as e:
            failed_files.append({"filename": filename, "reason": str(e)})
            log(f"❌ {filename}: đọc thất bại: {e}")
            continue

        chunks = process_text_for_chunking(text, min_chars, max_chars)

        if len(chunks) <= 1:
            skipped_files.append({"filename": filename, "reason": "Quá nhỏ, không cần chia"})
            log(f"⚠️ {filename}: quá nhỏ, không cần chia")
            continue

        stem = safe_path.stem
        suffix = safe_path.suffix
        chunk_paths = [safe_path.parent / f"{stem}_chunk_{i:03d}{suffix}" for i in range(1, len(chunks) + 1)]
        existing = next((path for path in chunk_paths if path.exists()), None)
        if existing is not None:
            failed_files.append({"filename": filename, "reason": f"Output đã tồn tại: {existing.name}"})
            log(f"❌ {filename}: output đã tồn tại: {existing.name}")
            continue

        created_paths: list[Path] = []
        had_error = False
        for chunk_path, chunk in zip(chunk_paths, chunks):
            chunk_name = chunk_path.name
            try:
                _write_new_text(chunk_path, chunk)
                created_paths.append(chunk_path)
                rel = str(chunk_path.resolve().relative_to(project_dir.resolve()))
                output_paths.append(rel)
                log(f"✅ {filename} → {rel}")
            except Exception as e:
                failed_files.append({"filename": chunk_name, "reason": str(e)})
                log(f"❌ {chunk_name}: ghi thất bại: {e}")
                had_error = True
                break

        if had_error:
            for created_path in created_paths:
                try:
                    created_path.unlink()
                    output_paths.remove(str(created_path.resolve().relative_to(project_dir.resolve())))
                except OSError:
                    pass

        if not had_error:
            processed_count += 1
            if delete_source:
                try:
                    safe_path.unlink()
                    deleted_files.append(filename)
                    log(f"🗑️ Đã xóa nguồn: {filename}")
                except Exception as e:
                    log(f"⚠️ Không thể xóa nguồn {filename}: {e}")

    has_failures = bool(failed_files)
    has_processed = processed_count > 0

    if has_failures and has_processed:
        status = "partial"
    elif has_failures:
        status = "error"
    else:
        status = "done"

    return {
        "status": status,
        "output_paths": output_paths,
        "processed_count": processed_count,
        "failed_files": failed_files,
        "deleted_files": deleted_files,
        "skipped_files": skipped_files,
    }


def _merge_html_bodies(paths: list[Path], log: Callable[[str], None]) -> str | None:
    """Merge multiple HTML files using BeautifulSoup.

    - File đầu tiên giữ nguyên doctype/html/head/body wrapper.
    - Các file sau: lấy nội dung trong <body> (nếu có), nối vào trước </body> của file đầu.
    - Trả về string nếu thành công, None nếu lỗi.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log("❌ BeautifulSoup không khả dụng, không thể ghép HTML")
        return None

    try:
        base_soup = BeautifulSoup(paths[0].read_text(encoding="utf-8"), "html.parser")
    except Exception as e:
        log(f"❌ Đọc file HTML cơ sở thất bại: {e}")
        return None

    base_body = base_soup.find("body")
    if base_body is None:
        base_body = base_soup.new_tag("body")
        base_soup.append(base_body)

    for sp in paths[1:]:
        try:
            content = sp.read_text(encoding="utf-8")
            soup = BeautifulSoup(content, "html.parser")
            other_body = soup.find("body")
            if other_body is not None:
                for child in list(other_body.children):
                    base_body.append(child.extract())
            else:
                base_body.append(soup)
        except Exception as e:
            log(f"❌ Đọc/ghép {sp.name} thất bại: {e}")
            return None

    return str(base_soup)


def merge_files(
    project_dir: Path,
    section: str,
    filenames: list[str],
    delete_source: bool,
    log: Callable[[str], None],
) -> dict[str, Any]:
    output_paths: list[str] = []
    processed_count = 0
    failed_files: list[dict[str, str]] = []
    deleted_files: list[str] = []
    skipped_files: list[dict[str, str]] = []

    if not filenames:
        return {
            "status": "error",
            "output_paths": [],
            "processed_count": 0,
            "failed_files": [{"filename": "", "reason": "Danh sách file rỗng"}],
            "deleted_files": [],
            "skipped_files": [],
        }

    if not all(isinstance(filename, str) and filename for filename in filenames):
        return {
            "status": "error",
            "output_paths": [],
            "processed_count": 0,
            "failed_files": [{"filename": "", "reason": "Tên file không hợp lệ"}],
            "deleted_files": [],
            "skipped_files": [],
        }

    suffix = Path(filenames[0]).suffix.lower()
    for fn in filenames:
        if Path(fn).suffix.lower() != suffix:
            return {
                "status": "error",
                "output_paths": [],
                "processed_count": 0,
                "failed_files": [{"filename": fn, "reason": f"Mixed suffix: {suffix} và {Path(fn).suffix.lower()}"}],
                "deleted_files": [],
                "skipped_files": [],
            }

    safe_paths: list[Path] = []
    for filename in filenames:
        sp = _safe_project_file(project_dir, section, filename)
        if sp is None:
            failed_files.append({"filename": filename, "reason": "Đường dẫn không hợp lệ"})
            log(f"❌ {filename}: đường dẫn không hợp lệ")
            continue
        if not sp.is_file():
            failed_files.append({"filename": filename, "reason": "Không phải file hoặc không tồn tại"})
            log(f"❌ {filename}: không tồn tại")
            continue
        if sp.suffix.lower() not in SUPPORTED_SUFFIXES:
            skipped_files.append({"filename": filename, "reason": f"Định dạng {sp.suffix} không hỗ trợ"})
            log(f"⚠️ {filename}: bỏ qua định dạng {sp.suffix}")
            continue
        safe_paths.append(sp)

    if not safe_paths:
        status = "error"
        return {
            "status": status,
            "output_paths": [],
            "processed_count": 0,
            "failed_files": failed_files,
            "deleted_files": [],
            "skipped_files": skipped_files,
        }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"merged_{ts}{suffix}"
    out_path = safe_paths[0].parent / base_name
    counter = 1
    while out_path.exists():
        base_name = f"merged_{ts}_{counter:02d}{suffix}"
        out_path = safe_paths[0].parent / base_name
        counter += 1

    html_suffixes = {".html", ".htm", ".xhtml"}

    if suffix in html_suffixes:
        merged_content = _merge_html_bodies(safe_paths, log)
        if merged_content is None:
            failed_files.append({"filename": safe_paths[0].name, "reason": "HTML merge thất bại"})
            return {
                "status": "error",
                "output_paths": [],
                "processed_count": 0,
                "failed_files": failed_files,
                "deleted_files": [],
                "skipped_files": skipped_files,
            }
    else:
        contents: list[str] = []
        for sp in safe_paths:
            try:
                contents.append(sp.read_text(encoding="utf-8").strip())
            except Exception as e:
                failed_files.append({"filename": sp.name, "reason": f"Đọc thất bại: {e}"})
                log(f"❌ {sp.name}: đọc thất bại: {e}")

        if failed_files:
            return {
                "status": "error",
                "output_paths": [],
                "processed_count": 0,
                "failed_files": failed_files,
                "deleted_files": [],
                "skipped_files": skipped_files,
            }

        merged_content = "\n\n".join(content for content in contents if content)

    try:
        _write_new_text(out_path, merged_content)
    except Exception as e:
        failed_files.append({"filename": base_name, "reason": str(e)})
        log(f"❌ Ghi output thất bại: {e}")
        return {
            "status": "error",
            "output_paths": [],
            "processed_count": 0,
            "failed_files": failed_files,
            "deleted_files": [],
            "skipped_files": skipped_files,
        }

    rel_output = str(out_path.resolve().relative_to(project_dir.resolve()))
    output_paths.append(rel_output)
    processed_count = len(safe_paths)
    log(f"✅ Đã ghép {processed_count} file → {rel_output}")

    if delete_source and not failed_files:
        for sp in safe_paths:
            try:
                if sp.resolve() != out_path.resolve():
                    sp.unlink()
                    deleted_files.append(sp.name)
                    log(f"🗑️ Đã xóa nguồn: {sp.name}")
            except Exception as e:
                log(f"⚠️ Không thể xóa nguồn {sp.name}: {e}")

    status = "done" if not failed_files else "partial"
    return {
        "status": status,
        "output_paths": output_paths,
        "processed_count": processed_count,
        "failed_files": failed_files,
        "deleted_files": deleted_files,
        "skipped_files": skipped_files,
    }
