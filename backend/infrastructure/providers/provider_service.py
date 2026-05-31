# backend/infrastructure/providers/provider_service.py
# ProviderService - AI provider management

"""
ProviderService quản lý việc chọn và cấu hình AI provider.

Phase 05: Tách logic provider ra khỏi webui/helpers.py.
"""

import configparser
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ProviderService:
    """
    AI provider management service.

    Gom logic từ:
    - webui/helpers.py:get_active_provider
    - webui/helpers.py:get_openai_base_url
    - webui/helpers.py:get_openai_model
    - webui/routes/settings.py:manage_provider

    Sử dụng:
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService()
        provider = provider_service.get_active_provider()
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Khởi tạo ProviderService.

        Args:
            config_dir: Đường dẫn đến config directory.
                       Mặc định: Path("config")
        """
        self._config_dir = config_dir or Path("config")

    def _load_config(self) -> configparser.ConfigParser:
        """Load config từ app.ini."""
        config = configparser.ConfigParser()
        config.optionxform = str
        config_file = self._config_dir / "app.ini"
        if config_file.exists():
            config.read(config_file, encoding="utf-8")
        return config

    def _save_config(self, config: configparser.ConfigParser) -> None:
        """Lưu config ra app.ini."""
        config_file = self._config_dir / "app.ini"
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            config.write(f)

    # ------------------------------------------------------------------
    # Provider management
    # ------------------------------------------------------------------

    def get_active_provider(self) -> str:
        """
        Lấy active AI provider.

        Returns:
            "gemini" hoặc "openai"
        """
        config = self._load_config()
        return config.get("PROVIDER", "ACTIVE_PROVIDER", fallback="gemini").lower()

    def set_active_provider(self, provider: str) -> None:
        """
        Set active AI provider.

        Args:
            provider: "gemini" hoặc "openai"
        """
        if provider not in ("gemini", "openai"):
            raise ValueError(f"Invalid provider: {provider}. Use 'gemini' or 'openai'.")

        config = self._load_config()
        if not config.has_section("PROVIDER"):
            config.add_section("PROVIDER")
        config.set("PROVIDER", "ACTIVE_PROVIDER", provider)
        self._save_config(config)
        logger.info(f"Switched AI provider to: {provider}")

    def get_available_providers(self) -> list:
        """
        Lấy danh sách providers khả dụng.

        Returns:
            List of provider info dicts
        """
        # Import từ services hiện có
        try:
            from services.ai_provider import get_available_providers
            return get_available_providers()
        except Exception:
            return [
                {"id": "gemini", "name": "Google Gemini"},
                {"id": "openai", "name": "OpenAI / OpenRouter"},
            ]

    # ------------------------------------------------------------------
    # OpenAI config
    # ------------------------------------------------------------------

    def get_openai_base_url(self) -> Optional[str]:
        """
        Lấy OpenAI base URL.

        Returns:
            Base URL hoặc None
        """
        config = self._load_config()
        url = config.get("OPENAI", "BASE_URL", fallback="").strip()
        return url if url else None

    def set_openai_base_url(self, base_url: str) -> None:
        """
        Set OpenAI base URL.

        Args:
            base_url: OpenAI base URL
        """
        config = self._load_config()
        if not config.has_section("OPENAI"):
            config.add_section("OPENAI")
        config.set("OPENAI", "BASE_URL", base_url)
        self._save_config(config)

    def get_openai_model(self) -> str:
        """
        Lấy OpenAI model mặc định.

        Returns:
            Model name
        """
        config = self._load_config()
        return config.get("OPENAI", "MODEL", fallback="gpt-4o-mini")

    def set_openai_model(self, model: str) -> None:
        """
        Set OpenAI model.

        Args:
            model: Model name
        """
        config = self._load_config()
        if not config.has_section("OPENAI"):
            config.add_section("OPENAI")
        config.set("OPENAI", "MODEL", model)
        self._save_config(config)

    # ------------------------------------------------------------------
    # Runtime config
    # ------------------------------------------------------------------

    def get_openai_runtime_config(self) -> dict:
        """
        Lấy OpenAI runtime config đầy đủ.

        Returns:
            Dict chứa base_url, model, has_key
        """
        from backend.infrastructure.config.api_key_service import ApiKeyService

        key_service = ApiKeyService(self._config_dir)

        return {
            "base_url": self.get_openai_base_url() or "",
            "model": self.get_openai_model(),
            "has_key": key_service.has_openai_key(),
        }
