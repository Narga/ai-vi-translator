# src/translators/cache_manager.py - v2.6.1
# Tác giả: Narga
# Chức năng: Quản lý cache kết quả dịch, thread-safe, lưu bằng pickle theo khóa băm MD5.

import os
import pickle
import hashlib
import logging
from threading import Lock
from typing import Optional

class TranslationCache:
    """
    Cache file-based đơn giản để giảm chi phí API.
    - Mỗi item lưu vào một .pkl đặt tên theo MD5 của key.
    - Thread-safe khi đọc/ghi.
    """
    def __init__(self, cache_dir: str, enabled: bool = True) -> None:
        self.enabled = enabled
        if not self.enabled:
            logging.info("ℹ️ Cache dịch thuật đã bị tắt.")
            return
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self._lock = Lock()
        logging.info(f"📦 Cache dịch thuật được bật. Thư mục: '{self.cache_dir}'")

    def _get_cache_key(self, text: str) -> str:
        """
        Tạo khóa băm MD5 ổn định từ văn bản đầu vào (key logic giữ nguyên).
        """
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def get(self, text: str) -> Optional[str]:
        """
        Trả về bản dịch đã cache nếu có, None nếu không.
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
        Lưu một bản dịch vào cache, im lặng nếu cache tắt.
        """
        if not self.enabled:
            return
        cache_file = os.path.join(self.cache_dir, self._get_cache_key(text) + ".pkl")
        try:
            with self._lock, open(cache_file, 'wb') as f:
                pickle.dump(translation, f)
        except Exception as e:
            logging.warning(f"⚠️ Cảnh báo: Không thể lưu cache. Lỗi: {e}")
