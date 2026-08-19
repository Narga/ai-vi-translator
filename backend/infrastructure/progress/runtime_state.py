# backend/infrastructure/progress/runtime_state.py
# RuntimeState - Quản lý runtime state cho WebUI

"""
RuntimeState tách global state ra khỏi webui/__init__.py.
Cung cấp singleton quản lý progress_queue, translation_result, v.v.

P0: Cancel luôn scoped theo job_id. KHÔNG còn global cancel.
"""

import logging
import threading
from queue import Queue
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class RuntimeState:
    """Quản lý runtime state cho WebUI."""

    _instance: Optional["RuntimeState"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls) -> "RuntimeState":
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._state_lock = threading.RLock()

        self.progress_queue: Queue = Queue()
        self.translation_result: Dict[str, Any] = {}
        self.translation_stats: Dict[str, Any] = {
            "translated_words": 0,
            "pending_words": 0,
            "tokens_used": 0,
            "total_input_words": 0,
            "total_done_words": 0,
            "total_translation_time": 0,
            "total_chunks_translated": 0,
            "cache_hit_rate": 0,
            "tm_hits": 0,
        }
        self.translation_memory = None
        # L3: KHÔNG còn `self._cancel_all` — attribute này là cửa hậu global cancel duy nhất
        # còn lại. Đã grep: chỉ runtime_state.py tự đọc/ghi nó (4 vị trí 53/80/84/95),
        # 0 caller ngoài file ⇒ xóa hẳn thay vì để lại và không bao giờ set.
        self._cancelled_jobs: Set[str] = set()

        logger.info("RuntimeState initialized")

    def reset_translation(self) -> None:
        """Reset translation state."""
        while not self.progress_queue.empty():
            try:
                self.progress_queue.get_nowait()
            except Exception:
                break
        self.translation_result = {}

    def set_translation_result(self, result: Dict[str, Any]) -> None:
        """Set translation result."""
        self.translation_result = result

    def get_translation_result(self) -> Dict[str, Any]:
        """Get translation result."""
        return self.translation_result

    def request_cancel(self, job_id: Optional[str] = None) -> None:
        """Yêu cầu dừng MỘT job.

        KHÔNG có global cancel: thiếu job_id → no-op (log cảnh báo) để không
        bao giờ kích hoạt dừng toàn bộ job khác.
        """
        if not job_id:
            logger.warning("request_cancel() thiếu job_id — bỏ qua để tránh global cancel")
            return
        with self._state_lock:
            self._cancelled_jobs.add(job_id)

    def is_cancelled(self, job_id: Optional[str] = None) -> bool:
        """Kiểm tra job cụ thể có bị yêu cầu dừng không. Không bao giờ true vì job khác."""
        if not job_id:
            return False
        with self._state_lock:
            return job_id in self._cancelled_jobs

    def reset_cancel(self, job_id: Optional[str] = None) -> None:
        """Xóa đúng token của job_id; KHÔNG đụng token job khác."""
        if not job_id:
            return
        with self._state_lock:
            self._cancelled_jobs.discard(job_id)

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
