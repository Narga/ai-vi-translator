# src/io_utils.py - v2.6.1
# Tác giả: Narga
# Chức năng: Cung cấp tiện ích nhập liệu không chặn với timeout, dùng chung cho workflow và verification.
# Thiết kế đa nền tảng (Windows dùng msvcrt; Unix dùng select). Khi hết thời gian chờ, tự động trả về giá trị mặc định.

import sys
import time
import select
from typing import Optional

def input_with_timeout(prompt: str, timeout: int = 5, default: str = 'y') -> str:
    """
    Nhận input từ người dùng với thời gian chờ tối đa, trả về giá trị mặc định nếu không có nhập liệu.

    Args:
        prompt (str): Chuỗi hiển thị để hỏi người dùng.
        timeout (int): Thời gian chờ tối đa tính bằng giây.
        default (str): Giá trị trả về khi không có nhập liệu.

    Returns:
        str: Chuỗi người dùng nhập (đã strip, lower), hoặc default nếu timeout.
    """
    # In prompt ngay lập tức để người dùng thấy, tránh buffering.
    print(prompt, end='', flush=True)

    # Đếm ngược theo từng giây để thể hiện còn bao nhiêu thời gian.
    for i in range(timeout, 0, -1):
        print(f"\r{prompt} ({i}s) ", end='', flush=True)
        # Windows: dùng msvcrt để không chặn
        if sys.platform == 'win32':
            try:
                import msvcrt  # Chỉ import khi cần trên Windows
                start_time = time.time()
                while time.time() - start_time < 1:
                    if msvcrt.kbhit():
                        # Đọc một dòng: gom phím cho đến khi gặp Enter
                        chars = []
                        while msvcrt.kbhit():
                            ch = msvcrt.getwch()
                            if ch in ('\r', '\n'):
                                break
                            chars.append(ch)
                        result = ''.join(chars).strip().lower()
                        print()  # Xuống dòng sau khi nhận input
                        return result if result else default
                    time.sleep(0.05)
            except Exception:
                # Nếu có lỗi (hiếm), fallback sang sleep 1s
                time.sleep(1)
        else:
            # Unix-like: dùng select để non-blocking đọc stdin
            try:
                ready, _, _ = select.select([sys.stdin], [], [], 1)
                if ready:
                    result = sys.stdin.readline().strip().lower()
                    return result if result else default
            except Exception:
                time.sleep(1)

    # Hết thời gian chờ, in thông báo và trả về mặc định
    print(f"\r{prompt} Tự động chọn '{default}'")
    return default
