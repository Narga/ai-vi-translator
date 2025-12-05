# services/api_service.py - v3.0.0
# Tác giả: Narga
# Chức năng: Quản lý API keys với SmartRateLimiter, backoff thông minh và cooldown.
# v3.0.0: Di chuyển từ src/translators/ sang services/ cho plugin architecture.


import time
import logging
from typing import List, Optional, Dict, Tuple
from threading import Lock


class SmartRateLimiter:
    """
    Điều tiết tần suất gọi API một cách thông minh, tự động backoff
    dựa trên loại lỗi và đưa key vào cooldown để tránh lãng phí.

    Thuộc tính:
        failure_count (Dict[str, int]): Đếm số lần lỗi liên tiếp của mỗi key
        cool_down_until (Dict[str, float]): Thời điểm kết thúc cooldown của mỗi key
        _lock (Lock): Lock để thread-safe khi đọc/ghi failure_count và cool_down_until
    """

    def __init__(self):
        """Khởi tạo SmartRateLimiter với các dictionary trống và lock."""
        self.failure_count: Dict[str, int] = {}
        self.cool_down_until: Dict[str, float] = {}
        self._lock = Lock()

    def should_retry(self, api_key: str, error: str) -> Tuple[bool, float]:
        """
        Quyết định xem có nên thử lại không và cần chờ bao lâu.

        Chiến lược:
        - Lỗi quota/rate-limit: cooldown dài (60-1800s) theo cấp số nhân.
        - Lỗi tạm thời khác: backoff ngắn (5s), tối đa 2 lần.
        - Lỗi nghiêm trọng: không thử lại.

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
                    # Đưa vào cooldown dài hạn sau nhiều lần thất bại liên tiếp
                    self.cool_down_until[api_key] = current_time + 1800  # 30 phút
                    logging.warning(f"Key ...{api_key[-4:]} vào cooldown 30 phút do lỗi quota liên tục.")
                    return False, 1800
                # Backoff theo cấp số nhân: 15s, 30s, 60s, 120s...
                delay = min(15 * (2 ** (failures - 1)), 120)
                logging.warning(f"Lỗi quota với key ...{api_key[-4:]}, thử lại sau {delay}s...")
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
        _keys (Dict[str, str]): Dictionary ánh xạ key -> trạng thái ('available')
        _key_list (List[str]): Danh sách các API keys
        _current_key_index (int): Chỉ số key hiện tại trong vòng xoay
        _lock (Lock): Lock để thread-safe khi truy cập _keys và _current_key_index
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
                # Nếu có ít nhất 1 key không trong cooldown → chưa exhausted
                if current_time >= self._rate_limiter.cool_down_until.get(key, 0):
                    return False
            return True
