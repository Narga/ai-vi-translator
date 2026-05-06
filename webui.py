# webui.py - v6.2.0
# Entry point cho Novel Translator Web UI
# Logic đã được module hóa trong package webui/

"""
Novel Translator Web UI
======================
Web interface cho dịch thuật với Flask.

Usage:
    uv run python webui.py
    python webui.py --port 7860
"""

from webui import create_app

app = create_app()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Novel Translator Web UI")
    parser.add_argument(
        "--port", "-p", type=int, default=7860, help="Port to run server (default: 7860)"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (use 0.0.0.0 for network access)")
    args = parser.parse_args()

    print("=" * 60)
    print("📚 Novel Translator Web UI v6.2.0")
    print("=" * 60)
    print(f"\n🌐 Mở trình duyệt và truy cập: http://localhost:{args.port}")
    print("\nNhấn Ctrl+C để dừng\n")

    import time
    import socket

    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    max_retries = 5
    for i in range(max_retries):
        try:
            app.run(host=args.host, port=args.port, debug=False, threaded=True)
            break
        except Exception as e:
            # Error 48 is for macOS (EADDRINUSE), Error 98 is for Linux
            err_msg = str(e)
            is_busy = "Address already in use" in err_msg or \
                      (isinstance(e, OSError) and e.errno in (48, 98))
            
            if is_busy:
                print(f"⚠️ Cổng {args.port} đang bận (có thể do tiến trình cũ đang thoát), thử lại sau 2 giây... ({i+1}/{max_retries})")
                time.sleep(2)
            else:
                raise e
    else:
        print(f"❌ Không thể khởi động server trên cổng {args.port} sau {max_retries} lần thử.")
