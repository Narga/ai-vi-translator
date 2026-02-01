# services/health_monitor.py - v4.0.0
# Tác giả: Narga
# Chức năng: Giám sát sức khỏe hệ thống và phát hiện stuck processes.
# Tham khảo từ: Book_translator v13.3.9

"""
Health Monitor - Giám sát sức khỏe hệ thống.

Tính năng:
- Theo dõi runtime tổng
- Phát hiện stall (không có tiến độ)
- Giám sát memory usage
- Health check API

Sử dụng:
    monitor = HealthMonitor(max_runtime_hours=48)
    is_healthy = monitor.update_progress(current_count)
"""

import time
import logging
from threading import Lock
from typing import Dict, Any, Optional
from datetime import datetime


class HealthMonitor:
    """
    Giám sát sức khỏe hệ thống và phát hiện các vấn đề.
    
    - Phát hiện process bị stuck (không tiến độ)
    - Giới hạn runtime tối đa
    - Theo dõi memory usage
    
    Attributes:
        max_runtime (float): Thời gian chạy tối đa (giây)
        stall_threshold (float): Thời gian không tiến độ để coi là stalled (giây)
    """
    
    def __init__(
        self,
        max_runtime_hours: int = 48,
        stall_threshold_minutes: int = 30,
        name: str = "default"
    ):
        """
        Khởi tạo Health Monitor.
        
        Args:
            max_runtime_hours (int): Runtime tối đa tính bằng giờ (mặc định: 48)
            stall_threshold_minutes (int): Thời gian stall tính bằng phút (mặc định: 30)
            name (str): Tên monitor để logging
        """
        self.name = name
        self.max_runtime = max_runtime_hours * 3600
        self.stall_threshold = stall_threshold_minutes * 60
        
        self._start_time = time.time()
        self._last_progress_time = time.time()
        self._last_progress_count = 0
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)
        
        self._logger.info(
            f"🏥 Health Monitor '{name}' initialized: "
            f"max_runtime={max_runtime_hours}h, stall_threshold={stall_threshold_minutes}min"
        )
    
    def update_progress(self, current_count: int) -> bool:
        """
        Cập nhật tiến độ và kiểm tra sức khỏe hệ thống.
        
        Args:
            current_count (int): Số lượng items đã xử lý
        
        Returns:
            bool: True nếu hệ thống healthy, False nếu có vấn đề
        """
        with self._lock:
            current_time = time.time()
            
            # Cập nhật tiến độ nếu có progress
            if current_count > self._last_progress_count:
                self._last_progress_time = current_time
                self._last_progress_count = current_count
            
            # Tính toán metrics
            elapsed_total = current_time - self._start_time
            elapsed_since_progress = current_time - self._last_progress_time
            
            # Kiểm tra runtime
            if elapsed_total > self.max_runtime:
                self._logger.critical(
                    f"💀 Health Monitor '{self.name}': Maximum runtime exceeded "
                    f"({elapsed_total/3600:.1f}h > {self.max_runtime/3600:.1f}h)"
                )
                return False
            
            # Kiểm tra stall (chỉ sau khi có ít nhất 1 progress)
            if elapsed_since_progress > self.stall_threshold and current_count > 0:
                self._logger.critical(
                    f"💀 Health Monitor '{self.name}': System stalled for "
                    f"{elapsed_since_progress/60:.1f} minutes (threshold: {self.stall_threshold/60:.1f}min)"
                )
                return False
            
            # Kiểm tra memory (optional)
            memory_ok = self._check_memory()
            if not memory_ok:
                return False
            
            return True
    
    def _check_memory(self) -> bool:
        """
        Kiểm tra memory usage.
        
        Returns:
            bool: True nếu memory OK, False nếu critical
        """
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
            
            if memory_percent > 95:
                self._logger.critical(
                    f"💀 Health Monitor '{self.name}': Critical memory usage {memory_percent:.1f}%"
                )
                return False
            elif memory_percent > 85:
                self._logger.warning(
                    f"⚠️ Health Monitor '{self.name}': High memory usage {memory_percent:.1f}%"
                )
            
            return True
        except ImportError:
            # psutil không có, bỏ qua memory check
            return True
    
    def get_health_info(self) -> Dict[str, Any]:
        """
        Lấy thông tin sức khỏe hiện tại.
        
        Returns:
            Dict với các metrics sức khỏe
        """
        with self._lock:
            current_time = time.time()
            elapsed_total = current_time - self._start_time
            elapsed_since_progress = current_time - self._last_progress_time
            
            # Memory info
            memory_percent = None
            try:
                import psutil
                memory_percent = psutil.virtual_memory().percent
            except ImportError:
                pass
            
            return {
                'name': self.name,
                'runtime_hours': elapsed_total / 3600,
                'runtime_remaining_hours': max(0, (self.max_runtime - elapsed_total) / 3600),
                'minutes_since_progress': elapsed_since_progress / 60,
                'stall_threshold_minutes': self.stall_threshold / 60,
                'last_progress_count': self._last_progress_count,
                'memory_percent': memory_percent,
                'is_healthy': self._is_healthy_internal(elapsed_total, elapsed_since_progress),
                'start_time': datetime.fromtimestamp(self._start_time).isoformat(),
                'last_progress_time': datetime.fromtimestamp(self._last_progress_time).isoformat()
            }
    
    def _is_healthy_internal(self, elapsed_total: float, elapsed_since_progress: float) -> bool:
        """Kiểm tra sức khỏe nội bộ (không lock)."""
        if elapsed_total > self.max_runtime:
            return False
        if elapsed_since_progress > self.stall_threshold and self._last_progress_count > 0:
            return False
        return True
    
    def reset(self) -> None:
        """Reset monitor về trạng thái ban đầu."""
        with self._lock:
            self._start_time = time.time()
            self._last_progress_time = time.time()
            self._last_progress_count = 0
            self._logger.info(f"🔄 Health Monitor '{self.name}' reset")
    
    def extend_runtime(self, additional_hours: float) -> None:
        """
        Gia hạn thời gian runtime tối đa.
        
        Args:
            additional_hours (float): Số giờ cần thêm
        """
        with self._lock:
            old_max = self.max_runtime / 3600
            self.max_runtime += additional_hours * 3600
            self._logger.info(
                f"⏰ Health Monitor '{self.name}': Extended runtime "
                f"{old_max:.1f}h → {self.max_runtime/3600:.1f}h"
            )
