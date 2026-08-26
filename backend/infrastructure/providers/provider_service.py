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
            self._validate_providers_data(data)
            return data
        except Exception as e:
            logger.error(f"Lỗi đọc providers.json: {e}")
            backup_path = self._providers_file.with_suffix(".json.bak")
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup = json.load(f)
                self._validate_providers_data(backup)
                import shutil
                shutil.copy2(backup_path, self._providers_file)
                logger.warning("Đã khôi phục providers.json từ providers.json.bak")
                return backup
            except Exception as backup_error:
                # Fail closed: do not overwrite either file with defaults.
                raise RuntimeError(f"providers.json bị corrupt: {e}; backup không dùng được: {backup_error}")

    def _validate_providers_data(self, data: Dict[str, Any]) -> None:
        """Validate the complete persisted provider document before any write."""
        if not isinstance(data, dict):
            raise ValueError("root phải là object")
        if not isinstance(data.get("version"), int):
            raise ValueError("version phải là số nguyên")
        providers = data.get("providers")
        if not isinstance(providers, list) or not providers:
            raise ValueError("providers phải là array không rỗng")
        active_id = data.get("active_id")
        if not isinstance(active_id, str) or not active_id.strip():
            raise ValueError("active_id phải là chuỗi không rỗng")

        ids = set()
        for provider in providers:
            if not isinstance(provider, dict):
                raise ValueError("mỗi provider phải là object")
            provider_id = provider.get("id")
            provider_type = provider.get("type")
            name = provider.get("name")
            if not isinstance(provider_id, str) or not provider_id.strip() or provider_id in ids:
                raise ValueError("provider id không hợp lệ hoặc bị trùng")
            if provider_type not in ("gemini", "openai"):
                raise ValueError(f"provider type không được hỗ trợ: {provider_type!r}")
            if not isinstance(name, str) or not name.strip() or not re.match(r"^[a-zA-Z0-9\s]+$", name):
                raise ValueError(f"tên provider không hợp lệ: {name!r}")
            ids.add(provider_id)

            if provider_type == "gemini":
                keys = provider.get("api_keys", [])
                if not isinstance(keys, list) or any(not isinstance(key, str) for key in keys):
                    raise ValueError(f"api_keys không hợp lệ cho provider {provider_id}")
                # R1/R4: chống cross-provider model ở tầng validate. Khi provider Gemini
                # chứa model của OpenAI-compatible (vd step-*, deepseek/*) sẽ raise
                # ngay khi load/save, không để lọt xuống runtime.
                for field in ("default_model", "qa_model"):
                    if field in provider and provider[field] not in (None, ""):
                        if not isinstance(provider[field], str):
                            raise ValueError(f"{field} phải là chuỗi cho provider {provider_id}")
                        if not self._is_model_valid_for_type("gemini", provider[field]):
                            raise ValueError(
                                f"{field}={provider[field]!r} không thuộc namespace Gemini/Gemma "
                                f"cho provider {provider_id} (chống cross-provider model)"
                            )
            else:
                for field in ("api_key", "base_url", "gateway_api_key", "credential_mode", "default_model", "qa_model"):
                    if field in provider and not isinstance(provider[field], str):
                        raise ValueError(f"{field} phải là chuỗi cho provider {provider_id}")
                base_url = provider.get("base_url", "")
                if base_url:
                    from backend.infrastructure.providers.endpoint_policy import classify_endpoint
                    classify_endpoint(base_url)
                # R4: OpenAI provider default_model/qa_model phải pass EndpointPolicy.
                provider_base_url = provider.get("base_url") or ""
                for field in ("default_model", "qa_model"):
                    if field in provider and provider[field] not in (None, ""):
                        if not self._is_model_valid_for_type("openai", provider[field], provider_base_url):
                            raise ValueError(
                                f"{field}={provider[field]!r} không hợp lệ với endpoint policy "
                                f"cho provider {provider_id}"
                            )

        if active_id not in ids:
            raise ValueError(f"active_id không tồn tại: {active_id}")

    def save_providers(self, data: Dict[str, Any]) -> None:
        """Ghi providers.json bằng atomic write + validate."""
        import shutil
        self._providers_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._providers_file.with_suffix(".json.tmp")
        backup_path = self._providers_file.with_suffix(".json.bak")
        backup_tmp_path = self._providers_file.with_suffix(".json.bak.tmp")
        # Reject malformed user input before creating or touching any file.
        self._validate_providers_data(data)
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
            self._validate_providers_data(verify)
            # Keep the last known-good document before replacing the live file.
            if self._providers_file.exists():
                shutil.copy2(self._providers_file, backup_tmp_path)
                os.replace(str(backup_tmp_path), str(backup_path))
            # Atomic rename — os.replace() hoạt động trên Linux + macOS
            try:
                os.replace(str(tmp_path), str(self._providers_file))
            except OSError:
                # Fallback: cross-filesystem (os.replace không hoạt động qua filesystem khác)
                shutil.move(str(tmp_path), str(self._providers_file))
        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            if backup_tmp_path.exists():
                backup_tmp_path.unlink()
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
        for key in ("name", "base_url", "default_model", "qa_model", "credential_mode"):
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
        """Lấy default_model của active provider. Không fallback cứng cross-provider.

        R14: trả về chuỗi rỗng khi provider không cấu hình model — caller (factory,
        route) có trách nhiệm validate và báo lỗi cấu hình. Không được ngầm
        định model lạ (vd "gemini-3-flash-preview" cho OpenAI provider).
        """
        config = self.get_active_provider_config()
        if not config:
            return ""
        return str(config.get("default_model", "") or "").strip()

    def get_active_qa_model(self) -> str:
        """Lấy qa_model của active provider từ providers.json. Trả '' khi không cấu hình.

        R-O2 + B1: đọc từ provider làm nguồn sự thật, không fallback về app.ini
        legacy hoặc hardcode. Caller (TranslationService, route) check '' và xử lý
        như cấu hình thiếu.
        """
        config = self.get_active_provider_config()
        if not config:
            return ""
        return str(config.get("qa_model", "") or "").strip()

    def _is_model_valid_for_type(
        self, provider_type: str, model: str, base_url: Optional[str] = None
    ) -> bool:
        """Kiểm tra model có thuộc namespace hợp lệ của provider type.

        R1/R4: chống cross-provider model. Gemini chỉ chấp nhận gemini-*/gemma-*;
        OpenAI-compatible dùng EndpointPolicy.validate_model để tránh hardcode.
        Trả False khi model rỗng để caller raise lỗi cấu hình thay vì âm thầm
        chấp nhận.

        Lưu ý: KHÔNG gọi get_active_provider_config() trong method này — sẽ gây
        đệ quy vô hạn (validate → load → validate → ...). Caller phải truyền
        base_url rõ ràng khi gọi cho provider openai.
        """
        if not model or not isinstance(model, str) or not model.strip():
            return False
        clean = model.strip()
        if provider_type == "gemini":
            # Reject rõ ràng các pattern cross-provider: namespace OpenRouter ("/"),
            # Step ("step-"), OpenAI Cloudflare worker ("workers-ai/"), OpenAI ":free" suffix.
            if "/" in clean or ":" in clean or clean.startswith("step-"):
                return False
            return clean.startswith("gemini-") or clean.startswith("gemma-")
        if provider_type == "openai":
            # Ủy quyền cho EndpointPolicy (đã có cho từng gateway). Nếu base_url
            # không hợp lệ, classify_endpoint sẽ raise ValueError → caller xử lý.
            #
            # R4: OpenAI-compatible KHÔNG chấp nhận model có prefix của provider
            # khác (gemini-*, gemma-*). EndpointPolicy.validate_model mặc định
            # chỉ check whitespace, nên cần reject rõ cross-namespace.
            try:
                from backend.infrastructure.providers.endpoint_policy import classify_endpoint
                policy = classify_endpoint(base_url)
                if not policy.validate_model(clean):
                    return False
                if clean.startswith(("gemini-", "gemma-")):
                    return False
                return True
            except Exception:
                # Không có policy hợp lệ (base_url rỗng, classify raise, ...) →
                # fallback check whitespace only. Caller nên validate base_url
                # riêng trước khi tạo provider.
                return bool(clean) and not any(c.isspace() for c in clean)
        return False

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
