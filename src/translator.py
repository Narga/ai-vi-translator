# src/translator.py - v2.0.1
# Tác giả: Narga
# Sửa lỗi: Bổ sung các phần thân và import bị thiếu.

import os, google.generativeai as genai, time, hashlib, pickle, logging, re
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path
from threading import Lock
from .emergency_stop import check_emergency_stop

CHINESE_CHAR_REGEX = re.compile("[\u4e00-\u9fff]")

class SmartRateLimiter:
    """Điều tiết tần suất gọi API một cách thông minh."""
    def __init__(self):
        self.failure_count = {}
        self.cool_down_until = {}
        self._lock = Lock()
        
    def should_retry(self, api_key: str, error: str) -> Tuple[bool, float]:
        with self._lock:
            current_time = time.time()
            if current_time < self.cool_down_until.get(api_key, 0):
                return False, self.cool_down_until[api_key] - current_time

            error_lower = error.lower()
            failures = self.failure_count.get(api_key, 0) + 1
            self.failure_count[api_key] = failures

            if any(kw in error_lower for kw in ["rate limit", "quota", "429", "resource_exhausted"]):
                if failures > 5:
                    self.cool_down_until[api_key] = current_time + 1800
                    logging.warning(f"Key ...{api_key[-4:]} vào cooldown 30 phút do lỗi quota.")
                    return False, 1800
                delay = min(15 * (2 ** (failures - 1)), 120)
                logging.warning(f"Lỗi quota, thử lại sau {delay}s...")
                return True, delay
            
            if failures > 2:
                return False, 0
            
            return True, 5.0
    
    def mark_success(self, api_key: str):
        with self._lock:
            if api_key in self.failure_count: self.failure_count[api_key] = 0
            if api_key in self.cool_down_until: del self.cool_down_until[api_key]

class ApiManager:
    """Quản lý API key, tích hợp SmartRateLimiter."""
    def __init__(self, api_keys: List[str]):
        if not api_keys:
            raise ValueError("Danh sách API key không được để trống trong config.ini.")
        self._keys = {key: 'available' for key in api_keys}
        self._key_list = list(api_keys)
        self._current_key_index = 0
        self._lock = Lock()
        self._rate_limiter = SmartRateLimiter()
        logging.info(f"🔑 Đã nạp {len(self._keys)} API key.")
    
    def get_next_available_key(self) -> Optional[str]:
        with self._lock:
            available_keys = [k for k, v in self._keys.items() if v == 'available' and time.time() >= self._rate_limiter.cool_down_until.get(k, 0)]
            if not available_keys: return None
            
            start_index = self._current_key_index
            while True:
                key = self._key_list[self._current_key_index]
                self._current_key_index = (self._current_key_index + 1) % len(self._key_list)
                if key in available_keys:
                    return key
                if self._current_key_index == start_index:
                    return None
    
    def handle_api_error(self, api_key: str, error_msg: str) -> Tuple[bool, float]:
        return self._rate_limiter.should_retry(api_key, error_msg)

    def mark_success(self, api_key: str):
        self._rate_limiter.mark_success(api_key)

class TranslationCache:
    """Quản lý việc cache các bản dịch."""
    def __init__(self, cache_dir: str, enabled: bool = True):
        self.enabled = enabled
        if not self.enabled: logging.info("ℹ️ Cache dịch thuật đã bị tắt."); return
        self.cache_dir = cache_dir; os.makedirs(self.cache_dir, exist_ok=True); self._lock = Lock()
        logging.info(f"📦 Cache dịch thuật được bật. Thư mục: '{self.cache_dir}'")

    def _get_cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

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
    """Hàm gọi API chung, được nâng cấp với logic retry."""
    max_attempts_total = len(api_manager._key_list) * 3
    for _ in range(max_attempts_total):
        if check_emergency_stop(): return None, "stopped"
        
        api_key = api_manager.get_next_available_key()
        if not api_key: return None, "all_keys_failed"
        
        try:
            time.sleep(config['request_delay'])
            genai.configure(api_key=api_key)
            model_name = model_override or config['model_name']
            model = genai.GenerativeModel(model_name)
            generation_config = genai.types.GenerationConfig(temperature=config['temperature'])
            full_prompt = f"{prompt}\n\n--- VĂN BẢN CẦN XỬ LÝ ---\n\n{text_to_process}"
            response = model.generate_content(full_prompt, generation_config=generation_config)
            
            api_manager.mark_success(api_key)
            return response.text.strip() if response and response.text else "", "success"
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Lỗi API với key ...{api_key[-4:]}: {error_msg[:200]}")
            should_retry, delay = api_manager.handle_api_error(api_key, error_msg)
            if should_retry:
                logging.info(f"Đợi {delay:.1f}s trước khi thử lại...")
                time.sleep(delay)
            else:
                continue
    
    return None, "api_error"

def robust_translate(
    original_chunk: str, api_manager: ApiManager, cache: TranslationCache, 
    prompts: Dict[str, str], config_params: Dict[str, Any]
) -> Tuple[str, str]:
    """Quy trình dịch chính cho mỗi chunk."""
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
    """Đọc một chunk đã dịch, kiểm tra sự nhất quán và ghi đè lại file."""
    try:
        translated_text = chunk_file.read_text(encoding='utf-8')
        if not translated_text.strip(): return

        consistency_prompt = prompts.get('consistency', '')
        if not consistency_prompt or "Không có ghi chú đặc biệt." in consistency_prompt: return
        
        logging.info(f"Kiểm tra sự nhất quán cho file {chunk_file.name}...")
        
        cache_key = consistency_prompt + translated_text
        cached_result = cache.get(cache_key)

        if cached_result:
            final_text = cached_result
        else:
            final_text, status = _call_api(translated_text, consistency_prompt, api_manager, config_params, model_override=config_params['consistency_model'])
            if status != "success" or not final_text:
                logging.warning(f"Không thể tinh chỉnh sự nhất quán cho {chunk_file.name}.")
                return
            cache.set(cache_key, final_text)

        chunk_file.write_text(final_text, encoding='utf-8')
    except Exception as e:
        logging.error(f"Lỗi trong quá trình kiểm tra sự nhất quán của file {chunk_file.name}: {e}")