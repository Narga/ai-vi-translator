"""Error taxonomy chuẩn duy nhất (docs/07 Phase 2.5a-2, mirror docs/02 §5).

Mọi client và run_all() phân loại theo đây, không tự chế riêng:
- 'rotate':     429 → đổi key rồi thử lại (mỗi key 1 lần/chunk).
- 'retry_same': mạng chập chờn/timeout/5xx → thử lại CÙNG key, tối đa
                 MAX_SAME_KEY_ATTEMPTS attempt/chunk, rồi dừng.
- 'fatal':      còn lại (401/404/payload sai/response rỗng/safety-block)
                 → dừng ngay, không retry, không đổi key.
"""

MAX_SAME_KEY_ATTEMPTS = 2

_RETRY_SAME_STATUS = {408, 500, 502, 503, 504}


class TranslateCancelled(Exception):
    """Người dùng hủy phiên giữa chừng — không phải lỗi provider, không retry."""


def classify(status_code: int | None = None, exc: BaseException | None = None) -> str:
    """Trả về 'rotate' | 'retry_same' | 'fatal'."""
    if status_code is not None:
        if status_code == 429:
            return "rotate"
        if status_code in _RETRY_SAME_STATUS:
            return "retry_same"
        return "fatal"
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return "retry_same"
    return "fatal"
