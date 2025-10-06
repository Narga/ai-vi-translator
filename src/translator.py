# src/translator.py - v2.4.1
# Tác giả: Narga
# Chức năng: Module lõi, chịu trách nhiệm gửi request đến API,
#            xử lý lỗi, cache và triển khai các quy trình dịch phức hợp.

import os
import google.generativeai as genai
import time
import hashlib
import pickle
import logging
import re
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path
from threading import Lock
from .emergency_stop import check_emergency_stop

# Biểu thức chính quy để phát hiện ký tự tiếng Trung
CHINESE_CHAR_REGEX = re.compile("[\u4e00-\u9fff]")


class SmartRateLimiter:
    """
    Điều tiết tần suất gọi API một cách thông minh, tự động backoff
    dựa trên loại lỗi và đưa key vào cooldown để tránh lãng phí.
    
    Thuộc tính:
        failure_count (Dict[str, int]): Đếm số lần lỗi liên tiếp của mỗi key
        cool_down_until (Dict[str, float]): Thời điểm kết thúc cooldown của mỗi key
    """
    
    def __init__(self):
        """Khởi tạo SmartRateLimiter với các dictionary trống."""
        self.failure_count: Dict[str, int] = {}
        self.cool_down_until: Dict[str, float] = {}
        self._lock = Lock()
    
    def should_retry(self, api_key: str, error: str) -> Tuple[bool, float]:
        """
        Quyết định xem có nên thử lại không và cần chờ bao lâu.
        
        Args:
            api_key (str): API key gặp lỗi
            error (str): Thông điệp lỗi từ API
            
        Returns:
            Tuple[bool, float]: (có_nên_thử_lại, thời_gian_chờ_giây)
        """
        with self._lock:
            current_time = time.time()
            
            # Kiểm tra xem key có đang trong cooldown không
            if current_time < self.cool_down_until.get(api_key, 0):
                return False, self.cool_down_until[api_key] - current_time
            
            error_lower = error.lower()
            failures = self.failure_count.get(api_key, 0) + 1
            self.failure_count[api_key] = failures
            
            # Xử lý lỗi quota/rate limit
            if any(kw in error_lower for kw in ["rate limit", "quota", "429", "resource_exhausted"]):
                if failures > 5:
                    # Đưa vào cooldown dài hạn sau nhiều lần thất bại
                    self.cool_down_until[api_key] = current_time + 1800  # 30 phút
                    logging.warning(f"Key ...{api_key[-4:]} vào cooldown 30 phút do lỗi quota liên tục.")
                    return False, 1800
                
                # Backoff theo cấp số nhân: 15s, 30s, 60s, 120s...
                delay = min(15 * (2 ** (failures - 1)), 120)
                logging.warning(f"Lỗi quota, thử lại sau {delay}s...")
                return True, delay
            
            # Lỗi khác: chỉ thử lại tối đa 2 lần
            if failures > 2:
                return False, 0
            
            return True, 5.0
    
    def mark_success(self, api_key: str) -> None:
        """
        Reset bộ đếm lỗi cho key khi có request thành công.
        
        Args:
            api_key (str): API key đã thành công
        """
        with self._lock:
            if api_key in self.failure_count:
                self.failure_count[api_key] = 0
            if api_key in self.cool_down_until:
                del self.cool_down_until[api_key]


class ApiManager:
    """
    Quản lý API key, tích hợp SmartRateLimiter để xoay vòng key thông minh.
    
    Thuộc tính:
        _keys (Dict[str, str]): Dictionary ánh xạ key -> trạng thái
        _key_list (List[str]): Danh sách các API keys
        _current_key_index (int): Chỉ số key hiện tại trong vòng xoay
        _rate_limiter (SmartRateLimiter): Đối tượng điều tiết tần suất
    """
    
    def __init__(self, api_keys: List[str]):
        """
        Khởi tạo ApiManager với danh sách API keys.
        
        Args:
            api_keys (List[str]): Danh sách các Gemini API keys
            
        Raises:
            ValueError: Nếu danh sách API keys trống
        """
        if not api_keys:
            raise ValueError("Danh sách API key không được để trống trong config.ini.")
        
        self._keys = {key: 'available' for key in api_keys}
        self._key_list = list(api_keys)
        self._current_key_index = 0
        self._lock = Lock()
        self._rate_limiter = SmartRateLimiter()
        
        logging.info(f"🔑 Đã nạp {len(self._keys)} API key.")
    
    def get_next_available_key(self) -> Optional[str]:
        """
        Lấy key hợp lệ tiếp theo trong danh sách (không trong cooldown).
        
        Returns:
            Optional[str]: API key hợp lệ hoặc None nếu không có key khả dụng
        """
        with self._lock:
            current_time = time.time()
            
            # Lọc ra các key available và không trong cooldown
            available_keys = [
                k for k, v in self._keys.items() 
                if v == 'available' and current_time >= self._rate_limiter.cool_down_until.get(k, 0)
            ]
            
            if not available_keys:
                return None
            
            start_index = self._current_key_index
            
            # Vòng lặp xoay vòng để tìm key khả dụng
            while True:
                key = self._key_list[self._current_key_index]
                self._current_key_index = (self._current_key_index + 1) % len(self._key_list)
                
                if key in available_keys:
                    return key
                
                # Đã quét hết vòng mà không tìm thấy
                if self._current_key_index == start_index:
                    return None
    
    def handle_api_error(self, api_key: str, error_msg: str) -> Tuple[bool, float]:
        """
        Ủy quyền xử lý lỗi cho SmartRateLimiter.
        
        Args:
            api_key (str): API key gặp lỗi
            error_msg (str): Thông điệp lỗi
            
        Returns:
            Tuple[bool, float]: (có_nên_thử_lại, thời_gian_chờ)
        """
        return self._rate_limiter.should_retry(api_key, error_msg)
    
    def mark_success(self, api_key: str) -> None:
        """
        Báo thành công cho SmartRateLimiter.
        
        Args:
            api_key (str): API key đã thực hiện request thành công
        """
        self._rate_limiter.mark_success(api_key)
    
    def all_keys_exhausted(self) -> bool:
        """
        Kiểm tra xem tất cả các keys có đều đang trong cooldown không.
        
        Returns:
            bool: True nếu không còn key nào khả dụng
        """
        with self._lock:
            current_time = time.time()
            
            for key in self._key_list:
                # Nếu có ít nhất 1 key không trong cooldown
                if current_time >= self._rate_limiter.cool_down_until.get(key, 0):
                    return False
            
            return True


class TranslationCache:
    """
    Quản lý việc cache các bản dịch để tiết kiệm chi phí API và thời gian.
    
    Thuộc tính:
        enabled (bool): Trạng thái bật/tắt cache
        cache_dir (str): Đường dẫn đến thư mục lưu cache
    """
    
    def __init__(self, cache_dir: str, enabled: bool = True):
        """
        Khởi tạo TranslationCache.
        
        Args:
            cache_dir (str): Đường dẫn thư mục cache
            enabled (bool): Bật/tắt tính năng cache
        """
        self.enabled = enabled
        
        if not self.enabled:
            logging.info("ℹ️  Cache dịch thuật đã bị tắt.")
            return
        
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self._lock = Lock()
        
        logging.info(f"📦 Cache dịch thuật được bật. Thư mục: '{self.cache_dir}'")
    
    def _get_cache_key(self, text: str) -> str:
        """
        Tạo hash MD5 cho văn bản để dùng làm key cache.
        
        Args:
            text (str): Văn bản cần hash
            
        Returns:
            str: Chuỗi MD5 hex digest
        """
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def get(self, text: str) -> Optional[str]:
        """
        Lấy bản dịch từ cache nếu có.
        
        Args:
            text (str): Văn bản gốc (dùng làm key)
            
        Returns:
            Optional[str]: Bản dịch từ cache hoặc None nếu không tìm thấy
        """
        if not self.enabled:
            return None
        
        cache_file = os.path.join(self.cache_dir, self._get_cache_key(text) + ".pkl")
        
        if os.path.exists(cache_file):
            try:
                with self._lock, open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                return None
        
        return None
    
    def set(self, text: str, translation: str) -> None:
        """
        Lưu bản dịch vào cache.
        
        Args:
            text (str): Văn bản gốc (dùng làm key)
            translation (str): Bản dịch cần lưu
        """
        if not self.enabled:
            return
        
        cache_file = os.path.join(self.cache_dir, self._get_cache_key(text) + ".pkl")
        
        try:
            with self._lock, open(cache_file, 'wb') as f:
                pickle.dump(translation, f)
        except Exception as e:
            logging.warning(f"⚠️  Cảnh báo: Không thể lưu cache. Lỗi: {e}")


def _call_api(
    text_to_process: str,
    prompt: str,
    api_manager: ApiManager,
    config: Dict[str, Any],
    model_override: Optional[str] = None
) -> Tuple[Optional[str], str, str]:
    """
    Hàm gọi API chung, xử lý lỗi mạng, quota và các vấn đề kết nối.
    
    Args:
        text_to_process (str): Văn bản cần gửi cho AI xử lý
        prompt (str): Prompt chỉ thị cho AI
        api_manager (ApiManager): Đối tượng quản lý API key
        config (Dict): Dictionary chứa các tham số như model_name, temperature
        model_override (Optional[str]): Tên model để sử dụng thay cho model mặc định
        
    Returns:
        Tuple[Optional[str], str, str]: (kết_quả, trạng_thái, api_key_đã_dùng)
            - kết_quả: Văn bản trả về từ API hoặc None nếu lỗi
            - trạng_thái: 'success', 'all_keys_exhausted', 'api_error', 'stopped'
            - api_key_đã_dùng: Key đã sử dụng thành công (hoặc 'unknown' nếu thất bại)
    """
    max_attempts_total = len(api_manager._key_list) * 3
    
    for _ in range(max_attempts_total):
        # Kiểm tra tín hiệu dừng khẩn cấp
        if check_emergency_stop():
            return None, "stopped", "unknown"
        
        # Lấy key khả dụng tiếp theo
        api_key = api_manager.get_next_available_key()
        
        if not api_key:
            # Kiểm tra xem có phải tất cả keys đều hết quota không
            if api_manager.all_keys_exhausted():
                logging.critical("🚨 Tất cả API keys đã hết quota hoặc trong cooldown.")
                return None, "all_keys_exhausted", "unknown"
            
            # Nếu không, có thể đợi một chút rồi thử lại
            logging.warning("Không có key khả dụng, đợi 10s...")
            time.sleep(10)
            continue
        
        try:
            # Chờ delay giữa các request
            time.sleep(config['request_delay'])
            
            # Cấu hình API
            genai.configure(api_key=api_key)
            model_name = model_override or config['model_name']
            model = genai.GenerativeModel(model_name)
            generation_config = genai.types.GenerationConfig(temperature=config['temperature'])
            
            # Tạo prompt đầy đủ
            full_prompt = f"{prompt}\n\n--- VĂN BẢN GỐC CẦN DỊCH ---\n\n{text_to_process}"
            
            # Gọi API
            response = model.generate_content(full_prompt, generation_config=generation_config)
            
            # Đánh dấu thành công
            api_manager.mark_success(api_key)
            
            result_text = response.text.strip() if response and response.text else ""
            return result_text, "success", api_key
        
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Lỗi API với key ...{api_key[-4:]}: {error_msg[:200]}")
            
            # Xử lý lỗi và quyết định có thử lại không
            should_retry, delay = api_manager.handle_api_error(api_key, error_msg)
            
            if should_retry:
                logging.info(f"Đợi {delay:.1f}s trước khi thử lại...")
                if delay > 0:
                    time.sleep(delay)
            else:
                # Không thử lại với key này nữa, chuyển sang key khác
                continue
    
    # Hết số lần thử
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
    Quy trình dịch chính cho mỗi chunk, kết hợp các bước xác thực và sửa lỗi.
    
    Quy trình:
    1. Kiểm tra cache
    2. Dịch lần đầu
    3. Kiểm tra độ dài và dịch lại nếu cần
    4. Kiểm tra và sửa ký tự tiếng Trung còn sót
    5. Chuẩn hóa văn bản (nếu có normalizer)
    6. Lưu vào cache
    
    Args:
        original_chunk (str): Nội dung chunk gốc cần dịch
        api_manager (ApiManager): Trình quản lý API key
        cache (TranslationCache): Trình quản lý cache
        prompts (Dict[str, str]): Dictionary chứa các prompt đã được nạp
        config_params (Dict[str, Any]): Dictionary chứa các tham số cấu hình
        previous_chunk_context (str): Một phần của chunk đã dịch trước đó để làm ngữ cảnh
        normalizer (Any): Đối tượng TextNormalizer để chuẩn hóa văn bản
        
    Returns:
        Tuple[str, str, str]: (kết_quả_dịch, trạng_thái, api_key_đã_dùng)
            - kết_quả_dịch: Văn bản đã dịch (hoặc thông báo lỗi)
            - trạng_thái: 'success', 'failed', 'all_keys_exhausted', ...
            - api_key_đã_dùng: Key đã sử dụng thành công
    """
    # Tạo prompt chính với ngữ cảnh (nếu có)
    main_prompt_template = prompts.get('main', '')
    main_prompt = main_prompt_template.replace('{previous_chunk_context}', previous_chunk_context)
    
    # Kiểm tra cache
    cache_key = main_prompt + original_chunk
    cached_translation = cache.get(cache_key)
    
    if cached_translation:
        logging.info("✅ Sử dụng bản dịch từ cache.")
        return cached_translation, "success", "cache"
    
    logging.info("Bắt đầu dịch chunk...")
    
    # Bước 1: Dịch lần đầu
    translated_text, status, api_key_used = _call_api(
        original_chunk, main_prompt, api_manager, config_params
    )
    
    if status != "success" or not translated_text:
        logging.error("Dịch lần đầu thất bại.")
        return "Dịch chunk thất bại.", "failed", api_key_used
    
    # Bước 2: Kiểm tra độ dài (chống cắt ngắn)
    original_len = len(original_chunk)
    translated_len = len(translated_text)
    
    if original_len > 200 and not (
        config_params['min_length_ratio'] * original_len <= translated_len <= config_params['max_length_ratio'] * original_len
    ):
        logging.warning(f"Phát hiện độ dài không hợp lệ ({translated_len}/{original_len}). Dịch lại để chống cắt ngắn...")
        
        retranslate_prompt_template = prompts.get('retranslate', main_prompt)
        retranslate_prompt = retranslate_prompt_template.replace('{previous_chunk_context}', previous_chunk_context)
        
        translated_text, status, api_key_used = _call_api(
            original_chunk, retranslate_prompt, api_manager, 
            config_params, model_override=config_params['qa_model']
        )
        
        if status != "success" or not translated_text:
            logging.error("Dịch lại để chống cắt ngắn thất bại.")
            return "Dịch chunk thất bại.", "failed", api_key_used
    
    # Bước 3: Sửa lỗi ký tự tiếng Trung còn sót (chỉ áp dụng nếu INPUT_LANG = CN)
    input_lang = config_params.get('input_lang', 'CN').upper()
    
    if input_lang == 'CN':
        refinement_count = 0
        correction_prompt = prompts.get('correction', '')
        
        while CHINESE_CHAR_REGEX.search(translated_text) and refinement_count < config_params['max_refinement_attempts']:
            refinement_count += 1
            logging.warning(f"Phát hiện ký tự Trung. Sửa lỗi lần {refinement_count}...")
            
            corrected_text, status, api_key_used = _call_api(
                translated_text, correction_prompt, api_manager, 
                config_params, model_override=config_params['qa_model']
            )
            
            if status == "success" and corrected_text:
                translated_text = corrected_text
            else:
                logging.error(f"Sửa lỗi lần {refinement_count} thất bại.")
        
        if CHINESE_CHAR_REGEX.search(translated_text):
            logging.error(f"Không thể loại bỏ hết ký tự Trung sau {config_params['max_refinement_attempts']} lần thử.")
            # Không return failed, vẫn lưu kết quả để người dùng có thể sửa thủ công
    
    # Bước 4: Chuẩn hóa văn bản (nếu có normalizer)
    if normalizer:
        try:
            translated_text = normalizer.normalize(translated_text)
            logging.info("✅ Đã chuẩn hóa văn bản.")
        except Exception as e:
            logging.warning(f"⚠️  Lỗi khi chuẩn hóa văn bản: {e}")
    
    logging.info("✅ Chunk được dịch và xử lý thành công!")
    
    # Lưu vào cache
    cache.set(cache_key, translated_text)
    
    return translated_text, "success", api_key_used


def consistency_check_chunk(
    chunk_file: Path,
    api_manager: ApiManager,
    cache: TranslationCache,
    prompts: Dict[str, str],
    config_params: Dict[str, Any],
    normalizer: Any = None
) -> None:
    """
    Đọc một chunk đã dịch, kiểm tra sự nhất quán và ghi đè lại file.
    
    Args:
        chunk_file (Path): Đường dẫn đến file chunk cần kiểm tra
        api_manager (ApiManager): Trình quản lý API key
        cache (TranslationCache): Trình quản lý cache
        prompts (Dict[str, str]): Dictionary chứa các prompt
        config_params (Dict[str, Any]): Dictionary chứa các tham số cấu hình
        normalizer (Any): Đối tượng TextNormalizer để chuẩn hóa văn bản
    """
    try:
        translated_text = chunk_file.read_text(encoding='utf-8')
        
        if not translated_text.strip():
            return
        
        consistency_prompt = prompts.get('consistency', '')
        
        # Bỏ qua nếu không có prompt consistency hoặc prompt trống
        if not consistency_prompt or "Không có ghi chú đặc biệt." in consistency_prompt:
            return
        
        logging.info(f"Kiểm tra sự nhất quán cho file {chunk_file.name}...")
        
        # Kiểm tra cache
        cache_key = consistency_prompt + translated_text
        cached_result = cache.get(cache_key)
        
        if cached_result:
            final_text = cached_result
        else:
            final_text, status, _ = _call_api(
                translated_text, consistency_prompt, api_manager, 
                config_params, model_override=config_params['consistency_model']
            )
            
            if status != "success" or not final_text:
                logging.warning(f"Không thể tinh chỉnh sự nhất quán cho {chunk_file.name}.")
                return
            
            cache.set(cache_key, final_text)
        
        # Chuẩn hóa văn bản trước khi ghi
        if normalizer:
            try:
                final_text = normalizer.normalize(final_text)
            except Exception as e:
                logging.warning(f"⚠️  Lỗi khi chuẩn hóa văn bản cho {chunk_file.name}: {e}")
        
        # Ghi đè lại file
        chunk_file.write_text(final_text, encoding='utf-8')
    
    except Exception as e:
        logging.error(f"Lỗi trong quá trình kiểm tra sự nhất quán của file {chunk_file.name}: {e}")
