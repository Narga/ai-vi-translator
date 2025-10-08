# src/translators/api_manager.py - v2.6.1
# Tác giả: Narga
# Chức năng: Quản lý vòng quay API key, phối hợp với SmartRateLimiter để xử lý lỗi và cooldown.
# Giữ nguyên giao diện công khai như trước để không phá vỡ mã gọi.

import time
import logging
from threading import Lock
from typing import List, Optional, Tuple

from .rate_limiter import SmartRateLimiter

class ApiManager:
    """
    Quản lý API key và tích hợp giới hạn tốc độ thông minh.

    Thuộc tính:
        _keys (dict): key -> trạng thái 'available' (mở rộng về sau)
        _key_list (List[str]): danh sách tuần tự các key
        _current_key_index (int): chỉ số xoay vòng hiện tại
        _rate_limiter (SmartRateLimiter): điều tiết backoff/cooldown
    """
    def __init__(self, api_keys: List[str]) -> None:
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
        Lấy key hợp lệ tiếp theo theo nguyên tắc vòng quay, bỏ qua key đang cooldown.
        """
        with self._lock:
            now = time.time()
            available = [k for k, v in self._keys.items()
                         if v == 'available' and now >= self._rate_limiter.cool_down_until.get(k, 0.0)]
            if not available:
                return None

            start = self._current_key_index
            while True:
                key = self._key_list[self._current_key_index]
                self._current_key_index = (self._current_key_index + 1) % len(self._key_list)
                if key in available:
                    return key
                if self._current_key_index == start:
                    return None

    def handle_api_error(self, api_key: str, error_msg: str) -> Tuple[bool, float]:
        """
        Ủy quyền quyết định retry/delay cho SmartRateLimiter.
        """
        return self._rate_limiter.should_retry(api_key, error_msg)

    def mark_success(self, api_key: str) -> None:
        """
        Thông báo thành công để reset bộ đếm lỗi/cooldown.
        """
        self._rate_limiter.mark_success(api_key)

    def all_keys_exhausted(self) -> bool:
        """
        True nếu tất cả các key đều đang trong cooldown (tức không còn key khả dụng ngay).
        """
        with self._lock:
            now = time.time()
            for key in self._key_list:
                if now >= self._rate_limiter.cool_down_until.get(key, 0.0):
                    return False
            return True
