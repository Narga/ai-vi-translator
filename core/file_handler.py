"""Đọc/ghi file an toàn: sanitize tên + relative_to() chống path traversal."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = PROJECT_ROOT / "workspace"


def atomic_write_text(target: Path, content: str, encoding: str = "utf-8") -> None:
    """Ghi file kiểu atomic: .tmp cùng thư mục rồi os.replace. Crash giữa chừng
    không bao giờ để lại file đích dở dang (giữ nguyên nội dung cũ)."""
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


class SafeFileHandler:
    def __init__(self, workspace_dir: Path = DEFAULT_WORKSPACE):
        self.base_dir = Path(workspace_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_name(self, name: str) -> str:
        if not name or not name.strip():
            raise ValueError("Tên không được để trống!")
        clean = name.strip()
        if ".." in clean or "/" in clean or "\\" in clean:
            raise ValueError(f"Tên chứa ký tự không hợp lệ (path traversal): {name}")
        return clean

    def _validate_path(self, target_path: Path) -> Path:
        resolved = target_path.resolve()
        try:
            resolved.relative_to(self.base_dir)
        except ValueError:
            raise ValueError(f"Đường dẫn không an toàn, nằm ngoài workspace: {target_path}")
        return resolved

    def get_project_dir(self, slug: str) -> Path:
        clean_slug = self._sanitize_name(slug)
        p = self._validate_path(self.base_dir / "projects" / clean_slug)
        (p / "sources").mkdir(parents=True, exist_ok=True)
        (p / "results").mkdir(parents=True, exist_ok=True)
        (p / "assets").mkdir(parents=True, exist_ok=True)
        self._migrate_translated(p)  # legacy translated/ -> results/
        return p

    @staticmethod
    def _migrate_translated(proj_dir: Path) -> None:
        """Chuyển file từ translated/ cũ sang results/ (không đè file đã có)."""
        old = proj_dir / "translated"
        new = proj_dir / "results"
        if not old.is_dir():
            return
        for f in old.iterdir():
            if f.is_file() and not (new / f.name).exists():
                f.rename(new / f.name)
        try:
            old.rmdir()  # chỉ xóa khi đã rỗng
        except OSError:
            pass

    def get_source_path(self, slug: str, filename: str) -> Path:
        clean_file = self._sanitize_name(filename)
        return self._validate_path(self.get_project_dir(slug) / "sources" / clean_file)

    def get_output_path(self, slug: str, filename: str) -> Path:
        clean_file = self._sanitize_name(filename)
        return self._validate_path(self.get_project_dir(slug) / "results" / clean_file)

    def list_sources(self, slug: str) -> List[str]:
        sources_dir = self.get_project_dir(slug) / "sources"
        return sorted([f.name for f in sources_dir.iterdir() if f.is_file()])

    def read_source(self, slug: str, filename: str) -> str:
        file_path = self.get_source_path(slug, filename)
        if not file_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file nguồn: {file_path}")
        return file_path.read_text(encoding="utf-8", errors="replace")

    def save_output(self, slug: str, filename: str, content: str):
        out_path = self.get_output_path(slug, filename)
        atomic_write_text(out_path, content)

    def delete_file(self, slug: str, filename: str) -> None:
        """Xóa file khỏi cả sources/ và results/ (tồn tại bên nào xóa bên đó)."""
        clean = self._sanitize_name(filename)
        found = False
        for sub in ("sources", "results"):
            p = self._validate_path(self.get_project_dir(slug) / sub / clean)
            if p.is_file():
                p.unlink()
                found = True
        if not found:
            raise FileNotFoundError(f"Không tìm thấy file: {filename}")

    def rename_file(self, slug: str, old: str, new: str) -> str:
        """Đổi tên ở cả sources/ và results/ (bên nào có thì đổi). Trùng tên → lỗi."""
        clean_old, clean_new = self._sanitize_name(old), self._sanitize_name(new)
        moved = False
        for sub in ("sources", "results"):
            src = self._validate_path(self.get_project_dir(slug) / sub / clean_old)
            if src.is_file():
                dst = self._validate_path(self.get_project_dir(slug) / sub / clean_new)
                if dst.exists():
                    raise ValueError(f"Đã tồn tại file: {new}")
                src.rename(dst)
                moved = True
        if not moved:
            raise FileNotFoundError(f"Không tìm thấy file: {old}")
        return clean_new

    def delete_project(self, slug: str) -> None:
        clean = self._sanitize_name(slug)
        d = self._validate_path(self.base_dir / "projects" / clean)
        if not d.is_dir():
            raise FileNotFoundError(f"Không tìm thấy dự án: {slug}")
        shutil.rmtree(d)
