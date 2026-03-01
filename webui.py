# webui.py - v5.0.0
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
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    args = parser.parse_args()

    print("=" * 60)
    print("📚 Novel Translator Web UI v5.0.0")
    print("=" * 60)
    print(f"\n🌐 Mở trình duyệt và truy cập: http://localhost:{args.port}")
    print("\nNhấn Ctrl+C để dừng\n")

    app.run(host=args.host, port=args.port, debug=False, threaded=True)
