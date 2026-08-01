# tests/unit/test_provider_services.py
# Unit tests cho Phase 05: Prompt, Provider, Model Services

import sys
import json
import pytest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestPromptServiceImport:
    """Test import PromptService."""

    def test_import(self):
        """Test import PromptService."""
        from backend.infrastructure.config.prompt_service import PromptService
        assert PromptService is not None

    def test_create_instance(self):
        """Test tạo PromptService instance."""
        from backend.infrastructure.config.prompt_service import PromptService
        service = PromptService()
        assert service is not None


class TestPromptServiceMethods:
    """Test các methods của PromptService."""

    def test_load_global_prompts_returns_dict(self):
        """Test load_global_prompts trả về dict."""
        from backend.infrastructure.config.prompt_service import PromptService
        service = PromptService()
        prompts = service.load_global_prompts()
        assert isinstance(prompts, dict)
        assert "main" in prompts

    def test_get_global_prompt_returns_string(self):
        """Test get_global_prompt trả về string."""
        from backend.infrastructure.config.prompt_service import PromptService
        service = PromptService()
        prompt = service.get_global_prompt("main")
        assert isinstance(prompt, str)

    def test_get_nonexistent_prompt(self):
        """Test get_global_prompt với key không tồn tại."""
        from backend.infrastructure.config.prompt_service import PromptService
        service = PromptService()
        prompt = service.get_global_prompt("nonexistent")
        assert prompt == ""

    def test_load_merged_prompts(self):
        """Test load_merged_prompts trả về dict."""
        from backend.infrastructure.config.prompt_service import PromptService
        service = PromptService()
        prompts = service.load_merged_prompts()
        assert isinstance(prompts, dict)
        assert "main" in prompts

    def test_load_merged_prompts_with_project(self, tmp_path):
        """Test load_merged_prompts với project override."""
        from backend.infrastructure.config.prompt_service import PromptService
        service = PromptService()

        # Tạo project prompt
        prompt_dir = tmp_path / "prompt"
        prompt_dir.mkdir()
        (prompt_dir / "main_prompt.txt").write_text("Custom project prompt")

        prompts = service.load_merged_prompts(project_dir=tmp_path)
        assert prompts["main"] == "Custom project prompt"

    def test_save_and_reset_project_prompts(self, tmp_path):
        """Test save và reset project prompts."""
        from backend.infrastructure.config.prompt_service import PromptService
        service = PromptService()

        # Save prompts
        service.save_project_prompts(tmp_path, {"main": "Test prompt"})
        prompt_file = tmp_path / "prompt" / "main_prompt.txt"
        assert prompt_file.exists()
        assert prompt_file.read_text() == "Test prompt"

        # Reset prompts
        service.reset_project_prompts(tmp_path)
        assert not (tmp_path / "prompt").exists()

    def test_import_prompts_to_project(self, tmp_path):
        """Test import_prompts_to_project."""
        from backend.infrastructure.config.prompt_service import PromptService
        service = PromptService()

        count = service.import_prompts_to_project(tmp_path, "default")
        assert isinstance(count, int)


class TestProviderServiceImport:
    """Test import ProviderService."""

    def test_import(self):
        """Test import ProviderService."""
        from backend.infrastructure.providers.provider_service import ProviderService
        assert ProviderService is not None

    def test_create_instance(self):
        """Test tạo ProviderService instance."""
        from backend.infrastructure.providers.provider_service import ProviderService
        service = ProviderService()
        assert service is not None


class TestProviderServiceMethods:
    """Test các methods của ProviderService."""

    def test_get_active_provider(self):
        """Test get_active_provider trả về gemini hoặc openai."""
        from backend.infrastructure.providers.provider_service import ProviderService
        service = ProviderService()
        provider = service.get_active_provider()
        assert provider in ("gemini", "openai")

    def test_get_available_providers(self):
        """Test get_available_providers trả về list."""
        from backend.infrastructure.providers.provider_service import ProviderService
        service = ProviderService()
        providers = service.get_available_providers()
        assert isinstance(providers, list)

    def test_get_openai_model(self):
        """Test get_openai_model trả về string."""
        from backend.infrastructure.providers.provider_service import ProviderService
        service = ProviderService()
        model = service.get_openai_model()
        assert isinstance(model, str)

    def test_get_openai_runtime_config(self):
        """Test get_openai_runtime_config trả về dict."""
        from backend.infrastructure.providers.provider_service import ProviderService
        service = ProviderService()
        config = service.get_openai_runtime_config()
        assert isinstance(config, dict)
        assert "base_url" in config
        assert "model" in config
        assert "has_key" in config

    def test_save_creates_backup_and_restores_corrupt_live_file(self, tmp_path):
        from backend.infrastructure.providers.provider_service import ProviderService

        service = ProviderService(tmp_path)
        first = {
            "version": 1,
            "active_id": "local-router",
            "providers": [{
                "id": "local-router",
                "type": "openai",
                "name": "9router",
                "api_key": "",
                "base_url": "http://localhost:20128/v1",
                "default_model": "deepseek-v4-flash-free",
            }],
        }
        second = dict(first, active_id="local-router-2", providers=[dict(first["providers"][0], id="local-router-2")])

        service.save_providers(first)
        service.save_providers(second)

        backup = json.loads((tmp_path / "providers.json.bak").read_text())
        assert backup["active_id"] == "local-router"

        (tmp_path / "providers.json").write_text("{broken", encoding="utf-8")
        restored = service.load_providers()
        assert restored["active_id"] == "local-router"

    def test_invalid_provider_document_is_rejected_without_overwriting(self, tmp_path):
        from backend.infrastructure.providers.provider_service import ProviderService

        service = ProviderService(tmp_path)
        valid = {
            "version": 1,
            "active_id": "local-router",
            "providers": [{
                "id": "local-router",
                "type": "openai",
                "name": "9router",
                "api_key": "",
                "base_url": "http://localhost:20128/v1",
                "default_model": "model-a",
            }],
        }
        service.save_providers(valid)

        invalid = dict(valid, providers=[dict(valid["providers"][0], name="9router/invalid")])
        with pytest.raises(ValueError):
            service.save_providers(invalid)

        assert service.load_providers()["active_id"] == "local-router"

    def test_model_catalog_lists_local_router_without_api_key(self, tmp_path):
        from backend.infrastructure.providers.provider_service import ProviderService
        from backend.infrastructure.providers.model_catalog_service import ModelCatalogService

        ProviderService(tmp_path).save_providers({
            "version": 1,
            "active_id": "local-router",
            "providers": [{
                "id": "local-router",
                "type": "openai",
                "name": "9router",
                "api_key": "",
                "base_url": "http://localhost:20128/v1",
                "default_model": "model-a",
            }],
        })

        with patch("services.openai_client.OpenAIClient") as client_cls:
            client_cls.return_value.list_models.return_value = ["model-a", "model-b"]
            models = ModelCatalogService(tmp_path).get_models("openai")

        assert models[:2] == ["model-a", "model-b"]
        client_cls.assert_called_once()
        assert client_cls.call_args.kwargs["api_key"] == ""


class TestModelCatalogServiceImport:
    """Test import ModelCatalogService."""

    def test_import(self):
        """Test import ModelCatalogService."""
        from backend.infrastructure.providers.model_catalog_service import ModelCatalogService
        assert ModelCatalogService is not None

    def test_create_instance(self):
        """Test tạo ModelCatalogService instance."""
        from backend.infrastructure.providers.model_catalog_service import ModelCatalogService
        service = ModelCatalogService()
        assert service is not None


class TestModelCatalogServiceMethods:
    """Test các methods của ModelCatalogService."""

    def test_get_models_returns_list(self):
        """Test get_models trả về list."""
        from backend.infrastructure.providers.model_catalog_service import ModelCatalogService
        service = ModelCatalogService()
        models = service.get_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_get_gemini_models(self):
        """Test get_gemini_models trả về list."""
        from backend.infrastructure.providers.model_catalog_service import ModelCatalogService
        service = ModelCatalogService()
        models = service.get_gemini_models()
        assert isinstance(models, list)
        assert len(models) > 0

    def test_get_default_model(self):
        """Test get_default_model trả về string."""
        from backend.infrastructure.providers.model_catalog_service import ModelCatalogService
        service = ModelCatalogService()
        model = service.get_default_model()
        assert isinstance(model, str)
        assert len(model) > 0

    def test_get_openai_model(self):
        """Test get_openai_model trả về string."""
        from backend.infrastructure.providers.model_catalog_service import ModelCatalogService
        service = ModelCatalogService()
        model = service.get_openai_model()
        assert isinstance(model, str)
