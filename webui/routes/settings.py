# webui/routes/settings.py - v5.0.0
# Blueprint: Models, Config, Stats, Cache, Token Estimation

import re
import logging
from pathlib import Path

from flask import Blueprint, request, jsonify

from webui.helpers import (
    load_api_keys, get_default_chunk_size, get_default_model,
    get_available_models, calculate_stats,
)

logger = logging.getLogger(__name__)

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/models")
def get_models():
    """Lấy danh sách models khả dụng."""
    try:
        models = get_available_models()
        default_model = get_default_model()
        return jsonify({"models": models, "default": default_model})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/model-info/<path:model_name>")
def get_model_info(model_name):
    """Lấy thông tin chi tiết của model (token limits, rate limits, availability)."""
    try:
        api_keys = load_api_keys()
        if not api_keys:
            return jsonify({"error": "Không tìm thấy API key"}), 400

        from google import genai

        client = genai.Client(api_key=api_keys[0])

        full_name = model_name if model_name.startswith("models/") else f"models/{model_name}"

        try:
            model = client.models.get(model=full_name)
        except Exception as e:
            return jsonify({"error": f"Không tìm thấy model: {model_name}", "detail": str(e)}), 404

        info = {
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

        raw_limits = getattr(model, "rate_limits", None) or getattr(model, "limits", None)
        if raw_limits:
            if isinstance(raw_limits, dict):
                for k, v in raw_limits.items():
                    rate_limits[k.upper()] = v
            elif isinstance(raw_limits, list):
                for item in raw_limits:
                    if hasattr(item, "key") and hasattr(item, "value"):
                        rate_limits[item.key.upper()] = item.value
                    elif isinstance(item, dict):
                        for k, v in item.items():
                            rate_limits[k.upper()] = v

        info["rate_limits"] = rate_limits

        all_attrs = {}
        for attr in dir(model):
            if not attr.startswith("_"):
                try:
                    val = getattr(model, attr)
                    if not callable(val) and val is not None:
                        all_attrs[attr] = str(val)[:200]
                except Exception:
                    pass
        info["_raw_attrs"] = all_attrs

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


@settings_bp.route("/api/remove-done", methods=["POST"])
def remove_done_file():
    """Xóa file khỏi thư mục done."""
    data = request.json
    filename = data.get("filename")

    if not filename:
        return jsonify({"error": "Thiếu filename"}), 400

    done_dir = Path("workspace/done")
    file_path = done_dir / filename

    if not file_path.exists():
        return jsonify({"error": "File không tồn tại"}), 404

    file_path.unlink()

    return jsonify({"success": True})
