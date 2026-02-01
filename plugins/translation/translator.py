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

# Regex phát hiện Hán tự (CJK Unified Ideographs)
CHINESE_CHAR_REGEX = re.compile(r'[\u4e00-\u9fff]')

# Cache GenAI clients theo API key để tránh khởi tạo lại
_client_cache: Dict[str, GenAIClient] = {}


def _get_client(api_key: str, config: Dict[str, Any]) -> GenAIClient:
    """
    Lấy hoặc tạo GenAIClient cho API key (có cache).
    
    Args:
        api_key (str): API key
        config (Dict[str, Any]): Cấu hình chứa SDK type và model
    
    Returns:
        GenAIClient: Client instance
    """
    global _client_cache
    
    sdk = config.get('sdk', 'google-genai')
    default_model = config.get('model_name', 'gemini-3-flash-preview')
    thinking_level = config.get('thinking_level', 'MEDIUM')
    
    cache_key = f"{api_key}_{sdk}"
    
    if cache_key not in _client_cache:
        _client_cache[cache_key] = GenAIClient(
            api_key=api_key,
            sdk=sdk,
            default_model=default_model,
            thinking_level=thinking_level
        )
    
    return _client_cache[cache_key]


def _call_api(
    text_to_process: str,
    prompt: str,
    api_manager: ApiManager,
    config: Dict[str, Any],
    model_override: Optional[str] = None
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

    for attempt in range(max_attempts_total):
        # Kiểm tra emergency stop
        if check_emergency_stop():
            logging.warning("⛔ Translation interrupted by emergency stop")
            return None, "stopped", "unknown"

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
            delay = float(config.get('request_delay', 0.0))
            if delay > 0:
                time.sleep(delay)

            # Lấy client từ cache
            client = _get_client(api_key, config)
            
            # Build prompt đầy đủ
            full_prompt = f"{prompt}\n\n--- VĂN BẢN GỐC CẦN DỊCH ---\n\n{text_to_process}"
            
            # Gọi API
            model_name = model_override or config.get('model_name', 'gemini-3-flash-preview')
            temperature = float(config.get('temperature', 1.0))  # Gemini 3 khuyến nghị 1.0
            thinking_level = config.get('thinking_level', 'MEDIUM')
            
            result_text, status = client.generate_content(
                prompt=full_prompt,
                model=model_name,
                temperature=temperature,
                thinking_level=thinking_level
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
            logging.error(f"Lỗi API với key ...{api_key[-4:]}: {error_msg[:200]}")
            should_retry, delay = api_manager.handle_api_error(api_key, error_msg)
            if should_retry:
                logging.info(f"Đợi {delay:.1f}s trước khi thử lại...")
                if delay > 0:
                    time.sleep(delay)
            else:
                continue

    return None, "api_error", "unknown"


def _call_api_with_original_context(
    translated_text: str,
    original_chunk: str,
    prompt_template: str,
    api_manager: ApiManager,
    config: Dict[str, Any],
    model_override: Optional[str] = None,
) -> Tuple[Optional[str], str, str]:
    """
    Gọi API với prompt correction song song (Parallel Context Correction - Phương án 2):
    gửi cả bản gốc (Trung) và bản dịch (Việt có lỗi) để AI đối chiếu và chỉ sửa phần lỗi.

    Args:
        translated_text (str): Bản dịch có lỗi (chứa ký tự Trung)
        original_chunk (str): Chunk gốc tiếng Trung
        prompt_template (str): Template correction prompt (chứa {original_chunk}, {contextual_snippet})
        api_manager (ApiManager): Quản lý API keys
        config (Dict[str, Any]): Cấu hình
        model_override (Optional[str]): Model ghi đè (thường dùng QA model)

    Returns:
        Tuple[Optional[str], str, str]: (kết_quả_text, status, api_key_dùng)
    """
    # Format prompt: thay thế placeholder
    prompt_filled = prompt_template.replace("{original_chunk}", original_chunk)
    prompt_filled = prompt_filled.replace("{contextual_snippet}", translated_text)

    max_attempts_total = max(3, len(api_manager._key_list) * 3)

    for _ in range(max_attempts_total):
        # Emergency stop check removed - handled by plugin manager

        api_key = api_manager.get_next_available_key()
        if not api_key:
            if api_manager.all_keys_exhausted():
                logging.critical("🚨 Tất cả API keys đã hết quota hoặc trong cooldown.")
                return None, "all_keys_exhausted", "unknown"
            logging.warning("Không có key khả dụng, đợi 10s...")
            time.sleep(10.0)
            continue

        try:
            delay = float(config.get('request_delay', 0.0))
            if delay > 0:
                time.sleep(delay)

            genai.configure(api_key=api_key)
            model_name = model_override or config['model_name']
            model = genai.GenerativeModel(model_name)
            generation_config = genai.types.GenerationConfig(
                temperature=float(config.get('temperature', 0.7))
            )

            # Prompt đã chứa cả gốc và dịch, gửi trực tiếp
            response = model.generate_content(prompt_filled, generation_config=generation_config)

            api_manager.mark_success(api_key)
            result_text = response.text.strip() if response and response.text else ""
            return result_text, "success", api_key

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Lỗi API với key ...{api_key[-4:]}: {error_msg[:200]}")
            should_retry, delay = api_manager.handle_api_error(api_key, error_msg)
            if should_retry:
                logging.info(f"Đợi {delay:.1f}s trước khi thử lại...")
                if delay > 0:
                    time.sleep(delay)
            else:
                continue

    return None, "api_error", "unknown"


def robust_translate(
    original_chunk: str,
    api_manager: ApiManager,
    cache: TranslationCache,
    prompts: Dict[str, str],
    config_params: Dict[str, Any],
    previous_chunk_context: str = "",
    normalizer: Any = None
) -> Tuple[str, str, str]:
    """
    Quy trình dịch chuẩn cho mỗi chunk (v2.8.2):

    1) Cache (khóa theo thành phần đầy đủ)
    2) Dịch lần đầu (Preventive Translation đã tích hợp trong prompt)
    3) Kiểm tra độ dài → dịch lại bằng QA model nếu lệch
    4) Sửa ký tự Trung còn sót:
       - Nếu correction_mode=parallel: gọi _call_api_with_original_context (gửi song song gốc+dịch)
       - Nếu correction_mode=legacy: gọi _call_api (chỉ gửi dịch lỗi)
    5) Chuẩn hóa văn bản
    6) Lưu cache & trả kết quả

    Args:
        original_chunk (str): Nội dung chunk gốc cần dịch
        api_manager (ApiManager): Quản lý API keys
        cache (TranslationCache): Quản lý cache
        prompts (Dict[str, str]): Dictionary chứa các prompt
        config_params (Dict[str, Any]): Cấu hình (model, temp, correction_mode,...)
        previous_chunk_context (str): Ngữ cảnh chunk trước
        normalizer (Any): TextNormalizer để chuẩn hóa văn bản

    Returns:
        Tuple[str, str, str]: (kết_quả_dịch, trạng_thái, api_key_đã_dùng)
    """
    # Prompt chính có ngữ cảnh
    main_prompt_template = prompts.get('main', '')
    main_prompt = main_prompt_template.replace('{previous_chunk_context}', previous_chunk_context)

    # Cache với khóa theo thành phần đầy đủ
    cached_translation = cache.get_by_components(
        original_chunk, prompts, config_params, previous_chunk_context
    )

    if cached_translation:
        logging.info("✅ Sử dụng bản dịch từ cache.")
        return cached_translation, "success", "cache"

    logging.info("Bắt đầu dịch chunk...")

    # Bước 1: Dịch lần đầu (Preventive Translation đã được tích hợp trong prompt)
    translated_text, status, api_key_used = _call_api(
        original_chunk, main_prompt, api_manager, config_params
    )

    if status != "success" or not translated_text:
        logging.error("Dịch lần đầu thất bại.")
        return "Dịch chunk thất bại.", "failed", api_key_used

    # Bước 2: Kiểm tra độ dài (chống cắt ngắn hoặc quá lệch)
    original_len = len(original_chunk)
    translated_len = len(translated_text)
    min_ratio = float(config_params.get('min_length_ratio', 0.5))
    max_ratio = float(config_params.get('max_length_ratio', 2.0))

    if original_len > 200 and not (min_ratio * original_len <= translated_len <= max_ratio * original_len):
        logging.warning(f"Phát hiện độ dài không hợp lệ ({translated_len}/{original_len}). Dịch lại để chống cắt ngắn...")
        retranslate_prompt_template = prompts.get('retranslate', main_prompt)
        retranslate_prompt = retranslate_prompt_template.replace('{previous_chunk_context}', previous_chunk_context)

        translated_text, status, api_key_used = _call_api(
            original_chunk, retranslate_prompt, api_manager, config_params, model_override=config_params.get('qa_model')
        )

        if status != "success" or not translated_text:
            logging.error("Dịch lại để chống cắt ngắn thất bại.")
            return "Dịch chunk thất bại.", "failed", api_key_used

    # Bước 3: Sửa ký tự Trung còn sót (chỉ khi INPUT_LANG=CN)
    input_lang = str(config_params.get('input_lang', 'CN')).upper()
    correction_mode = str(config_params.get('correction_mode', 'parallel')).lower()

    if input_lang == 'CN':
        refinement_count = 0
        correction_prompt_template = prompts.get('correction', '')
        max_refine = int(config_params.get('max_refinement_attempts', 2))

        while CHINESE_CHAR_REGEX.search(translated_text) and refinement_count < max_refine:
            refinement_count += 1

            if correction_mode == 'parallel':
                # Parallel Context Correction (Phương án 2): gửi song song gốc + dịch lỗi
                logging.warning(f"Phát hiện ký tự Trung. Parallel Correction lần {refinement_count}...")
                corrected_text, status, api_key_used = _call_api_with_original_context(
                    translated_text=translated_text,
                    original_chunk=original_chunk,
                    prompt_template=correction_prompt_template,
                    api_manager=api_manager,
                    config=config_params,
                    model_override=config_params.get('qa_model'),
                )
            else:
                # Legacy mode: chỉ gửi dịch lỗi
                logging.warning(f"Phát hiện ký tự Trung. Sửa lỗi (legacy) lần {refinement_count}...")
                corrected_text, status, api_key_used = _call_api(
                    translated_text, correction_prompt_template, api_manager, config_params,
                    model_override=config_params.get('qa_model')
                )

            if status == "success" and corrected_text:
                translated_text = corrected_text
            else:
                logging.error(f"Sửa lỗi lần {refinement_count} thất bại.")

        if CHINESE_CHAR_REGEX.search(translated_text):
            logging.error(f"Không thể loại bỏ hết ký tự Trung sau {max_refine} lần thử (mode: {correction_mode}).")

    # Bước 4: Chuẩn hóa văn bản
    if normalizer:
        try:
            translated_text = normalizer.normalize(translated_text)
            logging.info("✅ Đã chuẩn hóa văn bản.")
        except Exception as e:
            logging.warning(f"⚠️ Lỗi khi chuẩn hóa văn bản: {e}")

    logging.info("✅ Chunk được dịch và xử lý thành công!")

    cache.set_by_components(
        original_chunk, prompts, config_params, previous_chunk_context, translated_text
    )

    return translated_text, "success", api_key_used
