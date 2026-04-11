# webui/routes/settings.py - v5.0.0
# Blueprint: Models, Config, Stats, Cache, Token Estimation

import re
import logging
import configparser
from pathlib import Path

from flask import Blueprint, request, jsonify

from webui.helpers import (
    load_api_keys, get_default_chunk_size, get_default_model,
    get_available_models, calculate_stats, save_api_keys
)

logger = logging.getLogger(__name__)

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/models")
def get_models():
    """Lấy danh sách models khả dụng cho provider hiện tại hoặc provider chỉ định."""
    try:
        from webui.helpers import get_active_provider
        
        # Lấy provider từ query param hoặc active provider
        requested_provider = request.args.get("provider")
        provider = requested_provider if requested_provider in ("gemini", "openai") else get_active_provider()
        
        full = request.args.get("full", "false").lower() == "true"

        if provider == "openai":
            from webui.helpers import load_openai_key, get_openai_base_url
            api_key = load_openai_key()
            if not api_key:
                return jsonify({"models": [], "error": "Chưa cấu hình OpenAI key", "provider": "openai"}), 200
            from services.openai_client import OpenAIClient
            client = OpenAIClient(api_key=api_key, base_url=get_openai_base_url())
            if full:
                models = client.list_models_full()
                # Prioritize free models
                models.sort(key=lambda x: not x.get("is_free", False))
            else:
                models = client.list_models()
        else:
            # Gemini
            from webui.helpers import get_available_gemini_models
            models = get_available_gemini_models()
            if full:
                # Wrap Gemini names in objects for consistency
                models = [{"id": m, "name": m} for m in models]

        default_model = get_default_model()
        return jsonify({"models": models, "default": default_model, "provider": provider})
    except Exception as e:
        logger.error(f"get_models error: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/provider", methods=["GET", "POST"])
def manage_provider():
    """Quản lý provider AI (chuyển đổi Gemini ↔ OpenAI)."""
    from webui.helpers import get_active_provider, get_openai_base_url, get_openai_model, load_openai_key

    if request.method == "GET":
        try:
            from services.ai_provider import get_available_providers

            provider = get_active_provider()
            providers = get_available_providers()
            return jsonify({
                "active": provider,
                "providers": providers,
                "openai_config": {
                    "base_url": get_openai_base_url() or "",
                    "model": get_openai_model(),
                    "has_key": bool(load_openai_key()),
                },
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # POST: Chuyển đổi provider
    try:
        data = request.json
        new_provider = data.get("provider", "gemini").lower()

        if new_provider not in ("gemini", "openai"):
            return jsonify({"error": "Provider không hợp lệ. Sử dụng 'gemini' hoặc 'openai'."}), 400

        config_path = Path("config/app.ini")
        config = configparser.ConfigParser()
        config.optionxform = str
        if config_path.exists():
            config.read(config_path)

        if not config.has_section("PROVIDER"):
            config.add_section("PROVIDER")
        config.set("PROVIDER", "ACTIVE_PROVIDER", new_provider)

        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)

        logger.info(f"Switched AI provider to: {new_provider}")
        return jsonify({"success": True, "active": new_provider})

    except Exception as e:
        logger.error(f"Error switching provider: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/openai/models")
def get_openai_models():
    """Lấy danh sách models từ OpenAI/OpenRouter."""
    from webui.helpers import load_openai_key, get_openai_base_url

    try:
        api_key = load_openai_key()
        if not api_key:
            return jsonify({"error": "Chưa cấu hình OpenAI API key"}), 400

        full = request.args.get("full", "false").lower() == "true"

        from services.openai_client import OpenAIClient
        base_url = get_openai_base_url()
        client = OpenAIClient(api_key=api_key, base_url=base_url)
        
        if full:
            models = client.list_models_full()
            # Sort: free models first
            models.sort(key=lambda x: not x.get("is_free", False))
            return jsonify({"models": models})
        else:
            models = client.list_models()
            return jsonify({"models": models})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/openai/config", methods=["POST"])
def save_openai_config():
    """Lưu cấu hình OpenAI (API key, base URL, model)."""
    try:
        data = request.json
        api_key = data.get("api_key", "").strip()
        base_url = data.get("base_url", "").strip()
        model = data.get("model", "gpt-4o-mini").strip()

        # Lưu api_key vào .env
        if api_key:
            env_path = Path(".env")
            env_lines = []
            if env_path.exists():
                env_lines = env_path.read_text(encoding="utf-8").splitlines()

            # Update or add OPENAI_API_KEY
            found = False
            for i, line in enumerate(env_lines):
                if line.startswith("OPENAI_API_KEY"):
                    env_lines[i] = f"OPENAI_API_KEY={api_key}"
                    found = True
                    break
            if not found:
                env_lines.append(f"OPENAI_API_KEY={api_key}")

            env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

        # Lưu base_url và model vào app.ini
        config_path = Path("config/app.ini")
        config = configparser.ConfigParser()
        config.optionxform = str
        if config_path.exists():
            config.read(config_path)

        if not config.has_section("OPENAI"):
            config.add_section("OPENAI")
        if base_url:
            config.set("OPENAI", "BASE_URL", base_url)
        if model:
            config.set("OPENAI", "MODEL", model)

        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)

        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error saving OpenAI config: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/model-info/<path:model_name>")
def get_model_info(model_name):
    """Lấy thông tin chi tiết của model (Gemini hoặc OpenAI)."""
    from webui.helpers import get_active_provider
    provider = get_active_provider()

    try:
        if provider == "gemini":
            api_keys = load_api_keys()
            if not api_keys:
                return jsonify({"error": "Không tìm thấy API key Gemini"}), 400

            from google import genai
            client = genai.Client(api_key=api_keys[0])
            full_name = model_name if model_name.startswith("models/") else f"models/{model_name}"

            try:
                model = client.models.get(model=full_name)
                info = {
                    "provider": "gemini",
                    "name": getattr(model, "name", model_name),
                    "display_name": getattr(model, "display_name", model_name),
                    "description": getattr(model, "description", ""),
                    "input_token_limit": getattr(model, "input_token_limit", None),
                    "output_token_limit": getattr(model, "output_token_limit", None),
                }
                if info["input_token_limit"]:
                    info["input_token_display"] = f"{info['input_token_limit']:,}"
                if info["output_token_limit"]:
                    info["output_token_display"] = f"{info['output_token_limit']:,}"

                rate_limits = {}
                for attr_name, label in [
                    ("rpm_limit", "RPM"), ("rpd_limit", "RPD"),
                    ("tpm_limit", "TPM"), ("tpd_limit", "TPD"),
                    ("requests_per_minute", "RPM"), ("requests_per_day", "RPD"),
                    ("tokens_per_minute", "TPM"), ("tokens_per_day", "TPD"),
                ]:
                    val = getattr(model, attr_name, None)
                    if val is not None and label not in rate_limits:
                        rate_limits[label] = val
                info["rate_limits"] = rate_limits
                return jsonify(info)
            except Exception as e:
                return jsonify({"error": f"Không tìm thấy model Gemini: {model_name}", "detail": str(e)}), 404

        else:
            # OpenAI / OpenRouter
            from webui.helpers import load_openai_key, get_openai_base_url
            api_key = load_openai_key()
            if not api_key:
                return jsonify({"error": "Chưa cấu hình OpenAI key"}), 400

            from services.openai_client import OpenAIClient
            client = OpenAIClient(api_key=api_key, base_url=get_openai_base_url())
            
            models = client.list_models_full()
            target = next((m for m in models if m["id"] == model_name), None)
            
            if not target:
                return jsonify({"error": f"Không tìm thấy model OpenAI: {model_name}"}), 404
            
            info = {
                "provider": "openai",
                "name": target["id"],
                "display_name": target.get("name", target["id"]),
                "is_free": target.get("is_free", False),
            }
            
            if "context_length" in target:
                info["input_token_limit"] = target["context_length"]
                info["input_token_display"] = f"{target['context_length']:.0f}" if isinstance(target['context_length'], (int, float)) else str(target['context_length'])
                if isinstance(target['context_length'], (int, float)):
                    info["input_token_display"] = f"{target['context_length']:,}"
            
            # Pricing info if available (OpenRouter)
            if "pricing" in target:
                p = target["pricing"]
                info["description"] = f"Giá: {p.get('prompt', '0')} (in) / {p.get('completion', '0')} (out)"
                
            return jsonify(info)

    except Exception as e:
        logger.error(f"Model info error: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/estimate-tokens", methods=["POST"])
def estimate_tokens():
    """Ước tính token từ số ký tự văn bản."""
    data = request.json
    text = data.get("text", "")
    char_count = data.get("char_count", len(text))
    lang = data.get("lang", "CN").upper()

    if text:
        cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', text))
        total = len(text.strip())
        cjk_ratio = cjk_chars / total if total > 0 else 0
    else:
        cjk_ratio = 1.0 if lang in ("CN", "JP", "KR") else 0.0

    if cjk_ratio > 0.5:
        tokens_per_char = 1 / 1.5
        lang_label = "CJK"
    elif cjk_ratio > 0.2:
        tokens_per_char = 1 / 2.5
        lang_label = "Hỗn hợp"
    else:
        tokens_per_char = 1 / 4.0
        lang_label = "Latin"

    estimated_tokens = int(char_count * tokens_per_char)
    prompt_overhead = 2000
    total_input_tokens = estimated_tokens + prompt_overhead

    return jsonify({
        "char_count": char_count,
        "estimated_tokens": estimated_tokens,
        "total_input_tokens": total_input_tokens,
        "prompt_overhead": prompt_overhead,
        "tokens_per_char": round(tokens_per_char, 3),
        "lang_type": lang_label,
        "cjk_ratio": round(cjk_ratio, 2),
        "display": f"~{estimated_tokens:,} tokens ({char_count:,} ký tự, {lang_label})",
    })


@settings_bp.route("/api/config")
def get_config():
    """Lấy cấu hình mặc định."""
    try:
        return jsonify({
            "default_chunk_size": get_default_chunk_size(),
            "default_model": get_default_model(),
            "available_models": get_available_models(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/stats")
def get_stats():
    """Lấy thống kê hệ thống."""
    try:
        stats = calculate_stats()
        stats["status"] = "ready"
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/cache/clear", methods=["POST"])
def clear_cache():
    """Xóa cache."""
    try:
        cache_dir = Path("workspace/cache")
        if cache_dir.exists():
            count = 0
            for f in cache_dir.glob("*.pkl*"):
                f.unlink()
                count += 1
            return jsonify({"success": True, "deleted": count})
        return jsonify({"success": True, "deleted": 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/restart", methods=["POST"])
def restart_server():
    """Khởi động lại web server bằng cách thoát tiến trình."""
    import os
    import signal
    import threading
    import time

    def kill_process():
        time.sleep(3)
        logger.info("Restarting: Process re-executing...")
        import sys
        import os
        # Re-exec the process with same arguments
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # Chạy trong thread riêng để kịp trả về response cho UI
    threading.Thread(target=kill_process, daemon=True).start()
    return jsonify({"success": True, "message": "Server đang khởi động lại..."})


@settings_bp.route("/api/keys", methods=["GET", "POST"])
def manage_api_keys():
    """Lấy hoặc lưu danh sách API keys."""
    if request.method == "GET":
        try:
            api_file = Path("config/API.txt")
            if api_file.exists():
                with open(api_file, "r", encoding="utf-8") as f:
                    content = f.read()
                return jsonify({"content": content})
            return jsonify({"content": ""})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # POST
    try:
        data = request.json
        keys_text = data.get("content", "")
        save_api_keys(keys_text)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/settings/app", methods=["GET", "POST"])
def manage_app_settings():
    """Đọc hoặc ghi trực tiếp file config/app.ini."""
    config_path = Path("config/app.ini")
    config = configparser.ConfigParser()
    config.optionxform = str  # Preserve case

    if request.method == "GET":
        try:
            if config_path.exists():
                config.read(config_path)
            
            config_dict = {
                section: dict(config.items(section))
                for section in config.sections()
            }
            return jsonify({"success": True, "config": config_dict})
        except Exception as e:
            logger.error(f"Error reading app.ini: {e}")
            return jsonify({"error": str(e)}), 500

    # POST method
    try:
        payload = request.json
        if not payload or "config" not in payload:
            return jsonify({"error": "Missing config payload"}), 400
        
        new_config_data = payload["config"]
        
        if config_path.exists():
            config.read(config_path)
            
        for section, items in new_config_data.items():
            if not isinstance(items, dict):
                continue
            if not config.has_section(section):
                config.add_section(section)
            for key, val in items.items():
                config.set(section, key, str(val))
                
        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)
            
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error writing app.ini: {e}")
        return jsonify({"error": str(e)}), 500
