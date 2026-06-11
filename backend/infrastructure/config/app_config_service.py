# backend/infrastructure/config/app_config_service.py
# AppConfigService - Centralized config access cho backend

"""
AppConfigService bọc services/config_service.py hiện có
và cung cấp API dùng chung cho CLI và WebUI.

Phase 04: Tách logic config ra khỏi main.py và webui/helpers.py.
"""

import configparser
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AppConfigService:
    """
    Centralized configuration service cho backend.

    Bọc services/config_service.py:ConfigService hiện có
    và cung cấp API tiện lợi hơn cho các use case.

    Sử dụng:
        from backend.infrastructure.config.app_config_service import AppConfigService
        config_service = AppConfigService()
        model = config_service.get_default_model()
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Khởi tạo AppConfigService.

        Args:
            config_dir: Đường dẫn đến config directory.
                       Mặc định: Path("config")
        """
        self._config_dir = config_dir or Path("config")
        self._config = configparser.ConfigParser()
        self._config.optionxform = str  # Preserve case
        self._load_config()

    def _load_config(self) -> None:
        """Load config từ app.ini."""
        config_file = self._config_dir / "app.ini"
        if config_file.exists():
            self._config.read(config_file, encoding="utf-8")
            logger.debug(f"Loaded config from {config_file}")
        else:
            logger.warning(f"Config file not found: {config_file}")

    def reload(self) -> None:
        """Reload config từ disk."""
        self._load_config()

    # ------------------------------------------------------------------
    # Generic access
    # ------------------------------------------------------------------

    def get(
        self,
        section: str,
        key: str,
        fallback: Any = None,
        value_type: type = str,
    ) -> Any:
        """
        Lấy giá trị config.

        Args:
            section: Tên section (e.g., 'MODEL', 'PROCESSING')
            key: Tên key
            fallback: Giá trị mặc định
            value_type: Kiểu dữ liệu (str, int, float, bool)

        Returns:
            Giá trị config đã convert
        """
        if not self._config.has_section(section):
            return fallback

        if not self._config.has_option(section, key):
            return fallback

        if value_type == bool:
            return self._config.getboolean(section, key, fallback=fallback)
        elif value_type == int:
            return self._config.getint(section, key, fallback=fallback)
        elif value_type == float:
            return self._config.getfloat(section, key, fallback=fallback)
        else:
            return self._config.get(section, key, fallback=fallback)

    def get_section(self, section: str) -> Dict[str, str]:
        """Lấy tất cả key-value trong section."""
        if self._config.has_section(section):
            return dict(self._config.items(section))
        return {}

    def set_value(self, section: str, key: str, value: str) -> None:
        """
        Set giá trị config (in-memory).

        Args:
            section: Tên section
            key: Tên key
            value: Giá trị
        """
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, key, str(value))

    def save(self) -> None:
        """Lưu config ra file app.ini."""
        config_file = self._config_dir / "app.ini"
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            self._config.write(f)
        logger.info(f"Saved config to {config_file}")

    # ------------------------------------------------------------------
    # Convenience methods cho các giá trị thường dùng
    # ------------------------------------------------------------------

    def get_default_model(self) -> str:
        """Lấy model mặc định từ active provider."""
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService(self._config_dir)
        return provider_service.get_active_default_model()

    def get_qa_model(self) -> str:
        """Lấy QA model."""
        return self.get("MODEL", "QA_MODEL", fallback="gemini-3-flash-preview")

    def get_default_chunk_size(self) -> int:
        """Lấy chunk size mặc định."""
        return self.get(
            "PROCESSING", "MAX_CHARS_PER_CHUNK", fallback=100000, value_type=int
        )

    def get_temperature(self) -> float:
        """Lấy temperature mặc định."""
        return self.get(
            "PROCESSING", "TEMPERATURE", fallback=0.75, value_type=float
        )

    def get_context_char_count(self) -> int:
        """Lấy context char count."""
        return self.get(
            "PROCESSING", "CONTEXT_CHAR_COUNT", fallback=500, value_type=int
        )

    def get_active_provider(self) -> str:
        """Lấy active AI provider (gemini hoặc openai). Delegate sang ProviderService."""
        from backend.infrastructure.providers.provider_service import ProviderService
        return ProviderService(self._config_dir).get_active_provider()

    def set_active_provider(self, provider: str) -> None:
        """Set active AI provider. Delegate sang ProviderService."""
        from backend.infrastructure.providers.provider_service import ProviderService
        ProviderService(self._config_dir).select_provider_by_type(provider)

    def get_openai_base_url(self) -> Optional[str]:
        """Lấy OpenAI base URL. Delegate sang ProviderService."""
        from backend.infrastructure.providers.provider_service import ProviderService
        return ProviderService(self._config_dir).get_active_base_url()

    def get_openai_model(self) -> str:
        """Lấy OpenAI model mặc định. Delegate sang ProviderService."""
        from backend.infrastructure.providers.provider_service import ProviderService
        return ProviderService(self._config_dir).get_active_default_model()

    def is_cache_enabled(self) -> bool:
        """Kiểm tra cache có enabled không."""
        return self.get("CACHE", "ENABLE_CACHE", fallback=True, value_type=bool)

    def get_cache_dir(self) -> str:
        """Lấy cache directory path."""
        return self.get("DIRECTORIES", "CACHE_DIR", fallback="workspace/cache")

    def get_logs_dir(self) -> str:
        """Lấy logs directory path."""
        return self.get("DIRECTORIES", "LOGS_DIR", fallback="workspace/logs")

    def get_checkpoints_dir(self) -> str:
        """Lấy checkpoints directory path."""
        return self.get(
            "DIRECTORIES", "CHECKPOINTS_DIR", fallback="workspace/checkpoints"
        )
