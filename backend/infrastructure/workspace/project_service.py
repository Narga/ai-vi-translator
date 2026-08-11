# backend/infrastructure/workspace/project_service.py
# ProjectService - Project CRUD và metadata management

"""
ProjectService quản lý project metadata và CRUD operations.

Phase 06: Tách logic project ra khỏi webui/routes/projects.py.
"""

import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ProjectService:
    """
    Project CRUD và metadata management service.

    Gom logic từ:
    - webui/routes/projects.py:_get_project_dir
    - webui/routes/projects.py:_load_project_meta
    - webui/routes/projects.py:_save_project_meta
    - webui/routes/projects.py:_project_stats
    - webui/helpers.py:ensure_default_project

    Sử dụng:
        from backend.infrastructure.workspace.project_service import ProjectService
        project_service = ProjectService()
        projects = project_service.list_projects()
    """

    def __init__(self, workspace_dir: Optional[Path] = None):
        """
        Khởi tạo ProjectService.

        Args:
            workspace_dir: Đường dẫn đến workspace directory.
                          Mặc định: Path("workspace")
        """
        self._workspace_dir = workspace_dir or Path("workspace")
        self._projects_dir = self._workspace_dir / "projects"

    # ------------------------------------------------------------------
    # Project directory helpers
    # ------------------------------------------------------------------

    def get_project_dir(self, slug: str) -> Path:
        """
        Lấy đường dẫn project directory.

        Args:
            slug: Project slug

        Returns:
            Path to project directory
        """
        return self._projects_dir / slug

    def project_exists(self, slug: str) -> bool:
        """
        Kiểm tra project có tồn tại không.

        Args:
            slug: Project slug

        Returns:
            True nếu project tồn tại
        """
        project_dir = self.get_project_dir(slug)
        return project_dir.exists() and (project_dir / "project.json").exists()

    # ------------------------------------------------------------------
    # Project metadata
    # ------------------------------------------------------------------

    def load_project_meta(self, slug: str) -> Optional[Dict]:
        """
        Đọc project.json.

        Args:
            slug: Project slug

        Returns:
            Dict chứa metadata hoặc None nếu không tồn tại
        """
        meta_file = self.get_project_dir(slug) / "project.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading project meta for {slug}: {e}")
        return None

    def save_project_meta(self, slug: str, meta: Dict) -> None:
        """
        Lưu project.json an toàn bằng atomic write.
        """
        meta_file = self.get_project_dir(slug) / "project.json"
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = meta_file.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        os.replace(str(tmp_path), str(meta_file))

    def update_project_meta(self, slug: str, updates: Dict) -> Optional[Dict]:
        """
        Cập nhật project metadata.

        Args:
            slug: Project slug
            updates: Dict chứa các field cần cập nhật

        Returns:
            Updated metadata hoặc None nếu project không tồn tại
        """
        meta = self.load_project_meta(slug)
        if meta is None:
            return None

        for key in ["name", "description", "status"]:
            if key in updates:
                meta[key] = updates[key]

        meta["updated_at"] = datetime.now().isoformat()
        self.save_project_meta(slug, meta)
        return meta

    def update_project_task_meta(self, slug: str, filename: str, task_meta: Dict) -> Optional[Dict]:
        """
        Cập nhật translation task metadata trong project.json.

        Args:
            slug: Project slug
            filename: Tên file đang dịch
            task_meta: Dict chứa metadata cần cập nhật

        Returns:
            Updated metadata hoặc None nếu project không tồn tại
        """
        meta = self.load_project_meta(slug)
        if meta is None:
            return None

        tasks = meta.get("translation_tasks", {})
        tasks[filename] = {**tasks.get(filename, {}), **task_meta, "updated_at": datetime.now().isoformat()}
        meta["translation_tasks"] = tasks
        self.save_project_meta(slug, meta)
        return meta

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    def list_projects(self) -> List[Dict]:
        """
        Liệt kê tất cả projects.

        Returns:
            List of project metadata dicts
        """
        self._projects_dir.mkdir(parents=True, exist_ok=True)
        projects = []

        for d in sorted(self._projects_dir.iterdir()):
            if not d.is_dir():
                continue
            meta = self.load_project_meta(d.name)
            if not meta:
                continue
            stats = self.get_project_stats(d.name)
            projects.append({**meta, "slug": d.name, **stats})

        return projects

    def create_project(
        self,
        name: str,
        description: str = "",
    ) -> Dict:
        """
        Tạo project mới.

        Args:
            name: Tên project
            description: Mô tả

        Returns:
            Dict chứa slug và metadata

        Raises:
            ValueError: Nếu tên trống hoặc slug đã tồn tại
        """
        if not name.strip():
            raise ValueError("Tên dự án không được trống")

        # Tạo slug từ name
        slug = re.sub(r"[^\w\-]", "-", name.lower()).strip("-")
        slug = re.sub(r"-+", "-", slug)
        if not slug:
            slug = "project"

        # Đảm bảo projects root tồn tại
        self._projects_dir.mkdir(parents=True, exist_ok=True)

        pdir = self.get_project_dir(slug)
        if pdir.exists():
            raise ValueError(f"Dự án '{slug}' đã tồn tại")

        # Tạo thư mục structure
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        ws_service = WorkspaceService(self._workspace_dir)
        ws_service.ensure_workspace_structure()
        ws_service.ensure_project_structure(pdir)

        # Copy default prompts
        prompts_root = self._workspace_dir / "prompts" / "default"
        for fname in ["main_prompt.txt"]:
            src = prompts_root / fname
            if src.exists():
                shutil.copy2(src, pdir / "prompt" / fname)

        # Tạo metadata
        meta = {
            "name": name,
            "slug": slug,
            "description": description,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.save_project_meta(slug, meta)

        # Tạo asset files mặc định
        for fname, content in [
            ("glossary.txt", "# Bảng thuật ngữ\n# Format: thuật ngữ gốc | thuật ngữ dịch | ghi chú\n"),
            ("relationship.txt", "# Bảng nhân vật & quan hệ\n# Format: tên gốc | tên dịch | vai trò | quan hệ\n"),
            ("style_guide.txt", "# Hướng dẫn phong cách dịch\n# Mô tả tone, style, và các quy tắc dịch\n"),
            ("summary.txt", "# Tóm tắt cốt truyện\n# Ghi chú diễn biến chính\n"),
        ]:
            fp = pdir / "assets" / fname
            if not fp.exists():
                fp.write_text(content, encoding="utf-8")

        logger.info(f"Created project: {slug}")
        return {"success": True, "slug": slug, "meta": meta}

    def delete_project(self, slug: str) -> bool:
        """
        Xóa project.

        Args:
            slug: Project slug

        Returns:
            True nếu thành công

        Raises:
            ValueError: Nếu project không tồn tại
        """
        pdir = self.get_project_dir(slug)
        if not pdir.exists():
            raise ValueError(f"Dự án '{slug}' không tồn tại")

        shutil.rmtree(pdir)
        logger.info(f"Deleted project: {slug}")
        return True

    # ------------------------------------------------------------------
    # Project stats
    # ------------------------------------------------------------------

    def get_project_stats(self, slug: str) -> Dict:
        """
        Tính stats cho project.

        Args:
            slug: Project slug

        Returns:
            Dict chứa source_count, translated_count, source_words, translated_words
        """
        pdir = self.get_project_dir(slug)

        def get_files(folder: str) -> List[Path]:
            d = pdir / folder
            if d.exists():
                return [f for f in d.rglob("*") if f.is_file() and not f.name.startswith(".")]
            return []

        sources = get_files("sources")
        translated = get_files("translated")

        def count_words(files: List[Path]) -> int:
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

    # ------------------------------------------------------------------
    # File status
    # ------------------------------------------------------------------

    VALID_FILE_STATUSES = {"Chờ", "Xong"}

    def update_file_status(self, slug: str, filename: str, status: str) -> Dict:
        """
        Cập nhật trạng thái file.

        Args:
            slug: Project slug
            filename: Tên file
            status: Trạng thái ("Chờ" hoặc "Xong")

        Returns:
            Updated file_status dict

        Raises:
            ValueError: Nếu status không hợp lệ
        """
        if status not in self.VALID_FILE_STATUSES:
            raise ValueError(
                f"Trạng thái không hợp lệ. Chỉ chấp nhận: {', '.join(self.VALID_FILE_STATUSES)}"
            )

        meta = self.load_project_meta(slug)
        if meta is None:
            raise ValueError(f"Dự án '{slug}' không tồn tại")

        if "file_status" not in meta:
            meta["file_status"] = {}

        meta["file_status"][filename] = status
        meta["updated_at"] = datetime.now().isoformat()
        self.save_project_meta(slug, meta)

        return meta["file_status"]

    # ------------------------------------------------------------------
    # Default project
    # ------------------------------------------------------------------

    def ensure_default_project(self) -> None:
        """
        Đảm bảo dự án mặc định 'Dịch nhanh' tồn tại.
        """
        slug = "default-project"
        if self.project_exists(slug):
            return

        # Tạo trực tiếp với slug cố định
        pdir = self.get_project_dir(slug)
        self._projects_dir.mkdir(parents=True, exist_ok=True)

        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        ws_service = WorkspaceService(self._workspace_dir)
        ws_service.ensure_workspace_structure()
        ws_service.ensure_project_structure(pdir)

        meta = {
            "name": "Dịch nhanh",
            "slug": slug,
            "description": "Dự án mặc định cho các tác vụ dịch lẻ",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.save_project_meta(slug, meta)

        # Tạo asset files mặc định
        for fname, content in [
            ("glossary.txt", "# Bảng thuật ngữ\n# Format: thuật ngữ gốc | thuật ngữ dịch | ghi chú\n"),
            ("relationship.txt", "# Bảng nhân vật & quan hệ\n# Format: tên gốc | tên dịch | vai trò | quan hệ\n"),
            ("style_guide.txt", "# Hướng dẫn phong cách dịch\n# Mô tả tone, style, và các quy tắc dịch\n"),
            ("summary.txt", "# Tóm tắt cốt truyện\n# Ghi chú diễn biến chính\n"),
        ]:
            fp = pdir / "assets" / fname
            if not fp.exists():
                fp.write_text(content, encoding="utf-8")

        logger.info("Default project ensured")
