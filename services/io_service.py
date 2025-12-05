# services/io_service.py - v3.0.0
# User interaction utilities
# Non-blocking input with timeout for workflow

import sys
import time
import select
import logging
from typing import Optional


class IOService:
    """Service for user I/O operations with timeout support."""
    
    def __init__(self):
        """Initialize IO service."""
        self.logger = logging.getLogger(__name__)
    
    def input_with_timeout(
        self,
        prompt: str,
        timeout: int = 5,
        default: str = 'y'
    ) -> str:
        """
        Get user input with timeout.
        
        Args:
            prompt: Prompt message
            timeout: Timeout in seconds
            default: Default value if timeout
        
        Returns:
            User input or default
        """
        print(prompt, end='', flush=True)
        
        for i in range(timeout, 0, -1):
            print(f"\r{prompt} ({i}s) ", end='', flush=True)
            
            if sys.platform == 'win32':
                # Windows: use msvcrt
                try:
                    import msvcrt
                    start_time = time.time()
                    buf = []
                    while time.time() - start_time < 1:
                        if msvcrt.kbhit():
                            ch = msvcrt.getwch()
                            if ch in ('\r', '\n'):
                                break
                            buf.append(ch)
                        time.sleep(0.05)
                    
                    if buf:
                        print()
                        return ''.join(buf).strip().lower() or default
                except Exception:
                    time.sleep(1)
            else:
                # Unix: use select
                try:
                    ready, _, _ = select.select([sys.stdin], [], [], 1)
                    if ready:
                        result = sys.stdin.readline().strip().lower()
                        return result if result else default
                except Exception:
                    time.sleep(1)
        
        print(f"\r{prompt} Auto-selected '{default}'")
        return default
    
    def confirm(self, message: str, default: bool = True) -> bool:
        """
        Ask yes/no confirmation.
        
        Args:
            message: Question message
            default: Default answer
        
        Returns:
            True for yes, False for no
        """
        default_str = 'y' if default else 'n'
        result =self.input_with_timeout(
            f"{message} [y/n]: ",
            timeout=10,
            default=default_str
        )
        return result.lower() in ['y', 'yes', 'có', 'c']
