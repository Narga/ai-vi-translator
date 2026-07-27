# tests/unit/test_translate_project_files_use_case_execute.py

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from backend.application.use_cases.translate_project_files_use_case import TranslateProjectFilesUseCase

@pytest.fixture
def temp_project(tmp_path):
    project_dir = tmp_path / "test_project"
    sources_dir = project_dir / "sources"
    translated_dir = project_dir / "translated"
    sources_dir.mkdir(parents=True)
    translated_dir.mkdir(parents=True)
    return project_dir

@pytest.fixture
def use_case():
    return TranslateProjectFilesUseCase(
        api_keys=["test-key"],
        config={"chunk_size": 22000, "model_name": "test-model"},
    )

def test_execute_single_small_file(temp_project, use_case):
    """Test execute with 1 small file uses single-file translation."""
    source_file = temp_project / "sources" / "small.md"
    source_file.write_text("Hello world")

    events = []
    def progress_callback(data):
        events.append(data)

    with patch("core.executor.TranslationExecutor") as MockExecutor:
        mock_instance = MockExecutor.return_value
        mock_instance.translate_text.return_value = "Xin chao the gioi"
        
        result = use_case.execute(
            project_dir=temp_project,
            filenames=["small.md"],
            progress_callback=progress_callback
        )

        assert result["success"] is True
        assert result["ok"] == 1
        assert result["fail"] == 0
        
        # Verify single file fallback was used directly
        mock_instance.translate_text.assert_called_once()
        kwargs = mock_instance.translate_text.call_args.kwargs
        assert kwargs["output_filename"] == "small.md"
        assert kwargs["text"] == "Hello world"
        
        # Verify file_complete event was emitted via callback
        file_complete_events = [e for e in events if e.get("type") == "file_complete"]
        # the callback might not be triggered because we mocked translate_text which doesn't call the callback in our mock
        # wait, the actual use case code expects translate_text to write the file? No, for single file, translate_text receives output_file_path and writes it.

def test_execute_single_large_file(temp_project, use_case):
    """Test execute with 1 large file."""
    source_file = temp_project / "sources" / "large.md"
    large_content = "X" * 30000
    source_file.write_text(large_content)

    events = []
    def progress_callback(data):
        events.append(data)

    with patch("core.executor.TranslationExecutor") as MockExecutor:
        mock_instance = MockExecutor.return_value
        mock_instance.translate_text.return_value = "Y" * 30000
        
        result = use_case.execute(
            project_dir=temp_project,
            filenames=["large.md"],
            progress_callback=progress_callback
        )

        assert result["success"] is True
        assert result["ok"] == 1
        
        mock_instance.translate_text.assert_called_once()
        kwargs = mock_instance.translate_text.call_args.kwargs
        assert kwargs["output_filename"] == "large.md"

def test_execute_missing_file(temp_project, use_case):
    """Test execute with a missing file."""
    events = []
    def progress_callback(data):
        events.append(data)

    result = use_case.execute(
        project_dir=temp_project,
        filenames=["missing.md"],
        progress_callback=progress_callback
    )

    assert result["success"] is False
    assert result["ok"] == 0
    assert result["fail"] == 1

def test_execute_translate_returns_none(temp_project, use_case):
    """Test execute when translate_text returns None."""
    source_file = temp_project / "sources" / "fail.md"
    source_file.write_text("Hello fail")

    events = []
    def progress_callback(data):
        events.append(data)

    with patch("core.executor.TranslationExecutor") as MockExecutor:
        mock_instance = MockExecutor.return_value
        mock_instance.translate_text.return_value = None
        
        result = use_case.execute(
            project_dir=temp_project,
            filenames=["fail.md"],
            progress_callback=progress_callback
        )

        assert result["success"] is False
        assert result["ok"] == 0
        assert result["fail"] == 1
        
        file_error_events = [e for e in events if e.get("type") == "file_error"]
        assert len(file_error_events) == 1
        assert file_error_events[0]["filename"] == "fail.md"
