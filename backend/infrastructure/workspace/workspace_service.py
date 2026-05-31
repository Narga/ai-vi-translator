# backend/infrastructure/workspace/workspace_service.py
# WorkspaceService - Workspace directory management

"""
WorkspaceService quản lý cấu trúc thư mục workspace.

Phase 06: Tách logic workspace ra khỏi webui/helpers.py.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WorkspaceService:
    """
    Workspace directory management service.

    Gom logic từ:
    - webui/helpers.py:ensure_default_project (phần workspace dirs)
    - Các hardcoded paths trong routes

    Sử dụng:
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        ws_service = WorkspaceService()
        ws_service.ensure_workspace_structure()
    """

    def __init__(self, workspace_dir: Optional[Path] = None):
        """
        Khởi tạo WorkspaceService.

        Args:
            workspace_dir: Đường dẫn đến workspace directory.
                          Mặc định: Path("workspace")
        """
        self._workspace_dir = workspace_dir or Path("workspace")

    # ------------------------------------------------------------------
    # Directory accessors
    # ------------------------------------------------------------------

    def get_workspace_root(self) -> Path:
        """Lấy workspace root path."""
        return self._workspace_dir

    def get_projects_root(self) -> Path:
        """Lấy projects root path."""
        return self._workspace_dir / "projects"

    def get_logs_dir(self) -> Path:
        """Lấy logs directory path."""
        return self._workspace_dir / "logs"

    def get_cache_dir(self) -> Path:
        """Lấy cache directory path."""
        return self._workspace_dir / "cache"

    def get_checkpoints_dir(self) -> Path:
        """Lấy checkpoints directory path."""
        return self._workspace_dir / "checkpoints"

    def get_prompts_dir(self) -> Path:
        """Lấy prompts directory path."""
        return self._workspace_dir / "prompts"

    def get_archive_dir(self) -> Path:
        """Lấy archive directory path."""
        return self._workspace_dir / "archive"

    def get_default_prompts_dir(self) -> Path:
        """Lấy default prompts directory path."""
        return self._workspace_dir / "prompts" / "default"

    # ------------------------------------------------------------------
    # Directory creation
    # ------------------------------------------------------------------

    def ensure_workspace_structure(self) -> None:
        """
        Đảm bảo cấu trúc workspace cơ bản tồn tại.

        Tạo các thư mục cần thiết nếu chưa có.
        """
        dirs = [
            self.get_projects_root(),
            self.get_logs_dir(),
            self.get_cache_dir(),
            self.get_checkpoints_dir(),
            self.get_prompts_dir(),
            self.get_archive_dir(),
            self.get_default_prompts_dir(),
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        logger.info("Workspace structure ensured")

    def ensure_project_structure(self, project_dir: Path) -> None:
        """
        Đảm bảo cấu trúc thư mục project tồn tại.

        Args:
            project_dir: Đường dẫn đến project directory
        """
        subdirs = [
            "sources",
            "translated",
            "prompt",
            "assets",
            "output",
        ]

        for sub in subdirs:
            (project_dir / sub).mkdir(parents=True, exist_ok=True)

        # Đảm bảo translation_memory dir
        (project_dir / "assets" / "translation_memory").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Path validation
    # ------------------------------------------------------------------

    def is_valid_project_slug(self, slug: str) -> bool:
        """
        Kiểm tra project slug có hợp lệ không.

        Args:
            slug: Project slug

        Returns:
            True nếu hợp lệ
        """
        if not slug:
            return False
        if ".." in slug or "/" in slug or "\\" in slug:
            return False
        return True

    def get_project_dir(self, slug: str) -> Path:
        """
        Lấy đường dẫn project directory.

        Args:
            slug: Project slug

        Returns:
            Path to project directory
        """
        return self.get_projects_root() / slug

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
