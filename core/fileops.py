"""Helper dùng chung cho mọi endpoint file (R2#archi). Ranh giới rõ:
guard_name: validation. unique_name: naming/policy. read/write: I/O.
Quy tắc: không ghi đè im lặng ở luồng tạo/đổi tên; ghi đè chủ động chỉ qua atomic write."""

import os
import tempfile
import unicodedata
from pathlib import Path
from typing import List


def guard_name(name) -> str:
    """strip + NFC + từ chối rỗng/./.. / separator. Không check ext. Raise ValueError."""
    if not isinstance(name, str):
        raise ValueError(f"Tên không hợp lệ: {name!r}")
    clean = unicodedata.normalize("NFC", name.strip())
    if not clean or clean in (".", "..") or "/" in clean or "\\" in clean or ".." in clean:
        raise ValueError(f"Tên không hợp lệ: {name!r}")
    return clean


def unique_name(directory: Path, name: str) -> str:
    """Tên trống đầu tiên: name, name_conflict.ext, name_conflict2.ext...
    Check filesystem MỖI lần thử. Chỉ exists-check (không ghi) — ghi dùng
    write_bytes_no_overwrite để chống race."""
    directory = Path(directory)
    clean = guard_name(name)
    if not (directory / clean).exists():
        return clean
    stem, suffix = Path(clean).stem, Path(clean).suffix
    i = 1
    while True:
        cand = f"{stem}_conflict{suffix}" if i == 1 else f"{stem}_conflict{i}{suffix}"
        if not (directory / cand).exists():
            return cand
        i += 1


def read_text_strict(path) -> str:
    """Đọc UTF-8 strict. File nhị phân -> raise ValueError (không decode-replace-rồi-ghi)."""
    data = Path(path).read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"File không phải UTF-8 text: {Path(path).name}")


def atomic_write_text(target: Path, content: str, encoding: str = "utf-8") -> None:
    """Ghi file kiểu atomic: .tmp cùng thư mục rồi os.replace. Crash giữ file cũ."""
    target = Path(target)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_bytes_no_overwrite(directory: Path, name: str, data: bytes) -> str:
    """Ghi bytes, không bao giờ đè: thử mode "xb", va chạm -> tên tiếp theo.
    Trả tên thực tế đã lưu. Chống race 2 request đồng thời (R2#2)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    base = guard_name(name)
    stem, suffix = Path(base).stem, Path(base).suffix
    cand, i = base, 0
    while True:
        try:
            with open(directory / cand, "xb") as f:
                f.write(data)
            return cand
        except FileExistsError:
            i += 1
            cand = f"{stem}_conflict{suffix}" if i == 1 else f"{stem}_conflict{i}{suffix}"


def list_names(directory: Path, exts: set | None = None) -> List[str]:
    """Tên file sorted trong thư mục (deterministic cho batch). Lọc ext nếu cho."""
    d = Path(directory)
    if not d.is_dir():
        return []
    out = [f.name for f in d.iterdir()
           if f.is_file() and (exts is None or f.suffix.lower() in exts)]
    return sorted(out)


ALLOWED_DOC_EXTS = {".md", ".txt", ".html"}
MAX_DOC_BYTES = 2 * 1024 * 1024  # chống size abuse (đọc capped, vượt → 413)


class DocForbiddenError(ValueError):
    """Path resolve ra ngoài vùng tài liệu được phép → handler map 403."""


def resolve_doc(root: Path, rel: str) -> Path:
    """rel → Path đã resolve, nằm trong root, đúng ext, là file.
    Path xấu/traversal/sai ext → ValueError (400).
    Ngoài whitelist hoặc symlink thoát root → DocForbiddenError (403).
    Không tồn tại/không phải file → FileNotFoundError (404)."""
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel:
        raise ValueError(f"Đường dẫn không hợp lệ: {rel!r}")
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"Đường dẫn không hợp lệ: {rel!r}")
    target = (Path(root) / p).resolve()  # resolve symlink TRƯỚC…
    try:
        target.relative_to(Path(root).resolve())  # …rồi mới check vùng
    except ValueError:
        raise DocForbiddenError(f"Tệp tin không thuộc vùng tài liệu: {rel!r}")
    if target.suffix.lower() not in ALLOWED_DOC_EXTS:
        raise ValueError(f"Định dạng tệp không được hỗ trợ: {target.suffix}")
    if not target.is_file():
        raise FileNotFoundError(f"Tài liệu không tồn tại: {rel!r}")
    return target


def read_doc_limited(target: Path) -> str:
    """Đọc tối đa MAX_DOC_BYTES+1 byte (tránh race stat→read); vượt → ValueError."""
    raw = Path(target).read_bytes()[:MAX_DOC_BYTES + 1]
    if len(raw) > MAX_DOC_BYTES:
        raise ValueError(f"Tài liệu quá lớn (> {MAX_DOC_BYTES} bytes)")
    return raw.decode("utf-8", errors="replace")


def slugify(text: str, fallback: str = "du-an") -> str:
    """Tên sách -> slug thư mục: thường, gạch dưới, giữ chữ Unicode, không đặc biệt."""
    import re
    s = unicodedata.normalize("NFC", (text or "").strip().lower())
    s = re.sub(r"[\s_]+", "_", s)
    s = re.sub(r"[^\w-]", "", s, flags=re.UNICODE).strip("_-")
    return s or fallback


def unique_slug(base_dir: Path, slug: str) -> str:
    """slug trống đầu tiên: slug, slug_2, slug_3... (check thư mục)."""
    base = Path(base_dir)
    if not (base / slug).exists():
        return slug
    i = 2
    while True:
        cand = f"{slug}_{i}"
        if not (base / cand).exists():
            return cand
        i += 1
