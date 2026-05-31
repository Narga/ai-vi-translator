# backend/infrastructure/progress/runtime_state.py
# RuntimeState - Quản lý runtime state cho WebUI

"""
RuntimeState tách global state ra khỏi webui/__init__.py.
Cung cấp singleton quản lý progress_queue, translation_result, v.v.

Phase 15: Tách state runtime khỏi WebUI init.
"""

import logging
from queue import Queue
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RuntimeState:
    """
    Quản lý runtime state cho WebUI.

    Thay thế global variables trong webui/__init__.py.
    """

    _instance: Optional["RuntimeState"] = None

    def __new__(cls) -> "RuntimeState":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

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

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
