# backend/infrastructure/config/prompt_service.py
# PromptService - Centralized prompt management

"""
PromptService gom logic đọc/ghi prompts từ nhiều nguồn:
- workspace/prompts/default/ (global prompts)
- workspace/projects/<slug>/prompt/ (project prompts)

Phase 05: Tách logic prompts ra khỏi main.py và webui/helpers.py.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Danh sách prompt keys và filename tương ứng
PROMPT_KEY_FILE_MAP = {
    "main": "main_prompt.txt",
    "summary": "summary_prompt.txt",
    "relationships": "relationship_prompt.txt",
    "glossary": "glossary_prompt.txt",
    "chinh_ta": "chinh_ta_prompt.txt",
}


class PromptService:
    """
    Centralized prompt management service.

    Gom logic từ:
    - main.py:load_prompts
    - webui/helpers.py:load_prompts
    - webui/helpers.py:save_prompts
    - webui/routes/projects.py (project prompt CRUD)

    Sử dụng:
        from backend.infrastructure.config.prompt_service import PromptService
        prompt_service = PromptService()
        prompts = prompt_service.load_global_prompts()
    """

    def __init__(self, workspace_dir: Optional[Path] = None):
        """
        Khởi tạo PromptService.

        Args:
            workspace_dir: Đường dẫn đến workspace directory.
                          Mặc định: Path("workspace")
        """
        self._workspace_dir = workspace_dir or Path("workspace")
        self._global_prompts_dir = self._workspace_dir / "prompts" / "default"

    # ------------------------------------------------------------------
    # Global prompts
    # ------------------------------------------------------------------

    def load_global_prompts(self) -> Dict[str, str]:
        """
        Load tất cả global prompts từ workspace/prompts/default/.

        Returns:
            Dict mapping prompt key -> prompt content
        """
        self._global_prompts_dir.mkdir(parents=True, exist_ok=True)

        prompts = {}
        for key, filename in PROMPT_KEY_FILE_MAP.items():
            filepath = self._global_prompts_dir / filename
            if filepath.exists():
                prompts[key] = filepath.read_text(encoding="utf-8").strip()
            else:
                prompts[key] = ""

        return prompts

    def save_global_prompts(self, prompts: Dict[str, str]) -> None:
        """
        Lưu global prompts.

        Args:
            prompts: Dict mapping prompt key -> prompt content
        """
        self._global_prompts_dir.mkdir(parents=True, exist_ok=True)

        for key, content in prompts.items():
            if key in PROMPT_KEY_FILE_MAP:
                filename = PROMPT_KEY_FILE_MAP[key]
                filepath = self._global_prompts_dir / filename
                filepath.write_text(content, encoding="utf-8")

        logger.info(f"Saved {len(prompts)} global prompts")

    def get_global_prompt(self, key: str) -> str:
        """
        Lấy một global prompt theo key.

        Args:
            key: Prompt key (e.g., "main", "summary")

        Returns:
            Prompt content hoặc empty string
        """
        if key not in PROMPT_KEY_FILE_MAP:
            return ""

        filepath = self._global_prompts_dir / PROMPT_KEY_FILE_MAP[key]
        if filepath.exists():
            return filepath.read_text(encoding="utf-8").strip()
        return ""

    # ------------------------------------------------------------------
    # Project prompts
    # ------------------------------------------------------------------

    def load_project_prompts(self, project_dir: Path) -> Dict[str, str]:
        """
        Load prompts của project.

        Args:
            project_dir: Đường dẫn đến project directory

        Returns:
            Dict mapping prompt key -> prompt content
        """
        prompt_dir = project_dir / "prompt"

        prompts = {}
        if prompt_dir.exists():
            for key, filename in PROMPT_KEY_FILE_MAP.items():
                filepath = prompt_dir / filename
                if filepath.exists():
                    content = filepath.read_text(encoding="utf-8").strip()
                    if content:
                        prompts[key] = content

        return prompts

    def save_project_prompts(self, project_dir: Path, prompts: Dict[str, str]) -> None:
        """
        Lưu prompts cho project.

        Args:
            project_dir: Đường dẫn đến project directory
            prompts: Dict mapping prompt key -> prompt content
        """
        prompt_dir = project_dir / "prompt"
        prompt_dir.mkdir(parents=True, exist_ok=True)

        for key, content in prompts.items():
            if key in PROMPT_KEY_FILE_MAP:
                filename = PROMPT_KEY_FILE_MAP[key]
                filepath = prompt_dir / filename
                filepath.write_text(content, encoding="utf-8")

        logger.info(f"Saved {len(prompts)} project prompts to {project_dir}")

    def reset_project_prompts(self, project_dir: Path) -> None:
        """
        Xóa tất cả prompt tùy chỉnh của project.

        Args:
            project_dir: Đường dẫn đến project directory
        """
        import shutil

        prompt_dir = project_dir / "prompt"
        if prompt_dir.exists():
            shutil.rmtree(prompt_dir)
            logger.info(f"Reset project prompts for {project_dir}")

    def import_prompts_to_project(
        self, project_dir: Path, genre_slug: str = "default"
    ) -> int:
        """
        Import prompts từ thư viện vào project.

        Args:
            project_dir: Đường dẫn đến project directory
            genre_slug: Slug của bộ prompt nguồn

        Returns:
            Số file đã import
        """
        import shutil

        src_dir = self._workspace_dir / "prompts" / genre_slug
        if not src_dir.exists():
            src_dir = self._global_prompts_dir

        if not src_dir.exists():
            # Fallback: load từ global prompts
            global_prompts = self.load_global_prompts()
            dest_dir = project_dir / "prompt"
            dest_dir.mkdir(parents=True, exist_ok=True)
            count = 0
            for key, content in global_prompts.items():
                if content and key in PROMPT_KEY_FILE_MAP:
                    filename = PROMPT_KEY_FILE_MAP[key]
                    (dest_dir / filename).write_text(content, encoding="utf-8")
                    count += 1
            return count

        dest_dir = project_dir / "prompt"
        dest_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for f in src_dir.glob("*.txt"):
            shutil.copy2(f, dest_dir / f.name)
            count += 1

        return count

    # ------------------------------------------------------------------
    # Merged prompts (global + project override)
    # ------------------------------------------------------------------

    def load_merged_prompts(self, project_dir: Optional[Path] = None) -> Dict[str, str]:
        """
        Load prompts đã merge: global + project override.

        Args:
            project_dir: Đường dẫn đến project directory (optional)

        Returns:
            Dict mapping prompt key -> merged prompt content
        """
        # Load global trước
        prompts = self.load_global_prompts()

        # Override với project prompts nếu có
        if project_dir:
            project_prompts = self.load_project_prompts(project_dir)
            prompts.update(project_prompts)

        return prompts
