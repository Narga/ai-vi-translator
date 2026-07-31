# tests/unit/test_spellcheck_provider.py
# Unit tests cho spellcheck provider dispatch ở canonical layer (TranslationExecutor.spellcheck_text).

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSpellcheckExecutorProviderDispatch:
    """Provider dispatch kiểm tra ở executor layer — không dùng module đã xóa."""

    def setup_method(self):
        from core.executor import TranslationExecutor
        self._executor_cls = TranslationExecutor

    def test_spellcheck_method_exists(self):
        from core.executor import TranslationExecutor
        assert callable(getattr(TranslationExecutor, "spellcheck_text", None))

    def test_normal_result_returns_tuple(self):
        """spellcheck_text với Gemini mock trả về (clean_text, error_log)."""
        from core.executor import TranslationExecutor
        executor = TranslationExecutor(api_keys=["dummy"], config={})
        with patch("core.executor.robust_translate") as mock_rt, \
             patch("core.executor.process_text_for_chunking", return_value=["chunk-0"]), \
             patch.object(executor.api_manager, "get_next_available_key", return_value="key1"), \
             patch.object(executor.checkpoint_service, "get_resume_info", return_value={}), \
             patch.object(executor.checkpoint_service, "get_translated_chunks", return_value={}), \
             patch.object(executor.checkpoint_service, "init_session"), \
             patch.object(executor.checkpoint_service, "save_chunk"), \
             patch.object(executor.checkpoint_service, "cleanup"):
            mock_rt.return_value = ("Corrected text\n---\nErrors: none", "success", "key1")
            result = executor.spellcheck_text("Anything", "test_out")
        assert result is not None
        clean, log = result
        assert "Corrected" in clean

    def test_failed_status_still_returns_tuple(self):
        """API fail → clean=original chunk, log ghi nhận error, không crash."""
        from core.executor import TranslationExecutor
        executor = TranslationExecutor(api_keys=["dummy"], config={})
        with patch("core.executor.robust_translate") as mock_rt, \
             patch("core.executor.process_text_for_chunking", return_value=["chunk-0"]), \
             patch.object(executor.api_manager, "get_next_available_key", return_value="key1"), \
             patch.object(executor.checkpoint_service, "get_resume_info", return_value={}), \
             patch.object(executor.checkpoint_service, "get_translated_chunks", return_value={}), \
             patch.object(executor.checkpoint_service, "init_session"), \
             patch.object(executor.checkpoint_service, "save_chunk"), \
             patch.object(executor.checkpoint_service, "cleanup"):
            mock_rt.return_value = (None, "rate_limited", "key1")
            result = executor.spellcheck_text("Test chunk", "test_out")
        assert result is not None
        clean, log = result
        assert "rate_limited" in log or "Soát lỗi thất bại" in log
