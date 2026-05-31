# backend/infrastructure/progress/webui_progress_bridge.py
# WebUIProgressBridge - Bridge giữa backend use case và WebUI SSE queue

"""
WebUIProgressBridge kết nối backend use case với WebUI progress queue.
Cho phép use case emit events mà không cần biết về Flask/WebUI.

Phase 10: Tách thread worker khỏi route.
"""

import logging
from queue import Queue
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class WebUIProgressBridge:
    """
    Bridge kết nối backend use case với WebUI progress queue.

    Sử dụng:
        bridge = WebUIProgressBridge(progress_queue)
        callback = bridge.create_callback()
        use_case.execute(request, progress_callback=callback)
    """

    def __init__(self, queue: Queue):
        """
        Khởi tạo bridge.

        Args:
            queue: WebUI progress_queue instance
        """
        self._queue = queue

    def create_callback(self) -> Callable[[Dict[str, Any]], None]:
        """
        Tạo callback function để truyền vào use case.

        Returns:
            Callback function đẩy event vào queue
        """
        def callback(data: Dict[str, Any]) -> None:
            self._queue.put(data)

        return callback

    def emit(self, event: Dict[str, Any]) -> None:
        """
        Emit event vào queue.

        Args:
            event: Event dict
        """
        self._queue.put(event)

    def clear(self) -> None:
        """Xóa tất cả events trong queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break
