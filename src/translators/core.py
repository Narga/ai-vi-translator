# src/translators/core.py - v2.7.0
# Tác giả: Narga
# Chức năng: Lõi gọi API và quy trình robust_translate (dịch - kiểm độ dài - sửa Hán tự - chuẩn hóa - cache).
# Nâng cấp v2.7.0:
# - Hỗ trợ đính kèm project_file_uri (Gemini File API) vào nội dung gọi model.
# - Dùng khóa cache mới qua TranslationCache.build_key()/get_by_components()/set_by_components().

import time
import logging
import re
from typing import Optional, Tuple, Dict, Any, List

import google.generativeai as genai

from ..emergency_stop import check_emergency_stop
from .api_manager import ApiManager
from .cache_manager import TranslationCache

# Regex phát hiện Hán tự (CJK Unified Ideographs)
CHINESE_CHAR_REGEX = re.compile(r'[\u4e00-\u9fff]')

def _compose_contents(full_prompt: str, text_to_process: str, file_uri: Optional[str]) -> List[Dict[str, Any]]:
    """
    Tạo danh sách "content parts" cho Gemini:
    - Luôn có phần văn bản prompt.
    - Nếu có file_uri (gói nguồn đã upload), bổ sung phần file_data.
    - Cuối cùng là phần văn bản chứa nội dung cần dịch (hoặc trộn vào prompt nếu muốn).
    """
    parts: List[Dict[str, Any]] = [{"text": full_prompt}]
    if file_uri:
        parts.append({"file_data": {"file_uri": file_uri}})
    parts.append({"text": text_to_process})
    return parts

def _call_api(
    text_to_process: str,
    prompt: str,
    api_manager: ApiManager,
    config: Dict[str, Any],
    model_override: Optional[str] = None
) -> Tuple[Optional[str], str, str]:
    """
    Hàm gọi API chung:
      - Lấy key khả dụng, cấu hình model/temperature.
      - Gọi model.generate_content(contents).
      - Xử lý lỗi và backoff qua ApiManager.
    Trả về:
      (kết_quả_text, status, api_key_dùng)
      status ∈ {'success', 'all_keys_exhausted', 'api_error', 'stopped'}
    """
    max_attempts_total = max(3, len(api_manager._key_list) * 3)

    # Lấy file_uri từ cấu hình (nếu workflow đã chuẩn bị)
    project_file_uri = config.get("project_file_uri")

    for _ in range(max_attempts_total):
        if check_emergency_stop():
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
            # Tôn trọng RPM
            delay = float(config.get('request_delay', 0.0))
            if delay > 0:
                time.sleep(delay)

            genai.configure(api_key=api_key)
            model_name = model_override or config['model_name']
            model = genai.GenerativeModel(model_name)
            generation_config = genai.types.GenerationConfig(
                temperature=float(config.get('temperature', 0.7))
            )

            full_prompt = f"{prompt}\n\n--- VĂN BẢN GỐC CẦN DỊCH ---\n\n"
            contents = _compose_contents(full_prompt, text_to_process, project_file_uri)

            response = model.generate_content(contents, generation_config=generation_config)

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
    Quy trình dịch chuẩn cho mỗi chunk:
      1) Cache (khóa mới gắn với model/temperature/prompt/context/input)
      2) Dịch lần đầu
      3) Kiểm tra độ dài → dịch lại bằng QA model nếu lệch
      4) Sửa ký tự Trung còn sót (n lần)
      5) Chuẩn hóa văn bản
      6) Lưu cache & trả kết quả
    """
    # Prompt chính có ngữ cảnh
    main_prompt_template = prompts.get('main', '')
    main_prompt = main_prompt_template.replace('{previous_chunk_context}', previous_chunk_context)

    # Cache với khóa mới theo thành phần đầy đủ
    cached_translation = cache.get_by_components(
        original_chunk, prompts, config_params, previous_chunk_context
    )
    if cached_translation:
        logging.info("✅ Sử dụng bản dịch từ cache (khóa 2.7.0).")
        return cached_translation, "success", "cache"

    logging.info("Bắt đầu dịch chunk...")

    # Bước 1: Dịch lần đầu
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
    if input_lang == 'CN':
        refinement_count = 0
        correction_prompt = prompts.get('correction', '')
        max_refine = int(config_params.get('max_refinement_attempts', 2))
        while CHINESE_CHAR_REGEX.search(translated_text) and refinement_count < max_refine:
            refinement_count += 1
            logging.warning(f"Phát hiện ký tự Trung. Sửa lỗi lần {refinement_count}...")
            corrected_text, status, api_key_used = _call_api(
                translated_text, correction_prompt, api_manager, config_params,
                model_override=config_params.get('qa_model')
            )
            if status == "success" and corrected_text:
                translated_text = corrected_text
            else:
                logging.error(f"Sửa lỗi lần {refinement_count} thất bại.")
        if CHINESE_CHAR_REGEX.search(translated_text):
            logging.error(f"Không thể loại bỏ hết ký tự Trung sau {max_refine} lần thử.")

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
