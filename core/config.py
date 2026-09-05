import os
import json
from pathlib import Path
from typing import List, Dict, Any

from core.file_handler import atomic_write_text

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


def _num(v, default, integer=False, allow_zero=False):
    try:
        n = float(v)
    except (ValueError, TypeError):
        return default
    if n > 0 or (allow_zero and n == 0):
        return int(n) if integer else n
    return default


def normalize_prefs(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Chuẩn hóa prefs về contract duy nhất (manifesto v2.4 §8).
    Sai → rơi về mặc định, key lạ → bỏ. Dùng chung cho get_config() và PUT /api/settings."""
    raw = raw if isinstance(raw, dict) else {}
    return {
        "max_chunk_chars": _num(raw.get("max_chunk_chars", 16000), 16000, integer=True),
        "timeout_seconds": _num(raw.get("timeout_seconds", 90), 90.0),
        "api_delay_seconds": _num(raw.get("api_delay_seconds", 2.0), 2.0, allow_zero=True),
    }


class AppConfig:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self):
        if not CONFIG_FILE.exists():
            atomic_write_text(CONFIG_FILE, json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False))
        if not KEYS_FILE.exists():
            atomic_write_text(KEYS_FILE, json.dumps({"gemini_keys": [], "openai_compat_keys": []}, indent=2))

    def get_config(self) -> Dict[str, Any]:
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}
        return normalize_prefs(data)

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
        atomic_write_text(KEYS_FILE, json.dumps(data, indent=2))

    def save_gemini_keys(self, keys: List[str]):
        self.save_keys("gemini", keys)
