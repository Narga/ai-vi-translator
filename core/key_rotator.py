"""Xoay key tối giản: mỗi key thử tối đa 1 lần/chunk, hết key thì dừng."""

from typing import List, Optional


class KeyRotator:
    def __init__(self, keys: List[str]):
        self.keys = list(dict.fromkeys(k.strip() for k in keys if k.strip()))
        self.current_idx = 0
        self._tried_in_chunk = set()

    def has_keys(self) -> bool:
        return len(self.keys) > 0

    def start_chunk_attempt(self):
        """Đặt lại danh sách key đã thử cho chunk mới."""
        self._tried_in_chunk.clear()

    def get_current_key(self) -> str:
        if not self.keys:
            raise ValueError("Danh sách API Key đang trống! Vui lòng nạp key vào config/providers.json.")
        return self.keys[self.current_idx]

    def try_next_key(self) -> Optional[str]:
        """Chuyển sang key tiếp theo khi gặp 429. None nếu đã thử hết."""
        self._tried_in_chunk.add(self.current_idx)
        if len(self._tried_in_chunk) >= len(self.keys):
            return None
        self.current_idx = (self.current_idx + 1) % len(self.keys)
        return self.keys[self.current_idx]
