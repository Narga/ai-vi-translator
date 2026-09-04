"""Đọc/ghi file an toàn: sanitize tên + relative_to() chống path traversal."""

from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = PROJECT_ROOT / "workspace"


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
        (p / "translated").mkdir(parents=True, exist_ok=True)
        (p / "assets").mkdir(parents=True, exist_ok=True)
        return p

    def get_source_path(self, slug: str, filename: str) -> Path:
        clean_file = self._sanitize_name(filename)
        return self._validate_path(self.get_project_dir(slug) / "sources" / clean_file)

    def get_translated_path(self, slug: str, filename: str) -> Path:
        clean_file = self._sanitize_name(filename)
        return self._validate_path(self.get_project_dir(slug) / "translated" / clean_file)

    def list_sources(self, slug: str) -> List[str]:
        sources_dir = self.get_project_dir(slug) / "sources"
        return sorted([f.name for f in sources_dir.iterdir() if f.is_file()])

    def read_source(self, slug: str, filename: str) -> str:
        file_path = self.get_source_path(slug, filename)
        if not file_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file nguồn: {file_path}")
        return file_path.read_text(encoding="utf-8", errors="replace")

    def save_translated(self, slug: str, filename: str, content: str):
        out_path = self.get_translated_path(slug, filename)
        out_path.write_text(content, encoding="utf-8")
