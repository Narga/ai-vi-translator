# plugins/translation/translator.py - v4.0.0
# Tác giả: Narga
# Chức năng: Lõi gọi API và quy trình robust_translate (dịch - kiểm độ dài - sửa Hán tự - chuẩn hóa - cache).
#
# Nâng cấp v4.0.0:
# - Tích hợp GenAIClient wrapper hỗ trợ cả google-genai SDK mới và google-generativeai SDK cũ
# - Tích hợp emergency_stop module thực sự (thay vì placeholder)
# - Support gemini-3-flash-preview với thinking_level parameter
# - Tối ưu cho 20 RPD/key với AdaptiveRateLimiter

import time
import logging
import re
from typing import Optional, Tuple, Dict, Any

# Import GenAI Client wrapper (hỗ trợ cả SDK mới và cũ)
from services.genai_client import GenAIClient, SDKType

# Import services
from services.api_service import ApiManager

# Import emergency stop module
from services.emergency_stop import check_emergency_stop, EmergencyStopError


# Cache GenAI clients theo API key và config để tránh khởi tạo lại
_client_cache: Dict[str, Any] = {}


def _get_client(api_key: str, config: Dict[str, Any]) -> Any:
    global _client_cache

    provider_type = config.get("provider_type", "gemini")
    provider_kind = config.get("provider_kind", provider_type)
    base_url = config.get("base_url") or ""
    default_model = config.get("model_name", "gemini-3-flash-preview")
    thinking_level = config.get("thinking_level", "MEDIUM")
    gateway_api_key = config.get("gateway_api_key", "")
    credential_mode = config.get("credential_mode", "default")
    provider_api_key = config.get("provider_api_key", api_key)

    import hashlib
    header_str = f"{api_key}_{gateway_api_key}_{credential_mode}"
    header_hash = hashlib.md5(header_str.encode()).hexdigest()

    cache_key = f"{provider_kind}_{base_url}_{default_model}_{header_hash}"

    if cache_key not in _client_cache:
        if provider_type == "openai":
            from services.openai_client import OpenAIClient
            _client_cache[cache_key] = OpenAIClient(
                api_key=provider_api_key,
                base_url=base_url,
                default_model=default_model,
                gateway_api_key=gateway_api_key,
                credential_mode=credential_mode,
            )
        else:
            from services.genai_client import GenAIClient
            _client_cache[cache_key] = GenAIClient(
                api_key=api_key, default_model=default_model, thinking_level=thinking_level
            )

    return _client_cache[cache_key]


def _call_api(
    text_to_process: str,
    prompt: str,
    api_manager: ApiManager,
    config: Dict[str, Any],
    model_override: Optional[str] = None,
) -> Tuple[Optional[str], str, str]:
    """
    Hàm gọi API chung: lấy key khả dụng, cấu hình model/temperature, gọi API và xử lý lỗi.

    Hỗ trợ cả google-genai SDK mới và google-generativeai SDK cũ thông qua GenAIClient.

    Args:
        text_to_process (str): Văn bản cần gửi cho AI xử lý
        prompt (str): Prompt chỉ thị cho AI
        api_manager (ApiManager): Quản lý API keys
        config (Dict[str, Any]): Cấu hình (model, temperature, delay, sdk, thinking_level,...)
        model_override (Optional[str]): Model ghi đè (dùng cho QA/correction)

    Returns:
        Tuple[Optional[str], str, str]: (kết_quả_text, status, api_key_dùng)
            status ∈ {'success', 'all_keys_exhausted', 'api_error', 'stopped'}
    """
    max_attempts_total = max(3, len(api_manager._key_list) * 3)
    last_error_msg = "api_error"
    empty_streak = 0  # Số lần liên tiếp nhận empty response (không phải lỗi API thật sự)

    for attempt in range(max_attempts_total):
        # Kiểm tra emergency stop
        if check_emergency_stop():
            logging.warning("⛔ Translation interrupted by emergency stop")
            return None, "stopped", "unknown"

        # Acquire RPM token trước khi gọi API
        if not api_manager.acquire_rpm(blocking=True, timeout=120.0):
            logging.warning("RPM limit timeout, waiting 10s...")
            time.sleep(10.0)
            continue

        api_key = api_manager.get_next_available_key()
        if not api_key:
            if api_manager.all_keys_exhausted():
                logging.critical("🚨 Tất cả API keys đã hết quota hoặc trong cooldown.")
                return None, "all_keys_exhausted", "unknown"
            logging.warning("Không có key khả dụng, đợi 10s...")
            time.sleep(10.0)
            continue

        try:
            # Tôn trọng request delay
            delay = float(config.get("request_delay", 0.0))
            if delay > 0:
                time.sleep(delay)

            # Lấy client từ cache
            client = _get_client(api_key, config)

            # Build prompt đầy đủ (Không thêm header ẩn theo yêu cầu người dùng)
            full_prompt = f"{prompt}\n\n{text_to_process}"

            # Gọi API
            model_name = model_override or config.get(
                "model_name", "gemini-3-flash-preview"
            )
            temperature = float(
                config.get("temperature", 1.0)
            )  # Gemini 3 khuyến nghị 1.0
            thinking_level = config.get("thinking_level", "MEDIUM")

            request_kwargs = {"prompt": full_prompt, "model": model_name, "temperature": temperature}
            if config.get("provider_type", "gemini") != "openai":
                request_kwargs["thinking_level"] = thinking_level
            result_text, status = client.generate_content(**request_kwargs)

            if status == "success" and result_text:
                api_manager.mark_success(api_key)
                return result_text.strip(), "success", api_key
            elif status == "empty_response":
                empty_streak += 1
                logging.warning(f"Empty response từ API (attempt {attempt + 1}, streak {empty_streak})")
                if empty_streak >= 2:
                    logging.error(f"Nhận empty response {empty_streak} lần liên tiếp, dừng retry sớm.")
                    return None, "upstream_empty", api_key
                continue
            else:
                # A provider error status is not an empty response. Preserve it so
                # callers can fail the chunk and retain its checkpoint.
                return None, status or "api_error", api_key

        except EmergencyStopError:
            return None, "stopped", api_key
        except Exception as e:
            try:
                from backend.infrastructure.providers.endpoint_policy import ProviderRequestError
            except ImportError:
                ProviderRequestError = type('DummyProviderRequestError', (Exception,), {})

            empty_streak = 0  # Lỗi API thật sự -> reset streak
            
            if isinstance(e, ProviderRequestError):
                if not e.retryable:
                    logging.error(f"Lỗi không thể retry từ provider: {e.safe_message}")
                    if e.http_status == 451 or e.error_code == "censorship_blocked":
                        return None, "censorship_blocked", api_key
                    if e.http_status in (401, 403):
                        return None, "auth_error", api_key
                    if e.http_status == 404:
                        return None, "model_not_found", api_key
                    if e.http_status in (400, 422):
                        return None, "invalid_request", api_key
                    return None, f"api_error:{e.http_status}", api_key
                
                # Lỗi có thể retry
                error_msg = e.safe_message
                last_error_msg = f"Lỗi (retryable): {error_msg}"
                logging.error(f"Lỗi API với key ...{api_key[-4:]}: {error_msg[:200]}")
                should_retry, delay = api_manager.handle_api_error(api_key, error_msg)
            elif isinstance(e, ValueError):
                logging.error(f"Yêu cầu provider không hợp lệ: {e}")
                return None, "invalid_request", api_key
            else:
                # Lỗi khác (network, timeout, genai)
                error_msg = str(e)
                last_error_msg = f"Lỗi ngoại lệ: {error_msg}"
                logging.error(f"Lỗi ngoại lệ với key ...{api_key[-4:]}: {error_msg[:200]}")
                should_retry, delay = api_manager.handle_api_error(api_key, error_msg)

            if should_retry:
                logging.info(f"Đợi {delay:.1f}s trước khi thử lại...")
                if delay > 0:
                    time.sleep(delay)
            else:
                continue

    return None, last_error_msg, "unknown"


def robust_translate(
    original_chunk: str,
    api_manager: ApiManager,
    prompts: Dict[str, str],
    config_params: Dict[str, Any],
    previous_chunk_context: str = "",
    normalizer: Any = None,
) -> Tuple[str, str, str]:
    """
    Quy trình dịch chuẩn cho mỗi chunk (v7.0.0):

    1) Dịch 1 lần duy nhất bằng main prompt
    2) Chuẩn hóa văn bản
    3) Trả kết quả

    Args:
        original_chunk (str): Nội dung chunk gốc cần dịch
        api_manager (ApiManager): Quản lý API keys
        prompts (Dict[str, str]): Dictionary chứa các prompt
        config_params (Dict[str, Any]): Cấu hình (model, temp,...)
        previous_chunk_context (str): Ngữ cảnh chunk trước
        normalizer (Any): TextNormalizer để chuẩn hóa văn bản

    Returns:
        Tuple[str, str, str]: (kết_quả_dịch, trạng_thái, api_key_đã_dùng)
    """
    # Prompt chính có ngữ cảnh
    main_prompt_template = prompts.get("main", "")
    main_prompt = main_prompt_template.replace(
        "{previous_chunk_context}", previous_chunk_context
    )

    logging.info("Bắt đầu dịch chunk...")

    # Dịch 1 lần duy nhất
    translated_text, status, api_key_used = _call_api(
        original_chunk, main_prompt, api_manager, config_params
    )

    if status != "success" or not translated_text:
        logging.error("Dịch chunk thất bại.")
        return "Dịch chunk thất bại.", status, api_key_used

    # Chuẩn hóa văn bản
    if normalizer:
        try:
            translated_text = normalizer.normalize(translated_text)
            logging.info("✅ Đã chuẩn hóa văn bản.")
        except Exception as e:
            logging.warning(f"⚠️ Lỗi khi chuẩn hóa văn bản: {e}")

    logging.info("✅ Chunk được dịch thành công!")

    return translated_text, "success", api_key_used
