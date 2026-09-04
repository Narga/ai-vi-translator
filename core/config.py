import os
import json
from pathlib import Path
from typing import List, Dict, Any

# Định vị đường dẫn tuyệt đối theo thư mục gốc của project
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEYS_FILE = CONFIG_DIR / "keys.json"

DEFAULT_CONFIG = {
    "max_chunk_chars": 16000,
    "timeout_seconds": 90,
    "api_delay_seconds": 2.0,
}


class AppConfig:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self):
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
        if not KEYS_FILE.exists():
            KEYS_FILE.write_text(
                json.dumps({"gemini_keys": [], "openai_compat_keys": []}, indent=2), encoding="utf-8"
            )

    def get_config(self) -> Dict[str, Any]:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy rẻ, khỏi import copy
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cfg.update(data)
            except Exception:
                pass

        try:
            max_chars = int(cfg.get("max_chunk_chars", 16000))
            cfg["max_chunk_chars"] = max_chars if max_chars > 0 else 16000
        except (ValueError, TypeError):
            cfg["max_chunk_chars"] = 16000

        try:
            timeout = float(cfg.get("timeout_seconds", 90))
            cfg["timeout_seconds"] = timeout if timeout > 0 else 90.0
        except (ValueError, TypeError):
            cfg["timeout_seconds"] = 90.0

        try:
            delay = float(cfg.get("api_delay_seconds", 2.0))
            cfg["api_delay_seconds"] = delay if delay >= 0 else 2.0
        except (ValueError, TypeError):
            cfg["api_delay_seconds"] = 2.0

        return cfg

    def _keys_from(self, data: dict, field: str, env_name: str) -> List[str]:
        keys = [k.strip() for k in data.get(field, []) if isinstance(k, str) and k.strip()]
        for k in os.getenv(env_name, "").split(","):
            kc = k.strip()
            if kc and kc not in keys:
                keys.append(kc)
        return keys

    def get_keys(self, provider: str) -> List[str]:
        try:
            data = json.loads(KEYS_FILE.read_text(encoding="utf-8")) if KEYS_FILE.exists() else {}
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if provider == "openai_compat":
            return self._keys_from(data, "openai_compat_keys", "OPENAI_COMPAT_KEYS")
        return self._keys_from(data, "gemini_keys", "GEMINI_API_KEYS")

    def get_gemini_keys(self) -> List[str]:  # giữ tương thích test cũ
        return self.get_keys("gemini")

    def save_keys(self, provider: str, keys: List[str]):
        try:
            data = json.loads(KEYS_FILE.read_text(encoding="utf-8")) if KEYS_FILE.exists() else {}
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        field = "openai_compat_keys" if provider == "openai_compat" else "gemini_keys"
        data[field] = [k.strip() for k in keys if k.strip()]
        KEYS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_gemini_keys(self, keys: List[str]):
        self.save_keys("gemini", keys)
