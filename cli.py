# cli.py - v4.0.0
# Tác giả: Narga
# Chức năng: Command-line interface cho Novel Translator

"""
Novel Translator CLI
=====================
Cung cấp giao diện dòng lệnh mạnh mẽ với argparse.

Usage:
    python cli.py translate -i input/novel.txt
    python cli.py translate -i input/ -o output/
    python cli.py status
    python cli.py resume --checkpoint path/to/checkpoint.json
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Thiết lập logging cho CLI."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    return logging.getLogger(__name__)


class NovelTranslatorCLI:
    """CLI Controller cho Novel Translator."""

    def __init__(self):
        self.parser = self._create_parser()
        self.logger = logging.getLogger(__name__)

    def _create_parser(self) -> argparse.ArgumentParser:
        """Tạo argument parser."""
        parser = argparse.ArgumentParser(
            prog="novel-translator",
            description="📚 Novel Translator - Dịch tiểu thuyết tự động với Gemini AI",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Ví dụ sử dụng:
  %(prog)s translate -i input/novel.txt
  %(prog)s translate -i input/ -o output/
  %(prog)s translate -i input/ --dry-run
  %(prog)s status
  %(prog)s resume --checkpoint workspace/checkpoints/2024-01-01.json
            """,
        )

        # Version
        parser.add_argument(
            "--version", "-v", action="version", version="%(prog)s 4.0.0"
        )

        # Global options
        parser.add_argument(
            "--verbose", "-V", action="store_true", help="Bật chế độ debug"
        )

        # Subcommands
        subparsers = parser.add_subparsers(
            title="commands", dest="command", help="Các lệnh có sẵn"
        )

        # Translate command
        self._add_translate_command(subparsers)

        # Status command
        self._add_status_command(subparsers)

        # Resume command
        self._add_resume_command(subparsers)

        # Serve command (future: web UI)
        self._add_serve_command(subparsers)

        return parser

    def _add_translate_command(self, subparsers) -> None:
        """Thêm lệnh translate."""
        translate_parser = subparsers.add_parser(
            "translate", aliases=["t", "dịch"], help="Dịch file hoặc thư mục"
        )

        # Input
        translate_parser.add_argument(
            "--input",
            "-i",
            required=True,
            metavar="PATH",
            help="File hoặc thư mục đầu vào",
        )

        # Output
        translate_parser.add_argument(
            "--output",
            "-o",
            default="workspace/output",
            metavar="DIR",
            help="Thư mục đầu ra (mặc định: workspace/output)",
        )

        # Config
        translate_parser.add_argument(
            "--config",
            "-c",
            default="config/app.ini",
            metavar="FILE",
            help="File cấu hình (mặc định: config/app.ini)",
        )

        # Dry run
        translate_parser.add_argument(
            "--dry-run", action="store_true", help="Chạy thử không gọi API"
        )

        # Resume
        translate_parser.add_argument(
            "--resume", metavar="CHECKPOINT", help="Tiếp tục từ checkpoint"
        )

        # Language
        translate_parser.add_argument(
            "--lang",
            "-l",
            default="CN",
            choices=["CN", "EN", "JP", "KR"],
            help="Ngôn ngữ nguồn (mặc định: CN)",
        )

        # Model
        translate_parser.add_argument(
            "--model",
            "-m",
            default="gemini-3-flash-preview",
            help="Model AI (mặc định: gemini-3-flash-preview)",
        )

        # Temperature
        translate_parser.add_argument(
            "--temperature",
            "-t",
            type=float,
            default=1.0,
            help="Temperature cho model (mặc định: 1.0)",
        )

        # Chunk size
        translate_parser.add_argument(
            "--chunk-size",
            type=int,
            default=22000,
            help="Kích thước chunk tối đa (mặc định: 22000)",
        )

        # Force
        translate_parser.add_argument(
            "--force",
            "-f",
            action="store_true",
            help="Dịch lại cả những file đã có trong cache",
        )

        # Quiet
        translate_parser.add_argument(
            "--quiet", "-q", action="store_true", help="Chỉ hiển thị cảnh báo và lỗi"
        )

    def _add_status_command(self, subparsers) -> None:
        """Thêm lệnh status."""
        status_parser = subparsers.add_parser(
            "status", aliases=["s", "trạng thái"], help="Hiển thị trạng thái hệ thống"
        )

        status_parser.add_argument(
            "--api-keys", action="store_true", help="Hiển thị thông tin API keys"
        )

        status_parser.add_argument(
            "--cache", action="store_true", help="Hiển thị thống kê cache"
        )

    def _add_resume_command(self, subparsers) -> None:
        """Thêm lệnh resume."""
        resume_parser = subparsers.add_parser(
            "resume", aliases=["r", "tiếp tục"], help="Tiếp tục từ checkpoint"
        )

        resume_parser.add_argument(
            "--checkpoint",
            "-c",
            required=True,
            metavar="FILE",
            help="File checkpoint để tiếp tục",
        )

        resume_parser.add_argument(
            "--force", "-f", action="store_true", help="Tiếp tục cả khi checkpoint cũ"
        )

    def _add_serve_command(self, subparsers) -> None:
        """Thêm lệnh serve (future web UI)."""
        serve_parser = subparsers.add_parser(
            "serve", help="Khởi động web UI (chưa khả dụng)"
        )

        serve_parser.add_argument(
            "--host", default="localhost", help="Host (mặc định: localhost)"
        )

        serve_parser.add_argument(
            "--port", "-p", type=int, default=8080, help="Port (mặc định: 8080)"
        )

    def run(self, args: Optional[List[str]] = None) -> int:
        """
        Chạy CLI.

        Args:
            args: Arguments (mặc định: sys.argv)

        Returns:
            Exit code
        """
        parsed = self.parser.parse_args(args)

        if not parsed.command:
            self.parser.print_help()
            return 1

        # Setup logging
        setup_logging(parsed.verbose)

        # Route to handler
        if parsed.command in ["translate", "t", "dịch"]:
            return self._handle_translate(parsed)
        elif parsed.command in ["status", "s", "trạng thái"]:
            return self._handle_status(parsed)
        elif parsed.command in ["resume", "r", "tiếp tục"]:
            return self._handle_resume(parsed)
        elif parsed.command == "serve":
            return self._handle_serve(parsed)

        return 0

    def _handle_translate(self, args) -> int:
        """Xử lý lệnh translate."""
        from main import main as run_translation

        # Build arguments for main.py
        sys.argv = ["novel-translator"]

        if args.dry_run:
            sys.argv.append("--dry-run")
        if args.resume:
            sys.argv.extend(["--resume", args.resume])
        if args.force:
            sys.argv.append("--force")
        if args.quiet:
            sys.argv.append("--quiet")

        sys.argv.extend(["-i", args.input, "-o", args.output])

        # Override config
        if args.config != "config/app.ini":
            sys.argv.extend(["--config", args.config])

        self.logger.info(f"🚀 Bắt đầu dịch: {args.input}")
        self.logger.info(f"📁 Output: {args.output}")

        try:
            return run_translation()
        except KeyboardInterrupt:
            self.logger.warning("❌ Bị gián đoạn bởi người dùng")
            return 130

    def _handle_status(self, args) -> int:
        """Xử lý lệnh status."""
        from services.api_service import ApiManager
        from services.cache_service import TranslationCache
        from pathlib import Path

        self.logger.info("📊 Trạng thái hệ thống")
        self.logger.info("=" * 50)

        # Check API keys
        if args.api_keys:
            try:
                from main import load_api_keys

                keys = load_api_keys()
                self.logger.info(f"🔑 API Keys: {len(keys)} loaded")
                for i, key in enumerate(keys[:5], 1):
                    self.logger.info(f"  {i}. ...{key[-4:]}")
                if len(keys) > 5:
                    self.logger.info(f"  ... và {len(keys) - 5} keys khác")
            except Exception as e:
                self.logger.error(f"❌ Lỗi đọc API keys: {e}")

        # Check cache
        if args.cache:
            cache_dir = Path("workspace/cache")
            if cache_dir.exists():
                cache_files = list(cache_dir.glob("*.pkl"))
                self.logger.info(f"📦 Cache: {len(cache_files)} items")
            else:
                self.logger.info("📦 Cache: Chưa khởi tạo")

        # Check workspace
        input_dir = Path("workspace/input")
        output_dir = Path("workspace/output")

        self.logger.info(
            f"📂 Input: {input_dir} ({'exists' if input_dir.exists() else 'not found'})"
        )
        self.logger.info(
            f"📂 Output: {output_dir} ({'exists' if output_dir.exists() else 'not found'})"
        )

        return 0

    def _handle_resume(self, args) -> int:
        """Xử lý lệnh resume."""
        checkpoint_path = Path(args.checkpoint)

        if not checkpoint_path.exists():
            self.logger.error(f"❌ Không tìm thấy checkpoint: {args.checkpoint}")
            return 1

        self.logger.info(f"🔄 Tiếp tục từ: {args.checkpoint}")

        # TODO: Implement checkpoint resume logic
        self.logger.warning("⚠️ Chức năng resume đang được phát triển")

        return 0

    def _handle_serve(self, args) -> int:
        """Xử lý lệnh serve."""
        self.logger.error("❌ Web UI chưa khả dụng")
        self.logger.info("💡 Sử dụng CLI để dịch thuật:")
        self.logger.info("   python cli.py translate -i input/novel.txt")
        return 1


def main() -> int:
    """Entry point cho CLI."""
    cli = NovelTranslatorCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
