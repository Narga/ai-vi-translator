# tests/smoke/test_cli_help.py
# Smoke tests cho CLI parser

import sys
import pytest
from pathlib import Path

# Đảm bảo import được cli module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestCLIParser:
    """Test CLI parser cơ bản."""

    def test_import_cli(self):
        """Test rằng cli module import được."""
        import cli
        assert hasattr(cli, "NovelTranslatorCLI")
        assert hasattr(cli, "main")

    def test_create_parser(self):
        """Test rằng parser được tạo đúng."""
        from cli import NovelTranslatorCLI
        cli_instance = NovelTranslatorCLI()
        parser = cli_instance.parser
        assert parser is not None
        assert parser.prog == "novel-translator"

    def test_parser_has_subcommands(self):
        """Test rằng parser có các subcommands cần thiết."""
        from cli import NovelTranslatorCLI
        cli_instance = NovelTranslatorCLI()
        parser = cli_instance.parser

        # Parse --help để verify parser hoạt động
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_translate_command_parse(self):
        """Test rằng translate command parse đúng."""
        from cli import NovelTranslatorCLI
        cli_instance = NovelTranslatorCLI()

        # Test basic translate args
        args = cli_instance.parser.parse_args(["translate", "-i", "input.txt"])
        assert args.command == "translate"
        assert args.input == "input.txt"
        assert args.project == "default-project"

    def test_translate_command_aliases(self):
        """Test rằng translate command có aliases."""
        from cli import NovelTranslatorCLI
        cli_instance = NovelTranslatorCLI()

        # Test alias 't'
        args = cli_instance.parser.parse_args(["t", "-i", "input.txt"])
        assert args.command == "t"

    def test_status_command_parse(self):
        """Test rằng status command parse đúng."""
        from cli import NovelTranslatorCLI
        cli_instance = NovelTranslatorCLI()

        args = cli_instance.parser.parse_args(["status"])
        assert args.command == "status"

    def test_resume_command_parse(self):
        """Test rằng resume command parse đúng."""
        from cli import NovelTranslatorCLI
        cli_instance = NovelTranslatorCLI()

        args = cli_instance.parser.parse_args(["resume", "-c", "checkpoint.json"])
        assert args.command == "resume"
        assert args.checkpoint == "checkpoint.json"

    def test_serve_command_parse(self):
        """Test rằng serve command parse đúng."""
        from cli import NovelTranslatorCLI
        cli_instance = NovelTranslatorCLI()

        args = cli_instance.parser.parse_args(["serve"])
        assert args.command == "serve"
        assert args.host == "localhost"
        assert args.port == 8080

    def test_version_flag(self):
        """Test rằng --version flag hoạt động."""
        from cli import NovelTranslatorCLI
        cli_instance = NovelTranslatorCLI()

        with pytest.raises(SystemExit) as exc_info:
            cli_instance.parser.parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_verbose_flag(self):
        """Test rằng --verbose flag hoạt động."""
        from cli import NovelTranslatorCLI
        cli_instance = NovelTranslatorCLI()

        args = cli_instance.parser.parse_args(["--verbose", "status"])
        assert args.verbose is True

    def test_no_command_shows_help(self):
        """Test rằng không có command sẽ hiển thị help."""
        from cli import NovelTranslatorCLI
        cli_instance = NovelTranslatorCLI()

        result = cli_instance.run([])
        assert result == 1  # Exit code 1 khi không có command
