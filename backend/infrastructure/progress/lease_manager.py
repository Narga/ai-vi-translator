"""Lease Manager & LeaseKeepAlive Daemon (P1.7)

Quản lý chu kỳ sống của lease heartbeat trong suốt quá trình worker xử lý
(đặc biệt là trong các LLM network call dài).
Nếu lease bị thu hồi (touch_lease trả về False), kích hoạt abort_requested
để worker hủy bỏ kết quả và không ghi đè dữ liệu.
"""
import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class LeaseKeepAlive:
    """Context manager quản lý background daemon thread duy trì heartbeat lease định kỳ.

    Thread có threading.Event dừng sạch sẽ, join(timeout=1.0) và cleanup trong finally.
    """

    def __init__(
        self,
        task_id: str,
        lease_token: str,
        lease_epoch: int,
        task_store: Any,
        interval_seconds: float = 5.0,
        on_abort: Optional[Callable[[], None]] = None,
    ):
        self.task_id = task_id
        self.lease_token = lease_token
        self.lease_epoch = lease_epoch
        self.task_store = task_store
        self.interval_seconds = interval_seconds
        self.on_abort = on_abort
        self.abort_requested = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"LeaseKeepAlive-{self.task_id[:8]}",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_durable_valid(self) -> bool:
        """
        Kiểm tra trực tiếp vào tasks.db xem lease_epoch và lease_token có còn là chủ sở hữu hợp lệ.
        Nếu mất lease, đánh dấu abort_requested = True và kích hoạt on_abort callback nếu có.
        """
        if self.abort_requested:
            return False
        if hasattr(self.task_store, "is_lease_valid"):
            try:
                valid = self.task_store.is_lease_valid(self.task_id, self.lease_epoch, self.lease_token)
                if not valid:
                    logger.warning(
                        f"🚨 [DURABLE_LEASE_LOST] Task {self.task_id} lease (epoch={self.lease_epoch}, token={self.lease_token}) "
                        "không còn hợp lệ trong tasks.db (đã bị claim hoặc thu hồi)!"
                    )
                    self.abort_requested = True
                    if self.on_abort:
                        try:
                            self.on_abort()
                        except Exception as e:
                            logger.error(f"Lỗi khi thực thi on_abort callback: {e}")
                    return False
                return True
            except Exception as e:
                logger.warning(
                    f"🚨 [DURABLE_LEASE_ERROR] Lỗi khi durable check lease trong tasks.db ({e})! "
                    "Fail-closed: đánh dấu abort_requested để bảo vệ dữ liệu."
                )
                self.abort_requested = True
                if self.on_abort:
                    try:
                        self.on_abort()
                    except Exception as err:
                        logger.error(f"Lỗi khi thực thi on_abort callback: {err}")
                return False

        logger.warning(
            f"🚨 [DURABLE_LEASE_NO_VALIDATOR] task_store ({type(self.task_store)}) thiếu method is_lease_valid! "
            "Fail-closed: từ chối để bảo vệ an toàn dữ liệu."
        )
        self.abort_requested = True
        if self.on_abort:
            try:
                self.on_abort()
            except Exception as err:
                logger.error(f"Lỗi khi thực thi on_abort callback: {err}")
        return False

    def _run_loop(self):
        while not self._stop_event.is_set():
            # Wait ngắt quãng theo interval
            if self._stop_event.wait(timeout=self.interval_seconds):
                break
            try:
                ok = self.task_store.touch_lease(
                    self.task_id,
                    lease_epoch=self.lease_epoch,
                    lease_token=self.lease_token,
                )
                if not ok:
                    logger.warning(
                        f"🚨 [LEASE_LOST] Task {self.task_id} lease epoch {self.lease_epoch} "
                        "không còn hợp lệ (đã bị Reconciler thu hồi hoặc worker khác claim)!"
                    )
                    self.abort_requested = True
                    if self.on_abort:
                        try:
                            self.on_abort()
                        except Exception as e:
                            logger.error(f"Lỗi khi thực thi on_abort callback: {e}")
                    break
            except Exception as err:
                logger.warning(f"Lỗi khi cập nhật lease cho task {self.task_id}: {err}")
