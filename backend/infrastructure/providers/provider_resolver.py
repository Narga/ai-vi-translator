# backend/infrastructure/providers/provider_resolver.py
# Nhóm 3 (kế hoạch remediation): lớp phân giải & quản lý chính sách Provider/Model.

"""
ProviderConfigResolver - Lớp phân giải & quản lý chính sách Provider/Model tập trung.

Nhiệm vụ:
1. Phân giải cấu hình provider theo provider_id cụ thể hoặc active_id.
2. Kiểm tra tính hợp lệ của model theo EndpointPolicy.
3. Cung cấp danh sách model (catalog) độc lập cho từng provider, có cache TTL.
4. Che giấu (mask) API key trong dữ liệu public (R3).

Lưu ý quan trọng: Module này dùng ProviderService (đã patch ở Nhóm 1) làm
nguồn sự thật cho providers.json. KHÔNG tự ý validate chéo provider_id
vì ProviderService đã có _validate_providers_data fail-closed.

Phụ thuộc: backend.infrastructure.providers.provider_service
           backend.infrastructure.providers.endpoint_policy
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.infrastructure.providers.endpoint_policy import (
    classify_endpoint,
    EndpointPolicy,
)

logger = logging.getLogger(__name__)


@dataclass
class ResolvedProvider:
    """Provider đã được phân giải & validate, an toàn để truyền cho adapter."""

    id: str
    type: str
    name: str
    default_model: str
    qa_model: str
    api_key: str = ""
    api_keys: List[str] = field(default_factory=list)
    base_url: Optional[str] = None
    gateway_api_key: str = ""
    credential_mode: str = "default"
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_gemini(self) -> bool:
        return self.type == "gemini"

    @property
    def is_openai(self) -> bool:
        return self.type == "openai"

    def get_masked_info(self) -> Dict[str, Any]:
        """Trả metadata public an toàn, không chứa secret (R3)."""
        info: Dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "default_model": self.default_model,
            "qa_model": self.qa_model,
        }
        if self.is_gemini:
            info["has_api_key"] = bool(self.api_keys)
            info["key_count"] = len(self.api_keys)
            info["api_key_last4"] = [
                f"...{k[-4:]}" if len(k) >= 8 else "(set)" for k in self.api_keys
            ]
        else:
            info["base_url"] = self.base_url or ""
            info["credential_mode"] = self.credential_mode
            info["has_api_key"] = bool(self.api_key)
            info["has_gateway_api_key"] = bool(self.gateway_api_key)
            info["api_key_last4"] = (
                f"...{self.api_key[-4:]}" if len(self.api_key) >= 8
                else ("(set)" if self.api_key else "")
            )
        return info


class ProviderConfigResolver:
    """Service phân giải và quản lý chính sách Provider/Model.

    B5: list_models có cache TTL 5 phút, key = (provider_id, hash(credentials))
    để khi credentials đổi thì cache tự expire. Không cache ở tầng process-level
    nếu config_dir thay đổi.
    """

    MODEL_CACHE_TTL_SECONDS = 300  # 5 phút (B5)

    def __init__(self, config_dir: Optional[Path] = None):
        self._config_dir = config_dir or Path("config")
        self._model_cache: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}

    def _load_data(self) -> Dict[str, Any]:
        from backend.infrastructure.providers.provider_service import ProviderService
        return ProviderService(self._config_dir).load_providers()

    def _credentials_hash(self, provider: Dict[str, Any]) -> str:
        """Hash credentials để cache key thay đổi khi key đổi (B5)."""
        if provider.get("type") == "gemini":
            keys = provider.get("api_keys") or []
            material = "|".join(sorted(keys))
        else:
            material = "|".join([
                provider.get("api_key", ""),
                provider.get("gateway_api_key", ""),
                provider.get("base_url", ""),
            ])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    def invalidate(self, provider_id: Optional[str] = None) -> None:
        """Xoá cache. Gọi từ ProviderService khi credentials đổi (B5)."""
        if provider_id is None:
            self._model_cache.clear()
        else:
            keys_to_drop = [k for k in self._model_cache if k[0] == provider_id]
            for k in keys_to_drop:
                self._model_cache.pop(k, None)

    def resolve(self, provider_id: Optional[str] = None) -> ResolvedProvider:
        """Phân giải cấu hình provider.

        Nếu provider_id là None: dùng active_id. Nếu provider_id chỉ định
        mà không tồn tại: raise ValueError (R1 fail-closed, không fallback).
        """
        data = self._load_data()
        active_id = data.get("active_id", "gemini-default")
        target_id = provider_id if provider_id else active_id

        providers = data.get("providers", [])
        matched = next((p for p in providers if p.get("id") == target_id), None)
        if not matched:
            if provider_id is not None:
                raise ValueError(f"Provider '{provider_id}' không tồn tại")
            raise ValueError("Active provider không tồn tại trong providers.json")

        return self.resolve_from_document(matched)

    def resolve_from_document(self, provider_data: Dict[str, Any]) -> ResolvedProvider:
        """Resolve một provider từ document đã load; không đọc file lặp lại (R7)."""
        provider_id = provider_data.get("id")
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("Provider id không hợp lệ")
        provider_type = provider_data.get("type")
        if provider_type not in ("gemini", "openai"):
            raise ValueError(f"Provider type không được hỗ trợ: {provider_type!r}")

        if provider_type == "openai":
            base_url = provider_data.get("base_url") or ""
            api_key = provider_data.get("api_key", "")
        else:
            base_url = None
            api_key = ""

        return ResolvedProvider(
            id=provider_id,
            type=provider_type,
            name=provider_data.get("name", provider_id),
            default_model=str(provider_data.get("default_model", "") or "").strip(),
            qa_model=str(provider_data.get("qa_model", "") or "").strip(),
            api_key=api_key,
            api_keys=list(provider_data.get("api_keys") or []),
            base_url=base_url,
            gateway_api_key=provider_data.get("gateway_api_key", ""),
            credential_mode=provider_data.get("credential_mode", "default"),
            raw=provider_data,
        )

    def validate_model(
        self, provider: ResolvedProvider, model_name: str
    ) -> Tuple[bool, str]:
        """Validate model theo EndpointPolicy (R1, R4).

        Trả (is_valid, error_message). KHÔNG raise để caller có thể trả
        error có cấu trúc về UI (B3: errors: [{field, message}]).
        """
        if not model_name or not isinstance(model_name, str) or not model_name.strip():
            return False, "Tên model không được để trống"
        model = model_name.strip()

        if provider.is_gemini:
            if "/" in model or ":" in model or model.startswith("step-"):
                return False, f"Model '{model}' không thuộc namespace Google Gemini/Gemma"
            if not (model.startswith("gemini-") or model.startswith("gemma-")):
                return False, f"Model Gemini phải bắt đầu bằng 'gemini-' hoặc 'gemma-': {model}"
            return True, ""

        # OpenAI-compatible
        try:
            policy: EndpointPolicy = classify_endpoint(provider.base_url)
        except Exception as e:
            return False, f"Endpoint policy không hợp lệ: {e}"
        if not policy.validate_model(model):
            return False, (
                f"Model '{model}' không hợp lệ với endpoint policy "
                f"'{policy.provider_kind}'"
            )
        return True, ""

    def list_models(
        self, provider_id: Optional[str] = None, full: bool = False
    ) -> Dict[str, Any]:
        """Liệt kê model cho provider (B5: cache 5 phút).

        Cache key = (provider_id, credentials_hash) → tự expire khi key đổi.
        """
        provider = self.resolve(provider_id)
        cred_hash = self._credentials_hash(provider.raw)
        cache_key = (provider.id, cred_hash)
        now = time.time()
        cached = self._model_cache.get(cache_key)
        if cached and (now - cached[0]) < self.MODEL_CACHE_TTL_SECONDS:
            return cached[1]

        result = self._fetch_models(provider, full=full)
        self._model_cache[cache_key] = (now, result)
        return result

    def _fetch_models(
        self, provider: ResolvedProvider, full: bool
    ) -> Dict[str, Any]:
        """Thực hiện fetch model list; tách riêng để test dễ mock."""
        models: List[Any] = []
        error_msg: Optional[str] = None
        source = "fallback"

        if provider.is_gemini:
            models, error_msg, source = self._list_gemini_models(provider)
        else:
            models, error_msg, source = self._list_openai_models(provider, full=full)

        # R20: nếu default_model cấu hình không qua validate, KHÔNG raise; trả
        # errors[] có cấu trúc. Caller (route) sẽ map sang UI.
        # Khi default_model invalid thì KHÔNG được ngầm định model đầu tiên
        # trong list (R1: không fallback chéo); trả "" để caller biết thiếu config.
        errors: List[Dict[str, str]] = []
        default_invalid = False
        qa_invalid = False
        if provider.default_model:
            valid, err = self.validate_model(provider, provider.default_model)
            if not valid:
                errors.append({"field": "default_model", "message": err})
                default_invalid = True
        if provider.qa_model:
            valid, err = self.validate_model(provider, provider.qa_model)
            if not valid:
                errors.append({"field": "qa_model", "message": err})
                qa_invalid = True

        chosen_default = provider.default_model if not default_invalid else ""

        return {
            "provider_id": provider.id,
            "provider_type": provider.type,
            "provider_name": provider.name,
            "models": models,
            "default": chosen_default,
            "qa_model": "" if qa_invalid else provider.qa_model,
            "source": source,
            "errors": errors,
        }

    def _list_gemini_models(
        self, provider: ResolvedProvider
    ) -> Tuple[List[Any], Optional[str], str]:
        models: List[str] = []
        error_msg: Optional[str] = None
        source = "fallback"
        try:
            from google import genai
            if provider.api_keys:
                client = genai.Client(api_key=provider.api_keys[0])
                remote = []
                for m in client.models.list():
                    if m and m.name:
                        name = m.name.replace("models/", "")
                        if (
                            name.startswith("gemini-") or name.startswith("gemma-")
                        ) and "/" not in name:
                            remote.append(name)
                if remote:
                    models = remote
                    source = "api"
        except Exception as e:
            logger.warning("Không thể list models từ Gemini API: %s", e)
            error_msg = f"Không thể kết nối Gemini API: {e}"
        if not models:
            # Fallback danh sách cục bộ
            models = [
                "gemini-2.0-flash",
                "gemini-2.0-flash-exp",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.5-flash-8b",
            ]
        return models, error_msg, source

    def _list_openai_models(
        self, provider: ResolvedProvider, full: bool
    ) -> Tuple[List[Any], Optional[str], str]:
        models: List[Any] = []
        error_msg: Optional[str] = None
        source = "fallback"
        try:
            from services.openai_client import OpenAIClient
            policy = classify_endpoint(provider.base_url)
            if provider.api_key or provider.gateway_api_key or not policy.requires_api_key():
                client = OpenAIClient(
                    api_key=provider.api_key,
                    base_url=provider.base_url,
                    gateway_api_key=provider.gateway_api_key,
                    credential_mode=provider.credential_mode,
                )
                if full:
                    fetched = client.list_models_full()
                    if fetched:
                        models = [m for m in fetched if policy.validate_model(
                            m.get("id", "") if isinstance(m, dict) else m
                        )]
                        source = "api"
                else:
                    fetched = client.list_models()
                    if fetched:
                        models = [m for m in fetched if policy.validate_model(m)]
                        source = "api"
        except Exception as e:
            logger.warning("Không thể list OpenAI models: %s", e)
            error_msg = f"Không thể list models từ endpoint: {e}"
        return models, error_msg, source
