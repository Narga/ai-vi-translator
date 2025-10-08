# src/translators/rate_limiter.py - v2.6.1
# Tác giả: Narga
# Chức năng: Điều tiết tần suất gọi API, backoff thông minh, cooldown theo key.
# Triết lý: bảo vệ hạn mức, giảm lỗi lặp lại, và không làm lãng phí key.

import time
import logging
from threading import Lock
from typing import Dict, Tuple

class SmartRateLimiter:
    """
    Điều tiết tần suất gọi API một cách thông minh:
      - Backoff theo lỗi quota/rate limit.
      - Cooldown dài hạn nếu một key thất bại liên tiếp nhiều lần.
      - Thread-safe với Lock nội bộ.
    """
    def __init__(self) -> None:
        self.failure_count: Dict[str, int] = {}
        self.cool_down_until: Dict[str, float] = {}
        self._lock = Lock()

    def should_retry(self, api_key: str, error: str) -> Tuple[bool, float]:
        """
        Quyết định có retry không và chờ bao lâu, dựa trên thông điệp lỗi và lịch sử thất bại.
        """
        with self._lock:
            now = time.time()
            # Nếu key đang cooldown thì không retry ngay
            if now < self.cool_down_until.get(api_key, 0):
                return False, self.cool_down_until[api_key] - now

            error_lower = (error or "").lower()
            failures = self.failure_count.get(api_key, 0) + 1
            self.failure_count[api_key] = failures

            # Lỗi quota/429: backoff theo cấp số nhân và có thể cooldown dài hạn
            if any(kw in error_lower for kw in ("rate limit", "quota", "429", "resource_exhausted")):
                if failures > 5:
                    self.cool_down_until[api_key] = now + 1800.0  # 30 phút
                    logging.warning(f"Key ...{api_key[-4:]} vào cooldown 30 phút do lỗi quota liên tục.")
                    return False, 1800.0
                delay = min(15.0 * (2 ** (failures - 1)), 120.0)  # 15s, 30s, 60s, 120s
                logging.warning(f"Lỗi quota, thử lại sau {delay:.0f}s...")
                return True, delay

            # Lỗi khác: retry tối đa 2 lần, delay cố định 5s
            if failures > 2:
                return False, 0.0
            return True, 5.0

    def mark_success(self, api_key: str) -> None:
        """
        Reset trạng thái khi một lần gọi thành công; gỡ cooldown nếu có.
        """
        with self._lock:
            if api_key in self.failure_count:
                self.failure_count[api_key] = 0
            if api_key in self.cool_down_until:
                del self.cool_down_until[api_key]
