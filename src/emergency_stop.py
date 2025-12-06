# src/emergency_stop.py - v2.1.0
# Tác giả: Narga
# Chức năng: Module quản lý cơ chế dừng khẩn cấp toàn cục.

import threading
import logging
import signal
import sys

# Cờ (event) toàn cục để báo hiệu dừng, an toàn cho đa luồng
_emergency_stop = threading.Event()

def emergency_stop(reason: str = "Không rõ lý do"):
    """
    Kích hoạt cờ dừng khẩn cấp. Tất cả các luồng đang hoạt động sẽ
    kiểm tra cờ này và dừng lại một cách an toàn.
    """
    if not _emergency_stop.is_set():
        _emergency_stop.set()
        logging.critical(f"🚨 KÍCH HOẠT DỪNG KHẨN CẤP: {reason}")
        logging.critical("Tất cả các tác vụ sẽ dừng lại sau khi hoàn thành bước hiện tại...")

def check_emergency_stop() -> bool:
    """Kiểm tra xem cờ dừng khẩn cấp đã được kích hoạt chưa."""
    return _emergency_stop.is_set()

def reset_emergency_stop():
    """Reset lại cờ dừng khẩn cấp cho một phiên làm việc mới."""
    if _emergency_stop.is_set():
        logging.info("🔄 Reset lại cờ dừng khẩn cấp.")
        _emergency_stop.clear()

def signal_handler(sig, frame):
    """
    Hàm xử lý khi người dùng nhấn Ctrl+C.
    Kích hoạt cơ chế dừng khẩn cấp một cách an toàn.
    """
    print("\n") # Xuống dòng cho đẹp
    logging.warning("🛑 Nhận được tín hiệu dừng (Ctrl+C).")
    emergency_stop("Người dùng nhấn Ctrl+C")
    # Đợi một chút để các luồng khác có thời gian xử lý
    # sys.exit(0) # Không nên thoát đột ngột ở đây

def setup_signal_handlers():
    """Thiết lập các trình xử lý tín hiệu hệ thống."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)