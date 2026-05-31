# backend/facade/settings_facade.py
# SettingsFacade - Facade cho settings operations

"""
SettingsFacade gom logic settings từ nhiều services thành API đơn giản.
Routes chỉ gọi facade, không cần biết chi tiết service nào xử lý.

Phase 14: Tách settings logic ra khỏi routes.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SettingsFacade:
    """
    Facade cho settings operations.

    Gom logic từ webui/routes/settings.py thành API đơn giản.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        self._config_dir = config_dir or Path("config")

    def get_models(self, provider: Optional[str] = None, full: bool = False) -> Dict[str, Any]:
        """Lấy danh sách models."""
        from backend.infrastructure.providers.model_catalog_service import ModelCatalogService
        from backend.infrastructure.providers.provider_service import ProviderService

        catalog = ModelCatalogService(self._config_dir)
        provider_service = ProviderService(self._config_dir)

        if provider is None:
            provider = provider_service.get_active_provider()

        if provider == "openai":
            if full:
                models = catalog.get_openai_models_full()
            else:
                models = catalog.get_openai_models()
        else:
            models = catalog.get_gemini_models()
            if full:
                models = [{"id": m, "name": m} for m in models]

        default_model = catalog.get_default_model()
        return {"models": models, "default": default_model, "provider": provider}

    def get_provider_info(self) -> Dict[str, Any]:
        """Lấy thông tin provider hiện tại."""
        from backend.infrastructure.providers.provider_service import ProviderService
        from backend.infrastructure.config.api_key_service import ApiKeyService

        provider_service = ProviderService(self._config_dir)
        key_service = ApiKeyService(self._config_dir)

        provider = provider_service.get_active_provider()
        providers = provider_service.get_available_providers()
        openai_key = key_service.load_openai_key()

        return {
            "active": provider,
            "providers": providers,
            "openai_config": {
                "base_url": provider_service.get_openai_base_url() or "",
                "model": provider_service.get_openai_model(),
                "has_key": bool(openai_key),
                "key": openai_key or "",
            },
        }

    def get_config(self) -> Dict[str, Any]:
        """Lấy cấu hình mặc định."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        from backend.infrastructure.providers.model_catalog_service import ModelCatalogService

        config_service = AppConfigService(self._config_dir)
        catalog = ModelCatalogService(self._config_dir)

        return {
            "default_chunk_size": config_service.get_default_chunk_size(),
            "default_model": config_service.get_default_model(),
            "available_models": catalog.get_models(),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê hệ thống."""
        from webui.helpers import calculate_stats
        stats = calculate_stats()
        stats["status"] = "ready"
        return stats

    def get_api_keys(self, section: str = "GEMINI") -> str:
        """Lấy API keys theo section."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        key_service = ApiKeyService(self._config_dir)
        keys = key_service.load_keys_by_section(section)
        return "\n".join(keys)

    def save_api_keys(self, keys_text: str, section: str = "GEMINI") -> bool:
        """Lưu API keys."""
        from backend.infrastructure.config.api_key_service import ApiKeyService
        key_service = ApiKeyService(self._config_dir)
        return key_service.save_keys(section, keys_text)
