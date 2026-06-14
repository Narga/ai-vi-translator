# tests/unit/test_config_services.py
# Unit tests cho Phase 04: Config và Key Services

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestAppConfigServiceImport:
    """Test import AppConfigService."""

    def test_import(self):
        """Test import AppConfigService."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        assert AppConfigService is not None

    def test_create_instance(self):
        """Test tạo AppConfigService instance."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        service = AppConfigService()
        assert service is not None


class TestAppConfigServiceMethods:
    """Test các methods của AppConfigService."""

    def test_get_default_model(self):
        """Test get_default_model trả về string."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        service = AppConfigService()
        model = service.get_default_model()
        assert isinstance(model, str)
        assert len(model) > 0

    def test_get_default_chunk_size(self):
        """Test get_default_chunk_size trả về int."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        service = AppConfigService()
        chunk_size = service.get_default_chunk_size()
        assert isinstance(chunk_size, int)
        assert chunk_size > 0

    def test_get_active_provider(self):
        """Test get_active_provider trả về gemini hoặc openai."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        service = AppConfigService()
        provider = service.get_active_provider()
        assert provider in ("gemini", "openai")

    def test_get_temperature(self):
        """Test get_temperature trả về float."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        service = AppConfigService()
        temp = service.get_temperature()
        assert isinstance(temp, (int, float))
        assert 0 <= temp <= 2

    def test_get_context_char_count(self):
        """Test get_context_char_count trả về int."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        service = AppConfigService()
        count = service.get_context_char_count()
        assert isinstance(count, int)
        assert count > 0



    def test_get_openai_model(self):
        """Test get_openai_model trả về string."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        service = AppConfigService()
        model = service.get_openai_model()
        assert isinstance(model, str)

    def test_get_section(self):
        """Test get_section trả về dict."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        service = AppConfigService()
        section = service.get_section("MODEL")
        assert isinstance(section, dict)

    def test_get_nonexistent_section(self):
        """Test get_section với section không tồn tại."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        service = AppConfigService()
        section = service.get_section("NONEXISTENT")
        assert isinstance(section, dict)
        assert len(section) == 0

    def test_set_and_get_value(self):
        """Test set_value và get."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        service = AppConfigService()
        service.set_value("TEST", "test_key", "test_value")
        value = service.get("TEST", "test_key")
        assert value == "test_value"


class TestApiKeyServiceImport:
    """Test import ApiKeyService."""

    def test_import(self):
        """Test import ApiKeyService."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        assert ApiKeyService is not None

    def test_create_instance(self):
        """Test tạo ApiKeyService instance."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        service = ApiKeyService()
        assert service is not None


class TestApiKeyServiceMethods:
    """Test các methods của ApiKeyService."""

    def test_load_gemini_keys_returns_list(self):
        """Test load_gemini_keys trả về list."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        service = ApiKeyService()
        keys = service.load_gemini_keys()
        assert isinstance(keys, list)

    def test_load_openai_key_returns_optional(self):
        """Test load_openai_key trả về None hoặc string."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        service = ApiKeyService()
        key = service.load_openai_key()
        assert key is None or isinstance(key, str)

    def test_load_all_keys_returns_list(self):
        """Test load_all_keys trả về list."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        service = ApiKeyService()
        keys = service.load_all_keys()
        assert isinstance(keys, list)

    def test_load_keys_by_section(self):
        """Test load_keys_by_section trả về list."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        service = ApiKeyService()
        keys = service.load_keys_by_section("GEMINI")
        assert isinstance(keys, list)

    def test_load_keys_by_section_none(self):
        """Test load_keys_by_section với None trả về tất cả."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        service = ApiKeyService()
        keys = service.load_keys_by_section(None)
        assert isinstance(keys, list)

    def test_has_gemini_keys_returns_bool(self):
        """Test has_gemini_keys trả về bool."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        service = ApiKeyService()
        result = service.has_gemini_keys()
        assert isinstance(result, bool)

    def test_has_openai_key_returns_bool(self):
        """Test has_openai_key trả về bool."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        service = ApiKeyService()
        result = service.has_openai_key()
        assert isinstance(result, bool)

    def test_get_key_count_returns_int(self):
        """Test get_key_count trả về int."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        service = ApiKeyService()
        count = service.get_key_count()
        assert isinstance(count, int)
        assert count >= 0

    def test_save_keys(self, tmp_path):
        """Test save_keys lưu vào providers.json."""
        from backend.infrastructure.providers.provider_service import ProviderService
        from backend.infrastructure.config.api_key_service import ApiKeyService
        # Tạo providers.json mẫu
        import json
        providers_file = tmp_path / "providers.json"
        providers_file.write_text(json.dumps({
            "version": 1, "active_id": "gemini-default",
            "providers": [{"id": "gemini-default", "type": "gemini", "name": "Google Gemini", "api_keys": ["old_key"]}]
        }))
        service = ApiKeyService(config_dir=tmp_path)
        result = service.save_keys("GEMINI", "new_key1\nnew_key2\n")
        assert result is True
        # Verify providers.json đã được ghi
        data = json.loads(providers_file.read_text())
        gemini = next(p for p in data["providers"] if p["type"] == "gemini")
        assert "new_key1" in gemini["api_keys"]

    def test_parse_api_file(self, tmp_path):
        """Test ProviderService._parse_api_file parse đúng format."""
        from backend.infrastructure.providers.provider_service import ProviderService
        import json
        # Tạo providers.json để tránh trigger migration (sẽ xóa API.txt)
        (tmp_path / "providers.json").write_text(json.dumps({"version": 1, "active_id": "gemini-default", "providers": []}))
        api_file = tmp_path / "API.txt"
        api_file.write_text("[GEMINI]\ngemini_key1\ngemini_key2\n\n[OPENAI]\nopenai_key1\n")
        ps = ProviderService(config_dir=tmp_path)
        sections = ps._parse_api_file(api_file)
        assert "GEMINI" in sections
        assert "OPENAI" in sections
        assert len(sections["GEMINI"]) == 2
        assert len(sections["OPENAI"]) == 1

    def test_parse_api_file_legacy(self, tmp_path):
        """Test ProviderService._parse_api_file với legacy format (không có section)."""
        from backend.infrastructure.providers.provider_service import ProviderService
        import json
        (tmp_path / "providers.json").write_text(json.dumps({"version": 1, "active_id": "gemini-default", "providers": []}))
        api_file = tmp_path / "API.txt"
        api_file.write_text("key1\nkey2\nkey3\n")
        ps = ProviderService(config_dir=tmp_path)
        sections = ps._parse_api_file(api_file)
        assert "GEMINI" in sections  # Default section
        assert len(sections["GEMINI"]) == 3
