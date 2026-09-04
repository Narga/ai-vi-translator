"""AI Provider Manager: lưu API keys, dynamic model listing & model selection.

Hỗ trợ Google Gemini & OpenAI-Compatible (OpenRouter, Groq, Ollama, DeepSeek).
`config/providers.json` là nguồn sự thật duy nhất (SSOT).
Theo docs/06_AI_MODELS_MANAGEMENT_SPEC.md (học từ Novel-Translator).
"""

import hashlib
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"


class AIProviderManager:
    CACHE_TTL_SECONDS = 300  # Bộ đệm 5 phút

    # Dự phòng khi mất mạng/key lỗi. Danh sách live từ API mới là chuẩn —
    # fallback chỉ để UI không chết, sẽ lỗi thời theo thời gian là bình thường.
    FALLBACK_MODELS = {
        "gemini": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        "openai": [
            "gpt-4o",
            "gpt-4o-mini",
        ],
    }

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "providers.json"
        self._cache: Dict[Tuple[str, str], Tuple[float, List[str]]] = {}
        self._ensure_config_exists()

    # ------------------------------------------------------------------
    # 1. File cấu hình (atomic write + migration 1 chiều từ keys.json)
    # ------------------------------------------------------------------
    def _ensure_config_exists(self) -> None:
        if self.config_file.exists():
            return
        migrated = self._migrate_legacy()
        self.save_config(migrated or {
            "version": 1,
            "active_id": "gemini-default",
            "providers": [{
                "id": "gemini-default",
                "type": "gemini",
                "name": "Google Gemini",
                "api_keys": [],
                "default_model": "",
            }],
        })

    def _migrate_legacy(self) -> Optional[Dict[str, Any]]:
        """Migration 1 chiều: keys.json + config.json cũ -> providers.json."""
        keys_file = self.config_dir / "keys.json"
        cfg_file = self.config_dir / "config.json"
        if not keys_file.exists() and not cfg_file.exists():
            return None
        try:
            keys = json.loads(keys_file.read_text(encoding="utf-8")) if keys_file.exists() else {}
            cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else {}
        except Exception:
            return None
        if not isinstance(keys, dict):
            keys = {}
        if not isinstance(cfg, dict):
            cfg = {}
        gemini_keys = [k for k in keys.get("gemini_keys", []) if isinstance(k, str) and k.strip()]
        oa_keys = [k for k in keys.get("openai_compat_keys", []) if isinstance(k, str) and k.strip()]
        providers = []
        if gemini_keys or not oa_keys:
            providers.append({
                "id": "gemini-default", "type": "gemini", "name": "Google Gemini",
                "api_keys": gemini_keys, "default_model": "",
            })
        if oa_keys:
            prov_cfg = cfg.get("providers", {}).get("openai_compat", {}) if isinstance(cfg.get("providers"), dict) else {}
            providers.append({
                "id": "openai-compat", "type": "openai", "name": "OpenAI-Compatible",
                "api_key": oa_keys[0], "base_url": prov_cfg.get("base_url", "https://openrouter.ai/api/v1"),
                "default_model": "",
            })
        if not providers:
            return None
        logger.info("Migrated legacy keys.json -> providers.json")
        return {"version": 1, "active_id": providers[0]["id"], "providers": providers}

    def load_config(self) -> Dict[str, Any]:
        if not self.config_file.exists():
            self._ensure_config_exists()
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            bak = self.config_file.with_suffix(".json.bak")
            if bak.exists():
                logger.warning("providers.json hỏng, khôi phục từ .bak")
                with open(bak, "r", encoding="utf-8") as f:
                    return json.load(f)
            raise RuntimeError(f"providers.json bị corrupt và không có backup: {e}")

    def save_config(self, data: Dict[str, Any]) -> None:
        """Atomic write + backup + validate (học Novel-Translator)."""
        self._validate(data)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.config_file.with_suffix(".json.tmp")
        bak_path = self.config_file.with_suffix(".json.bak")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            with open(tmp_path, "r", encoding="utf-8") as f:
                verify = json.load(f)
            self._validate(verify)
            if self.config_file.exists():
                shutil.copy2(self.config_file, bak_path)
            os.replace(str(tmp_path), str(self.config_file))
        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise RuntimeError(f"Lưu providers.json thất bại: {e}")

    @staticmethod
    def _validate(data: Dict[str, Any]) -> None:
        if not isinstance(data.get("providers"), list):
            raise ValueError("providers phải là array")
        ids = [p.get("id") for p in data["providers"]]
        if data.get("active_id") not in ids:
            raise ValueError(f"active_id '{data.get('active_id')}' không tồn tại trong providers")

    # ------------------------------------------------------------------
    # 2. Truy vấn provider đang dùng
    # ------------------------------------------------------------------
    def get_active(self) -> Dict[str, Any]:
        config = self.load_config()
        active = next((p for p in config["providers"] if p.get("id") == config.get("active_id")), None)
        if active:
            return active
        return config["providers"][0]

    def get_by_id(self, provider_id: str) -> Dict[str, Any]:
        config = self.load_config()
        p = next((x for x in config["providers"] if x.get("id") == provider_id), None)
        if not p:
            raise ValueError(f"Provider ID '{provider_id}' không tồn tại.")
        return p

    def get_keys(self, provider: Dict[str, Any]) -> List[str]:
        """Keys xoay vòng: Gemini = mảng, OpenAI = key đơn."""
        if provider.get("type") == "gemini":
            return [k for k in provider.get("api_keys", []) if isinstance(k, str) and k.strip()]
        k = (provider.get("api_key") or "").strip()
        return [k] if k else []

    # ------------------------------------------------------------------
    # 3. Cập nhật keys/model (sentinel protection) + đổi active
    # ------------------------------------------------------------------
    def update_provider_keys_and_model(
        self,
        provider_id: str,
        api_keys: Optional[List[str]] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        selected_model: Optional[str] = None,
    ) -> bool:
        config = self.load_config()
        provider = next((p for p in config["providers"] if p["id"] == provider_id), None)
        if not provider:
            raise ValueError(f"Provider ID '{provider_id}' không tồn tại.")

        if api_keys is not None:  # single-user: lưu nguyên danh sách đang sửa
            provider["api_keys"] = [k.strip() for k in api_keys if k.strip()]

        if api_key is not None:
            provider["api_key"] = api_key.strip()

        if base_url is not None:
            provider["base_url"] = base_url.strip().rstrip("/")

        if selected_model is not None and selected_model.strip():
            model_clean = selected_model.strip()
            self._validate_model_namespace(provider["type"], model_clean, provider.get("base_url", ""))
            provider["default_model"] = model_clean

        self.save_config(config)
        return True

    def set_active_provider(self, provider_id: str) -> None:
        config = self.load_config()
        if not any(p["id"] == provider_id for p in config["providers"]):
            raise ValueError(f"Provider ID '{provider_id}' không tồn tại.")
        config["active_id"] = provider_id
        self.save_config(config)

    # ------------------------------------------------------------------
    # 4. Dynamic model listing (cache TTL 5 phút theo credential hash)
    # ------------------------------------------------------------------
    def list_models_for_provider(self, provider_id: str) -> Dict[str, Any]:
        config = self.load_config()
        provider = next((p for p in config["providers"] if p["id"] == provider_id), None)
        if not provider:
            raise ValueError(f"Provider ID '{provider_id}' không tồn tại.")

        cred_str = f"{provider.get('api_keys')}-{provider.get('api_key')}-{provider.get('base_url')}"
        cred_hash = hashlib.sha256(cred_str.encode("utf-8")).hexdigest()[:16]
        cache_key = (provider_id, cred_hash)

        now = time.time()
        if cache_key in self._cache:
            cached_time, cached_models = self._cache[cache_key]
            if now - cached_time < self.CACHE_TTL_SECONDS:
                return {"provider_id": provider_id, "models": cached_models,
                        "selected_model": provider.get("default_model", ""),
                        "source": "cache", "error": None}

        models, error_msg, source = [], None, "api"
        try:
            if provider["type"] == "gemini":
                if not provider.get("api_keys"):
                    # Chưa có key thì không gọi live — trả fallback kèm cảnh báo rõ ràng
                    raise RuntimeError("Chưa nhập API key — hiển thị danh sách dự phòng.")
                models = self._fetch_gemini_models(provider.get("api_keys", []))
            else:
                models = self._fetch_openai_models(provider.get("api_key", ""), provider.get("base_url", ""))
        except Exception as e:
            logger.warning(f"Lỗi truy vấn models của {provider_id}: {e}")
            error_msg, source = str(e), "fallback"
            models = list(self.FALLBACK_MODELS.get(provider["type"], []))

        current_model = provider.get("default_model", "")
        if current_model and current_model not in models:
            models.insert(0, current_model)

        if source == "api" and models:
            self._cache[cache_key] = (now, models)

        return {"provider_id": provider_id, "models": models,
                "selected_model": current_model, "source": source, "error": error_msg}

    def _fetch_gemini_models(self, api_keys: List[str]) -> List[str]:
        if not api_keys or not api_keys[0]:
            return list(self.FALLBACK_MODELS["gemini"])
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_keys[0]}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error ({resp.status_code})")
            data = resp.json()
        models = []
        for item in data.get("models", []):
            if "generateContent" in item.get("supportedGenerationMethods", []):
                name = item.get("name", "").replace("models/", "")
                if name.startswith("gemini-") or name.startswith("gemma-"):
                    models.append(name)
        return sorted(models, reverse=True) if models else list(self.FALLBACK_MODELS["gemini"])

    def _fetch_openai_models(self, api_key: str, base_url: str) -> List[str]:
        base = base_url.strip().rstrip("/") if base_url else "https://api.openai.com/v1"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base}/models", headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API error ({resp.status_code})")
            data = resp.json()
        models = [item["id"] for item in data.get("data", []) if "id" in item]
        return sorted(models) if models else list(self.FALLBACK_MODELS["openai"])

    # ------------------------------------------------------------------
    # 5. Helpers
    # ------------------------------------------------------------------
    def _validate_model_namespace(self, provider_type: str, model: str, base_url: str) -> None:
        if provider_type == "gemini":
            if not (model.startswith("gemini-") or model.startswith("gemma-")):
                raise ValueError(f"Model '{model}' không hợp lệ cho Google Gemini.")
        elif provider_type == "openai":
            if not ("openrouter.ai" in (base_url or "") or "/" in model):
                if model.startswith(("gemini-", "gemma-")):
                    raise ValueError(f"Model '{model}' thuộc Gemini, không hợp lệ cho OpenAI chuẩn.")

    @staticmethod
    def mask_key(key: str) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

    def masked_providers(self, mask: bool = False) -> Dict[str, Any]:
        """Dữ liệu cho UI. Single-user: mặc định trả FULL key để sửa trực tiếp.
        mask=True chỉ dùng khi cần che (log/share)."""
        config = self.load_config()
        out = []
        for p in config["providers"]:
            q = dict(p)
            if mask:
                if "api_keys" in q:
                    q["api_keys"] = [self.mask_key(k) for k in q["api_keys"]]
                if "api_key" in q:
                    q["api_key"] = self.mask_key(q["api_key"])
            out.append(q)
        return {"version": config.get("version", 1), "active_id": config.get("active_id"), "providers": out}
