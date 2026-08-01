# backend/infrastructure/providers/provider_service.py
# ProviderService - AI provider management (v7.3.0)

"""
ProviderService quản lý việc chọn và cấu hình AI provider.

v7.3.0: providers.json là nguồn sự thật duy nhất cho tất cả provider configs.
Migration một chiều từ API.txt + app.ini → providers.json.
"""

import json
import configparser
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProviderService:
    """
    AI provider management service.

    providers.json là nguồn sự thật duy nhất cho Gemini + OpenAI-Compatible providers.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        self._config_dir = config_dir or Path("config")
        self._providers_file = self._config_dir / "providers.json"
        # Migration chạy 1 lần nếu providers.json chưa tồn tại
        if not self._providers_file.exists():
            self._migrate_from_legacy()

    # ------------------------------------------------------------------
    # providers.json I/O
    # ------------------------------------------------------------------

    def load_providers(self) -> Dict[str, Any]:
        """Đọc providers.json. Trả về dict có {version, active_id, providers[]}."""
        if not self._providers_file.exists():
            return {"version": 1, "active_id": "gemini-default", "providers": [
                {"id": "gemini-default", "type": "gemini", "name": "Google Gemini", "api_keys": [], "default_model": ""}
            ]}
        try:
            with open(self._providers_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data.get("providers"), list):
                raise ValueError("providers phải là array")
            if not isinstance(data.get("active_id"), str):
                raise ValueError("active_id phải là string")
            return data
        except Exception as e:
            logger.error(f"Lỗi đọc providers.json: {e}")
            # Fail closed: KHÔNG overwrite file corrupt
            raise RuntimeError(f"providers.json bị corrupt: {e}")

    def save_providers(self, data: Dict[str, Any]) -> None:
        """Ghi providers.json bằng atomic write + validate."""
        import shutil
        self._providers_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._providers_file.with_suffix(".json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # Validate: đọc lại
            with open(tmp_path, "r", encoding="utf-8") as f:
                verify = json.load(f)
            if not isinstance(verify.get("providers"), list):
                raise ValueError("providers phải là array")
            if not isinstance(verify.get("active_id"), str):
                raise ValueError("active_id phải là string")
            # Atomic rename — os.replace() hoạt động trên Linux + macOS
            try:
                os.replace(str(tmp_path), str(self._providers_file))
            except OSError:
                # Fallback: cross-filesystem (os.replace không hoạt động qua filesystem khác)
                shutil.move(str(tmp_path), str(self._providers_file))
        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise RuntimeError(f"Lưu providers.json thất bại: {e}")

    # ------------------------------------------------------------------
    # Active provider (backward compat + mới)
    # ------------------------------------------------------------------

    def get_active_provider(self) -> str:
        """
        Trả type string ('gemini' | 'openai') của active provider.
        Giữ backward compat — callers so sánh provider == "openai".
        """
        data = self.load_providers()
        active_id = data.get("active_id")
        providers = data.get("providers", [])
        active = next((p for p in providers if p.get("id") == active_id), None)
        if active:
            return active.get("type", "gemini")
        # Fallback: provider đầu tiên type=gemini
        gemini_first = next((p for p in providers if p.get("type") == "gemini"), None)
        if gemini_first:
            logger.warning(f"active_id '{active_id}' không tồn tại, fallback '{gemini_first['id']}'")
            return "gemini"
        if providers:
            return providers[0].get("type", "gemini")
        return "gemini"

    def get_active_provider_config(self) -> Optional[Dict[str, Any]]:
        """Trả full provider object đang active."""
        data = self.load_providers()
        active_id = data.get("active_id")
        providers = data.get("providers", [])
        active = next((p for p in providers if p.get("id") == active_id), None)
        if active:
            return active
        return providers[0] if providers else None

    def get_active_provider_type(self) -> str:
        """Alias cho get_active_provider()."""
        return self.get_active_provider()

    def select_provider(self, provider_id: str) -> None:
        """Set active_id trong providers.json."""
        data = self.load_providers()
        provider = next((p for p in data["providers"] if p["id"] == provider_id), None)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' không tồn tại")
        data["active_id"] = provider_id
        self.save_providers(data)
        logger.info(f"Activated provider: {provider_id}")

    def select_provider_by_type(self, type: str) -> Optional[str]:
        """
        Chọn provider mặc định theo type (cho legacy /api/provider POST).
        Ưu tiên provider có key. Trả về id hoặc None.
        """
        if type not in ("gemini", "openai"):
            raise ValueError(f"Invalid provider type: {type}")
        data = self.load_providers()
        same_type = [p for p in data["providers"] if p.get("type") == type]
        with_key = [p for p in same_type if p.get("api_key") or p.get("api_keys")]
        chosen = with_key[0] if with_key else (same_type[0] if same_type else None)
        if not chosen:
            return None
        data["active_id"] = chosen["id"]
        self.save_providers(data)
        return chosen["id"]

    def set_active_provider(self, provider: str) -> None:
        """
        Legacy: set active provider theo type.
        Chuyển thành select_provider_by_type().
        """
        if provider not in ("gemini", "openai"):
            raise ValueError(f"Invalid provider: {provider}. Use 'gemini' or 'openai'.")
        self.select_provider_by_type(provider)
        logger.info(f"Switched AI provider to: {provider}")

    # ------------------------------------------------------------------
    # Provider CRUD
    # ------------------------------------------------------------------

    def add_provider(
        self,
        name: str,
        type: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        default_model: Optional[str] = None,
        gateway_api_key: Optional[str] = None,
        credential_mode: str = "default",
    ) -> Dict[str, Any]:
        """Tạo provider mới. Tự sinh id từ name."""
        if type not in ("gemini", "openai"):
            raise ValueError(f"Invalid type: {type}")
        if not re.match(r"^[a-zA-Z0-9\s]+$", name):
            raise ValueError("Tên chỉ được chứa chữ, số và dấu cách")
        base_id = re.sub(r"\s+", "-", name.strip().lower())
        base_id = re.sub(r"[^a-z0-9\-]", "", base_id)
        if not base_id:
            raise ValueError("Tên provider không hợp lệ sau khi normalize")
        data = self.load_providers()
        existing_ids = {p["id"] for p in data["providers"]}
        new_id = base_id
        suffix = 2
        while new_id in existing_ids:
            new_id = f"{base_id}-{suffix}"
            suffix += 1
        if new_id == "gemini-default":
            raise ValueError("Không thể tạo provider với id 'gemini-default' (id hệ thống)")
        provider: Dict[str, Any] = {"id": new_id, "type": type, "name": name.strip()}
        if type == "openai":
            provider["api_key"] = api_key or ""
            provider["base_url"] = base_url or ""
            provider["gateway_api_key"] = gateway_api_key or ""
            provider["credential_mode"] = credential_mode
        else:
            provider["api_keys"] = api_keys or []
        provider["default_model"] = default_model or ""
        data["providers"].append(provider)
        self.save_providers(data)
        return provider

    def update_provider(self, provider_id: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Cập nhật provider. Chỉ update field có trong kwargs.
        api_key rỗng → giữ nguyên key cũ (tránh vô tình xóa).
        """
        data = self.load_providers()
        provider = next((p for p in data["providers"] if p["id"] == provider_id), None)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' không tồn tại")
        for key in ("name", "base_url", "default_model", "credential_mode"):
            if key in kwargs and kwargs[key]:
                provider[key] = kwargs[key]
        if "api_key" in kwargs and kwargs["api_key"]:
            provider["api_key"] = kwargs["api_key"]
        if "gateway_api_key" in kwargs and kwargs["gateway_api_key"]:
            provider["gateway_api_key"] = kwargs["gateway_api_key"]
        if "api_keys" in kwargs and kwargs["api_keys"]:
            provider["api_keys"] = kwargs["api_keys"]
        self.save_providers(data)
        return provider

    def delete_provider(self, provider_id: str) -> bool:
        """Xóa provider. Không cho xóa gemini-default."""
        if provider_id == "gemini-default":
            raise ValueError("Không thể xóa provider Gemini hệ thống")
        data = self.load_providers()
        provider = next((p for p in data["providers"] if p["id"] == provider_id), None)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' không tồn tại")
        if data["active_id"] == provider_id:
            same_type = [p for p in data["providers"]
                         if p["type"] == provider["type"] and p["id"] != provider_id]
            data["active_id"] = same_type[0]["id"] if same_type else "gemini-default"
        data["providers"] = [p for p in data["providers"] if p["id"] != provider_id]
        self.save_providers(data)
        return True

    def get_provider_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        data = self.load_providers()
        return next((p for p in data["providers"] if p["id"] == provider_id), None)

    def get_providers_by_type(self, type: str) -> List[Dict[str, Any]]:
        data = self.load_providers()
        return [p for p in data["providers"] if p.get("type") == type]

    def get_available_providers(self) -> list:
        """Trả danh sách providers từ providers.json."""
        data = self.load_providers()
        return [
            {"id": p["id"], "name": p.get("name", p["id"]), "type": p.get("type", "gemini")}
            for p in data.get("providers", [])
        ]

    # ------------------------------------------------------------------
    # Active config accessors
    # ------------------------------------------------------------------

    def get_active_api_keys(self) -> List[str]:
        """Lấy API keys của active provider (cho Gemini key rotation)."""
        config = self.get_active_provider_config()
        if not config:
            return []
        if config.get("type") == "gemini":
            return config.get("api_keys", [])
        else:
            key = config.get("api_key", "")
            return [key] if key else []

    def get_active_api_key(self) -> str:
        """Lấy single API key của active provider (cho OpenAI)."""
        config = self.get_active_provider_config()
        if not config:
            return ""
        return config.get("api_key", "")

    def get_active_gateway_api_key(self) -> str:
        """Lấy gateway API key của active provider."""
        config = self.get_active_provider_config()
        if not config:
            return ""
        return config.get("gateway_api_key", "")

    def get_active_credential_mode(self) -> str:
        """Lấy credential mode của active provider."""
        config = self.get_active_provider_config()
        if not config:
            return "default"
        return config.get("credential_mode", "default")

    def get_active_base_url(self) -> Optional[str]:
        """Lấy base_url của active OpenAI provider."""
        config = self.get_active_provider_config()
        if not config or config.get("type") != "openai":
            return None
        url = config.get("base_url", "")
        return url if url else None

    def get_active_default_model(self) -> str:
        """Lấy default_model của active provider."""
        config = self.get_active_provider_config()
        if not config:
            return "gemini-3-flash-preview"
        return config.get("default_model", "") or "gemini-3-flash-preview"

    # ------------------------------------------------------------------
    # Legacy accessors (backward compat — delegate to new methods)
    # ------------------------------------------------------------------

    def get_openai_base_url(self) -> Optional[str]:
        return self.get_active_base_url()

    def set_openai_base_url(self, base_url: str) -> None:
        active = self.get_active_provider_config()
        if active and active.get("type") == "openai":
            self.update_provider(active["id"], base_url=base_url)

    def get_openai_model(self) -> str:
        return self.get_active_default_model()

    def set_openai_model(self, model: str) -> None:
        active = self.get_active_provider_config()
        if active and active.get("type") == "openai":
            self.update_provider(active["id"], default_model=model)

    def get_openai_runtime_config(self) -> dict:
        return {
            "base_url": self.get_active_base_url() or "",
            "model": self.get_active_default_model(),
            "has_key": bool(self.get_active_api_key()),
        }

    # ------------------------------------------------------------------
    # Migration (chạy 1 lần)
    # ------------------------------------------------------------------

    def _migrate_from_legacy(self) -> None:
        """Migration một chiều: API.txt + app.ini → providers.json."""
        logger.info("Running migration: legacy → providers.json")
        api_file = self._config_dir / "API.txt"
        config = configparser.ConfigParser()
        config.optionxform = str
        app_ini = self._config_dir / "app.ini"
        if app_ini.exists():
            config.read(app_ini, encoding="utf-8")

        # 1. Đọc Gemini keys từ API.txt
        gemini_keys: List[str] = []
        openai_key = ""
        if api_file.exists():
            sections = self._parse_api_file(api_file)
            gemini_keys = sections.get("GEMINI", [])
            openai_keys = sections.get("OPENAI", [])
            openai_key = openai_keys[0] if openai_keys else ""

        # 2. Đọc OpenAI config từ app.ini
        base_url = config.get("OPENAI", "BASE_URL", fallback="").strip()
        openai_model = config.get("OPENAI", "MODEL", fallback="").strip()
        active_type = config.get("PROVIDER", "ACTIVE_PROVIDER", fallback="gemini").lower()

        # 3. Tạo providers list
        providers: List[Dict[str, Any]] = []
        providers.append({
            "id": "gemini-default",
            "type": "gemini",
            "name": "Google Gemini",
            "api_keys": gemini_keys,
            "default_model": config.get("MODEL", "MODEL", fallback="").strip(),
        })

        # Tạo OpenAI provider nếu có key hoặc base_url
        if openai_key or base_url:
            providers.append({
                "id": "openai-default",
                "type": "openai",
                "name": "OpenAI Compatible",
                "api_key": openai_key,
                "base_url": base_url,
                "default_model": openai_model,
            })

        # 4. Set active_id
        active_id = "gemini-default"
        if active_type == "openai":
            openai_providers = [p for p in providers if p["type"] == "openai"]
            if openai_providers:
                active_id = openai_providers[0]["id"]
            else:
                logger.warning("ACTIVE_PROVIDER=openai nhưng không có OpenAI provider, fallback gemini")
                active_id = "gemini-default"

        data = {"version": 1, "active_id": active_id, "providers": providers}

        # 5. Ghi providers.json bằng atomic write
        try:
            self.save_providers(data)
        except Exception as e:
            logger.error(f"Migration failed (providers.json write error): {e}")
            return

        # 6. Xóa API.txt (không backup)
        if api_file.exists():
            try:
                api_file.unlink()
                logger.info("Deleted config/API.txt")
            except Exception as e:
                logger.warning(f"Không thể xóa API.txt: {e}")

        # 7. Xóa [PROVIDER], [OPENAI], [API] khỏi app.ini
        self._cleanup_app_ini()

        logger.info("Migration complete: providers.json is now the single source of truth")

    def _cleanup_app_ini(self) -> None:
        """Xóa [PROVIDER], [OPENAI], [API] sections khỏi app.ini."""
        config = configparser.ConfigParser()
        config.optionxform = str
        app_ini = self._config_dir / "app.ini"
        if not app_ini.exists():
            return
        config.read(app_ini, encoding="utf-8")
        changed = False
        for section in ("PROVIDER", "OPENAI", "API"):
            if config.has_section(section):
                config.remove_section(section)
                changed = True
        if changed:
            with open(app_ini, "w", encoding="utf-8") as f:
                config.write(f)

    def _parse_api_file(self, filepath: Path) -> Dict[str, List[str]]:
        """Parse API.txt theo [SECTION] format."""
        sections: Dict[str, List[str]] = {}
        current_section = "GEMINI"
        try:
            with open(filepath, "r", encoding="utf-8") as f:
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
            logger.error(f"Error parsing {filepath}: {e}")
        return sections
