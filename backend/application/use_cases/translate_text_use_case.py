# backend/application/use_cases/translate_text_use_case.py
# TranslateTextUseCase - Use case bọc TranslationExecutor

"""
TranslateTextUseCase là lớp use case dịch thuật dùng chung.
Bọc TranslationExecutor và chuẩn hóa config assembly.

Phase 08: Tạo translation use case shell.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.application.dto.translation_request import TranslationRequest
from backend.application.dto.translation_result import TranslationResult

logger = logging.getLogger(__name__)


class TranslateTextUseCase:
    """
    Use case dịch thuật text.

    Bọc TranslationExecutor hiện có và cung cấp interface chuẩn.
    Config assembly (prompts, glossary, API keys) được xử lý ở đây,
    không để caller tự ráp.

    Sử dụng:
        from backend.application.use_cases.translate_text_use_case import TranslateTextUseCase
        use_case = TranslateTextUseCase(api_keys=[...], config_service=..., prompt_service=...)
        result = use_case.execute(request)
    """

    def __init__(
        self,
        api_keys: List[str],
        config: Dict[str, Any],
        glossary_paths: Optional[List[Path]] = None,
    ):
        """
        Khởi tạo use case.

        Args:
            api_keys: Danh sách API keys
            config: Config dict cho TranslationExecutor
            glossary_paths: Danh sách đường dẫn glossary files
        """
        self._api_keys = api_keys
        self._config = config
        self._glossary_paths = glossary_paths

    def execute(
        self,
        request: TranslationRequest,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> TranslationResult:
        """
        Thực hiện dịch thuật.

        Args:
            request: TranslationRequest DTO
            progress_callback: Callback cho progress updates (override request's callback)

        Returns:
            TranslationResult DTO
        """
        from core.executor import TranslationExecutor

        callback = progress_callback or request.progress_callback

        # Merge config từ request
        config = request.to_config()
        if self._config:
            config.update(self._config)

        # Resolve glossary paths
        glossary_paths = request.glossary_paths or self._glossary_paths

        try:
            executor = TranslationExecutor(
                api_keys=self._api_keys,
                config=config,
                glossary_paths=glossary_paths,
            )

            translated_text = executor.translate_text(
                text=request.text,
                output_filename=request.output_filename,
                output_file_path=request.output_file_path,
                progress_callback=callback,
                translation_memory=request.translation_memory,
            )

            if translated_text:
                output_path = str(request.output_file_path) if request.output_file_path else None
                return TranslationResult(
                    translated_text=translated_text,
                    output_path=output_path,
                    source_length=len(request.text),
                    translated_length=len(translated_text),
                    success=True,
                )
            else:
                return TranslationResult(
                    success=False,
                    error_message="Translation returned None",
                )

        except Exception as e:
            logger.error(f"Translation error: {e}", exc_info=True)
            return TranslationResult(
                success=False,
                error_message=str(e),
            )

    @classmethod
    def from_services(
        cls,
        api_keys: List[str],
        config_service=None,
        prompt_service=None,
        project_dir: Optional[Path] = None,
        glossary_paths: Optional[List[Path]] = None,
    ) -> "TranslateTextUseCase":
        """
        Factory method tạo use case từ backend services.

        Args:
            api_keys: Danh sách API keys
            config_service: AppConfigService instance
            prompt_service: PromptService instance
            project_dir: Project directory (nếu có)
            glossary_paths: Glossary paths (nếu có)

        Returns:
            TranslateTextUseCase instance
        """
        config = {}

        if config_service:
            config["model_name"] = config_service.get_default_model()
            config["qa_model"] = config_service.get_qa_model()
            config["temperature"] = config_service.get_temperature()
            config["chunk_size"] = config_service.get_default_chunk_size()
            config["context_char_count"] = config_service.get_context_char_count()

        if prompt_service:
            config["prompts"] = prompt_service.load_merged_prompts(project_dir)
        else:
            config["prompts"] = {}

        return cls(
            api_keys=api_keys,
            config=config,
            glossary_paths=glossary_paths,
        )
