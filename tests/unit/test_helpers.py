# tests/unit/test_helpers.py
# Unit tests cho webui.helpers

import sys
import pytest
from pathlib import Path

# Đảm bảo import được webui.helpers
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestHelpersImports:
    """Test rằng các hàm trong webui.helpers import được."""

    def test_import_load_config(self):
        """Test import load_config."""
        from webui.helpers import load_config
        assert callable(load_config)

    def test_import_get_default_chunk_size(self):
        """Test import get_default_chunk_size."""
        from webui.helpers import get_default_chunk_size
        assert callable(get_default_chunk_size)

    def test_import_get_default_model(self):
        """Test import get_default_model."""
        from webui.helpers import get_default_model
        assert callable(get_default_model)

    def test_import_get_active_provider(self):
        """Test import get_active_provider."""
        from webui.helpers import get_active_provider
        assert callable(get_active_provider)

    def test_import_load_api_keys(self):
        """Test import load_api_keys."""
        from webui.helpers import load_api_keys
        assert callable(load_api_keys)

    def test_import_save_api_keys(self):
        """Test import save_api_keys."""
        from webui.helpers import save_api_keys
        assert callable(save_api_keys)

    def test_import_load_prompts(self):
        """Test import load_prompts."""
        from webui.helpers import load_prompts
        assert callable(load_prompts)

    def test_import_save_prompts(self):
        """Test import save_prompts."""
        from webui.helpers import save_prompts
        assert callable(save_prompts)

    def test_import_ensure_default_project(self):
        """Test import ensure_default_project."""
        from webui.helpers import ensure_default_project
        assert callable(ensure_default_project)

    def test_import_calculate_stats(self):
        """Test import calculate_stats."""
        from webui.helpers import calculate_stats
        assert callable(calculate_stats)

    def test_import_get_app_version(self):
        """Test import get_app_version."""
        from webui.helpers import get_app_version
        assert callable(get_app_version)


class TestHelpersBasicFunctions:
    """Test các hàm cơ bản trong webui.helpers."""

    def test_load_config_returns_configparser(self):
        """Test rằng load_config trả về ConfigParser."""
        from webui.helpers import load_config
        config = load_config()
        assert config is not None
        # ConfigParser có method sections()
        assert hasattr(config, "sections")

    def test_get_default_chunk_size_returns_int(self):
        """Test rằng get_default_chunk_size trả về int."""
        from webui.helpers import get_default_chunk_size
        chunk_size = get_default_chunk_size()
        assert isinstance(chunk_size, int)
        assert chunk_size > 0

    def test_get_default_model_returns_string(self):
        """Test rằng get_default_model trả về string."""
        from webui.helpers import get_default_model
        model = get_default_model()
        assert isinstance(model, str)
        assert len(model) > 0

    def test_get_active_provider_returns_string(self):
        """Test rằng get_active_provider trả về string."""
        from webui.helpers import get_active_provider
        provider = get_active_provider()
        assert isinstance(provider, str)
        assert provider in ("gemini", "openai")

    def test_load_api_keys_returns_list(self):
        """Test rằng load_api_keys trả về list."""
        from webui.helpers import load_api_keys
        keys = load_api_keys()
        assert isinstance(keys, list)

    def test_load_prompts_returns_dict(self):
        """Test rằng load_prompts trả về dict."""
        from webui.helpers import load_prompts
        prompts = load_prompts()
        assert isinstance(prompts, dict)
        assert "main" in prompts

    def test_get_app_version_returns_string(self):
        """Test rằng get_app_version trả về string."""
        from webui.helpers import get_app_version
        version = get_app_version()
        assert isinstance(version, str)
        # Version format: x.y.z
        parts = version.split(".")
        assert len(parts) == 3

    def test_calculate_stats_returns_dict(self):
        """Test rằng calculate_stats trả về dict."""
        from webui.helpers import calculate_stats
        stats = calculate_stats()
        assert isinstance(stats, dict)
        assert "project_count" in stats
        assert "default_model" in stats


class TestHelpersParseApiFile:
    """Test _parse_api_file function — DEPRECATED in v7.3.0."""

    def test_parse_api_file_raises_not_implemented(self, tmp_path):
        """Test rằng _parse_api_file raises NotImplementedError sau migration v7.3.0."""
        from webui.helpers import _parse_api_file
        import pytest
        api_file = tmp_path / "API.txt"
        api_file.write_text("[GEMINI]\nkey1\nkey2\n")
        with pytest.raises(NotImplementedError):
            _parse_api_file(api_file)


class TestCoreImports:
    """Test rằng core modules import được."""

    def test_import_executor(self):
        """Test import TranslationExecutor."""
        from core.executor import TranslationExecutor
        assert TranslationExecutor is not None

    def test_import_spellcheck_executor(self):
        """Test import SpellcheckExecutor."""
        from core.spellcheck_executor import SpellcheckExecutor
        assert SpellcheckExecutor is not None

    def test_import_config_service(self):
        """Test import AppConfigService."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        assert AppConfigService is not None

    def test_import_checkpoint_service(self):
        """Test import CheckpointService."""
        from services.checkpoint_service import CheckpointService
        assert CheckpointService is not None

    def test_import_glossary_service(self):
        """Test import GlossaryService."""
        from services.glossary_service import GlossaryService
        assert GlossaryService is not None
