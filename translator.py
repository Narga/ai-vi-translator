# translator.py - v1.0
# Module chịu trách nhiệm dịch văn bản sử dụng Gemini API.
# Quản lý API key, cache và các lần thử lại.

import os
import google.generativeai as genai
import time
import hashlib
import pickle
from typing import List, Optional
from threading import Lock

class ApiManager:
    """Quản lý và xoay vòng các API key của Gemini."""
    def __init__(self, api_keys: List[str]):
        self._keys = api_keys
        self._current_key_index = 0
        self._lock = Lock()
        if not self._keys:
            raise ValueError("Danh sách API key không được để trống trong config.ini.")
        print(f"🔑 Đã nạp {len(self._keys)} API key.")

    def get_next_key(self) -> str:
        """Lấy key tiếp theo trong danh sách một cách thread-safe."""
        with self._lock:
            key = self._keys[self._current_key_index]
            self._current_key_index = (self._current_key_index + 1) % len(self._keys)
            return key

class TranslationCache:
    """Quản lý việc cache các bản dịch để tiết kiệm chi phí API."""
    def __init__(self, cache_dir: str, enabled: bool = True):
        self.enabled = enabled
        if not self.enabled:
            print("ℹ️ Cache dịch thuật đã bị tắt.")
            return
            
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self._lock = Lock()
        print(f"📦 Cache dịch thuật được bật. Thư mục: '{self.cache_dir}'")

    def _get_cache_key(self, text: str) -> str:
        """Tạo hash MD5 cho văn bản để dùng làm key cache."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def get(self, text: str) -> Optional[str]:
        """Lấy bản dịch từ cache nếu có."""
        if not self.enabled:
            return None
        
        cache_file = os.path.join(self.cache_dir, self._get_cache_key(text) + ".pkl")
        if os.path.exists(cache_file):
            try:
                with self._lock:
                    with open(cache_file, 'rb') as f:
                        return pickle.load(f)
            except Exception:
                return None
        return None

    def set(self, text: str, translation: str):
        """Lưu bản dịch vào cache."""
        if not self.enabled:
            return
            
        cache_file = os.path.join(self.cache_dir, self._get_cache_key(text) + ".pkl")
        try:
            with self._lock:
                with open(cache_file, 'wb') as f:
                    pickle.dump(translation, f)
        except Exception as e:
            print(f"⚠️ Cảnh báo: Không thể lưu cache. Lỗi: {e}")

def translate_text(
    text: str,
    api_manager: ApiManager,
    cache: TranslationCache,
    model_name: str,
    prompt: str,
    temperature: float
) -> Optional[str]:
    """
    Gửi văn bản đến Gemini API để dịch, có hỗ trợ cache và xoay vòng API key.
    """
    # 1. Kiểm tra cache trước khi gọi API
    cached_translation = cache.get(prompt + text)
    if cached_translation:
        return cached_translation

    # 2. Nếu không có cache, tiến hành gọi API
    max_retries = len(api_manager._keys) # Thử lại tối đa bằng số lượng key
    for attempt in range(max_retries):
        api_key = api_manager.get_next_key()
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            generation_config = genai.types.GenerationConfig(temperature=temperature)
            
            full_prompt = f"{prompt}\n\n--- VĂN BẢN GỐC ---\n\n{text}"
            response = model.generate_content(full_prompt, generation_config=generation_config)

            if response and response.text:
                translated_text = response.text.strip()
                cache.set(prompt + text, translated_text) # Lưu kết quả vào cache
                return translated_text
            else:
                raise Exception("API trả về phản hồi rỗng.")

        except Exception as e:
            error_msg = str(e).lower()
            print(f"API Key: ...{api_key[-4:]} gặp lỗi: {error_msg}. Đang thử key tiếp theo...")
            
            # Tạm dừng một chút để tránh spam API
            time.sleep(1) 
    
    # Nếu tất cả các key đều lỗi
    print(f"❌ Lỗi nghiêm trọng: Không thể dịch được đoạn văn bản sau khi đã thử tất cả {max_retries} API key.")
    return None

# Có thể chạy độc lập để kiểm thử
if __name__ == '__main__':
    # Hướng dẫn sử dụng từ dòng lệnh
    print("Đây là module dịch thuật, được thiết kế để sử dụng bên trong script chính.")
    print("Để kiểm thử, bạn cần cung cấp API key và các thông tin khác.")
    
    # Ví dụ kiểm thử nhỏ
    try:
        # Giả lập các tham số để kiểm thử
        test_keys = os.environ.get("GEMINI_API_KEYS", "").split(',')
        if not test_keys or not test_keys[0]:
            print("\nVui lòng đặt biến môi trường GEMINI_API_KEYS để kiểm thử.")
            print("Ví dụ: export GEMINI_API_KEYS=\"key1,key2\"")
        else:
            manager = ApiManager(api_keys=test_keys)
            cache_test = TranslationCache(cache_dir="test_cache", enabled=True)
            test_text = "**Chapter 1**\n\nHello, world."
            test_prompt = "Translate this English text to Vietnamese, keeping the **...** format."
            
            print(f"\nĐang dịch đoạn văn bản thử nghiệm: '{test_text}'")
            translation = translate_text(test_text, manager, cache_test, 'gemini-1.5-flash-latest', test_prompt, 0.1)
            
            if translation:
                print(f"✅ Kết quả dịch: '{translation}'")
            else:
                print("❌ Dịch thử nghiệm thất bại.")

    except Exception as e:
        print(f"Lỗi khi chạy kiểm thử: {e}")