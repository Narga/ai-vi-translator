# tests/unit/test_translation_executor.py
# Unit tests cho TranslationExecutor force_retranslate behavior

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def mock_deps():
    """Mock các dependencies của TranslationExecutor."""
    with patch("core.executor.CheckpointService") as mock_cp_cls, \
         patch("core.executor.robust_translate") as mock_translate, \
         patch("core.executor.process_text_for_chunking") as mock_chunker, \
         patch("core.executor.ApiManager") as mock_api_cls, \
         patch("backend.infrastructure.providers.provider_service.ProviderService") as mock_ps_cls:

        mock_cp = MagicMock()
        mock_cp_cls.return_value = mock_cp

        mock_translate.return_value = ("Bản dịch AI", "success", "key-abc")

        mock_chunker.return_value = ["Chunk 1 cần dịch", "Chunk 2 cần dịch"]

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_ps = MagicMock()
        mock_ps.get_active_provider_config.return_value = {
            "type": "gemini",
            "base_url": "https://gateway.ai.cloudflare.com/v1/a/b/google-ai-studio",
            "max_rpm": 15,
            "rpd_per_key": 1500
        }
        mock_ps_cls.return_value = mock_ps

        yield {
            "cp_cls": mock_cp_cls,
            "cp": mock_cp,
            "translate": mock_translate,
            "chunker": mock_chunker,
            "api_cls": mock_api_cls,
            "api": mock_api,
            "ps_cls": mock_ps_cls,
            "ps": mock_ps,
        }


def _make_executor(config, deps):
    """Helper tạo TranslationExecutor với mocked dependencies."""
    from core.executor import TranslationExecutor
    return TranslationExecutor(
        api_keys=["test-key-1"],
        config=config,
    )


class TestForceRetranslateFlag:
    """Kiểm tra cờ force_retranslate được đọc đúng từ config."""

    def test_default_false(self, mock_deps):
        executor = _make_executor({"prompts": {"main": "Dịch:"}}, mock_deps)
        assert executor.force_retranslate is False

    def test_explicit_true(self, mock_deps):
        executor = _make_executor(
            {"force_retranslate": True, "prompts": {"main": "Dịch:"}},
            mock_deps,
        )
        assert executor.force_retranslate is True

    def test_explicit_false(self, mock_deps):
        executor = _make_executor(
            {"force_retranslate": False, "prompts": {"main": "Dịch:"}},
            mock_deps,
        )
        assert executor.force_retranslate is False


class TestForceRetranslateCleanup:
    """Kiểm tra force_retranslate gọi cleanup checkpoint."""

    def test_cleanup_called_when_force(self, mock_deps):
        executor = _make_executor(
            {"force_retranslate": True, "prompts": {"main": "Dịch:"}},
            mock_deps,
        )
        mock_tm = MagicMock()
        mock_tm.find_match.return_value = None

        executor.translate_text(
            text="Nội dung test",
            output_filename="test_file",
            translation_memory=mock_tm,
        )

        mock_deps["cp"].cleanup.assert_any_call("test_file")

    def test_no_resume_when_force(self, mock_deps):
        """Khi force=True, KHÔNG gọi get_resume_info."""
        executor = _make_executor(
            {"force_retranslate": True, "prompts": {"main": "Dịch:"}},
            mock_deps,
        )

        executor.translate_text(
            text="Nội dung test",
            output_filename="test_file",
        )

        mock_deps["cp"].get_resume_info.assert_not_called()


class TestForceRetranslateSkipsTM:
    """Kiểm tra force_retranslate bỏ qua TM nhưng vẫn ghi TM mới."""

    def test_tm_find_match_not_called(self, mock_deps):
        executor = _make_executor(
            {"force_retranslate": True, "prompts": {"main": "Dịch:"}},
            mock_deps,
        )
        mock_tm = MagicMock()
        mock_tm.find_match.return_value = {
            "similarity": 1.0,
            "translation": "Bản dịch cũ trong TM",
        }

        executor.translate_text(
            text="Nội dung test",
            output_filename="test_file",
            translation_memory=mock_tm,
        )

        mock_tm.find_match.assert_not_called()

    def test_tm_add_translation_still_called(self, mock_deps):
        """Khi force=True, vẫn ghi TM mới sau khi dịch thành công."""
        executor = _make_executor(
            {"force_retranslate": True, "prompts": {"main": "Dịch:"}},
            mock_deps,
        )
        mock_tm = MagicMock()
        mock_tm.find_match.return_value = {
            "similarity": 1.0,
            "translation": "Bản dịch cũ",
        }

        executor.translate_text(
            text="Chunk 1 cần dịch",
            output_filename="test_file",
            translation_memory=mock_tm,
        )

        mock_tm.add_translation.assert_called()

    def test_tm_find_match_called_when_not_force(self, mock_deps):
        """Khi force=False, PHẢI gọi find_match."""
        executor = _make_executor(
            {"force_retranslate": False, "prompts": {"main": "Dịch:"}},
            mock_deps,
        )
        mock_tm = MagicMock()
        mock_tm.find_match.return_value = {
            "similarity": 1.0,
            "translation": "Bản dịch từ TM",
        }

        result = executor.translate_text(
            text="Chunk 1 cần dịch",
            output_filename="test_file",
            translation_memory=mock_tm,
        )

        mock_tm.find_match.assert_called()
        # 2 chunks → joined with \n\n, each chunk matched from TM
        assert "Bản dịch từ TM" in result


class TestForceRetranslateNewSession:
    """Kiểm tra force_retranslate tạo session mới."""

    def test_init_session_called(self, mock_deps):
        executor = _make_executor(
            {"force_retranslate": True, "prompts": {"main": "Dịch:"}},
            mock_deps,
        )

        executor.translate_text(
            text="Nội dung test",
            output_filename="test_file",
        )

        mock_deps["cp"].init_session.assert_called_once()


class TestNormalModeBehavior:
    """Kiểm tra hành vi bình thường (không force)."""

    def test_checkpoint_resume_checked(self, mock_deps):
        """Khi force=False, kiểm tra resume info."""
        executor = _make_executor(
            {"force_retranslate": False, "prompts": {"main": "Dịch:"}},
            mock_deps,
        )
        mock_deps["cp"].get_resume_info.return_value = None

        executor.translate_text(
            text="Nội dung test",
            output_filename="test_file",
        )

        mock_deps["cp"].get_resume_info.assert_called_once_with("test_file")
