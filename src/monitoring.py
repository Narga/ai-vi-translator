# src/monitoring.py - v2.1.0
# Tác giả: Narga
# Chức năng: Module giám sát "sức khỏe" của quy trình dịch thuật.

import time
import logging
from threading import Lock
from .emergency_stop import emergency_stop

class HealthMonitor:
    """
    Giám sát quy trình dịch để phát hiện các sự cố như bị treo (stalled)
    hoặc chạy quá lâu và kích hoạt dừng khẩn cấp nếu cần.
    """
    def __init__(self, max_runtime_hours: int = 24, stall_threshold_minutes: int = 30):
        self.start_time = time.time()
        self.last_progress_time = time.time()
        self.last_progress_count = 0
        self.max_runtime_seconds = max_runtime_hours * 3600
        self.stall_threshold_seconds = stall_threshold_minutes * 600
        self._lock = Lock()
        logging.info(f"⛑️ HealthMonitor đã khởi động (Max runtime: {max_runtime_hours}h, Stall threshold: {stall_threshold_minutes}min).")

    def update_progress(self, current_count: int) -> bool:
        """
        Cập nhật tiến trình và kiểm tra sức khỏe hệ thống.

        Args:
            current_count (int): Số lượng chunk đã hoàn thành.

        Returns:
            bool: True nếu hệ thống khỏe mạnh, False nếu có sự cố.
        """
        with self._lock:
            current_time = time.time()
            
            # Nếu có tiến triển, cập nhật thời gian
            if current_count > self.last_progress_count:
                self.last_progress_time = current_time
                self.last_progress_count = current_count
            
            # Kiểm tra thời gian chạy tối đa
            if current_time - self.start_time > self.max_runtime_seconds:
                reason = f"Vượt quá thời gian chạy tối đa ({self.max_runtime_seconds / 3600} giờ)."
                logging.critical(f"💀 HealthMonitor: {reason}")
                emergency_stop(reason)
                return False
            
            # Kiểm tra tình trạng bị treo
            if current_time - self.last_progress_time > self.stall_threshold_seconds:
                reason = f"Hệ thống bị treo, không có tiến triển trong {self.stall_threshold_seconds / 60} phút."
                logging.critical(f"💀 HealthMonitor: {reason}")
                emergency_stop(reason)
                return False
            
            return True