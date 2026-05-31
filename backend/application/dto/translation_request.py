# backend/application/dto/translation_request.py
# TranslationRequest - Input DTO cho translation use case

"""
TranslationRequest là input DTO chuẩn cho translation use case.
Gom tất cả parameters cần thiết thành một object.

Phase 08: Tạo translation use case shell.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class TranslationRequest:
    """
    Input DTO cho translation use case.

    Attributes:
        text: Nội dung cần dịch
        output_filename: Tên file output (không có extension)
        output_file_path: Đường dẫn file output đầy đủ
        project_slug: Slug của project (optional)
        model_name: Tên model AI
        qa_model: Tên QA model
        temperature: Temperature cho model
        chunk_size: Kích thước chunk tối đa
        use_cache: Có sử dụng cache không
        prompts: Dict chứa prompts
        context_char_count: Số ký tự context cho chunk tiếp theo
        glossary_paths: Danh sách đường dẫn glossary files
        progress_callback: Callback function cho progress updates
        translation_memory: TranslationMemory instance (optional)
    """

    text: str
    output_filename: str = "translated"
    output_file_path: Optional[Path] = None
    project_slug: Optional[str] = None
    model_name: str = "gemini-3-flash-preview"
    qa_model: str = "gemini-3-flash-preview"
    temperature: float = 1.0
    chunk_size: int = 22000
    use_cache: bool = True
    prompts: Dict[str, str] = field(default_factory=dict)
    context_char_count: int = 500
    glossary_paths: Optional[List[Path]] = None
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    translation_memory: Optional[Any] = None

    def to_config(self) -> Dict[str, Any]:
        """
        Convert sang config dict format mà TranslationExecutor hiểu.

        Returns:
            Config dict
        """
        return {
            "model_name": self.model_name,
            "qa_model": self.qa_model,
            "temperature": self.temperature,
            "chunk_size": self.chunk_size,
            "use_cache": self.use_cache,
            "prompts": self.prompts,
            "context_char_count": self.context_char_count,
            "max_refinement_attempts": 2,
            "min_length_ratio": 0.5,
            "max_length_ratio": 5.0,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranslationRequest":
        """
        Tạo TranslationRequest từ dict (backward compatible).

        Args:
            data: Dict chứa request data

        Returns:
            TranslationRequest instance
        """
        return cls(
            text=data.get("text", ""),
            output_filename=data.get("output_filename", data.get("filename", "translated")),
            output_file_path=data.get("output_file_path"),
            project_slug=data.get("project_slug"),
            model_name=data.get("model_name", data.get("model", "gemini-3-flash-preview")),
            qa_model=data.get("qa_model", data.get("model", "gemini-3-flash-preview")),
            temperature=float(data.get("temperature", 1.0)),
            chunk_size=int(data.get("chunk_size", 22000)),
            use_cache=data.get("use_cache", True),
            prompts=data.get("prompts", {}),
            context_char_count=int(data.get("context_char_count", 500)),
            glossary_paths=data.get("glossary_paths"),
            progress_callback=data.get("progress_callback"),
            translation_memory=data.get("translation_memory"),
        )
