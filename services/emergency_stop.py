# services/emergency_stop.py - v4.0.0
# Tác giả: Narga
# Chức năng: Cơ chế dừng khẩn cấp an toàn cho tất cả processes.
# Tham khảo từ: Book_translator v13.3.9

"""
Emergency Stop - Cơ chế dừng khẩn cấp toàn hệ thống.

Tính năng:
- Thread-safe global flag
- Reason tracking
- Decorator cho functions
- Graceful shutdown

Sử dụng:
    from services.emergency_stop import emergency_stop, check_emergency_stop
    
    # Kích hoạt dừng khẩn cấp
    emergency_stop("Tất cả API keys đã hết quota")
    
    # Kiểm tra trong loop
    if check_emergency_stop():
        break
"""

import time
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from functools import wraps


# ====================================================================== 
# GLOBAL STATE - Thread-safe
# ======================================================================

_emergency_stop_event = threading.Event()
_emergency_lock = threading.Lock()
_emergency_reason = ""
_emergency_timestamp = 0.0
_logger = logging.getLogger(__name__)


# ====================================================================== 
# PUBLIC FUNCTIONS
# ======================================================================

def emergency_stop(reason: str = "Manual trigger") -> None:
    """
    Kích hoạt dừng khẩn cấp cho toàn hệ thống.
    
    Sau khi gọi, tất cả các processes kiểm tra check_emergency_stop()
    sẽ nhận được True và nên dừng ngay lập tức.
    
    Args:
        reason (str): Lý do dừng khẩn cấp
    """
    global _emergency_reason, _emergency_timestamp
    
    with _emergency_lock:
        if not _emergency_stop_event.is_set():
            _emergency_stop_event.set()
            _emergency_reason = reason
            _emergency_timestamp = time.time()
            
            _logger.critical(f"🚨 EMERGENCY STOP ACTIVATED: {reason}")
            _logger.critical("🚨 All running processes will be terminated safely")
        else:
            _logger.warning(f"🚨 Emergency stop already active: {_emergency_reason}")


def check_emergency_stop() -> bool:
    """
    Kiểm tra xem emergency stop đã được kích hoạt chưa.
    
    Returns:
        bool: True nếu đã kích hoạt emergency stop
    """
    return _emergency_stop_event.is_set()


def reset_emergency_stop() -> None:
    """
    Reset emergency stop flag để cho phép workflow mới.
    
    Chỉ nên gọi khi bắt đầu workflow mới hoặc sau khi đã xử lý
    xong tình huống khẩn cấp.
    """
    global _emergency_reason, _emergency_timestamp
    
    with _emergency_lock:
        if _emergency_stop_event.is_set():
            _emergency_stop_event.clear()
            old_reason = _emergency_reason
            _emergency_reason = ""
            _emergency_timestamp = 0.0
            
            _logger.info(f"🔄 Emergency stop reset (was: {old_reason})")
        else:
            _logger.info("🔄 Emergency stop reset (was not active)")


def get_emergency_info() -> Dict[str, Any]:
    """
    Lấy thông tin chi tiết về emergency stop.
    
    Returns:
        Dict với các thông tin: active, reason, elapsed_seconds, timestamp
    """
    with _emergency_lock:
        if _emergency_stop_event.is_set():
            elapsed = time.time() - _emergency_timestamp if _emergency_timestamp > 0 else 0
            return {
                'active': True,
                'reason': _emergency_reason,
                'elapsed_seconds': elapsed,
                'timestamp': (
                    datetime.fromtimestamp(_emergency_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    if _emergency_timestamp > 0 else None
                )
            }
        else:
            return {
                'active': False,
                'reason': None,
                'elapsed_seconds': 0,
                'timestamp': None
            }





class EmergencyStopError(Exception):
    """Exception khi operation bị chặn bởi emergency stop."""
    pass


# ====================================================================== 
# SIGNAL HANDLER
# ======================================================================

def setup_signal_handlers() -> None:
    """
    Cài đặt signal handlers để bắt SIGINT (Ctrl+C) và SIGTERM.
    
    Khi nhận signal, sẽ kích hoạt emergency stop.
    """
    import signal
    
    def signal_handler(signum, frame):
        signal_name = signal.Signals(signum).name
        emergency_stop(f"Received signal {signal_name}")
    
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        _logger.info("📡 Signal handlers installed (SIGINT, SIGTERM)")
    except Exception as e:
        _logger.warning(f"⚠️ Could not install signal handlers: {e}")
