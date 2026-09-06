"""Đọc/ghi file an toàn: sanitize tên + relative_to() chống path traversal."""

import shutil
import zipfile
from pathlib import Path

from core.fileops import atomic_write_text, guard_name  # helper dùng chung (R2#archi)

_TESTZIP_LIMIT = 100 * 1024 * 1024  # 100MB: dưới thì testzip, trên chỉ check size

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = PROJECT_ROOT / "workspace"


class SafeFileHandler:
    def __init__(self, workspace_dir: Path = DEFAULT_WORKSPACE):
        self.base_dir = Path(workspace_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_name(self, name: str) -> str:
        return guard_name(name)  # NFC + từ chối rỗng/./.. /separator, dùng chung mọi endpoint

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

    def get_side_dir(self, slug: str, side: str) -> Path:
        """Thư mục sources|results của project (validate cả slug lẫn side)."""
        if side not in ("sources", "results"):
            raise ValueError(f"side phải là sources|results, nhận được: {side!r}")
        return self._validate_path(self.get_project_dir(slug) / side)

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

    def rename_paired(self, slug: str, old: str, new: str):
        """Đổi tên ở MỌI bên chứa old (sources/results giữ cặp cùng tên).
        Va chạm -> _conflict từng bên (không ghi đè, không báo lỗi).
        Trả [(side, newname)]. Không thấy old ở đâu -> FileNotFoundError."""
        from core.fileops import unique_name
        clean_old = self._sanitize_name(old)
        clean_new = self._sanitize_name(new)
        out = []
        for sub, getter in (("sources", self.get_source_path),
                            ("results", self.get_output_path)):
            src = getter(slug, clean_old)
            if not src.is_file():
                continue
            dest_name = clean_new if not (src.parent / clean_new).exists() \
                else unique_name(src.parent, clean_new)
            src.rename(src.parent / dest_name)
            out.append((sub, dest_name))
        if not out:
            raise FileNotFoundError(f"Không tìm thấy file: {old}")
        return out

    def delete_project(self, slug: str) -> None:
        clean = self._sanitize_name(slug)
        d = self._validate_path(self.base_dir / "projects" / clean)
        if not d.is_dir():
            raise FileNotFoundError(f"Không tìm thấy dự án: {slug}")
        shutil.rmtree(d)

    def archive_project(self, slug: str, archive_dir: Path | None = None) -> Path:
        """Nén project thành zip trong archive/ rồi xóa thư mục gốc."""
        clean = self._sanitize_name(slug)
        d = self._validate_path(self.base_dir / "projects" / clean)
        if not d.is_dir():
            raise FileNotFoundError(f"Không tìm thấy dự án: {slug}")
        out_dir = Path(archive_dir) if archive_dir else self.base_dir / "archive"
        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = Path(shutil.make_archive(str(out_dir / clean), "zip",
                                            root_dir=str(d.parent), base_dir=clean))
        if not zip_path.is_file() or zip_path.stat().st_size == 0:
            raise OSError(f"Archive lỗi/không tạo được: {zip_path}")
        if zip_path.stat().st_size <= _TESTZIP_LIMIT:
            bad = zipfile.ZipFile(zip_path).testzip()
            if bad is not None:
                raise OSError(f"Archive hỏng tại entry: {bad}")
        shutil.rmtree(d)
        return zip_path
