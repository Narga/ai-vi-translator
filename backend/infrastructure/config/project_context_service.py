"""Service đọc và render project context (assets) vào prompt dịch."""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ProjectContextService:
    """Đọc file assets và chèn vào prompt dịch."""

    ASSET_FILES = {
        "translation_guidelines": "style_guide.txt",
        "project_summary": "summary.txt",
    }
    # glossary.txt và relationship.txt được xử lý riêng bởi GlossaryService

    PLACEHOLDER_MAP = {
        "{translation_guidelines}": "translation_guidelines",
        "{project_summary}": "project_summary",
        "{project_context}": "__all__",
    }

    def load_context(self, project_dir: Path) -> Dict[str, str]:
        """Đọc tất cả asset files, trả dict key→content.
        Bỏ qua file rỗng hoặc chỉ có comment template (bắt đầu bằng #).
        """
        assets_dir = project_dir / "assets"
        context = {}
        for key, filename in self.ASSET_FILES.items():
            fp = assets_dir / filename
            if not fp.exists():
                continue
            content = fp.read_text(encoding="utf-8").strip()
            if not content or content.startswith("#"):
                continue
            context[key] = content
        return context

    def render_prompt(self, main_prompt: str, context: Dict[str, str]) -> str:
        """Chèn context vào prompt.

        Quy tắc:
        - Nếu prompt có placeholder → replace placeholder
        - Nếu prompt KHÔNG có placeholder → append context cuối prompt
        - {project_context} → chèn tất cả context gộp lại
        """
        if not context:
            return main_prompt

        has_placeholder = False

        for placeholder, context_key in self.PLACEHOLDER_MAP.items():
            if placeholder in main_prompt:
                has_placeholder = True
                if context_key == "__all__":
                    all_content = self._build_all_context(context)
                    main_prompt = main_prompt.replace(placeholder, all_content)
                else:
                    main_prompt = main_prompt.replace(
                        placeholder, context.get(context_key, "")
                    )

        # Fallback: append nếu không có placeholder
        if not has_placeholder:
            append_block = self._build_all_context(context)
            if append_block:
                main_prompt += "\n\n" + append_block

        return main_prompt

    def _build_all_context(self, context: Dict[str, str]) -> str:
        """Gộp tất cả context thành 1 block text."""
        parts = []
        if "translation_guidelines" in context:
            parts.append(f"# Hướng dẫn phong cách\n{context['translation_guidelines']}")
        if "project_summary" in context:
            parts.append(f"# Tóm tắt dự án\n{context['project_summary']}")
        return "\n\n".join(parts)
