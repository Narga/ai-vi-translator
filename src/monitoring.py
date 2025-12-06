# src/monitoring.py - v2.6.1
# Tác giả: Narga
# Chức năng: Module giám sát "sức khỏe" của quy trình dịch thuật.
# - Phát hiện treo (stall) dựa trên thời gian không có tiến triển.
# - Dừng khẩn cấp khi vượt quá thời gian chạy tối đa hoặc phát hiện treo.
# THAY ĐỔI v2.6.1:
# - Sửa đơn vị chuyển phút→giây: stall_threshold_seconds = stall_threshold_minutes * 60 (trước đây *600 là sai).
# - Bổ sung comment chi tiết và thông điệp log rõ ràng cho nhánh dừng khẩn.

import time
import logging
from threading import Lock
from .emergency_stop import emergency_stop

class HealthMonitor:
    """
    Giám sát quy trình dịch để phát hiện các sự cố như bị treo (stalled)
    hoặc chạy quá lâu và kích hoạt dừng khẩn cấp nếu cần.

    Cơ chế:
    - Mỗi khi đạt tiến triển (current_count tăng), cập nhật last_progress_time.
    - Nếu thời gian từ last_progress_time vượt quá stall_threshold_seconds → dừng khẩn cấp.
    - Nếu tổng thời gian chạy vượt max_runtime_seconds → dừng khẩn cấp.
    """

    def __init__(self, max_runtime_hours: int = 24, stall_threshold_minutes: int = 30):
        """
        Khởi tạo bộ giám sát.

        Args:
            max_runtime_hours (int): Số giờ tối đa được phép chạy trước khi dừng.
            stall_threshold_minutes (int): Số phút không có tiến triển được coi là "treo".
        """
        self.start_time = time.time()
        self.last_progress_time = time.time()
        self.last_progress_count = 0
        self.max_runtime_seconds = max_runtime_hours * 3600
        # Sửa đơn vị phút → giây (đúng): 60; trước đây 600 là sai và gây ngưỡng gấp 10 lần
        self.stall_threshold_seconds = stall_threshold_minutes * 60
        self._lock = Lock()
        logging.info(
            f"⛑️ HealthMonitor đã khởi động (Max runtime: {max_runtime_hours}h, "
            f"Stall threshold: {stall_threshold_minutes}min)."
        )

    def update_progress(self, current_count: int) -> bool:
        """
        Cập nhật tiến trình và kiểm tra sức khỏe hệ thống.

        Args:
            current_count (int): Số lượng đơn vị công việc đã hoàn thành (chunk/file).

        Returns:
            bool: True nếu hệ thống khỏe mạnh, False nếu phát hiện sự cố và đã dừng khẩn cấp.
        """
        with self._lock:
            current_time = time.time()

            # Nếu có tiến triển, cập nhật mốc thời gian và bộ đếm
            if current_count > self.last_progress_count:
                self.last_progress_time = current_time
                self.last_progress_count = current_count

            # Kiểm tra thời gian chạy tối đa
            if current_time - self.start_time > self.max_runtime_seconds:
                reason = f"Vượt quá thời gian chạy tối đa ({self.max_runtime_seconds / 3600:.1f} giờ)."
                logging.critical(f"💀 HealthMonitor: {reason}")
                emergency_stop(reason)
                return False

            # Kiểm tra tình trạng bị treo (không có tiến triển trong ngưỡng cho phép)
            if current_time - self.last_progress_time > self.stall_threshold_seconds:
                reason = (
                    f"Hệ thống bị treo, không có tiến triển trong "
                    f"{self.stall_threshold_seconds / 60:.1f} phút."
                )
                logging.critical(f"💀 HealthMonitor: {reason}")
                emergency_stop(reason)
                return False

            return True
