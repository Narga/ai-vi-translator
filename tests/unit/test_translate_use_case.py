# tests/unit/test_translate_use_case.py
# Unit tests cho Phase 08: Translation Use Case

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestTranslationRequest:
    """Test TranslationRequest DTO."""

    def test_import(self):
        """Test import TranslationRequest."""
        from backend.application.dto.translation_request import TranslationRequest
        assert TranslationRequest is not None

    def test_create_minimal(self):
        """Test tạo TranslationRequest với minimal fields."""
        from backend.application.dto.translation_request import TranslationRequest
        req = TranslationRequest(text="hello")
        assert req.text == "hello"
        assert req.output_filename == "translated"
        assert req.model_name == ""

    def test_to_config(self):
        """Test to_config trả về dict đúng format."""
        from backend.application.dto.translation_request import TranslationRequest
        req = TranslationRequest(
            text="test",
            model_name="gemini-3-flash",
            temperature=1.0,
            chunk_size=22000,
        )
        config = req.to_config()
        assert config["model_name"] == "gemini-3-flash"
        assert config["temperature"] == 1.0
        assert config["chunk_size"] == 22000
        assert "prompts" in config

    def test_from_dict(self):
        """Test from_dict tạo TranslationRequest đúng."""
        from backend.application.dto.translation_request import TranslationRequest
        d = {
            "text": "test",
            "model": "gemini-3-flash",
            "temperature": 0.5,
        }
        req = TranslationRequest.from_dict(d)
        assert req.text == "test"
        assert req.model_name == "gemini-3-flash"
        assert req.temperature == 0.5


class TestTranslationResult:
    """Test TranslationResult DTO."""

    def test_import(self):
        """Test import TranslationResult."""
        from backend.application.dto.translation_result import TranslationResult
        assert TranslationResult is not None

    def test_create_default(self):
        """Test tạo TranslationResult với default values."""
        from backend.application.dto.translation_result import TranslationResult
        result = TranslationResult()
        assert result.success is False
        assert result.translated_text is None

    def test_to_dict(self):
        """Test to_dict."""
        from backend.application.dto.translation_result import TranslationResult
        result = TranslationResult(
            translated_text="translated",
            success=True,
            chunks=3,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["chunks"] == 3


class TestTranslateTextUseCase:
    """Test TranslateTextUseCase."""

    def test_import(self):
        """Test import TranslateTextUseCase."""
        from backend.application.use_cases.translate_text_use_case import TranslateTextUseCase
        assert TranslateTextUseCase is not None

    def test_create_instance(self):
        """Test tạo TranslateTextUseCase instance."""
        from backend.application.use_cases.translate_text_use_case import TranslateTextUseCase
        use_case = TranslateTextUseCase(
            api_keys=["test-key"],
            config={"model_name": "test-model"},
        )
        assert use_case is not None

    def test_from_services(self):
        """Test from_services factory method."""
        from backend.application.use_cases.translate_text_use_case import TranslateTextUseCase
        from backend.infrastructure.config.app_config_service import AppConfigService
        from backend.infrastructure.config.prompt_service import PromptService

        config_service = AppConfigService()
        prompt_service = PromptService()

        use_case = TranslateTextUseCase.from_services(
            api_keys=["test-key"],
            config_service=config_service,
            prompt_service=prompt_service,
        )
        assert use_case is not None
