# backend/infrastructure/config/prompt_service.py
# PromptService - Centralized prompt management

"""
PromptService gom logic đọc/ghi prompts từ nhiều nguồn:
- workspace/prompts/default/ (global prompts - fallback cuối)
- workspace/prompts/library/<slug>/ (thư viện bộ prompt mẫu)
- workspace/projects/<slug>/prompt/ (copy tùy chỉnh của dự án)

Architecture:
  default/   ← Gốc hệ thống (fallback cuối, cố định)
  library/   ← Thư viện bộ prompt mẫu (Fantasy, Sci-Fi, ...)
  projects/<slug>/prompt/ ← Copy/tùy chỉnh của dự án (chỉ chứa file đã đổi)
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional

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

    Architecture:
      - default/   = Gốc hệ thống (fallback cuối, cố định)
      - library/   = Thư viện bộ prompt mẫu
      - projects/<slug>/prompt/ = Copy tùy chỉnh của dự án

    Merge logic: default + project override (file trong project ghi đè default).
    """

    def __init__(self, workspace_dir: Optional[Path] = None):
        self._workspace_dir = workspace_dir or Path("workspace")
        self._global_prompts_dir = self._workspace_dir / "prompts" / "default"
        self._library_dir = self._workspace_dir / "prompts"

    # ------------------------------------------------------------------
    # Global prompts (default/)
    # ------------------------------------------------------------------

    def load_global_prompts(self) -> Dict[str, str]:
        """Load tất cả global prompts từ workspace/prompts/default/."""
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
        """Lưu global prompts."""
        self._global_prompts_dir.mkdir(parents=True, exist_ok=True)
        for key, content in prompts.items():
            if key in PROMPT_KEY_FILE_MAP:
                filepath = self._global_prompts_dir / PROMPT_KEY_FILE_MAP[key]
                filepath.write_text(content, encoding="utf-8")
        logger.info(f"Saved {len(prompts)} global prompts")

    def get_global_prompt(self, key: str) -> str:
        """Lấy một global prompt theo key."""
        if key not in PROMPT_KEY_FILE_MAP:
            return ""
        filepath = self._global_prompts_dir / PROMPT_KEY_FILE_MAP[key]
        if filepath.exists():
            return filepath.read_text(encoding="utf-8").strip()
        return ""

    # ------------------------------------------------------------------
    # Library (workspace/prompts/)
    # ------------------------------------------------------------------

    def list_library_sets(self) -> List[dict]:
        """Liệt kê tất cả bộ prompt trong thư viện."""
        self._library_dir.mkdir(parents=True, exist_ok=True)
        sets = []
        for d in sorted(self._library_dir.iterdir()):
            if not d.is_dir():
                continue
            # Bỏ qua folder library cũ nếu còn tồn tại để tránh rác dữ liệu
            if d.name == "library":
                continue
            meta = {}
            mf = d / "meta.json"
            if mf.exists():
                try:
                    meta = json.loads(mf.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    meta = {}
            meta["slug"] = d.name
            if d.name == "default" and "name" not in meta:
                meta["name"] = "Mặc định (Hệ thống)"
                meta["description"] = "Bộ chỉ dẫn gốc của hệ thống"
            for key, filename in PROMPT_KEY_FILE_MAP.items():
                meta[f"has_{key}"] = (d / filename).exists()
            sets.append(meta)
        return sets

    def get_library_set(self, slug: str) -> dict:
        """Lấy nội dung 1 bộ prompt trong thư viện."""
        d = self._library_dir / slug
        if not d.exists():
            raise FileNotFoundError(f"Library set '{slug}' not found")
        meta = {}
        mf = d / "meta.json"
        if mf.exists():
            try:
                meta = json.loads(mf.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                meta = {}
        meta["slug"] = slug
        if slug == "default" and "name" not in meta:
            meta["name"] = "Mặc định (Hệ thống)"
            meta["description"] = "Bộ chỉ dẫn gốc của hệ thống"
        prompts = {}
        for key, filename in PROMPT_KEY_FILE_MAP.items():
            fpath = d / filename
            if fpath.exists():
                prompts[key] = fpath.read_text(encoding="utf-8")
            else:
                prompts[key] = ""
        return {"meta": meta, "prompts": prompts}

    def save_library_set(self, slug: str, name: str, prompts: Dict[str, str],
                         description: str = "") -> None:
        """Tạo hoặc cập nhật bộ prompt trong thư viện."""
        d = self._library_dir / slug
        d.mkdir(parents=True, exist_ok=True)
        meta = {"name": name, "slug": slug, "description": description}
        (d / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for key, content in prompts.items():
            if key in PROMPT_KEY_FILE_MAP:
                (d / PROMPT_KEY_FILE_MAP[key]).write_text(content, encoding="utf-8")
        logger.info(f"Saved library set: {slug}")

    def delete_library_set(self, slug: str) -> None:
        """Xóa bộ prompt trong thư viện (không xóa 'default')."""
        if slug == "default":
            raise ValueError("Cannot delete default library set")
        d = self._library_dir / slug
        if d.exists():
            shutil.rmtree(d)
            logger.info(f"Deleted library set: {slug}")

    # ------------------------------------------------------------------
    # Project prompts (projects/<slug>/prompt/)
    # ------------------------------------------------------------------

    def load_project_prompts(self, project_dir: Path) -> Dict[str, str]:
        """Load prompts tùy chỉnh của project (chỉ file đã đổi)."""
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
        Lưu prompts cho project. File rỗng → unlink (quay về default).
        """
        prompt_dir = project_dir / "prompt"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        for key, content in prompts.items():
            if key not in PROMPT_KEY_FILE_MAP:
                continue
            filepath = prompt_dir / PROMPT_KEY_FILE_MAP[key]
            if content is None or content.strip() == "":
                if filepath.exists():
                    filepath.unlink()
            else:
                filepath.write_text(content, encoding="utf-8")
        logger.info(f"Saved {len(prompts)} project prompts to {project_dir}")


    # ------------------------------------------------------------------
    # Merged prompts (default + project override)
    # ------------------------------------------------------------------

    def load_merged_prompts(self, project_dir: Optional[Path] = None) -> Dict[str, str]:
        """
        Load prompts đã merge: default + project override.
        File trong project/prompt/ ghi đè default tương ứng.
        """
        prompts = self.load_global_prompts()
        if project_dir:
            project_prompts = self.load_project_prompts(project_dir)
            prompts.update(project_prompts)
        return prompts

    def get_project_prompt_status(self, project_dir: Path) -> Dict[str, bool]:
        """Trả về dict {key: is_custom} cho biết prompt nào đã tùy chỉnh."""
        prompt_dir = project_dir / "prompt"
        status = {}
        for key in PROMPT_KEY_FILE_MAP:
            if prompt_dir.exists():
                status[key] = (prompt_dir / PROMPT_KEY_FILE_MAP[key]).exists()
            else:
                status[key] = False
        return status
