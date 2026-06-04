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
        """Lấy thông tin provider hiện tại (v7.3.0 response shape)."""
        from backend.infrastructure.providers.provider_service import ProviderService

        provider_service = ProviderService(self._config_dir)

        active_type = provider_service.get_active_provider()  # "gemini" | "openai"
        active_config = provider_service.get_active_provider_config()
        providers_list = [
            {"id": p["id"], "name": p.get("name", p["id"]), "type": p.get("type", "gemini")}
            for p in provider_service.load_providers().get("providers", [])
        ]

        result: Dict[str, Any] = {
            "active": active_type,
            "active_id": active_config["id"] if active_config else "gemini-default",
            "providers": providers_list,
        }

        # openai_config: trả full key cho UI cấu hình nội bộ
        if active_type == "openai" and active_config:
            result["openai_config"] = {
                "provider_id": active_config["id"],
                "provider_name": active_config.get("name", ""),
                "base_url": active_config.get("base_url", ""),
                "model": active_config.get("default_model", ""),
                "has_key": bool(active_config.get("api_key")),
                "api_key": active_config.get("api_key", ""),
            }
        else:
            # Gemini active: trả openai_config từ provider openai đầu tiên
            openai_providers = provider_service.get_providers_by_type("openai")
            if openai_providers:
                first = openai_providers[0]
                result["openai_config"] = {
                    "provider_id": first["id"],
                    "provider_name": first.get("name", ""),
                    "base_url": first.get("base_url", ""),
                    "model": first.get("default_model", ""),
                    "has_key": bool(first.get("api_key")),
                    "api_key": first.get("api_key", ""),
                }
            else:
                result["openai_config"] = {
                    "base_url": "", "model": "", "has_key": False, "api_key": "",
                }

        return result

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
