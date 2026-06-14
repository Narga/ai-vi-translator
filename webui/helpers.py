# webui/helpers.py - v5.0.0
# Shared utility functions for WebUI blueprints

import os
import re
import logging
import configparser
from pathlib import Path

logger = logging.getLogger(__name__)

# Available Gemini models (fallback list)
AVAILABLE_GEMINI_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-3-pro",
    "gemini-3-flash",
]


def get_app_version():
    """Tự động nhận diện phiên bản từ CHANGELOG.md."""
    try:
        changelog_path = Path("CHANGELOG.md")
        if changelog_path.exists():
            with open(changelog_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Tìm entry đầu tiên có dạng ## [x.y.z]
                match = re.search(r"##\s*\[(\d+\.\d+\.\d+)\]", content)
                if match:
                    return match.group(1)
    except Exception as e:
        logger.debug(f"Could not extract version from CHANGELOG.md: {e}")

    # Fallback
    return "6.8.0"


# Available OpenAI-compatible models (fallback list)
AVAILABLE_OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
]


def load_config():
    """Load configuration from config/app.ini."""
    config = configparser.ConfigParser()
    config_file = Path("config/app.ini")
    if config_file.exists():
        config.read(config_file)
    return config


def get_default_chunk_size():
    """Get default chunk size from config."""
    config = load_config()
    try:
        return config.getint("PROCESSING", "MAX_CHARS_PER_CHUNK", fallback=100000)
    except Exception:
        return 100000


def get_default_model():
    """Get default model từ active provider."""
    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService()
        active_config = provider_service.get_active_provider_config()
        if active_config and active_config.get("default_model"):
            return active_config["default_model"]
        # Fallback to gemini default model
        gemini_providers = provider_service.get_providers_by_type("gemini")
        if gemini_providers:
            return gemini_providers[0].get("default_model", "gemini-2.0-flash-exp")
        return "gemini-2.0-flash-exp"
    except Exception as e:
        logger.debug(f"get_default_model fallback: {e}")
        # Fallback to legacy app.ini
        config = load_config()
        try:
            return config.get("MODEL", "MODEL", fallback="gemini-2.0-flash-exp")
        except Exception:
            return "gemini-2.0-flash-exp"


def get_active_provider():
    """Get active AI provider from providers.json."""
    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        return ProviderService().get_active_provider()
    except Exception as e:
        logger.debug(f"get_active_provider fallback: {e}")
        return "gemini"


def load_openai_key():
    """Load OpenAI/OpenRouter key. Ưu tiên active provider, fallback sang provider openai đầu tiên."""
    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService()
        # Nếu active là openai → trả key của nó
        active = provider_service.get_active_provider_config()
        if active and active.get("type") == "openai":
            return active.get("api_key", "")
        # Fallback: tìm provider openai đầu tiên
        openai_providers = provider_service.get_providers_by_type("openai")
        if openai_providers:
            return openai_providers[0].get("api_key", "")
    except Exception as e:
        logger.debug(f"load_openai_key error: {e}")
    return ""


def _parse_api_file(filepath):
    """Helper để parse file API.txt — DEPRECATED in v7.3.0 (providers.json is source of truth)."""
    raise NotImplementedError("_parse_api_file đã bị xóa sau migration v7.3.0. Dùng ProviderService.")


def get_openai_base_url():
    """Get OpenAI base URL. Ưu tiên active provider, fallback sang provider openai đầu tiên."""
    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        ps = ProviderService()
        url = ps.get_active_base_url()
        if url:
            return url
        openai_providers = ps.get_providers_by_type("openai")
        if openai_providers:
            u = openai_providers[0].get("base_url", "")
            return u if u else None
    except Exception:
        pass
    return None


def get_openai_model():
    """Get default OpenAI model. Ưu tiên active provider, fallback sang provider openai đầu tiên."""
    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        ps = ProviderService()
        active = ps.get_active_provider_config()
        if active and active.get("type") == "openai":
            return active.get("default_model", "") or "gpt-4o-mini"
        openai_providers = ps.get_providers_by_type("openai")
        if openai_providers:
            return openai_providers[0].get("default_model", "") or "gpt-4o-mini"
    except Exception:
        pass
    return "gpt-4o-mini"


def get_available_models():
    """Get list of available models for the active provider."""
    provider = get_active_provider()

    if provider == "openai":
        return get_available_openai_models()
    else:
        return get_available_gemini_models()


def get_available_gemini_models():
    """Get list of available Gemini models."""
    models = AVAILABLE_GEMINI_MODELS.copy()

    try:
        api_keys = load_api_keys("GEMINI")
        if api_keys:
            first_key = api_keys[0]
            try:
                from google import genai

                client = genai.Client(api_key=first_key)
                try:
                    for model in client.models.list():
                        if model and model.name:
                            model_name = model.name.replace("models/", "")
                            if "gemini" in model_name and model_name not in models:
                                models.insert(0, model_name)
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass

    default_model = get_default_model()
    if default_model not in models:
        models.insert(0, default_model)

    return list(dict.fromkeys(models))


def get_available_openai_models():
    """Get list of available OpenAI-compatible models."""
    models = AVAILABLE_OPENAI_MODELS.copy()

    try:
        api_key = load_openai_key()
        if api_key:
            from services.ai_provider import list_models_for_provider

            fetched = list_models_for_provider("openai", api_key, get_openai_base_url())
            if fetched:
                models = fetched
    except Exception as e:
        logger.debug(f"Could not fetch OpenAI models: {e}")

    openai_model = get_openai_model()
    if openai_model not in models:
        models.insert(0, openai_model)

    return list(dict.fromkeys(models))


def load_api_keys(section=None):
    """Load API keys từ providers.json. section=None → tất cả, 'GEMINI', hoặc 'OPENAI'."""
    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService()
        if section is None:
            all_keys = []
            for p in provider_service.load_providers().get("providers", []):
                if p.get("type") == "gemini":
                    all_keys.extend(p.get("api_keys", []))
                else:
                    if p.get("api_key"):
                        all_keys.append(p["api_key"])
            return all_keys
        type_name = "gemini" if section.upper() == "GEMINI" else "openai"
        providers = provider_service.get_providers_by_type(type_name)
        keys = []
        for p in providers:
            if type_name == "openai":
                if p.get("api_key"):
                    keys.append(p["api_key"])
            else:
                keys.extend(p.get("api_keys", []))
        return keys
    except Exception as e:
        logger.debug(f"load_api_keys error: {e}")
        return []


def save_api_keys(keys_text, section="GEMINI"):
    """Lưu API keys vào providers.json theo section."""
    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService()
        if section.upper() == "OPENAI":
            active = provider_service.get_active_provider_config()
            if active and active.get("type") == "openai":
                api_key = keys_text.strip()
                if api_key:
                    provider_service.update_provider(active["id"], api_key=api_key)
                return True
            return False
        # GEMINI
        keys = [k.strip() for k in keys_text.splitlines() if k.strip()]
        providers = provider_service.get_providers_by_type("gemini")
        if providers:
            provider_service.update_provider(providers[0]["id"], api_keys=keys)
            return True
        return False
    except Exception as e:
        logger.error(f"save_api_keys error: {e}")
        return False


def calculate_stats():
    """Tính toán thống kê hệ thống (project-based)."""
    from webui import translation_memory

    # Count projects
    projects_dir = Path("workspace/projects")
    project_count = 0
    total_sources = 0
    total_translated = 0
    if projects_dir.exists():
        for p in projects_dir.iterdir():
            if p.is_dir() and (p / "project.json").exists():
                project_count += 1
                src = p / "sources"
                tr = p / "translated"
                if src.exists():
                    total_sources += len([f for f in src.rglob("*") if f.is_file() and not f.name.startswith(".")])
                if tr.exists():
                    total_translated += len([f for f in tr.rglob("*") if f.is_file() and not f.name.startswith(".")])

    # Count archives
    archive_dir = Path("workspace/archive")
    archive_count = len(list(archive_dir.glob("*.zip"))) if archive_dir.exists() else 0

    # Get TM stats
    tm_stats = {}
    if translation_memory:
        tm_stats = translation_memory.get_stats()

    stats = {
        "project_count": project_count,
        "archive_count": archive_count,
        "total_sources": total_sources,
        "total_translated": total_translated,
        "cache_files": 0,
        "cache_size_mb": 0,
        "default_model": get_default_model(),
        "default_chunk_size": get_default_chunk_size(),
        "tm_entries": tm_stats.get("total_entries", 0),
        "tm_size_mb": tm_stats.get("memory_size_mb", 0),
    }

    return stats


def load_prompts():
    """Load prompts từ thư mục workspace/prompts/default/."""
    prompts_dir = Path("workspace/prompts/default")
    prompts_dir.mkdir(parents=True, exist_ok=True)
    
    prompts = {}
    for key, filename in [
        ("main", "main_prompt.txt"),
        ("summary", "summary_prompt.txt"),
        ("relationships", "relationship_prompt.txt"),
        ("glossary", "glossary_prompt.txt"),
        ("chinh_ta", "chinh_ta_prompt.txt"),
    ]:
        filepath = prompts_dir / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8").strip()
            prompts[key] = content
        else:
            prompts[key] = ""

    return prompts


def save_prompts(prompts):
    """Lưu prompts vào thư mục workspace/prompts/default/."""
    prompts_dir = Path("workspace/prompts/default")
    prompts_dir.mkdir(parents=True, exist_ok=True)

    for key, filename in [
        ("main", "main_prompt.txt"),
        ("summary", "summary_prompt.txt"),
        ("relationships", "relationship_prompt.txt"),
        ("glossary", "glossary_prompt.txt"),
        ("chinh_ta", "chinh_ta_prompt.txt"),
    ]:
        if key in prompts:
            filepath = prompts_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(prompts.get(key, ""))


def ensure_default_project():
    """Đảm bảo dự án mặc định 'Dịch nhanh' tồn tại."""
    slug = "default-project"
    pdir = Path("workspace/projects") / slug
    if pdir.exists():
        return

    import re
    import shutil
    import json
    from datetime import datetime

    pdir.mkdir(parents=True, exist_ok=True)
    for sub in ["sources", "translated", "prompt", "assets", "output"]:
        (pdir / sub).mkdir(parents=True, exist_ok=True)

    prompts_root = Path("workspace/prompts/default")
    for fname in ["main_prompt.txt"]:
        src = prompts_root / fname
        if src.exists():
            shutil.copy2(src, pdir / "prompt" / fname)

    meta = {
        "name": "Dịch nhanh",
        "slug": slug,
        "description": "Dự án mặc định cho các tác vụ dịch lẻ",
        "genre": "",
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    with open(pdir / "project.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    for fname, content in [
        ("glossary.txt", "# Bảng thuật ngữ\n# Format: thuật ngữ gốc | thuật ngữ dịch | ghi chú\n"),
        (
            "relationship.txt",
            "# Bảng nhân vật & quan hệ\n# Format: tên gốc | tên dịch | vai trò | quan hệ\n",
        ),
        (
            "style_guide.txt",
            "# Hướng dẫn phong cách dịch\n# Mô tả tone, style, và các quy tắc dịch\n",
        ),
        (
            "summary.txt",
            "# Tóm tắt cốt truyện\n# Ghi chú diến biến chính\n",
        ),
    ]:
        fp = pdir / "assets" / fname
        if not fp.exists():
            fp.write_text(content, encoding="utf-8")
