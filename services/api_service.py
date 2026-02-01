# services/api_service.py - v4.0.0
# Tác giả: Narga
# Chức năng: Quản lý API keys với AdaptiveRateLimiter, tối ưu cho 20 RPD/key.
# v4.0.0: Nâng cấp cho google-genai SDK mới, hỗ trợ 30 keys (600 RPD capacity).

import time
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple, Any
from threading import Lock


class AdaptiveRateLimiter:
    """
    Rate limiter thông minh tối ưu cho giới hạn 20 RPD/key.
    
    Chiến lược:
    - Phân bổ đều: 20 requests / 24h = 1 request mỗi 72 phút/key
    - Burst mode: Cho phép burst tối đa, sau đó cooldown
    - Progressive backoff: 30s → 60s → 120s → 240s → 300s (max)
    - Daily quota tracking: Reset vào 0:00 UTC
    
    Attributes:
        daily_limit (int): Giới hạn requests mỗi ngày cho mỗi key
        failure_count (Dict): Đếm số lần lỗi liên tiếp
        cool_down_until (Dict): Thời điểm kết thúc cooldown
        daily_usage (Dict): Số requests đã dùng trong ngày
        last_reset_date (str): Ngày cuối cùng reset quota
    """
    
    DAILY_LIMIT = 20  # RPD per key
    MAX_RETRIES = 8   # Tối đa 8 lần thử lại trước khi cooldown dài
    
    def __init__(self):
        """Khởi tạo AdaptiveRateLimiter."""
        self.failure_count: Dict[str, int] = {}
        self.cool_down_until: Dict[str, float] = {}
        self.daily_usage: Dict[str, int] = {}
        self.last_reset_date: str = datetime.utcnow().strftime('%Y-%m-%d')
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)
    
    def _check_daily_reset(self) -> None:
        """Reset daily usage nếu đã sang ngày mới (UTC)."""
        current_date = datetime.utcnow().strftime('%Y-%m-%d')
        if current_date != self.last_reset_date:
            self._logger.info(f"🔄 Daily quota reset: {self.last_reset_date} → {current_date}")
            self.daily_usage.clear()
            self.failure_count.clear()
            # Giữ cooldown - chỉ clear những key đã hết cooldown
            expired_keys = [
                k for k, v in self.cool_down_until.items() 
                if time.time() >= v
            ]
            for k in expired_keys:
                del self.cool_down_until[k]
            self.last_reset_date = current_date
    
    def should_retry(self, api_key: str, error: str) -> Tuple[bool, float]:
        """
        Quyết định xem có nên thử lại không và cần chờ bao lâu.
        
        Chiến lược cải tiến từ Book_translator:
        - Rate limit/quota: Progressive backoff 30s→300s, max 8 retries
        - Network timeout: Shorter delays 10s→60s, max 5 retries  
        - Other errors: 5s delay, max 3 retries
        
        Args:
            api_key (str): API key gặp lỗi
            error (str): Thông điệp lỗi từ API
        
        Returns:
            Tuple[bool, float]: (có_nên_thử_lại, thời_gian_chờ_giây)
        """
        with self._lock:
            self._check_daily_reset()
            current_time = time.time()
            
            # Kiểm tra cooldown
            if api_key in self.cool_down_until:
                if current_time < self.cool_down_until[api_key]:
                    remaining = self.cool_down_until[api_key] - current_time
                    return False, remaining
                else:
                    # Cooldown hết hạn
                    del self.cool_down_until[api_key]
                    self.failure_count[api_key] = 0
            
            error_lower = error.lower()
            failures = self.failure_count.get(api_key, 0) + 1
            self.failure_count[api_key] = failures
            
            # Lỗi quota/rate limit - progressive backoff
            if any(kw in error_lower for kw in ["rate limit", "quota", "429", "resource_exhausted"]):
                if failures > self.MAX_RETRIES:
                    # Đưa vào cooldown 30 phút
                    self.cool_down_until[api_key] = current_time + 1800
                    self._logger.warning(
                        f"🔑 Key ...{api_key[-4:]} vào cooldown 30 phút "
                        f"sau {failures} lần thất bại"
                    )
                    return False, 1800
                
                # Progressive backoff: 30s, 60s, 120s, 240s, 300s (max 5 min)
                delay = min(30 * (2 ** (failures - 1)), 300)
                self._logger.warning(
                    f"⏳ Lỗi quota key ...{api_key[-4:]}, "
                    f"thử lại {failures}/{self.MAX_RETRIES} sau {delay}s"
                )
                return True, delay
            
            # Lỗi network/timeout - shorter delays
            elif any(kw in error_lower for kw in ["timeout", "deadline", "connection"]):
                if failures > 5:
                    self.cool_down_until[api_key] = current_time + 300  # 5 min
                    return False, 300
                
                delay = min(10 * failures, 60)
                return True, delay
            
            # Lỗi khác - minimal retry
            else:
                if failures > 3:
                    return False, 0
                return True, 5.0
    
    def mark_success(self, api_key: str) -> None:
        """
        Đánh dấu request thành công, reset failure count và tăng daily usage.
        
        Args:
            api_key (str): API key đã thành công
        """
        with self._lock:
            self._check_daily_reset()
            
            # Reset failure count
            if api_key in self.failure_count:
                self.failure_count[api_key] = 0
            
            # Tăng daily usage
            self.daily_usage[api_key] = self.daily_usage.get(api_key, 0) + 1
            
            # Clear cooldown nếu có
            if api_key in self.cool_down_until:
                del self.cool_down_until[api_key]
    
    def get_available_keys(self, all_keys: List[str]) -> List[str]:
        """
        Lấy danh sách keys khả dụng (không trong cooldown, chưa hết quota).
        
        Args:
            all_keys (List[str]): Danh sách tất cả API keys
        
        Returns:
            List[str]: Các keys có thể sử dụng
        """
        with self._lock:
            self._check_daily_reset()
            current_time = time.time()
            available = []
            
            for key in all_keys:
                # Bỏ qua keys trong cooldown
                if key in self.cool_down_until and current_time < self.cool_down_until[key]:
                    continue
                
                # Bỏ qua keys đã hết quota daily
                if self.daily_usage.get(key, 0) >= self.DAILY_LIMIT:
                    continue
                
                available.append(key)
            
            return available
    
    def get_stats(self) -> Dict[str, Any]:
        """Trả về thống kê rate limiter."""
        with self._lock:
            self._check_daily_reset()
            current_time = time.time()
            
            in_cooldown = sum(
                1 for v in self.cool_down_until.values() 
                if current_time < v
            )
            
            total_usage = sum(self.daily_usage.values())
            
            return {
                'daily_limit_per_key': self.DAILY_LIMIT,
                'total_daily_usage': total_usage,
                'keys_in_cooldown': in_cooldown,
                'last_reset_date': self.last_reset_date,
                'failure_counts': dict(self.failure_count)
            }


# Alias cũ để backward compatibility
SmartRateLimiter = AdaptiveRateLimiter


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
