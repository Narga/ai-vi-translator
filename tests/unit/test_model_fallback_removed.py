# tests/unit/test_model_fallback_removed.py
# Regression tests cho việc loại bỏ hoàn toàn model fallback runtime.
# Đảm bảo: thiếu model → lỗi cấu hình rõ ràng, không tự chọn model thay thế.

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestNoHardcodedModelFallback:
    """Đảm bảo constructor client không hardcode model mặc định runtime."""

    def test_genai_client_default_model_is_empty(self):
        """GenAIClient() không được có default model hardcoded."""
        pytest.importorskip("google.genai")
        from unittest.mock import patch
        with patch("google.genai.Client"):
            from services.genai_client import GenAIClient
            client = GenAIClient(api_key="test-key")
            assert client.default_model == ""

    def test_openai_client_default_model_is_empty(self):
        """OpenAIClient() không được có default model hardcoded."""
        pytest.importorskip("openai")
        from unittest.mock import patch
        with patch("openai.OpenAI"):
            from services.openai_client import OpenAIClient
            client = OpenAIClient(api_key="test-key", base_url="https://example.com/v1")
            assert client.default_model == ""


class TestTranslationRequestNoDefault:
    """DTO không tự điền model mặc định."""

    def test_minimal_request_has_empty_model(self):
        from backend.application.dto.translation_request import TranslationRequest
        req = TranslationRequest(text="hello")
        assert req.model_name == ""

    def test_from_dict_without_model(self):
        from backend.application.dto.translation_request import TranslationRequest
        req = TranslationRequest.from_dict({"text": "x"})
        assert req.model_name == ""

    def test_from_dict_with_explicit_model(self):
        from backend.application.dto.translation_request import TranslationRequest
        req = TranslationRequest.from_dict({"text": "x", "model": "gemini-3-flash"})
        assert req.model_name == "gemini-3-flash"

    def test_from_dict_drops_qa_model(self):
        """v8.29.2: DTO bỏ qua qa_model (không phải HTTP boundary), to_config() không có key."""
        from backend.application.dto.translation_request import TranslationRequest
        req = TranslationRequest.from_dict({"text": "x", "qa_model": "should-be-ignored"})
        assert not hasattr(req, "qa_model")
        assert "qa_model" not in req.to_config()


class TestCallApiMissingModel:
    """_call_api() dừng trước retry/API call khi model rỗng."""

    def test_call_api_missing_model_returns_missing_model_status(self, monkeypatch):
        """Model rỗng → return ('missing_model', ...) không gọi SDK, không lấy key."""
        from unittest.mock import MagicMock

        # Mock ApiManager để track xem có gọi get_next_available_key không
        api_manager = MagicMock()
        api_manager._key_list = ["key1", "key2"]
        api_manager.acquire_rpm.return_value = True
        api_manager.get_next_available_key.return_value = "key1"

        from plugins.translation.translator import _call_api

        result_text, status, api_key = _call_api(
            text_to_process="hello",
            prompt="translate",
            api_manager=api_manager,
            config={},  # no model_name
        )

        assert result_text is None
        assert status == "missing_model"
        assert api_key == "unknown"
        # Đảm bảo KHÔNG gọi acquire_rpm / get_next_available_key (fail-fast)
        api_manager.acquire_rpm.assert_not_called()
        api_manager.get_next_available_key.assert_not_called()

    def test_call_api_with_model_proceeds(self, monkeypatch):
        """Model hợp lệ → gọi SDK, status success."""
        from unittest.mock import MagicMock, patch

        api_manager = MagicMock()
        api_manager._key_list = ["key1"]
        api_manager.acquire_rpm.return_value = True
        api_manager.get_next_available_key.return_value = "key1"
        api_manager.mark_success.return_value = None

        # Mock GenAIClient để trả về success
        with patch("plugins.translation.translator._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.generate_content.return_value = ("translated", "success")
            mock_get_client.return_value = mock_client

            from plugins.translation.translator import _call_api

            result_text, status, api_key = _call_api(
                text_to_process="hello",
                prompt="translate",
                api_manager=api_manager,
                config={"model_name": "gemini-3-flash"},
            )

            assert result_text == "translated"
            assert status == "success"
            assert api_key == "key1"
            # Verify model được pass tới SDK
            call_kwargs = mock_client.generate_content.call_args.kwargs
            assert call_kwargs["model"] == "gemini-3-flash"


class TestSettingsRouteEmptyDefault:
    """GET /api/models không hardcode model khi default_model rỗng."""

    def test_get_models_gemini_empty_default_returns_empty(self, tmp_path, monkeypatch):
        """Khi default_model rỗng, helper get_default_model() trả rỗng.

        Test trực tiếp helper, không qua Flask (Flask load config thật).
        """
        from unittest.mock import patch
        from backend.infrastructure.providers.provider_service import ProviderService

        ps = ProviderService(tmp_path)
        with patch.object(ps, "get_active_provider_config", return_value={
            "id": "gemini-default",
            "type": "gemini",
            "name": "Test",
            "api_keys": ["test-key"],
            "default_model": "",
        }), patch.object(ps, "get_providers_by_type", return_value=[]):
            with patch("backend.infrastructure.providers.provider_service.ProviderService", return_value=ps):
                from webui.helpers import get_default_model
                result = get_default_model()
        assert result == ""  # Phải rỗng khi không cấu hình, không tự chọn model


class TestGetOpenaiModelNoFallback:
    """get_openai_model() không hardcode fallback."""

    def test_get_openai_model_empty_when_no_config(self, tmp_path, monkeypatch):
        # Skip khi webui (Flask) không khả dụng
        pytest.importorskip("flask")
        from webui.helpers import get_openai_model
        from unittest.mock import patch
        from backend.infrastructure.providers.provider_service import ProviderService

        ps = ProviderService(tmp_path)
        with patch.object(ps, "get_active_provider_config", return_value={
            "id": "openai-default",
            "type": "openai",
            "name": "Test",
            "api_key": "test-key",
            "base_url": "https://example.com/v1",
            "default_model": "",
        }), patch.object(ps, "get_providers_by_type", return_value=[]):
            with patch("backend.infrastructure.providers.provider_service.ProviderService", return_value=ps):
                result = get_openai_model()
        assert result == ""  # Phải rỗng khi không cấu hình, không tự chọn model

    def test_get_openai_model_returns_configured(self, tmp_path, monkeypatch):
        pytest.importorskip("flask")
        from webui.helpers import get_openai_model
        from unittest.mock import patch
        from backend.infrastructure.providers.provider_service import ProviderService

        ps = ProviderService(tmp_path)
        with patch.object(ps, "get_active_provider_config", return_value={
            "id": "openai-default",
            "type": "openai",
            "name": "Test",
            "api_key": "test-key",
            "base_url": "https://example.com/v1",
            "default_model": "test-model",
        }), patch.object(ps, "get_providers_by_type", return_value=[]):
            with patch("backend.infrastructure.providers.provider_service.ProviderService", return_value=ps):
                result = get_openai_model()
        assert result == "test-model"


class TestProviderConfigResolverValidatesEmpty:
    """ProviderConfigResolver.validate_model rejects empty string."""

    def test_validate_rejects_empty(self):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver, ResolvedProvider,
        )
        resolver = ProviderConfigResolver()
        provider = ResolvedProvider(
            id="gemini-default",
            type="gemini",
            name="Test",
            default_model="",
        )
        valid, err = resolver.validate_model(provider, "")
        assert valid is False
        assert "trống" in err.lower() or "empty" in err.lower()
