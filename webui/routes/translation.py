# webui/routes/translation.py - v5.0.0
# Blueprint: Translation Worker, SSE Progress, Direct Translate

import json
import logging
from pathlib import Path
from datetime import datetime
from threading import Thread

from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context

from webui.helpers import (
    load_api_keys, load_prompts, save_prompts, calculate_stats,
    get_default_chunk_size, get_default_model, get_available_models,
)

logger = logging.getLogger(__name__)

translation_bp = Blueprint("translation", __name__)


def translate_worker(text, config, output_filename="translated", input_file_path=None):
    """Worker thread để dịch - dùng backend use case."""
    from webui import progress_queue, translation_memory
    import webui as _state
    from backend.infrastructure.progress.webui_progress_bridge import WebUIProgressBridge
    from backend.application.use_cases.translate_text_use_case import TranslateTextUseCase
    from backend.application.dto.translation_request import TranslationRequest
    from backend.infrastructure.config.api_key_service import ApiKeyService
    from backend.infrastructure.workspace.workspace_service import WorkspaceService

    try:
        from backend.infrastructure.providers.provider_service import ProviderService
        ws_service = WorkspaceService()

        provider_service = ProviderService()
        active_provider = provider_service.get_active_provider_config() or {}
        
        provider_type = active_provider.get("type", "gemini")
        if provider_type == "gemini":
            api_keys = active_provider.get("api_keys", [])
        else:
            api_key = active_provider.get("api_key")
            gateway_api_key = active_provider.get("gateway_api_key", "")
            api_keys = [api_key or gateway_api_key] if (api_key or gateway_api_key) else []

        if not api_keys or not api_keys[0]:
            progress_queue.put({
                "type": "error",
                "message": f"Không tìm thấy API keys cho provider {active_provider.get('name', provider_type)}",
            })
            return

        pdir = ws_service.get_project_dir("default-project")
        out_path = pdir / "translated" / output_filename

        base_url = active_provider.get("base_url")
        gateway_api_key = active_provider.get("gateway_api_key", "")
        credential_mode = active_provider.get("credential_mode", "default")
        
        from backend.infrastructure.providers.endpoint_policy import classify_endpoint
        policy = classify_endpoint(base_url)
        provider_kind = policy.provider_kind
        
        worker_config = config.copy() if hasattr(config, "copy") else dict(config)
        worker_config["provider_type"] = provider_type
        worker_config["provider_kind"] = provider_kind
        worker_config["base_url"] = base_url
        worker_config["gateway_api_key"] = gateway_api_key
        worker_config["credential_mode"] = credential_mode
        worker_config["provider_api_key"] = active_provider.get("api_key", "")
        worker_config["provider_id"] = active_provider.get("id", "")

        # Model validation
        model_from_req = worker_config.get("model_name")
        if not model_from_req:
            model_from_req = active_provider.get("default_model") or "gpt-4o-mini"
            
        model_from_req = policy.normalize_model(model_from_req)
        if not policy.validate_model(model_from_req):
            progress_queue.put({
                "type": "error",
                "message": f"Model '{model_from_req}' không hợp lệ với provider '{provider_kind}'",
            })
            return

        worker_config["model_name"] = model_from_req
        worker_config["qa_model"] = model_from_req

        bridge = WebUIProgressBridge(progress_queue)

        use_case = TranslateTextUseCase(
            api_keys=api_keys,
            config=worker_config,
        )

        request = TranslationRequest(
            text=text,
            output_filename=output_filename,
            output_file_path=out_path,
            translation_memory=translation_memory,
        )

        result = use_case.execute(request, progress_callback=bridge.create_callback())

        if result.success and result.output_path:
            _state.translation_result = {
                "text": result.translated_text,
                "filename": output_filename,
                "path": result.output_path,
            }

    except Exception as e:
        logger.error(f"Translation error: {e}", exc_info=True)
        from webui import progress_queue
        progress_queue.put({"type": "error", "message": f"Lỗi: {str(e)}"})


@translation_bp.route("/")
def index():
    """Render main page."""
    default_model = get_default_model()
    available_models = get_available_models()

    if default_model not in available_models:
        available_models.insert(0, default_model)

    prompts = load_prompts()

    from webui.helpers import get_app_version
    app_version = get_app_version()

    import configparser
    from pathlib import Path
    from backend.infrastructure.providers.provider_service import ProviderService

    provider_service = ProviderService()
    prov_data = provider_service.load_providers()
    providers_list = prov_data.get("providers", [])
    active_id = prov_data.get("active_id", "")
    active_prov = provider_service.get_active_provider_config() or {}
    active_provider_type = active_prov.get("type", "gemini")

    gemini_provs = [p for p in providers_list if p.get("type") == "gemini"]
    gemini_keys = []
    for gp in gemini_provs:
        gemini_keys.extend(gp.get("api_keys", []))
    gemini_api_keys_text = "\n".join(gemini_keys)

    openai_providers = [p for p in providers_list if p.get("type") == "openai"]
    active_openai = active_prov if active_prov.get("type") == "openai" else (openai_providers[0] if openai_providers else {})

    app_ini_path = Path("config/app.ini")
    app_cfg = configparser.ConfigParser()
    app_cfg.optionxform = str
    if app_ini_path.exists():
        app_cfg.read(app_ini_path)
    
    app_config_dict = {
        section: dict(app_cfg.items(section))
        for section in app_cfg.sections()
    }

    return render_template(
        "index.html",
        default_chunk=get_default_chunk_size(),
        default_model=default_model,
        available_models=json.dumps(available_models),
        prompts_json=json.dumps(prompts),
        app_version=app_version,
        active_provider_type=active_provider_type,
        gemini_api_keys_text=gemini_api_keys_text,
        openai_providers=openai_providers,
        active_openai=active_openai,
        active_id=active_id,
        app_config=app_config_dict,
    )





@translation_bp.route("/api/progress")
def progress_stream():
    """SSE endpoint cho real-time progress."""
    from webui import progress_queue

    def generate():
        while True:
            try:
                data = progress_queue.get(timeout=60)
                yield f"data: {json.dumps(data)}\n\n"

                if data["type"] in ["complete", "error", "cancelled"]:
                    break
            except Exception:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@translation_bp.route("/api/translate/cancel", methods=["POST"])
def cancel_translation():
    """Compatibility shim: chỉ cancel khi có job_id. KHÔNG BAO GIỜ cancel toàn cục."""
    from backend.infrastructure.progress.runtime_state import RuntimeState
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id") or request.args.get("job_id")
    if not job_id:
        return jsonify({
            "error": "Thiếu job_id — không thể cancel toàn cục",
            "code": "job_id_required",
        }), 400
    state = RuntimeState()
    state.request_cancel(job_id)
    # GIỮ LẠI: SSE legacy của trang dịch đơn lẻ đọc từ progress_queue (generate() cùng file).
    # Bỏ dòng này là mất phản hồi "đã dừng" trên UI dịch đơn — đây là hồi quy UX, không phải dọn rác.
    from webui import progress_queue
    progress_queue.put({"type": "cancelled", "message": "Đã dừng theo yêu cầu"})
    return jsonify({"success": True, "message": "Đã gửi yêu cầu dừng"})


@translation_bp.route("/api/translate-text", methods=["POST"])
def translate_text():
    """Dịch text trực tiếp (cho Retranslate/Correction)."""
    try:
        from plugins.translation.translator import robust_translate
        from services.api_service import ApiManager

        data = request.json
        text = data.get("text", "")
        mode = data.get("mode", "main")
        prompts = data.get("prompts", {})
        model = data.get("model")
        temperature = float(data.get("temperature", 1.0))

        if not text.strip():
            return jsonify({"error": "Vui lòng nhập văn bản"}), 400

        if not prompts:
            prompts = load_prompts()

        prompt_key = mode if mode in prompts else "main"
        prompt = prompts.get(prompt_key, prompts.get("main", ""))

        if not prompt:
            prompt = load_prompts().get("main", "")

        from backend.infrastructure.providers.provider_service import ProviderService
        from backend.infrastructure.providers.endpoint_policy import classify_endpoint
        
        provider_service = ProviderService()
        active_provider = provider_service.get_active_provider_config() or {}
        
        provider_type = active_provider.get("type", "gemini")
        base_url = active_provider.get("base_url")
        gateway_api_key = active_provider.get("gateway_api_key", "")
        credential_mode = active_provider.get("credential_mode", "default")
        
        policy = classify_endpoint(base_url)
        provider_kind = policy.provider_kind

        if not model:
            model = active_provider.get("default_model") or (
                "gemini-3-flash-preview" if provider_type == "gemini" else "gpt-4o-mini"
            )
        
        if provider_type == "gemini":
            api_keys = active_provider.get("api_keys", [])
        else:
            api_key = active_provider.get("api_key")
            api_keys = [api_key or gateway_api_key] if (api_key or gateway_api_key) else []
            
        if not api_keys or not api_keys[0]:
            return jsonify({"error": f"Không tìm thấy API keys cho provider {active_provider.get('name', provider_type)}"}), 400

        api_manager = ApiManager(api_keys)
        
        from webui.helpers import load_config
        app_config = load_config()

        model = policy.normalize_model(model)
        if not policy.validate_model(model):
            return jsonify({"error": f"Model {model} không hợp lệ với provider {provider_kind}"}), 400

        config_params = {
            "model_name": model,
            "qa_model": model,
            "temperature": temperature,
            "chunk_size": 22000,
            "provider_type": provider_type,
            "provider_kind": provider_kind,
            "base_url": base_url,
            "gateway_api_key": gateway_api_key,
            "credential_mode": credential_mode,
            "provider_api_key": active_provider.get("api_key", ""),
            "provider_id": active_provider.get("id", ""),
        }

        translated, stats, log = robust_translate(
            text, api_manager, {"main": prompt}, config_params
        )

        return jsonify({"translated": translated, "mode": mode, "chars": len(text)})

    except Exception as e:
        logger.error(f"Translate text error: {e}")
        return jsonify({"error": str(e)}), 500
