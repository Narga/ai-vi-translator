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
from services.cache_service import TranslationCache

# Import emergency stop module
from services.emergency_stop import check_emergency_stop, EmergencyStopError


# Cache GenAI clients theo API key để tránh khởi tạo lại
_client_cache: Dict[str, GenAIClient] = {}


def _get_client(api_key: str, config: Dict[str, Any]) -> GenAIClient:
    """
    Lấy hoặc tạo GenAIClient cho API key (có cache).

    Args:
        api_key (str): API key
        config (Dict[str, Any]): Cấu hình chứa model và thinking_level

    Returns:
        GenAIClient: Client instance
    """
    global _client_cache

    default_model = config.get("model_name", "gemini-3-flash-preview")
    thinking_level = config.get("thinking_level", "MEDIUM")

    # Cache key chỉ dựa trên API key (SDK đã fixed là google-genai)
    cache_key = api_key

    if cache_key not in _client_cache:
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

            # Build prompt đầy đủ
            full_prompt = (
                f"{prompt}\n\n--- VĂN BẢN GỐC CẦN DỊCH ---\n\n{text_to_process}"
            )

            # Gọi API
            model_name = model_override or config.get(
                "model_name", "gemini-3-flash-preview"
            )
            temperature = float(
                config.get("temperature", 1.0)
            )  # Gemini 3 khuyến nghị 1.0
            thinking_level = config.get("thinking_level", "MEDIUM")

            result_text, status = client.generate_content(
                prompt=full_prompt,
                model=model_name,
                temperature=temperature,
                thinking_level=thinking_level,
            )

            if status == "success" and result_text:
                api_manager.mark_success(api_key)
                return result_text.strip(), "success", api_key
            else:
                logging.warning(f"Empty response từ API (attempt {attempt + 1})")
                continue

        except EmergencyStopError:
            return None, "stopped", api_key
        except Exception as e:
            error_msg = str(e)
            last_error_msg = f"Lỗi: {error_msg}"
            logging.error(f"Lỗi API với key ...{api_key[-4:]}: {error_msg[:200]}")
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
    cache: TranslationCache,
    prompts: Dict[str, str],
    config_params: Dict[str, Any],
    previous_chunk_context: str = "",
    normalizer: Any = None,
) -> Tuple[str, str, str]:
    """
    Quy trình dịch chuẩn cho mỗi chunk (v6.5.0 - Single Pass):

    1) Cache (khóa theo thành phần đầy đủ)
    2) Dịch 1 lần duy nhất bằng main prompt
    3) Chuẩn hóa văn bản
    4) Lưu cache & trả kết quả

    Không còn bước dịch lại tự động hay sửa lỗi ký tự — người dùng tự kiểm tra và dịch lại thủ công nếu cần.

    Args:
        original_chunk (str): Nội dung chunk gốc cần dịch
        api_manager (ApiManager): Quản lý API keys
        cache (TranslationCache): Quản lý cache
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

    # Cache với khóa theo thành phần đầy đủ
    cached_translation = cache.get_by_components(
        original_chunk, prompts, config_params, previous_chunk_context
    )

    if cached_translation:
        logging.info("✅ Sử dụng bản dịch từ cache.")
        return cached_translation, "success", "cache"

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

    cache.set_by_components(
        original_chunk, prompts, config_params, previous_chunk_context, translated_text
    )

    return translated_text, "success", api_key_used
