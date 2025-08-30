# src/translator.py - v2.0.0
# Tác giả: Narga
# Chức năng: Module lõi, chịu trách nhiệm gửi request đến API,
# xử lý lỗi, cache và triển khai các quy trình dịch phức hợp.

import os, google.generativeai as genai, time, hashlib, pickle, logging, re
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path
from threading import Lock

# Biểu thức chính quy để tìm ký tự tiếng Trung
CHINESE_CHAR_REGEX = re.compile("[\u4e00-\u9fff]")

class ApiManager:
    # ... (Nội dung không đổi)
    def __init__(self, api_keys: List[str]):
        if not api_keys: raise ValueError("Danh sách API key không được để trống trong config.ini.")
        self._keys = {key: 'available' for key in api_keys}; self._key_list = list(api_keys)
        self._current_key_index = 0; self._lock = Lock()
        logging.info(f"🔑 Đã nạp {len(self._keys)} API key.")
    def get_next_available_key(self) -> Optional[str]:
        with self._lock:
            for _ in range(len(self._key_list)):
                key = self._key_list[self._current_key_index]
                self._current_key_index = (self._current_key_index + 1) % len(self._key_list)
                if self._keys[key] == 'available': return key
            return None
    def mark_key_exhausted(self, api_key: str):
        with self._lock:
            if self._keys.get(api_key) == 'available':
                logging.warning(f"🚫 API Key ...{api_key[-4:]} đã hết quota. Tạm thời vô hiệu hóa.")
                self._keys[api_key] = 'exhausted'

class TranslationCache:
    # ... (Nội dung không đổi)
    def __init__(self, cache_dir: str, enabled: bool = True):
        self.enabled = enabled;
        if not self.enabled: logging.info("ℹ️ Cache dịch thuật đã bị tắt."); return
        self.cache_dir = cache_dir; os.makedirs(self.cache_dir, exist_ok=True); self._lock = Lock()
        logging.info(f"📦 Cache dịch thuật được bật. Thư mục: '{self.cache_dir}'")
    def _get_cache_key(self, text: str) -> str: return hashlib.md5(text.encode('utf-8')).hexdigest()
    def get(self, text: str) -> Optional[str]:
        if not self.enabled: return None
        cache_file = os.path.join(self.cache_dir, self._get_cache_key(text) + ".pkl")
        if os.path.exists(cache_file):
            try:
                with self._lock, open(cache_file, 'rb') as f: return pickle.load(f)
            except Exception: return None
        return None
    def set(self, text: str, translation: str):
        if not self.enabled: return
        cache_file = os.path.join(self.cache_dir, self._get_cache_key(text) + ".pkl")
        try:
            with self._lock, open(cache_file, 'wb') as f: pickle.dump(translation, f)
        except Exception as e: logging.warning(f"⚠️ Cảnh báo: Không thể lưu cache. Lỗi: {e}")

def _call_api(text_to_process: str, prompt: str, api_manager: ApiManager, config: Dict[str, Any], model_override: Optional[str] = None) -> Tuple[Optional[str], str]:
    """Hàm gọi API chung, xử lý lỗi mạng, quota và các vấn đề kết nối."""
    time.sleep(config['request_delay'])
    api_key = api_manager.get_next_available_key()
    if not api_key: return None, "all_keys_failed"
    try:
        genai.configure(api_key=api_key)
        model_name = model_override or config['model_name']
        model = genai.GenerativeModel(model_name)
        generation_config = genai.types.GenerationConfig(temperature=config['temperature'])
        full_prompt = f"{prompt}\n\n--- VĂN BẢN CẦN XỬ LÝ ---\n\n{text_to_process}"
        response = model.generate_content(full_prompt, generation_config=generation_config)
        return response.text.strip() if response and response.text else "", "success"
    except Exception as e:
        error_msg = str(e).lower()
        if "resource has been exhausted" in error_msg or "429" in error_msg:
            api_manager.mark_key_exhausted(api_key)
            logging.warning(f"Key ...{api_key[-4:]} đã hết quota. Đang chuyển key...")
        else:
            logging.error(f"Lỗi API không xác định với key ...{api_key[-4:]}: {e}")
        return None, "api_error"

def robust_translate(
    original_chunk: str, api_manager: ApiManager, cache: TranslationCache, 
    prompts: Dict[str, str], config_params: Dict[str, Any]
) -> Tuple[str, str]:
    """Quy trình dịch chính cho mỗi chunk, kết hợp các bước xác thực và sửa lỗi."""
    main_prompt = prompts.get('main', '')
    cache_key = main_prompt + original_chunk
    cached_translation = cache.get(cache_key)
    if cached_translation: return cached_translation, "success"

    logging.info("Bắt đầu dịch chunk...")
    translated_text, status = _call_api(original_chunk, main_prompt, api_manager, config_params)
    
    if status != "success" or not translated_text:
        logging.error("Dịch lần đầu thất bại."); return "Dịch chunk thất bại.", "failed"

    original_len, translated_len = len(original_chunk), len(translated_text)
    if original_len > 200 and not (config_params['min_length_ratio'] * original_len <= translated_len <= config_params['max_length_ratio'] * original_len):
        logging.warning(f"Phát hiện độ dài không hợp lệ. Dịch lại để chống cắt ngắn...")
        retranslate_prompt = prompts.get('retranslate', main_prompt)
        translated_text, status = _call_api(original_chunk, retranslate_prompt, api_manager, config_params, model_override=config_params['qa_model'])
        if status != "success" or not translated_text:
             logging.error("Dịch lại để chống cắt ngắn thất bại."); return "Dịch chunk thất bại.", "failed"

    refinement_count = 0
    correction_prompt = prompts.get('correction', '')
    while CHINESE_CHAR_REGEX.search(translated_text) and refinement_count < config_params['max_refinement_attempts']:
        refinement_count += 1
        logging.warning(f"Phát hiện ký tự Trung. Sửa lỗi lần {refinement_count}...")
        corrected_text, status = _call_api(translated_text, correction_prompt, api_manager, config_params, model_override=config_params['qa_model'])
        if status == "success" and corrected_text: translated_text = corrected_text
        else: logging.error(f"Sửa lỗi lần {refinement_count} thất bại.")
    
    if CHINESE_CHAR_REGEX.search(translated_text):
        logging.error(f"Không thể loại bỏ hết ký tự Trung."); return translated_text, "failed"
    else:
        logging.info("Chunk được dịch và làm sạch thành công!")
        cache.set(cache_key, translated_text); return translated_text, "success"

def consistency_check_chunk(
    chunk_file: Path, api_manager: ApiManager, cache: TranslationCache,
    prompts: Dict[str, str], config_params: Dict[str, Any]
):
    """Đọc một chunk đã dịch, kiểm tra và tinh chỉnh sự nhất quán, rồi ghi đè lại file."""
    try:
        translated_text = chunk_file.read_text(encoding='utf-8')
        if not translated_text.strip(): return

        consistency_prompt = prompts.get('consistency', '')
        if not consistency_prompt: return
        
        # Sửa lỗi SyntaxError: f-string
        logging.info(f"Kiểm tra sự nhất quán cho file {chunk_file.name}...")
        
        cache_key = consistency_prompt + translated_text
        cached_result = cache.get(cache_key)

        if cached_result:
            final_text = cached_result
        else:
            final_text, status = _call_api(translated_text, consistency_prompt, api_manager, config_params, model_override=config_params['consistency_model'])
            if status != "success" or not final_text:
                logging.warning(f"Không thể tinh chỉnh sự nhất quán cho {chunk_file.name}. Giữ nguyên bản gốc.")
                return
            cache.set(cache_key, final_text)

        chunk_file.write_text(final_text, encoding='utf-8')
    except Exception as e:
        logging.error(f"Lỗi trong quá trình kiểm tra sự nhất quán của file {chunk_file.name}: {e}")