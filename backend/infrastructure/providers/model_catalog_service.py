# backend/infrastructure/providers/model_catalog_service.py
# ModelCatalogService - Model discovery và catalog

"""
ModelCatalogService quản lý việc liệt kê và khám phá models.

Phase 05: Tách logic model discovery ra khỏi webui/helpers.py.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Fallback models cho Gemini
AVAILABLE_GEMINI_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-3-pro",
    "gemini-3-flash",
]

# Fallback models cho OpenAI
AVAILABLE_OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
]


class ModelCatalogService:
    """
    Model discovery và catalog service.

    Gom logic từ:
    - webui/helpers.py:get_available_models
    - webui/helpers.py:get_available_gemini_models
    - webui/helpers.py:get_available_openai_models
    - webui/helpers.py:get_default_model

    Sử dụng:
        from backend.infrastructure.providers.model_catalog_service import ModelCatalogService
        catalog = ModelCatalogService()
        models = catalog.get_models("gemini")
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Khởi tạo ModelCatalogService.

        Args:
            config_dir: Đường dẫn đến config directory.
                       Mặc định: Path("config")
        """
        self._config_dir = config_dir or Path("config")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_models(self, provider: Optional[str] = None, full: bool = False) -> List:
        """
        Lấy danh sách models cho provider.

        Args:
            provider: "gemini" hoặc "openai". Nếu None, dùng active provider.
            full: Nếu True, trả về full model objects (cho OpenAI)

        Returns:
            List of model names hoặc model objects
        """
        if provider is None:
            from backend.infrastructure.providers.provider_service import ProviderService
            provider_service = ProviderService(self._config_dir)
            provider = provider_service.get_active_provider()

        if provider == "openai":
            return self.get_openai_models(full=full)
        else:
            return self.get_gemini_models()

    def get_gemini_models(self) -> List[str]:
        """
        Lấy danh sách Gemini models.

        Returns:
            List of model names
        """
        models = AVAILABLE_GEMINI_MODELS.copy()

        try:
            from backend.infrastructure.config.api_key_service import ApiKeyService
            key_service = ApiKeyService(self._config_dir)
            gemini_keys = key_service.load_gemini_keys()

            if gemini_keys:
                first_key = gemini_keys[0]
                try:
                    from google import genai

                    client = genai.Client(api_key=first_key)
                    try:
                        for model in client.models.list():
                            if model and model.name:
                                model_name = model.name.replace("models/", "")
                                if "gemini" in model_name and model_name not in models:
                                    models.insert(0, model_name)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

        # Đảm bảo default model có trong list
        default_model = self.get_default_model()
        if default_model not in models:
            models.insert(0, default_model)

        return list(dict.fromkeys(models))  # Remove duplicates, preserve order

    def get_openai_models(self, full: bool = False) -> List:
        """
        Lấy danh sách OpenAI-compatible models.

        Args:
            full: Nếu True, trả về full model objects

        Returns:
            List of model names hoặc model objects
        """
        models = AVAILABLE_OPENAI_MODELS.copy()

        try:
            from backend.infrastructure.config.api_key_service import ApiKeyService
            from backend.infrastructure.providers.provider_service import ProviderService

            key_service = ApiKeyService(self._config_dir)
            provider_service = ProviderService(self._config_dir)

            api_key = key_service.load_openai_key()
            if api_key:
                from services.ai_provider import list_models_for_provider

                base_url = provider_service.get_openai_base_url()
                fetched = list_models_for_provider("openai", api_key, base_url)
                if fetched:
                    models = fetched
        except Exception as e:
            logger.debug(f"Could not fetch OpenAI models: {e}")

        # Đảm bảo default model có trong list
        openai_model = self.get_openai_model()
        if openai_model not in models:
            models.insert(0, openai_model)

        return list(dict.fromkeys(models))

    def get_openai_models_full(self) -> List[Dict]:
        """
        Lấy danh sách OpenAI models với full info.

        Returns:
            List of model info dicts
        """
        try:
            from backend.infrastructure.config.api_key_service import ApiKeyService
            from backend.infrastructure.providers.provider_service import ProviderService

            key_service = ApiKeyService(self._config_dir)
            provider_service = ProviderService(self._config_dir)

            api_key = key_service.load_openai_key()
            if not api_key:
                return []

            from services.openai_client import OpenAIClient

            base_url = provider_service.get_openai_base_url()
            client = OpenAIClient(api_key=api_key, base_url=base_url)
            models = client.list_models_full()
            models.sort(key=lambda x: not x.get("is_free", False))
            return models
        except Exception as e:
            logger.error(f"Error fetching OpenAI models: {e}")
            return []

    # ------------------------------------------------------------------
    # Default models
    # ------------------------------------------------------------------

    def get_default_model(self) -> str:
        """
        Lấy default model cho active provider.

        Returns:
            Model name
        """
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService(self._config_dir)

        config = configparser.ConfigParser()
        config_file = self._config_dir / "app.ini"
        if config_file.exists():
            config.read(config_file)

        return config.get("MODEL", "MODEL", fallback="gemini-3-flash-preview")

    def get_openai_model(self) -> str:
        """
        Lấy default OpenAI model.

        Returns:
            Model name
        """
        config = configparser.ConfigParser()
        config_file = self._config_dir / "app.ini"
        if config_file.exists():
            config.read(config_file)

        return config.get("OPENAI", "MODEL", fallback="gpt-4o-mini")


# Cần import configparser ở module level
import configparser
