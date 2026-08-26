# tests/unit/test_provider_resolver.py
# Nhóm 3: Test cho ProviderConfigResolver — cache, validate, mask, list_models.

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def mock_providers_env(tmp_path):
    """Tạo config dir với providers.json hợp lệ v2 để test resolver."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    providers_data = {
        "version": 1,
        "active_id": "gemini-default",
        "providers": [
            {
                "id": "gemini-default",
                "type": "gemini",
                "name": "Google Gemini",
                "api_keys": ["AIzaTest12345"],
                "default_model": "gemini-2.0-flash",
                "qa_model": "gemini-1.5-pro",
            },
            {
                "id": "openrouter",
                "type": "openai",
                "name": "OpenRouter",
                "api_key": "sk-or-test-1234567890",
                "base_url": "https://openrouter.ai/api/v1",
                "default_model": "deepseek/deepseek-chat",
            },
        ],
    }
    (config_dir / "providers.json").write_text(
        json.dumps(providers_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (config_dir / "providers.json.bak").write_text(
        json.dumps(providers_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return config_dir


class TestProviderConfigResolverResolve:

    def test_resolve_active_by_default(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        p = resolver.resolve()
        assert p.id == "gemini-default"
        assert p.is_gemini is True
        assert p.api_keys == ["AIzaTest12345"]
        assert p.default_model == "gemini-2.0-flash"
        assert p.qa_model == "gemini-1.5-pro"

    def test_resolve_by_provider_id(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        p = resolver.resolve("openrouter")
        assert p.id == "openrouter"
        assert p.is_openai is True
        assert p.base_url == "https://openrouter.ai/api/v1"
        assert p.api_key == "sk-or-test-1234567890"

    def test_resolve_unknown_provider_raises(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        with pytest.raises(ValueError, match="không tồn tại"):
            resolver.resolve("does-not-exist")

    def test_resolve_from_document(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        doc = {
            "id": "custom",
            "type": "openai",
            "name": "Custom",
            "api_key": "k",
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
        }
        p = resolver.resolve_from_document(doc)
        assert p.id == "custom"
        assert p.base_url == "https://api.openai.com/v1"


class TestProviderConfigResolverValidateModel:

    def test_validate_gemini_model_accepted(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        p = resolver.resolve("gemini-default")
        valid, err = resolver.validate_model(p, "gemini-2.5-flash")
        assert valid is True
        assert err == ""

    def test_validate_gemini_rejects_cross_provider(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        p = resolver.resolve("gemini-default")
        for bad in ["step-3.7-flash", "workers-ai/@cf/x", "deepseek/deepseek-chat",
                    "claude-3.5:free"]:
            valid, err = resolver.validate_model(p, bad)
            assert valid is False, f"should reject {bad}"
            assert err

    def test_validate_gemini_rejects_empty(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        p = resolver.resolve("gemini-default")
        valid, err = resolver.validate_model(p, "")
        assert valid is False
        assert "trống" in err

    def test_validate_openai_model_uses_policy(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        p = resolver.resolve("openrouter")
        # OpenRouter namespace chấp nhận model có "/"
        valid, err = resolver.validate_model(p, "deepseek/deepseek-chat")
        assert valid is True, err

    def test_validate_openai_rejects_gemini_namespace_model(self, mock_providers_env):
        """R4 fix: OpenAI-compatible provider phải reject model có prefix Gemini/Gemma.

        Note: openrouter dùng Cloudflare gateway policy có validate_model riêng
        (reject :free suffix). Test với openai-compatible đơn thuần để check
        logic cross-namespace ở _is_model_valid_for_type.
        """
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
            ResolvedProvider,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        # Tạo provider openai-compatible (không phải gateway đặc biệt)
        compat_provider = ResolvedProvider(
            id="custom-openai",
            type="openai",
            name="Custom OpenAI",
            api_key="k",
            base_url="https://api.example.com/v1",
            default_model="some-model",
            qa_model="",
            credential_mode="default",
            raw={"id": "custom-openai", "type": "openai"},
        )
        for bad in ("gemini-2.0-flash", "gemini-1.5-pro", "gemma-2-9b"):
            valid, err = resolver.validate_model(compat_provider, bad)
            assert valid is False, f"OpenAI provider should reject {bad}, got valid=True"
            assert "namespace" in err.lower() or "gemini" in err.lower() or "gemma" in err.lower()


class TestProviderConfigResolverMaskedInfo:

    def test_gemini_mask_does_not_leak_keys(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        p = resolver.resolve("gemini-default")
        masked = p.get_masked_info()
        assert "api_keys" not in masked
        assert "api_key" not in masked
        assert masked["has_api_key"] is True
        assert masked["key_count"] == 1
        assert masked["api_key_last4"] == ["...2345"]
        assert "AIzaTest12345" not in str(masked)

    def test_openai_mask_does_not_leak_key(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        p = resolver.resolve("openrouter")
        masked = p.get_masked_info()
        assert "api_key" not in masked or masked["api_key"] == ""
        # api_key_last4 only contains last 4 chars, not full key
        assert "sk-or-test-1234567890" not in str(masked)
        assert masked["has_api_key"] is True
        assert "...7890" in masked["api_key_last4"]


class TestProviderConfigResolverListModels:

    def test_list_models_returns_provider_info(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        result = resolver.list_models("gemini-default")
        assert result["provider_id"] == "gemini-default"
        assert result["provider_type"] == "gemini"
        assert isinstance(result["models"], list)
        # Default model trong config phải có trong catalog (vì hợp lệ)
        assert "gemini-2.0-flash" in result["models"]
        assert result["default"] == "gemini-2.0-flash"
        assert result["qa_model"] == "gemini-1.5-pro"
        assert result["errors"] == []

    def test_list_models_with_invalid_default_returns_error_not_raise(
        self, mock_providers_env
    ):
        """R20: list endpoint không raise 500 khi default_model cấu hình sai.

        Note: Ở Nhóm 1, _validate_providers_data đã fail-closed ở tầng load,
        nên config sai sẽ raise ngay khi load. Để test behavior R20 của
        resolver (trả errors[] có cấu trúc), ta bypass _load_data bằng mock
        để truyền doc có default_model sai.
        """
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
            ResolvedProvider,
        )
        resolver = ProviderConfigResolver(mock_providers_env)

        bad_provider = ResolvedProvider(
            id="gemini-default",
            type="gemini",
            name="Google Gemini",
            default_model="step-3.7-flash",  # sai namespace
            qa_model="step-3.5-flash",      # sai namespace
            api_keys=["AIzaTest12345"],
            raw={"id": "gemini-default", "type": "gemini"},
        )
        # Patch resolve để trả về bad_provider
        with patch.object(resolver, "resolve", return_value=bad_provider):
            result = resolver.list_models("gemini-default")

        # R20: KHÔNG raise; trả errors[] có cấu trúc
        assert "errors" in result
        fields = {e["field"] for e in result["errors"]}
        assert "default_model" in fields
        assert "qa_model" in fields
        # default phải rỗng vì default_model invalid
        assert result["default"] == ""

    def test_list_models_uses_cache_within_ttl(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        # Lần 1: build cache
        r1 = resolver.list_models("gemini-default")
        assert ("gemini-default", resolver._credentials_hash(resolver.resolve("gemini-default").raw)) in resolver._model_cache
        # Lần 2: phải trả cùng object từ cache
        r2 = resolver.list_models("gemini-default")
        assert r1 is r2

    def test_invalidate_clears_cache(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        resolver.list_models("gemini-default")
        assert len(resolver._model_cache) >= 1
        resolver.invalidate("gemini-default")
        assert ("gemini-default", resolver._credentials_hash(resolver.resolve("gemini-default").raw)) not in resolver._model_cache

    def test_invalidate_all_clears_everything(self, mock_providers_env):
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        resolver.list_models("gemini-default")
        resolver.list_models("openrouter")
        assert len(resolver._model_cache) >= 2
        resolver.invalidate()
        assert len(resolver._model_cache) == 0


class TestProviderConfigResolverNoRecursion:

    def test_resolve_does_not_call_get_active_provider_config(
        self, mock_providers_env
    ):
        """Bug đệ quy: _is_model_valid_for_type gọi get_active_provider_config gây ∞.

        Resolver.resolve() KHÔNG được gọi get_active_provider_config() ở bất kỳ
        đâu trong quá trình resolve (tránh đệ quy tương tự).
        """
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        resolver = ProviderConfigResolver(mock_providers_env)
        # Patch method để detect nếu bị gọi
        with patch.object(
            resolver, "_load_data", wraps=resolver._load_data
        ) as mock_load:
            resolver.resolve("gemini-default")
            # Chỉ gọi _load_data 1 lần; KHÔNG có đệ quy
            assert mock_load.call_count == 1
