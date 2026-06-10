# tests/unit/test_spellcheck_provider.py
# Unit tests cho spellcheck provider dispatch

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSpellcheckGetClient:
    """Test _get_client dispatch theo provider_type."""

    def setup_method(self):
        """Reset client cache trước mỗi test."""
        from plugins.spellcheck import spellchecker
        spellchecker._client_cache.clear()

    @patch("services.genai_client.GenAIClient", autospec=True)
    def test_gemini_provider_creates_genai_client(self, mock_genai_cls):
        """Config provider_type=gemini phải tạo GenAIClient."""
        from plugins.spellcheck.spellchecker import _get_client
        config = {"provider_type": "gemini", "model_name": "gemini-2.0-flash", "base_url": ""}
        _get_client("test-key", config)
        mock_genai_cls.assert_called_once_with(
            api_key="test-key", default_model="gemini-2.0-flash", thinking_level="MEDIUM"
        )

    @patch("services.openai_client.OpenAIClient", autospec=True)
    def test_openai_provider_creates_openai_client(self, mock_openai_cls):
        """Config provider_type=openai phải tạo OpenAIClient."""
        from plugins.spellcheck.spellchecker import _get_client
        config = {
            "provider_type": "openai",
            "model_name": "gpt-4o-mini",
            "base_url": "https://openrouter.ai/api/v1",
        }
        _get_client("test-openai-key", config)
        mock_openai_cls.assert_called_once_with(
            api_key="test-openai-key",
            base_url="https://openrouter.ai/api/v1",
            default_model="gpt-4o-mini",
        )

    @patch("services.openai_client.OpenAIClient", autospec=True)
    def test_openai_provider_does_not_create_genai(self, mock_openai_cls):
        """Config provider_type=openai KHÔNG được tạo GenAIClient."""
        from plugins.spellcheck.spellchecker import _get_client
        config = {
            "provider_type": "openai",
            "model_name": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
        }
        with patch("services.genai_client.GenAIClient") as mock_genai_cls:
            _get_client("test-key", config)
            mock_genai_cls.assert_not_called()

    def test_default_provider_type_is_gemini(self):
        """Khi config thiếu provider_type, mặc định là gemini."""
        from plugins.spellcheck.spellchecker import _get_client
        config = {"model_name": "gemini-2.0-flash"}
        with patch("services.genai_client.GenAIClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = _get_client("test-key", config)
            mock_cls.assert_called_once()

    def test_client_cache_reuse(self):
        """Gọi _get_client 2 lần với cùng config phải trả cùng instance."""
        from plugins.spellcheck.spellchecker import _get_client
        config = {"provider_type": "gemini", "model_name": "gemini-2.0-flash"}
        with patch("services.genai_client.GenAIClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            client1 = _get_client("key1", config)
            client2 = _get_client("key1", config)
            assert client1 is client2
            assert mock_cls.call_count == 1  # Chỉ tạo 1 lần

    def test_client_cache_different_provider(self):
        """Cùng key nhưng khác provider_type phải tạo client khác."""
        from plugins.spellcheck.spellchecker import _get_client
        with patch("services.genai_client.GenAIClient") as mock_genai:
            mock_genai.return_value = MagicMock()
            with patch("services.openai_client.OpenAIClient") as mock_openai:
                mock_openai.return_value = MagicMock()
                c1 = _get_client("key1", {"provider_type": "gemini", "model_name": "m1"})
                c2 = _get_client("key1", {"provider_type": "openai", "model_name": "m1", "base_url": "http://x"})
                assert c1 is not c2


class TestSpellcheckChunkInterface:
    """Test spellcheck_chunk giữ nguyên interface."""

    def test_import(self):
        """Test import spellcheck_chunk."""
        from plugins.spellcheck.spellchecker import spellcheck_chunk
        assert callable(spellcheck_chunk)

    def test_return_type_on_no_key(self):
        """Khi không có key, trả Tuple[str, str, str]."""
        from plugins.spellcheck.spellchecker import spellcheck_chunk
        mock_manager = MagicMock()
        mock_manager.get_next_available_key.return_value = None
        result = spellcheck_chunk("text", "prompt", mock_manager, {})
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert result[1] == "no_api_key"