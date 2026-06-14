# cli.py - v7.0.0
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
            "--version", "-v", action="version", version="%(prog)s 7.0.0"
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

        # Project
        translate_parser.add_argument(
            "--project",
            "-p",
            default="default-project",
            metavar="SLUG",
            help="Slug của dự án (mặc định: default-project)",
        )

        # Input (Optional if project specified)
        translate_parser.add_argument(
            "--input",
            "-i",
            metavar="PATH",
            help="File hoặc thư mục đầu vào (mặc định: project/sources)",
        )

        # Output
        translate_parser.add_argument(
            "--output",
            "-o",
            metavar="DIR",
            help="Thư mục đầu ra (mặc định: project/translated)",
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
        """Xử lý lệnh translate - dùng backend use case."""
        from pathlib import Path
        from backend.infrastructure.config.api_key_service import ApiKeyService
        from backend.infrastructure.config.app_config_service import AppConfigService
        from backend.infrastructure.config.prompt_service import PromptService
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        from backend.infrastructure.workspace.project_service import ProjectService
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        from backend.application.use_cases.translate_text_use_case import TranslateTextUseCase
        from backend.application.dto.translation_request import TranslationRequest

        self.logger.info(f"🚀 Bắt đầu dịch: {args.input}")
        self.logger.info(f"📁 Output: {args.output}")

        try:
            # Khởi tạo services
            config_service = AppConfigService()
            key_service = ApiKeyService()
            prompt_service = PromptService()
            ws_service = WorkspaceService()
            project_service = ProjectService()
            file_service = FileDiscoveryService()

            # Đảm bảo project tồn tại
            project_dir = ws_service.get_project_dir(args.project)
            if not project_dir.exists():
                if args.project == "default-project":
                    project_service.ensure_default_project()
                else:
                    self.logger.error(f"❌ Dự án '{args.project}' không tồn tại.")
                    return 1

            # Load API keys
            api_keys = key_service.load_gemini_keys()
            if not api_keys:
                self.logger.error("❌ Không tìm thấy API keys")
                return 1

            # Resolve paths
            input_dir = Path(args.input) if args.input else project_dir / "sources"
            output_dir = Path(args.output) if args.output else project_dir / "translated"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Tìm files
            files = file_service.find_input_files(input_dir)
            if not files:
                self.logger.warning(f"No files in {input_dir}")
                return 0

            self.logger.info(f"\nFiles: {len(files)}")
            for f in files:
                self.logger.info(f"  • {f.name}")

            # Load prompts
            prompts = prompt_service.load_merged_prompts(project_dir)

            # Glossary paths
            glossary_filenames = ["glossary.txt", "characters.txt"]
            glossary_paths = [
                project_dir / "profile" / gf
                for gf in glossary_filenames
                if (project_dir / "profile" / gf).exists()
            ]

            # Tạo use case
            use_case = TranslateTextUseCase.from_services(
                api_keys=api_keys,
                config_service=config_service,
                prompt_service=prompt_service,
                project_dir=project_dir,
                glossary_paths=glossary_paths or None,
            )

            # Dịch từng file
            ok = fail = 0
            from tqdm import tqdm
            from threading import Lock

            for filepath in files:
                self.logger.info(f"\n{'=' * 80}\n{filepath.name}\n{'=' * 80}")

                try:
                    text_content = filepath.read_text(encoding="utf-8")
                    self.logger.info(f"Source: {len(text_content):,} chars")
                except Exception as e:
                    self.logger.error(f"Cannot read file {filepath.name}: {e}")
                    fail += 1
                    continue

                # Progress bar
                pbar_lock = Lock()
                pbar_state = {"bar": None, "last_current": 0}

                def cli_callback(data, _fname=filepath.name):
                    with pbar_lock:
                        evt_type = data.get("type")
                        if evt_type == "error":
                            self.logger.error(data.get("message", ""))
                        elif evt_type == "progress":
                            bar = pbar_state["bar"]
                            if bar is None:
                                bar = tqdm(total=data["total"], desc=f"Translating {_fname}", unit="chunk")
                                pbar_state["bar"] = bar
                            current = data.get("current", 0)
                            if current > pbar_state["last_current"]:
                                bar.update(current - pbar_state["last_current"])
                                pbar_state["last_current"] = current
                        elif evt_type == "complete":
                            bar = pbar_state["bar"]
                            if bar:
                                bar.close()
                                pbar_state["bar"] = None
                            self.logger.info(data.get("message", ""))

                out_path = output_dir / (filepath.stem + "_translated.txt")

                request = TranslationRequest(
                    text=text_content,
                    output_filename=filepath.stem,
                    output_file_path=out_path,
                    progress_callback=cli_callback,
                )

                result = use_case.execute(request)

                if result.success:
                    ok += 1
                    self.logger.info(f"✅ Saved: {out_path}")
                else:
                    fail += 1
                    self.logger.error(f"❌ Failed: {result.error_message}")

            self.logger.info(f"\n{'=' * 80}\nComplete!\n{'=' * 80}")
            self.logger.info(f"Success: {ok}, Failed: {fail}")
            self.logger.info(f"Output: {output_dir}")

            return 0 if fail == 0 else 1

        except KeyboardInterrupt:
            self.logger.warning("❌ Bị gián đoạn bởi người dùng")
            return 130
        except Exception as e:
            self.logger.critical(f"Error: {e}", exc_info=True)
            return 1

    def _handle_status(self, args) -> int:
        """Xử lý lệnh status - dùng backend services."""
        from pathlib import Path
        from backend.infrastructure.config.api_key_service import ApiKeyService
        from backend.infrastructure.config.app_config_service import AppConfigService
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        from backend.infrastructure.workspace.project_service import ProjectService

        self.logger.info("📊 Trạng thái hệ thống")
        self.logger.info("=" * 50)

        config_service = AppConfigService()
        key_service = ApiKeyService()
        ws_service = WorkspaceService()
        project_service = ProjectService()

        # Check API keys
        if args.api_keys:
            try:
                keys = key_service.load_gemini_keys()
                self.logger.info(f"🔑 API Keys: {len(keys)} loaded")
                for i, key in enumerate(keys[:5], 1):
                    self.logger.info(f"  {i}. ...{key[-4:]}")
                if len(keys) > 5:
                    self.logger.info(f"  ... và {len(keys) - 5} keys khác")
            except Exception as e:
                self.logger.error(f"❌ Lỗi đọc API keys: {e}")

        # Check workspace
        pdir = ws_service.get_project_dir("default-project")
        input_dir = pdir / "sources"
        output_dir = pdir / "translated"

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
