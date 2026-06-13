"""Unit tests cho services/api_service.py — AdaptiveRateLimiter & ApiManager."""

import time
import pytest
from services.api_service import AdaptiveRateLimiter, ApiManager


class TestAdaptiveRateLimiter:
    """Tests cho AdaptiveRateLimiter."""

    def test_should_retry_api_key_invalid_returns_false(self):
        """Lỗi API_KEY_INVALID phải trả (False, 0) ngay lần đầu."""
        limiter = AdaptiveRateLimiter(daily_limit=500)
        should_retry, delay = limiter.should_retry(
            "test_key_abc", "400 INVALID_ARGUMENT. API_KEY_INVALID"
        )
        assert should_retry is False
        assert delay == 0

    def test_should_retry_api_key_invalid_cooldown_set(self):
        """Lỗi API_KEY_INVALID phải đưa key vào cooldown."""
        limiter = AdaptiveRateLimiter(daily_limit=500)
        limiter.should_retry("test_key_abc", "API Key not found. Please pass a valid API key.")
        assert "test_key_abc" in limiter.cool_down_until
        # Cooldown phải >= 24 giờ
        remaining = limiter.cool_down_until["test_key_abc"] - time.time()
        assert remaining > 86000  # ~24h trừ vài giây xử lý

    def test_should_retry_permission_denied(self):
        """Lỗi PERMISSION_DENIED phải xử lý giống API_KEY_INVALID."""
        limiter = AdaptiveRateLimiter(daily_limit=500)
        should_retry, delay = limiter.should_retry(
            "test_key_xyz", "PERMISSION_DENIED: The caller does not have permission"
        )
        assert should_retry is False
        assert delay == 0
        assert "test_key_xyz" in limiter.cool_down_until

    def test_should_retry_unauthenticated(self):
        """Lỗi UNAUTHENTICATED phải xử lý giống API_KEY_INVALID."""
        limiter = AdaptiveRateLimiter(daily_limit=500)
        should_retry, delay = limiter.should_retry(
            "test_key_xyz", "UNAUTHENTICATED: Request had invalid authentication"
        )
        assert should_retry is False
        assert delay == 0
        assert "test_key_xyz" in limiter.cool_down_until

    def test_should_retry_rate_limit_still_retries(self):
        """Lỗi rate limit vẫn retry như cũ (regression test)."""
        limiter = AdaptiveRateLimiter(daily_limit=500)
        should_retry, delay = limiter.should_retry(
            "test_key_abc", "429 Too Many Requests: rate limit exceeded"
        )
        assert should_retry is True
        assert delay > 0

    def test_should_retry_quota_exhausted_no_retry(self):
        """Lỗi quota exhausted trả (False, 0) và cooldown (regression test)."""
        limiter = AdaptiveRateLimiter(daily_limit=500)
        should_retry, delay = limiter.should_retry(
            "test_key_abc", "RESOURCE_EXHAUSTED: quota exceeded"
        )
        assert should_retry is False
        assert delay == 0
        assert "test_key_abc" in limiter.cool_down_until

    def test_get_least_used_key_tie_break_rotates(self):
        """Khi nhiều key cùng usage, các lần gọi phải xoay vòng."""
        limiter = AdaptiveRateLimiter(daily_limit=500)
        keys = ["key_a", "key_b", "key_c"]

        results = set()
        for _ in range(6):
            chosen = limiter.get_least_used_key(keys)
            results.add(chosen)

        # Phải chọn ít nhất 2 key khác nhau (không kẹt ở key đầu)
        assert len(results) >= 2

    def test_get_least_used_key_respects_usage(self):
        """Key có usage thấp hơn phải được ưu tiên."""
        limiter = AdaptiveRateLimiter(daily_limit=500)
        limiter.daily_usage["key_a"] = 10
        limiter.daily_usage["key_b"] = 0
        limiter.daily_usage["key_c"] = 5

        chosen = limiter.get_least_used_key(["key_a", "key_b", "key_c"])
        assert chosen == "key_b"

    def test_get_least_used_key_skips_cooldown(self):
        """Key đang trong cooldown không được chọn."""
        limiter = AdaptiveRateLimiter(daily_limit=500)
        limiter.cool_down_until["key_a"] = time.time() + 3600  # Cooldown 1h

        chosen = limiter.get_least_used_key(["key_a", "key_b"])
        assert chosen == "key_b"

    def test_get_available_keys_after_invalid(self):
        """Sau khi key bị đánh dấu invalid, get_available_keys phải bỏ qua nó."""
        limiter = AdaptiveRateLimiter(daily_limit=500)
        limiter.should_retry("key_a", "API_KEY_INVALID")

        available = limiter.get_available_keys(["key_a", "key_b", "key_c"])
        assert "key_a" not in available
        assert "key_b" in available
        assert "key_c" in available


class TestApiManager:
    """Tests cho ApiManager."""

    def test_get_next_key_skips_invalid_key(self):
        """ApiManager phải bỏ qua key đã bị đánh dấu invalid."""
        mgr = ApiManager(api_keys=["key_a", "key_b", "key_c"], key_strategy="least_used")
        # Giả lập key_a bị invalid
        mgr.handle_api_error("key_a", "API_KEY_INVALID: API Key not found")

        # key tiếp theo phải là key_b hoặc key_c, không phải key_a
        next_key = mgr.get_next_available_key()
        assert next_key != "key_a"
        assert next_key in ("key_b", "key_c")

    def test_all_keys_exhausted_when_all_invalid(self):
        """Khi tất cả key đều invalid, all_keys_exhausted phải trả True."""
        mgr = ApiManager(api_keys=["key_a", "key_b"], key_strategy="least_used")
        mgr.handle_api_error("key_a", "API_KEY_INVALID")
        mgr.handle_api_error("key_b", "UNAUTHENTICATED")

        assert mgr.all_keys_exhausted() is True

    def test_handle_error_then_next_key_round_robin(self):
        """Với round_robin, sau khi key_a bị invalid, phải chọn key_b."""
        mgr = ApiManager(api_keys=["key_a", "key_b", "key_c"], key_strategy="round_robin")
        mgr.handle_api_error("key_a", "API_KEY_INVALID")

        next_key = mgr.get_next_available_key()
        assert next_key != "key_a"
