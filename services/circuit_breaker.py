# services/circuit_breaker.py - v4.0.0
# Tác giả: Narga
# Chức năng: Circuit Breaker pattern để ngăn chặn cascade failures khi gọi API.
# Tham khảo từ: Book_translator v13.3.9

"""
Circuit Breaker - Bảo vệ hệ thống khỏi cascade failures.

States:
- CLOSED: Hoạt động bình thường, cho phép requests
- OPEN: Đã đạt ngưỡng lỗi, chặn tất cả requests
- HALF_OPEN: Thử nghiệm phục hồi, cho phép 1 request

Sử dụng:
    breaker = CircuitBreaker(failure_threshold=10, timeout=300)
    result = breaker.call(api_function, *args)
"""

import time
import logging
from threading import Lock
from typing import Callable, Any, Optional, Dict
from enum import Enum


class CircuitState(Enum):
    """Trạng thái của Circuit Breaker."""
    CLOSED = "CLOSED"       # Hoạt động bình thường
    OPEN = "OPEN"           # Đang chặn requests
    HALF_OPEN = "HALF_OPEN" # Đang thử nghiệm phục hồi


class CircuitBreakerError(Exception):
    """Exception khi Circuit Breaker đang OPEN."""
    pass


class CircuitBreaker:
    """
    Circuit Breaker để bảo vệ hệ thống khỏi cascade failures.
    
    Khi số lỗi liên tiếp vượt ngưỡng, breaker chuyển sang OPEN và
    chặn tất cả requests trong một khoảng thời gian (timeout).
    Sau đó chuyển sang HALF_OPEN để thử nghiệm phục hồi.
    
    Attributes:
        failure_threshold (int): Số lỗi liên tiếp để kích hoạt OPEN
        timeout (int): Thời gian (giây) ở trạng thái OPEN trước khi thử lại
        state (CircuitState): Trạng thái hiện tại
    """
    
    def __init__(
        self,
        failure_threshold: int = 10,
        timeout: int = 300,
        name: str = "default"
    ):
        """
        Khởi tạo Circuit Breaker.
        
        Args:
            failure_threshold (int): Số lỗi để kích hoạt OPEN (mặc định: 10)
            timeout (int): Thời gian OPEN tính bằng giây (mặc định: 300 = 5 phút)
            name (str): Tên breaker để logging
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.name = name
        
        self._failure_count = 0
        self._last_failure_time = 0
        self._state = CircuitState.CLOSED
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)
        
        self._logger.info(
            f"🔌 Circuit Breaker '{name}' initialized: "
            f"threshold={failure_threshold}, timeout={timeout}s"
        )
    
    @property
    def state(self) -> CircuitState:
        """Trả về trạng thái hiện tại của breaker."""
        with self._lock:
            return self._state
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Thực thi function với bảo vệ của Circuit Breaker.
        
        Args:
            func (Callable): Function cần thực thi
            *args: Positional arguments cho function
            **kwargs: Keyword arguments cho function
        
        Returns:
            Any: Kết quả từ function
        
        Raises:
            CircuitBreakerError: Khi breaker đang OPEN
        """
        # Kiểm tra trạng thái trước khi gọi
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Kiểm tra xem có thể chuyển sang HALF_OPEN chưa
                if time.time() - self._last_failure_time >= self.timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._logger.info(
                        f"🔌 Circuit Breaker '{self.name}': OPEN → HALF_OPEN (testing recovery)"
                    )
                else:
                    remaining = self.timeout - (time.time() - self._last_failure_time)
                    raise CircuitBreakerError(
                        f"Circuit Breaker '{self.name}' OPEN - "
                        f"bị chặn trong {remaining:.0f}s nữa"
                    )
        
        # Thực thi function
        try:
            result = func(*args, **kwargs)
            
            # Thành công - reset breaker
            with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    self._logger.info(
                        f"🔌 Circuit Breaker '{self.name}': HALF_OPEN → CLOSED (recovered)"
                    )
                
                self._state = CircuitState.CLOSED
                self._failure_count = 0
            
            return result
        
        except Exception as e:
            # Lỗi - tăng failure count
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()
                
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._logger.critical(
                        f"🔌 Circuit Breaker '{self.name}': CLOSED → OPEN "
                        f"after {self._failure_count} consecutive failures"
                    )
            
            raise e
    
    def get_state_info(self) -> Dict[str, Any]:
        """
        Trả về thông tin chi tiết về trạng thái breaker.
        
        Returns:
            Dict chứa state, failure_count, time_since_last_failure
        """
        with self._lock:
            return {
                'name': self.name,
                'state': self._state.value,
                'failure_count': self._failure_count,
                'failure_threshold': self.failure_threshold,
                'timeout': self.timeout,
                'time_since_last_failure': (
                    time.time() - self._last_failure_time 
                    if self._last_failure_time > 0 else 0
                ),
                'time_until_retry': max(
                    0, 
                    self.timeout - (time.time() - self._last_failure_time)
                ) if self._state == CircuitState.OPEN else 0
            }
    
    def reset(self) -> None:
        """Reset breaker về trạng thái CLOSED."""
        with self._lock:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0
            
            if old_state != CircuitState.CLOSED:
                self._logger.info(
                    f"🔄 Circuit Breaker '{self.name}': {old_state.value} → CLOSED (manual reset)"
                )
    
    def force_open(self, reason: str = "Manual trigger") -> None:
        """
        Buộc breaker chuyển sang OPEN.
        
        Args:
            reason (str): Lý do buộc OPEN
        """
        with self._lock:
            self._state = CircuitState.OPEN
            self._last_failure_time = time.time()
            self._logger.warning(
                f"🔌 Circuit Breaker '{self.name}': Forced OPEN - {reason}"
            )
