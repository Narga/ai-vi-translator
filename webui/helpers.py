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
    return "6.3.0"


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
    """Get default model from config."""
    config = load_config()
    try:
        return config.get("MODEL", "MODEL", fallback="gemini-2.0-flash-exp")
    except Exception:
        return "gemini-2.0-flash-exp"


def get_active_provider():
    """Get active AI provider from config."""
    config = load_config()
    try:
        return config.get("PROVIDER", "ACTIVE_PROVIDER", fallback="gemini").lower()
    except Exception:
        return "gemini"


def load_openai_key():
    """Load OpenAI/OpenRouter API key từ .env hoặc config."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
        key = os.environ.get("OPENAI_API_KEY", "")
        if key:
            return key.strip()
    except ImportError:
        pass

    # Fallback: đọc từ config/app.ini [OPENAI] section
    config = load_config()
    try:
        return config.get("OPENAI", "API_KEY", fallback="").strip()
    except Exception:
        return ""


def get_openai_base_url():
    """Get OpenAI base URL from config."""
    config = load_config()
    try:
        url = config.get("OPENAI", "BASE_URL", fallback="").strip()
        return url if url else None
    except Exception:
        return None


def get_openai_model():
    """Get default OpenAI model from config."""
    config = load_config()
    try:
        return config.get("OPENAI", "MODEL", fallback="gpt-4o-mini")
    except Exception:
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
        api_keys = load_api_keys()
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


def load_api_keys():
    """Load API keys từ .env hoặc config."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
        env_value = os.environ.get("GEMINI_API_KEYS", "")
        if env_value:
            return [k.strip() for k in env_value.split(",") if k.strip()]
    except ImportError:
        pass

    api_file = Path("config/API.txt")
    if api_file.exists():
        with open(api_file, "r") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return []


def save_api_keys(keys_text):
    """Lưu API keys vào file config/API.txt."""
    api_dir = Path("config")
    api_dir.mkdir(parents=True, exist_ok=True)
    api_file = api_dir / "API.txt"
    with open(api_file, "w", encoding="utf-8") as f:
        f.write(keys_text)
    return True


def calculate_stats():
    """Tính toán thống kê hệ thống (project-based)."""
    from webui import translation_memory

    cache_dir = Path("workspace/cache")
    cache_files = list(cache_dir.glob("*.pkl*")) if cache_dir.exists() else []
    cache_size = sum(f.stat().st_size for f in cache_files) if cache_files else 0

    api_keys = load_api_keys()

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
                    total_sources += len(list(src.glob("*.txt")))
                if tr.exists():
                    total_translated += len(list(tr.glob("*.txt")))

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
        "cache_files": len(cache_files),
        "cache_size_mb": round(cache_size / 1024 / 1024, 2),
        "api_keys_count": len(api_keys),
        "default_model": get_default_model(),
        "default_chunk_size": get_default_chunk_size(),
        "tm_entries": tm_stats.get("total_entries", 0),
        "tm_size_mb": tm_stats.get("memory_size_mb", 0),
    }

    return stats


def load_prompts():
    """Load prompts từ thư mục workspace/prompts/default/."""
    prompts_dir = Path("workspace/prompts/default")
    prompts = {
        "main": "",
        "summary": "",
        "relationships": "",
        "glossary": "",
    }

    for key, filename in [
        ("main", "main_prompt.txt"),
        ("summary", "summary_prompt.txt"),
        ("relationships", "relationship_prompt.txt"),
        ("glossary", "glossary_prompt.txt"),
    ]:
        filepath = prompts_dir / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                prompts[key] = f.read()

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
    ]:
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
