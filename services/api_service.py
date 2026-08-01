# services/api_service.py - v4.1.0
# Tác giả: Narga
# Chức năng: Quản lý API keys với AdaptiveRateLimiter, đọc RPD từ config.
# v4.1.0: Cấu hình hóa RPD/key, chiến lược least_used, TPD tracking.

import time
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple, Any
from threading import Lock
from collections import deque


class GlobalRPMRateLimiter:
    """
    Global Rate Limiter sử dụng Sliding Window để tránh vượt quá giới hạn IP.

    Gemini API Free Tier: 15 RPM
    Với nhiều keys, cần giới hạn tổng RPM để tránh bị chặn IP.
    """

    def __init__(self, max_rpm: int = 15, window_seconds: int = 60):
        """
        Args:
            max_rpm: Số request tối đa mỗi phút (mặc định 15 cho Free Tier)
            window_seconds: Kích thước cửa sổ trượt (mặc định 60 giây)
        """
        self.max_rpm = max_rpm
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._request_times: deque = deque()
        self._total_requests = 0
        self._logger = logging.getLogger(__name__)

    def _clean_old_requests(self, current_time: float) -> None:
        """Loại bỏ các request cũ khỏi cửa sổ."""
        cutoff = current_time - self.window_seconds
        while self._request_times and self._request_times[0] < cutoff:
            self._request_times.popleft()

    def acquire(self, blocking: bool = True, timeout: float = 60.0) -> bool:
        """
        Kiểm tra và chờ nếu cần để giữ RPM trong giới hạn.

        Args:
            blocking: Có chờ nếu vượt limit hay trả về ngay
            timeout: Thời gian tối đa chờ

        Returns:
            True nếu được phép request, False nếu timeout
        """
        start_time = time.time()

        while True:
            with self._lock:
                current_time = time.time()
                self._clean_old_requests(current_time)

                if len(self._request_times) < self.max_rpm:
                    self._request_times.append(current_time)
                    self._total_requests += 1
                    return True

            if not blocking:
                return False

            if time.time() - start_time >= timeout:
                self._logger.warning(f"RPM limiter timeout sau {timeout}s")
                return False

            time.sleep(0.1)

    def get_stats(self) -> Dict[str, Any]:
        """Trả về thống kê rate limiter."""
        with self._lock:
            current_time = time.time()
            self._clean_old_requests(current_time)
            return {
                "current_rpm": len(self._request_times),
                "max_rpm": self.max_rpm,
                "total_requests": self._total_requests,
                "utilization_pct": len(self._request_times) / self.max_rpm * 100,
            }


class AdaptiveRateLimiter:
    """
    Rate limiter thông minh, đọc RPD từ config.

    Chiến lược:
    - daily_limit đọc từ config (mặc định 500 RPD/key)
    - Burst mode: Cho phép burst tối đa, sau đó cooldown
    - Progressive backoff: 30s → 60s → 120s → 240s → 300s (max)
    - Daily quota tracking: Reset vào 0:00 Pacific Time

    Attributes:
        daily_limit (int): Giới hạn requests mỗi ngày cho mỗi key
        failure_count (Dict): Đếm số lần lỗi liên tiếp
        cool_down_until (Dict): Thời điểm kết thúc cooldown
        daily_usage (Dict): Số requests đã dùng trong ngày
        daily_tokens (Dict): Số tokens đã dùng trong ngày cho mỗi key
        last_reset_date (str): Ngày cuối cùng reset quota
    """

    MAX_RETRIES = 8  # Tối đa 8 lần thử lại trước khi cooldown dài

    def __init__(self, daily_limit: int = 500, daily_token_limit: int = 0):
        """
        Khởi tạo AdaptiveRateLimiter.

        Args:
            daily_limit: RPD per key (đọc từ config, mặc định 500)
            daily_token_limit: TPD per key (0 = không giới hạn)
        """
        self.daily_limit = daily_limit
        self.daily_token_limit = daily_token_limit
        self.failure_count: Dict[str, int] = {}
        self.cool_down_until: Dict[str, float] = {}
        self.daily_usage: Dict[str, int] = {}
        self.daily_tokens: Dict[str, int] = {}
        self.last_reset_date: str = datetime.utcnow().strftime("%Y-%m-%d")
        self._round_robin_offset: int = 0  # Tie-break cho least_used
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)

    def _check_daily_reset(self) -> None:
        """Reset daily usage nếu đã sang ngày mới (UTC)."""
        current_date = datetime.utcnow().strftime("%Y-%m-%d")
        if current_date != self.last_reset_date:
            self._logger.info(
                f"🔄 Daily quota reset: {self.last_reset_date} → {current_date}"
            )
            self.daily_usage.clear()
            self.daily_tokens.clear()
            self.failure_count.clear()
            # Giữ cooldown - chỉ clear những key đã hết cooldown
            expired_keys = [
                k for k, v in self.cool_down_until.items() if time.time() >= v
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

            # Lỗi quota/rate limit
            if any(
                kw in error_lower
                for kw in ["rate limit", "quota", "429", "resource_exhausted"]
            ):
                # Quota exhausted (hết hạn ngày) => cooldown dài ngay lập tức
                if any(kw in error_lower for kw in ["quota", "resource_exhausted"]):
                    self.cool_down_until[api_key] = current_time + 1800
                    self._logger.warning(
                        f"🔑 Key ...{api_key[-4:]} hết quota, cooldown 30 phút"
                    )
                    return False, 0  # Chuyển key ngay, không delay

                # Rate limit tạm thời => progressive backoff
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
                    f"⏳ Lỗi rate limit key ...{api_key[-4:]}, "
                    f"thử lại {failures}/{self.MAX_RETRIES} sau {delay}s"
                )
                return True, delay

            # Lỗi key vĩnh viễn - loại key khỏi phiên dịch ngay
            elif any(
                kw in error_lower
                for kw in [
                    "api_key_invalid",
                    "api key not found",
                    "invalid api key",
                    "please pass a valid api key",
                    "permission_denied",
                    "unauthenticated",
                ]
            ):
                # Cooldown 24 giờ (loại khỏi phiên dịch hiện tại)
                self.cool_down_until[api_key] = current_time + 86400
                self._logger.warning(
                    f"🔑 Key ...{api_key[-4:]} không hợp lệ (invalid/permission), "
                    f"loại khỏi phiên dịch hiện tại (cooldown 24h)"
                )
                return False, 0  # Chuyển key ngay, không retry

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

    def mark_success(self, api_key: str, tokens_used: int = 0) -> None:
        """
        Đánh dấu request thành công, reset failure count và tăng daily usage.

        Args:
            api_key (str): API key đã thành công
            tokens_used (int): Số tokens đã sử dụng
        """
        with self._lock:
            self._check_daily_reset()

            # Reset failure count
            if api_key in self.failure_count:
                self.failure_count[api_key] = 0

            # Tăng daily usage
            self.daily_usage[api_key] = self.daily_usage.get(api_key, 0) + 1

            # Tăng daily tokens
            if tokens_used > 0:
                self.daily_tokens[api_key] = self.daily_tokens.get(api_key, 0) + tokens_used

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
                if (
                    key in self.cool_down_until
                    and current_time < self.cool_down_until[key]
                ):
                    continue

                # Bỏ qua keys đã hết quota daily
                if self.daily_usage.get(key, 0) >= self.daily_limit:
                    continue

                available.append(key)

            return available

    def get_least_used_key(self, all_keys: List[str]) -> Optional[str]:
        """
        Chọn key có daily_usage thấp nhất (chiến lược least_used).
        Giúp phân bổ đều tải qua ngày, tối đa hóa throughput.

        Args:
            all_keys: Danh sách tất cả API keys

        Returns:
            Key có usage thấp nhất hoặc None
        """
        available = self.get_available_keys(all_keys)
        if not available:
            return None

        with self._lock:
            # Tìm usage thấp nhất
            min_usage = min(self.daily_usage.get(k, 0) for k in available)
            # Lọc các key cùng usage thấp nhất
            candidates = [k for k in available if self.daily_usage.get(k, 0) == min_usage]
            # Tie-break: chọn theo round-robin offset
            chosen = candidates[self._round_robin_offset % len(candidates)]
            self._round_robin_offset += 1
            return chosen

    def get_stats(self) -> Dict[str, Any]:
        """Trả về thống kê rate limiter."""
        with self._lock:
            self._check_daily_reset()
            current_time = time.time()

            in_cooldown = sum(
                1 for v in self.cool_down_until.values() if current_time < v
            )

            total_usage = sum(self.daily_usage.values())
            total_tokens = sum(self.daily_tokens.values())

            return {
                "daily_limit_per_key": self.daily_limit,
                "total_daily_usage": total_usage,
                "total_daily_tokens": total_tokens,
                "keys_in_cooldown": in_cooldown,
                "last_reset_date": self.last_reset_date,
                "failure_counts": dict(self.failure_count),
                "usage_per_key": dict(self.daily_usage),
            }


class ApiManager:
    """
    Quản lý API key, tích hợp AdaptiveRateLimiter để xoay vòng key thông minh.
    Bao gồm Global RPM Limiter để tránh vượt quá giới hạn IP.

    Thuộc tính:
        _keys (Dict[str, str]): Dictionary ánh xạ key -> trạng thái ('available')
        _key_list (List[str]): Danh sách các API keys
        _current_key_index (int): Chỉ số key hiện tại trong vòng xoay
        _lock (Lock): Lock để thread-safe khi truy cập _keys và _current_key_index
        _rate_limiter (AdaptiveRateLimiter): Đối tượng điều tiết tần suất per-key
        _rpm_limiter (GlobalRPMRateLimiter): Đối tượng giới hạn RPM toàn cục
    """

    def __init__(
        self,
        api_keys: List[str],
        max_rpm: Optional[int] = None,
        rpd_per_key: Optional[int] = None,
        tpd_per_key: int = 0,
        key_strategy: str = "least_used",
    ):
        """
        Khởi tạo ApiManager với danh sách API keys.

        Args:
            api_keys (List[str]): Danh sách các Gemini API keys
            max_rpm (int): Giới hạn RPM toàn cục (mặc định 15 cho Free Tier)
            rpd_per_key (int): Giới hạn RPD cho mỗi key (mặc định 500)
            tpd_per_key (int): Giới hạn TPD cho mỗi key (0 = không giới hạn)
            key_strategy (str): Chiến lược chọn key: 'round_robin' hoặc 'least_used'

        Raises:
            ValueError: Nếu danh sách API keys trống
        """
        if not api_keys:
            raise ValueError("Danh sách API key không được để trống trong config.ini.")
            
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService()
        active_provider = provider_service.get_active_provider_config() or {}
        
        provider_type = active_provider.get("type", "gemini")
        
        if provider_type == "gemini":
            actual_rpm = max_rpm if max_rpm is not None else int(active_provider.get("max_rpm", 15))
            actual_rpd = rpd_per_key if rpd_per_key is not None else int(active_provider.get("rpd_per_key", 1500))
        else:
            actual_rpm = max_rpm if max_rpm is not None else int(active_provider.get("max_rpm", 20))
            actual_rpd = rpd_per_key if rpd_per_key is not None else int(active_provider.get("rpd_per_key", 1000000))
            
        self._keys = {key: "available" for key in api_keys}
        self._key_list = list(api_keys)
        self._current_key_index = 0
        self._lock = Lock()
        self._key_strategy = key_strategy
        self._rate_limiter = AdaptiveRateLimiter(
            daily_limit=actual_rpd, daily_token_limit=tpd_per_key
        )
        self._rpm_limiter = GlobalRPMRateLimiter(max_rpm=actual_rpm)
        logging.info(
            f"🔑 Đã nạp {len(self._keys)} API key. "
            f"RPM={actual_rpm}, RPD/key={actual_rpd}, strategy={key_strategy}, provider={provider_type}"
        )

    def get_next_available_key(self) -> Optional[str]:
        """
        Lấy key hợp lệ tiếp theo dựa trên chiến lược đã cấu hình.
        - least_used: Chọn key có daily_usage thấp nhất
        - round_robin: Xoay vòng tuần tự

        Returns:
            Optional[str]: API key hợp lệ hoặc None nếu không có key khả dụng
        """
        # Sử dụng chiến lược least_used nếu được cấu hình
        if self._key_strategy == "least_used":
            return self._rate_limiter.get_least_used_key(self._key_list)

        # Fallback: round_robin
        with self._lock:
            current_time = time.time()

            available_keys = []

            for key in self._key_list:
                if key not in self._keys:
                    continue
                if self._keys.get(key) != "available":
                    continue
                if key in self._rate_limiter.cool_down_until:
                    if current_time < self._rate_limiter.cool_down_until[key]:
                        continue
                if (
                    self._rate_limiter.daily_usage.get(key, 0)
                    >= self._rate_limiter.daily_limit
                ):
                    continue
                available_keys.append(key)

            if not available_keys:
                return None

            start_index = self._current_key_index

            while True:
                key = self._key_list[self._current_key_index]
                self._current_key_index = (self._current_key_index + 1) % len(
                    self._key_list
                )
                if key in available_keys:
                    return key
                if self._current_key_index == start_index:
                    return None

    def handle_api_error(self, api_key: str, error_msg: str) -> Tuple[bool, float]:
        """
        Ủy quyền xử lý lỗi cho AdaptiveRateLimiter.

        Args:
            api_key (str): API key gặp lỗi
            error_msg (str): Thông điệp lỗi

        Returns:
            Tuple[bool, float]: (có_nên_thử_lại, thời_gian_chờ)
        """
        return self._rate_limiter.should_retry(api_key, error_msg)

    def mark_success(self, api_key: str) -> None:
        """
        Báo thành công cho AdaptiveRateLimiter.

        Args:
            api_key (str): API key đã thực hiện request thành công
        """
        self._rate_limiter.mark_success(api_key)

    def acquire_rpm(self, blocking: bool = True, timeout: float = 60.0) -> bool:
        """
        Kiểm tra và chờ nếu cần để giữ RPM trong giới hạn toàn cục.

        Gọi method này trước mỗi API request.

        Args:
            blocking: Có chờ nếu vượt limit hay trả về ngay
            timeout: Thời gian tối đa chờ

        Returns:
            True nếu được phép request, False nếu timeout
        """
        return self._rpm_limiter.acquire(blocking=blocking, timeout=timeout)

    def get_rpm_stats(self) -> Dict[str, Any]:
        """Trả về thống kê RPM limiter."""
        return self._rpm_limiter.get_stats()

    def all_keys_exhausted(self) -> bool:
        """
        Kiểm tra xem tất cả các keys có đều đang trong cooldown hoặc hết quota không.

        Returns:
            bool: True nếu không còn key nào khả dụng
        """
        with self._lock:
            available = self._rate_limiter.get_available_keys(self._key_list)
            return len(available) == 0
