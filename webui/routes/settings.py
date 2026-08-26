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
from webui.decorators import handle_route_errors

logger = logging.getLogger(__name__)

settings_bp = Blueprint("settings", __name__)


# ------------------------------------------------------------------
# DEPRECATED SHIM: /api/provider — sẽ xóa ở phiên bản tiếp theo
# Frontend cũ vẫn gọi endpoint này. Delegate sang ProviderService.
# ------------------------------------------------------------------

@settings_bp.route("/api/provider", methods=["GET", "POST"])
def legacy_provider_shim():
    """[DEPRECATED] Shim cho frontend cũ. Dùng /api/providers/* thay thế."""
    from backend.infrastructure.providers.provider_service import ProviderService
    provider_service = ProviderService()

    if request.method == "GET":
        active = provider_service.get_active_provider_config()
        if not active:
            return jsonify({"active": "gemini", "provider": {}})
        return jsonify({
            "active": active.get("type", "gemini"),
            "active_id": active.get("id", ""),
            "provider": active,
        })

    # POST: { "provider": "gemini" } hoặc { "provider": "openai" }
    data = request.json or {}
    provider_type = data.get("provider", "gemini")
    try:
        providers = provider_service.get_providers_by_type(provider_type)
        if not providers:
            return jsonify({"error": f"Không tìm thấy provider loại {provider_type}"}), 400
        # Kích hoạt provider đầu tiên của type đó
        provider_service.select_provider(providers[0]["id"])
        return jsonify({"success": True, "active": provider_type, "active_id": providers[0]["id"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@settings_bp.route("/api/models")
def get_models():
    """Lấy danh sách models khả dụng cho provider hiện tại hoặc provider chỉ định."""
    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        from backend.infrastructure.providers.endpoint_policy import classify_endpoint
        
        provider_service = ProviderService()
        active_provider = provider_service.get_active_provider_config() or {}
        
        # Lấy provider từ query param hoặc active provider
        requested_provider = request.args.get("provider")
        provider = requested_provider if requested_provider in ("gemini", "openai") else active_provider.get("type", "gemini")
        
        full = request.args.get("full", "false").lower() == "true"

        if provider == "openai":
            api_key = active_provider.get("api_key", "")
            base_url = active_provider.get("base_url") if (not requested_provider or requested_provider == active_provider.get("type")) else None
            gateway_api_key = active_provider.get("gateway_api_key", "") if (not requested_provider or requested_provider == active_provider.get("type")) else ""
            credential_mode = active_provider.get("credential_mode", "default") if (not requested_provider or requested_provider == active_provider.get("type")) else "default"

            policy = classify_endpoint(base_url)
            if not api_key and not gateway_api_key and policy.requires_api_key():
                return jsonify({"models": [], "error": "Chưa cấu hình OpenAI key", "provider": "openai"}), 200

            from services.openai_client import OpenAIClient
            client = OpenAIClient(
                api_key=api_key, 
                base_url=base_url,
                gateway_api_key=gateway_api_key,
                credential_mode=credential_mode
            )
            try:
                if full:
                    models = client.list_models_full()
                    # Prioritize free models
                    models.sort(key=lambda x: not x.get("is_free", False))
                else:
                    models = client.list_models()
            except Exception as e:
                logger.warning(f"Failed to fetch OpenAI models: {e}")
                def_m = active_provider.get("default_model") or get_default_model() or ""
                fallback_models = [{"id": def_m, "name": def_m}] if (full and def_m) else ([def_m] if def_m else [])
                return jsonify({
                    "models": fallback_models,
                    "default": def_m,
                    "provider": "openai",
                    "error": f"Không thể lấy danh sách models từ provider: {e}"
                }), 200
        else:
            # Gemini
            from webui.helpers import get_available_gemini_models
            def is_gemini_model_id(model_id):
                model_id = str(model_id or "")
                # OpenAI-compatible model ids often contain namespaces/pricing suffixes.
                # Gemini ids from Google are plain names such as gemini-* or gemma-*.
                return (
                    (model_id.startswith("gemini-") or model_id.startswith("gemma-"))
                    and "/" not in model_id
                    and ":" not in model_id
                )

            models = [m for m in get_available_gemini_models() if is_gemini_model_id(m)]
            if not models:
                from webui.helpers import AVAILABLE_GEMINI_MODELS
                models = AVAILABLE_GEMINI_MODELS.copy()
            if full:
                # Wrap Gemini names in objects for consistency
                models = [{"id": m, "name": m} for m in models]

        default_model = get_default_model()
        if provider == "gemini":
            model_ids = [m["id"] if isinstance(m, dict) else m for m in models]
            if default_model not in model_ids:
                default_model = model_ids[0] if model_ids else "gemini-2.0-flash-exp"
        return jsonify({"models": models, "default": default_model, "provider": provider})
    except Exception as e:
        logger.error(f"get_models error: {e}")
        return jsonify({"models": [], "default": "", "provider": provider if 'provider' in locals() else 'gemini', "error": str(e)}), 200





@settings_bp.route("/api/openai/models")
def get_openai_models():
    """Lấy danh sách models từ OpenAI/OpenRouter."""
    from webui.helpers import load_openai_key, get_openai_base_url, get_openai_model

    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        active = ProviderService().get_active_provider_config() or {}
        api_key = active.get("api_key") or load_openai_key()
        gateway_api_key = active.get("gateway_api_key", "")
        if not api_key and not gateway_api_key:
            return jsonify({"models": [], "error": "Chưa cấu hình OpenAI API key"}), 200

        full = request.args.get("full", "false").lower() == "true"

        from services.openai_client import OpenAIClient
        base_url = active.get("base_url") or get_openai_base_url()
        client = OpenAIClient(
            api_key=api_key,
            base_url=base_url,
            gateway_api_key=gateway_api_key,
            credential_mode=active.get("credential_mode", "default"),
        )
        
        if full:
            models = client.list_models_full()
            # Sort: free models first
            models.sort(key=lambda x: not x.get("is_free", False))
        else:
            models = client.list_models()

        default_model = get_openai_model()
        return jsonify({"models": models, "default": default_model, "provider": "openai"})
    except Exception as e:
        logger.error(f"get_openai_models error: {e}")
        return jsonify({"models": [], "error": str(e)}), 200


@settings_bp.route("/api/openai/config", methods=["POST"])
def save_openai_config():
    """Lưu cấu hình OpenAI (API key, base URL, model) vào providers.json."""
    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        data = request.json
        api_key = data.get("api_key", "").strip()
        gateway_api_key = data.get("gateway_api_key", "").strip()
        credential_mode = data.get("credential_mode", "default").strip()
        base_url = data.get("base_url", "").strip()
        model = data.get("model", "").strip()

        provider_service = ProviderService()
        # Tìm active OpenAI provider
        active = provider_service.get_active_provider_config()
        if not active or active.get("type") != "openai":
            # Fallback: tìm openai provider đầu tiên
            openai_providers = provider_service.get_providers_by_type("openai")
            if openai_providers:
                active = openai_providers[0]
            else:
                return jsonify({"error": "Không tìm thấy OpenAI provider"}), 400

        update_kwargs = {}
        if api_key:
            update_kwargs["api_key"] = api_key
        if gateway_api_key:
            update_kwargs["gateway_api_key"] = gateway_api_key
        if credential_mode:
            update_kwargs["credential_mode"] = credential_mode
        if base_url:
            update_kwargs["base_url"] = base_url
        if model:
            update_kwargs["default_model"] = model

        if update_kwargs:
            provider_service.update_provider(active["id"], **update_kwargs)

        # Kích hoạt provider này
        provider_service.select_provider(active["id"])

        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error saving OpenAI config: {e}")
        return jsonify({"error": str(e)}), 500



@settings_bp.route("/api/model-info/<path:model_name>")
def get_model_info(model_name):
    """Lấy thông tin chi tiết của model (Gemini hoặc OpenAI)."""
    from webui.helpers import get_active_provider
    requested_provider = request.args.get("provider")
    provider = requested_provider if requested_provider in ("gemini", "openai") else get_active_provider()

    try:
        if provider == "gemini":
            if "/" in model_name or ":" in model_name or not (
                model_name.startswith("gemini-") or model_name.startswith("gemma-")
            ):
                return jsonify({"error": f"Model không thuộc Gemini: {model_name}"}), 400

            gemini_fallback_info = {
                "gemini-2.0-flash-exp": (1048576, 8192),
                "gemini-2.0-flash": (1048576, 8192),
                "gemini-1.5-pro": (2097152, 8192),
                "gemini-1.5-flash": (1048576, 8192),
                "gemini-1.5-flash-8b": (1048576, 8192),
                "gemini-3-pro": (1048576, 8192),
                "gemini-3-flash": (1048576, 8192),
            }

            def fallback_gemini_info(detail=""):
                limits = gemini_fallback_info.get(model_name)
                if not limits:
                    return None
                input_limit, output_limit = limits
                return {
                    "provider": "gemini",
                    "name": model_name,
                    "display_name": model_name,
                    "description": "Thông tin fallback cục bộ; dùng khi Gemini API không trả metadata live.",
                    "input_token_limit": input_limit,
                    "output_token_limit": output_limit,
                    "input_token_display": f"{input_limit:,}",
                    "output_token_display": f"{output_limit:,}",
                    "rate_limits": {},
                    "fallback": True,
                    "detail": detail,
                }

            api_keys = load_api_keys()
            if not api_keys:
                fallback = fallback_gemini_info("Không tìm thấy API key Gemini")
                if fallback:
                    return jsonify(fallback)
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
                fallback = fallback_gemini_info(str(e))
                if fallback:
                    return jsonify(fallback)
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
@handle_route_errors
def get_config():
    """Lấy cấu hình mặc định."""
    from backend.infrastructure.config.app_config_service import AppConfigService
    config_service = AppConfigService()
    poll_interval = config_service.get("PROCESSING", "TASK_POLL_INTERVAL", 15, int)
    return jsonify({
        "default_chunk_size": get_default_chunk_size(),
        "default_model": get_default_model(),
        "available_models": get_available_models(),
        "task_poll_interval": poll_interval,
    })


@settings_bp.route("/api/stats")
@handle_route_errors
def get_stats():
    """Lấy thống kê hệ thống."""
    stats = calculate_stats()
    stats["status"] = "ready"
    return jsonify(stats)


@settings_bp.route("/api/cache/clear", methods=["POST"])
@handle_route_errors
def clear_cache():
    """[DEPRECATED] Cache endpoint - Translation Cache is no longer used."""
    return jsonify({
        "success": True,
        "deleted": 0,
        "message": "Translation Cache đã bị loại bỏ khỏi luồng dịch."
    })


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
@handle_route_errors
def manage_api_keys():
    """Lấy hoặc lưu danh sách API keys theo provider type (mặc định: GEMINI)."""
    section = request.args.get("section", "GEMINI").upper()

    if request.method == "GET":
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService()

        if section == "OPENAI":
            active = provider_service.get_active_provider_config()
            if active and active.get("type") == "openai":
                return jsonify({"content": active.get("api_key", ""), "provider_id": active["id"]})
            # Fallback: openai provider đầu tiên
            openai_providers = provider_service.get_providers_by_type("openai")
            if openai_providers:
                return jsonify({"content": openai_providers[0].get("api_key", ""), "provider_id": openai_providers[0]["id"]})
            return jsonify({"content": ""})

        # GEMINI (default)
        providers = provider_service.get_providers_by_type("gemini")
        all_keys = []
        for p in providers:
            all_keys.extend(p.get("api_keys", []))
        return jsonify({"content": "\n".join(all_keys)})

    # POST
    from backend.infrastructure.providers.provider_service import ProviderService
    provider_service = ProviderService()
    data = request.json
    keys_text = data.get("content", "")

    if section == "OPENAI":
        active = provider_service.get_active_provider_config()
        if active and active.get("type") == "openai":
            api_key = keys_text.strip()
            if api_key:
                provider_service.update_provider(active["id"], api_key=api_key)
            return jsonify({"success": True})
        return jsonify({"error": "Không có OpenAI provider đang active"}), 400

    # GEMINI
    keys = [k.strip() for k in keys_text.splitlines() if k.strip()]
    providers = provider_service.get_providers_by_type("gemini")
    if not providers:
        return jsonify({"error": "Không tìm thấy Gemini provider"}), 400
    provider_service.update_provider(providers[0]["id"], api_keys=keys)
    return jsonify({"success": True})
    
    # POST
    try:
        data = request.json
        keys_text = data.get("content", "")
        from webui.helpers import save_api_keys
        if save_api_keys(keys_text, section=section):
            return jsonify({"success": True})
        return jsonify({"error": "Không thể lưu file"}), 500
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
            # R2: section [MODEL] cũ đã deprecated, không chấp nhận ghi vào
            # providers.json từ app-config endpoint. Model/QA model phải được
            # lưu qua endpoint provider (PUT /api/providers/<id>/models).
            if section == "MODEL":
                return jsonify({
                    "error": "Section MODEL đã legacy; dùng endpoint provider riêng để lưu model"
                }), 400
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


@settings_bp.route("/api/logs", methods=["GET"])
def get_sys_logs():
    """Lấy danh sách các file log hệ thống."""
    try:
        log_dir = Path("workspace/logs")
        if not log_dir.exists():
            return jsonify([])
            
        logs = []
        for f in sorted(log_dir.glob("*.log"), reverse=True):
            size = f.stat().st_size
            logs.append({
                "filename": f.name,
                "size": size,
                "size_display": f"{size/1024:.1f} KB" if size < 1048576 else f"{size/1048576:.1f} MB",
                "mtime": f.stat().st_mtime
            })
        return jsonify(logs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/logs/<filename>", methods=["GET", "DELETE"])
def manage_sys_log(filename):
    """Đọc nội dung hoặc xóa file log."""
    try:
        log_dir = Path("workspace/logs")
        log_path = log_dir / filename
        
        if not log_path.exists():
            return jsonify({"error": "File log không tồn tại"}), 404
            
        # Prevent path traversal
        if log_path.resolve().parent != log_dir.resolve():
            return jsonify({"error": "Path không hợp lệ"}), 403

        if request.method == "DELETE":
            log_path.unlink()
            return jsonify({"success": True})
            
        # GET method - Đọc content log
        content = log_path.read_text(encoding="utf-8", errors="replace")
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# /api/providers/* — Multi-provider CRUD endpoints (v7.3.0)
# ------------------------------------------------------------------

@settings_bp.route("/api/providers", methods=["GET"])
@handle_route_errors
def list_providers():
    """Danh sách tất cả providers với API key đã mask.

    R3: KHÔNG trả về plaintext API key về browser. Mỗi provider chỉ trả
    metadata an toàn: has_api_key, key_count, api_key_last4, base_url, etc.
    Caller muốn update key thì dùng endpoint PUT /api/providers/<id> riêng.
    """
    from backend.infrastructure.providers.provider_service import ProviderService
    provider_service = ProviderService()
    data = provider_service.load_providers()
    masked_providers = []
    for p in data.get("providers", []):
        item = {
            "id": p.get("id"),
            "type": p.get("type"),
            "name": p.get("name"),
            "default_model": p.get("default_model", ""),
            "qa_model": p.get("qa_model", ""),
        }
        if p.get("type") == "gemini":
            keys = p.get("api_keys") or []
            item["has_api_key"] = bool(keys)
            item["key_count"] = len(keys)
            item["api_key_last4"] = [
                f"...{k[-4:]}" if len(k) >= 8 else "(set)" for k in keys
            ]
        else:
            api_key = p.get("api_key", "")
            gateway_key = p.get("gateway_api_key", "")
            item["base_url"] = p.get("base_url", "")
            item["credential_mode"] = p.get("credential_mode", "default")
            item["has_api_key"] = bool(api_key)
            item["has_gateway_api_key"] = bool(gateway_key)
            item["api_key_last4"] = (
                f"...{api_key[-4:]}" if len(api_key) >= 8
                else ("(set)" if api_key else "")
            )
        masked_providers.append(item)
    return jsonify({
        "active_id": data.get("active_id", "gemini-default"),
        "providers": masked_providers,
    })


@settings_bp.route("/api/providers", methods=["POST"])
@handle_route_errors
def create_provider():
    """Tạo provider mới."""
    from backend.infrastructure.providers.provider_service import ProviderService
    data = request.json
    name = data.get("name", "").strip()
    type_ = data.get("type", "openai")
    if not name:
        return jsonify({"error": "Tên provider không được để trống"}), 400
    try:
        provider_service = ProviderService()
        provider = provider_service.add_provider(name=name, type=type_)
        return jsonify({"success": True, "provider": provider})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@settings_bp.route("/api/providers/<provider_id>", methods=["PUT"])
@handle_route_errors
def update_provider(provider_id):
    """Cập nhật provider."""
    from backend.infrastructure.providers.provider_service import ProviderService
    data = request.json
    try:
        provider_service = ProviderService()
        # Không cho update gemini-default name/type
        if provider_id == "gemini-default" and ("name" in data or "type" in data):
            pass  # Cho phép update name, nhưng không cho đổi type
        provider = provider_service.update_provider(provider_id, **data)
        return jsonify({"success": True, "provider": provider})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@settings_bp.route("/api/providers/<provider_id>", methods=["DELETE"])
@handle_route_errors
def delete_provider(provider_id):
    """Xóa provider."""
    from backend.infrastructure.providers.provider_service import ProviderService
    try:
        provider_service = ProviderService()
        provider_service.delete_provider(provider_id)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@settings_bp.route("/api/providers/select", methods=["POST"])
@handle_route_errors
def select_provider():
    """Kích hoạt provider theo id."""
    from backend.infrastructure.providers.provider_service import ProviderService
    data = request.json
    active_id = data.get("active_id", "").strip()
    if not active_id:
        return jsonify({"error": "active_id không được để trống"}), 400
    try:
        provider_service = ProviderService()
        provider_service.select_provider(active_id)
        return jsonify({"success": True, "active_id": active_id})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
