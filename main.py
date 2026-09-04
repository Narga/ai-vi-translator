"""Điểm vào chính: tự bật WebUI server. CLI (run.py) chỉ là tính năng phụ."""

import sys

from server import run


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    run(host, port)
