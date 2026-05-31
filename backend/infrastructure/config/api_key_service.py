# backend/infrastructure/config/api_key_service.py
# ApiKeyService - Centralized API key management

"""
ApiKeyService gom logic đọc/ghi API keys từ nhiều nguồn:
- config/API.txt (theo section)
- .env fallback
- config/app.ini (OPENAI section)

Phase 04: Tách logic API key ra khỏi main.py và webui/helpers.py.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ApiKeyService:
    """
    Centralized API key management service.

    Gom logic từ:
    - main.py:load_api_keys
    - webui/helpers.py:load_api_keys
    - webui/helpers.py:load_openai_key
    - webui/helpers.py:_parse_api_file
    - webui/helpers.py:save_api_keys

    Sử dụng:
        from backend.infrastructure.config.api_key_service import ApiKeyService
        key_service = ApiKeyService()
        gemini_keys = key_service.load_gemini_keys()
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Khởi tạo ApiKeyService.

        Args:
            config_dir: Đường dẫn đến config directory.
                       Mặc định: Path("config")
        """
        self._config_dir = config_dir or Path("config")
        self._api_file = self._config_dir / "API.txt"

    def _parse_api_file(self) -> Dict[str, List[str]]:
        """
        Parse file API.txt theo format [SECTION].

        Returns:
            Dict mapping section name -> list of keys
        """
        sections: Dict[str, List[str]] = {}
        current_section = "GEMINI"  # Default cho legacy files

        if not self._api_file.exists():
            return sections

        try:
            with open(self._api_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("[") and line.endswith("]"):
                        current_section = line[1:-1].upper()
                        if current_section not in sections:
                            sections[current_section] = []
                        continue

                    if current_section not in sections:
                        sections[current_section] = []
                    sections[current_section].append(line)
        except Exception as e:
            logger.error(f"Error parsing {self._api_file}: {e}")

        return sections

    # ------------------------------------------------------------------
    # Load methods
    # ------------------------------------------------------------------

    def load_gemini_keys(self) -> List[str]:
        """
        Load Gemini API keys.

        Thứ tự ưu tiên:
        1. config/API.txt [GEMINI] section
        2. .env GEMINI_API_KEYS

        Returns:
            Danh sách Gemini API keys
        """
        # Ưu tiên từ API.txt
        sections = self._parse_api_file()
        keys = sections.get("GEMINI", [])
        if keys:
            logger.info(f"Loaded {len(keys)} Gemini keys from API.txt")
            return keys

        # Fallback: .env
        try:
            from dotenv import load_dotenv

            load_dotenv()
            env_value = os.environ.get("GEMINI_API_KEYS", "")
            if env_value:
                keys = [k.strip() for k in env_value.split(",") if k.strip()]
                logger.info(f"Loaded {len(keys)} Gemini keys from .env")
                return keys
        except Exception:
            pass

        return []

    def load_openai_key(self) -> Optional[str]:
        """
        Load OpenAI/OpenRouter API key.

        Thứ tự ưu tiên:
        1. config/API.txt [OPENAI] section
        2. .env OPENAI_API_KEY
        3. config/app.ini [OPENAI] API_KEY

        Returns:
            OpenAI API key hoặc None
        """
        # 1. Từ API.txt
        sections = self._parse_api_file()
        keys = sections.get("OPENAI", [])
        if keys:
            return keys[0]

        # 2. Từ .env
        try:
            from dotenv import load_dotenv

            load_dotenv()
            key = os.environ.get("OPENAI_API_KEY", "")
            if key:
                return key.strip()
        except Exception:
            pass

        # 3. Từ app.ini
        try:
            import configparser

            config = configparser.ConfigParser()
            config_file = self._config_dir / "app.ini"
            if config_file.exists():
                config.read(config_file)
                key = config.get("OPENAI", "API_KEY", fallback="").strip()
                if key:
                    return key
        except Exception:
            pass

        return None

    def load_all_keys(self) -> List[str]:
        """
        Load tất cả API keys từ mọi section.

        Returns:
            Danh sách tất cả keys (flatten)
        """
        sections = self._parse_api_file()
        all_keys = []
        for keys in sections.values():
            all_keys.extend(keys)
        return all_keys

    def load_keys_by_section(self, section: Optional[str] = None) -> List[str]:
        """
        Load keys theo section.

        Args:
            section: Tên section (e.g., "GEMINI", "OPENAI").
                    Nếu None, load tất cả.

        Returns:
            Danh sách keys
        """
        if section is None:
            return self.load_all_keys()

        sections = self._parse_api_file()
        return sections.get(section.upper(), [])

    # ------------------------------------------------------------------
    # Save methods
    # ------------------------------------------------------------------

    def save_keys(self, section: str, keys_text: str) -> bool:
        """
        Lưu API keys vào file theo section.

        Args:
            section: Tên section (e.g., "GEMINI", "OPENAI")
            keys_text: Nội dung keys (mỗi key một dòng)

        Returns:
            True nếu thành công
        """
        sections = self._parse_api_file()

        # Parse keys từ text
        new_keys = [k.strip() for k in keys_text.splitlines() if k.strip()]
        sections[section.upper()] = new_keys

        # Ghi lại toàn bộ file
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._api_file, "w", encoding="utf-8") as f:
                for sec, keys in sections.items():
                    f.write(f"[{sec}]\n")
                    for k in keys:
                        f.write(f"{k}\n")
                    f.write("\n")
            logger.info(f"Saved {len(new_keys)} keys to [{section}]")
            return True
        except Exception as e:
            logger.error(f"Error saving keys: {e}")
            return False

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def has_gemini_keys(self) -> bool:
        """Kiểm tra có Gemini keys không."""
        return len(self.load_gemini_keys()) > 0

    def has_openai_key(self) -> bool:
        """Kiểm tra có OpenAI key không."""
        return self.load_openai_key() is not None

    def get_key_count(self) -> int:
        """Đếm tổng số keys."""
        return len(self.load_all_keys())
