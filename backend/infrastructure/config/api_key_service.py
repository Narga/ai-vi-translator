# backend/infrastructure/config/api_key_service.py
# ApiKeyService - Centralized API key management (v7.3.0 wrapper)

"""
ApiKeyService gom logic đọc/ghi API keys.
v7.3.0: Delegate sang ProviderService (providers.json).
Giữ nguyên interface để callers không phải sửa.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ApiKeyService:
    """
    Centralized API key management service.
    v7.3.0: Wrapper around ProviderService.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        self._config_dir = config_dir or Path("config")

    def _get_provider_service(self):
        from backend.infrastructure.providers.provider_service import ProviderService
        return ProviderService(self._config_dir)

    # ------------------------------------------------------------------
    # Load methods
    # ------------------------------------------------------------------

    def load_gemini_keys(self) -> List[str]:
        """Load Gemini API keys từ providers.json."""
        try:
            ps = self._get_provider_service()
            providers = ps.get_providers_by_type("gemini")
            keys: List[str] = []
            for p in providers:
                keys.extend(p.get("api_keys", []))
            return keys
        except Exception as e:
            logger.debug(f"load_gemini_keys error: {e}")
            return []

    def load_openai_key(self) -> Optional[str]:
        """Load OpenAI API key từ active provider."""
        try:
            ps = self._get_provider_service()
            config = ps.get_active_provider_config()
            if config and config.get("type") == "openai":
                key = config.get("api_key", "")
                return key if key else None
        except Exception as e:
            logger.debug(f"load_openai_key error: {e}")
        return None

    def load_all_keys(self) -> List[str]:
        """Load tất cả API keys từ mọi providers."""
        try:
            ps = self._get_provider_service()
            all_keys: List[str] = []
            for p in ps.load_providers().get("providers", []):
                if p.get("type") == "gemini":
                    all_keys.extend(p.get("api_keys", []))
                else:
                    if p.get("api_key"):
                        all_keys.append(p["api_key"])
            return all_keys
        except Exception as e:
            logger.debug(f"load_all_keys error: {e}")
            return []

    def load_keys_by_section(self, section: Optional[str] = None) -> List[str]:
        """Load keys theo section. None → tất cả."""
        if section is None:
            return self.load_all_keys()
        try:
            ps = self._get_provider_service()
            if section.upper() == "OPENAI":
                key = ps.get_active_api_key()
                return [key] if key else []
            # GEMINI
            providers = ps.get_providers_by_type("gemini")
            keys: List[str] = []
            for p in providers:
                keys.extend(p.get("api_keys", []))
            return keys
        except Exception as e:
            logger.debug(f"load_keys_by_section error: {e}")
            return []

    # ------------------------------------------------------------------
    # Save methods
    # ------------------------------------------------------------------

    def save_keys(self, section: str, keys_text: str) -> bool:
        """Lưu API keys vào providers.json."""
        try:
            ps = self._get_provider_service()
            if section.upper() == "OPENAI":
                config = ps.get_active_provider_config()
                if config and config.get("type") == "openai":
                    api_key = keys_text.strip()
                    if api_key:
                        ps.update_provider(config["id"], api_key=api_key)
                    return True
                return False
            # GEMINI
            keys = [k.strip() for k in keys_text.splitlines() if k.strip()]
            providers = ps.get_providers_by_type("gemini")
            if providers:
                ps.update_provider(providers[0]["id"], api_keys=keys)
                return True
            return False
        except Exception as e:
            logger.error(f"save_keys error: {e}")
            return False

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def has_gemini_keys(self) -> bool:
        return len(self.load_gemini_keys()) > 0

    def has_openai_key(self) -> bool:
        return self.load_openai_key() is not None

    def get_key_count(self) -> int:
        return len(self.load_all_keys())
