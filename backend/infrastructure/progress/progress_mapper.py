# backend/infrastructure/progress/progress_mapper.py
# ProgressMapper - Map progress events cho CLI và WebUI

"""
ProgressMapper chuyển đổi progress events sang format phù hợp
cho CLI (callback) và WebUI (queue).

Phase 07: Chuẩn hóa progress event consumption.
"""

import logging
from queue import Queue
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ProgressMapper:
    """
    Mapper chuyển đổi progress events cho các consumers khác nhau.

    Sử dụng:
        from backend.infrastructure.progress.progress_mapper import ProgressMapper

        # Cho WebUI
        mapper = ProgressMapper.for_webui(progress_queue)
        mapper.emit({"type": "progress", "message": "..."})

        # Cho CLI
        mapper = ProgressMapper.for_cli(tqdm_callback)
        mapper.emit({"type": "progress", "message": "..."})
    """

    def __init__(self, callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        Khởi tạo ProgressMapper.

        Args:
            callback: Hàm callback nhận event dict
        """
        self._callback = callback

    @classmethod
    def for_webui(cls, queue: Queue) -> "ProgressMapper":
        """
        Tạo mapper cho WebUI (đẩy event vào queue).

        Args:
            queue: Queue instance để đẩy events

        Returns:
            ProgressMapper instance
        """
        def queue_callback(event: Dict[str, Any]) -> None:
            queue.put(event)

        return cls(callback=queue_callback)

    @classmethod
    def for_cli(
        cls,
        on_progress: Optional[Callable] = None,
        on_info: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> "ProgressMapper":
        """
        Tạo mapper cho CLI với các callbacks riêng cho từng loại event.

        Args:
            on_progress: Callback cho progress events
            on_info: Callback cho info events
            on_complete: Callback cho complete events
            on_error: Callback cho error events

        Returns:
            ProgressMapper instance
        """
        def cli_callback(event: Dict[str, Any]) -> None:
            event_type = event.get("type")
            if event_type == "progress" and on_progress:
                on_progress(event)
            elif event_type == "info" and on_info:
                on_info(event)
            elif event_type == "complete" and on_complete:
                on_complete(event)
            elif event_type == "error" and on_error:
                on_error(event)

        return cls(callback=cli_callback)

    def emit(self, event: Dict[str, Any]) -> None:
        """
        Emit một progress event.

        Args:
            event: Dict chứa event data
        """
        if self._callback:
            try:
                self._callback(event)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    def create_callback(self) -> Callable[[Dict[str, Any]], None]:
        """
        Tạo callback function để truyền vào TranslationExecutor.

        Returns:
            Callback function
        """
        return self.emit
