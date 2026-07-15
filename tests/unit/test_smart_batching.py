# tests/unit/test_smart_batching.py
# Unit tests cho Smart Batching feature trong Phase 08

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.application.use_cases.translate_project_files_use_case import TranslateProjectFilesUseCase


class TestDelimiterOverhead:
    """Test hàm tính overhead delimiter."""

    @pytest.fixture
    def use_case(self):
        return TranslateProjectFilesUseCase(
            api_keys=["test-key"],
            config={"model_name": "test-model"},
        )

    def test_index_zero(self, use_case):
        """Test tính overhead cho index 0."""
        overhead = use_case._delimiter_overhead("test-token", 0)
        expected = len("<<<test-token:0>>>\n") + len("\n<<<test-token:0>>>\n")
        assert overhead == expected

    def test_index_large(self, use_case):
        """Test tính overhead cho index lớn (99)."""
        overhead = use_case._delimiter_overhead("test-token", 99)
        expected = len("<<<test-token:99>>>\n") + len("\n<<<test-token:99>>>\n")
        assert overhead == expected

    def test_index_five(self, use_case):
        """Test tính overhead cho index 5."""
        overhead = use_case._delimiter_overhead("token123", 5)
        expected = len("<<<token123:5>>>\n") + len("\n<<<token123:5>>>\n")
        assert overhead == expected


class TestBuildBatches:
    """Test _build_batches."""

    @pytest.fixture
    def use_case(self):
        return TranslateProjectFilesUseCase(
            api_keys=["test-key"],
            config={"chunk_size": 22000, "model_name": "test-model"},
        )

    def test_all_small_files(self, use_case):
        """Test gom nhóm 5 file nhỏ (mỗi file 2,000 ký tự), chunk_size=22000."""
        filenames = [f"file_{i}.md" for i in range(5)]
        file_contents = {f"file_{i}.md": "x" * 2000 for i in range(5)}
        
        session_token = "abc123"
        batches = use_case._build_batches(filenames, file_contents, 22000, session_token)
        
        assert len(batches) == 1
        assert len(batches[0]) == 5
        assert set(batches[0]) == set(filenames)

    def test_single_large_file(self, use_case):
        """Test một file lớn (30,000 ký tự), chunk_size=22000."""
        filenames = ["large_file.md"]
        file_contents = {"large_file.md": "x" * 30000}
        
        session_token = "def456"
        batches = use_case._build_batches(filenames, file_contents, 22000, session_token)
        
        assert len(batches) == 1
        assert batches[0] == ["large_file.md"]

    def test_mixed_large_small(self, use_case):
        """Test mix file lớn và nhỏ - file lớn ra batch riêng, file nhỏ gom với nhau."""
        filenames = ["large_file.md", "small1.md", "small2.md"]
        file_contents = {
            "large_file.md": "x" * 30000,
            "small1.md": "y" * 1000,
            "small2.md": "z" * 1500,
        }
        
        session_token = "ghi789"
        batches = use_case._build_batches(filenames, file_contents, 22000, session_token)
        
        assert len(batches) == 2
        assert len(batches[0]) == 1 and batches[0] == ["large_file.md"]
        assert len(batches[1]) == 2 and set(batches[1]) == {"small1.md", "small2.md"}

    def test_multiple_batches_small_files(self, use_case):
        """Test nhiều batch khi file nhỏ nhưng tổng vượt quá chunk_size."""
        filenames = [f"file_{i}.md" for i in range(14)]  # 14 files, mỗi 2000 ký tự = 28000
        file_contents = {f"file_{i}.md": "x" * 2000 for i in range(14)}
        
        session_token = "jkl012"
        batches = use_case._build_batches(filenames, file_contents, 22000, session_token)
        
        assert len(batches) == 2  # 2 batches: 10 files + 4 files
        assert len(batches[0]) == 10
        assert len(batches[1]) == 4

    def test_empty_file_contents(self, use_case):
        """Test với file trống."""
        filenames = ["empty.md"]
        file_contents = {"empty.md": ""}
        
        session_token = "mno345"
        batches = use_case._build_batches(filenames, file_contents, 22000, session_token)
        
        assert len(batches) == 1
        assert batches[0] == ["empty.md"]


class TestParseBatchResponse:
    """Test _parse_batch_response."""

    @pytest.fixture
    def use_case(self):
        return TranslateProjectFilesUseCase(
            api_keys=["test-key"],
            config={"model_name": "test-model"},
        )

    def test_valid_response(self, use_case):
        """Test parse response đúng format, đúng index sequence [0,1,2]."""
        session_token = "abc123"
        response = (
            "<<<abc123:0>>>\nTranslated content 0\n"
            "<<</abc123:0>>>\n"
            "<<<abc123:1>>>\nTranslated content 1\n"
            "<<</abc123:1>>>\n"
            "<<<abc123:2>>>\nTranslated content 2\n"
            "<<</abc123:2>>>\n"
            "<<<abc123:0>>>\n"
            "<<<abc123:1>>>\n"
            "<<<abc123:2>>>\n"
        )
        batch_index_map = {
            0: "file_1.md",
            1: "file_2.md", 
            2: "file_3.md"
        }
        
        result = use_case._parse_batch_response(
            session_token, response, batch_index_map
        )
        
        expected = {
            "file_1.md": "Translated content 0",
            "file_2.md": "Translated content 1",
            "file_3.md": "Translated content 2"
        }
        assert result == expected

    def test_missing_index(self, use_case):
        """Test AI trả về thiếu 1 index (chỉ có [0,2])."""
        session_token = "def456"
        response = (
            "<<<def456:0>>>\nContent 0\n"
            "<<</def456:0>>>\n"
            "<<<def456:2>>>\nContent 2\n"
            "<<</def456:2>>>\n"
            "<<<def456:0>>>\n"
            "<<<def456:2>>>\n"
        )
        batch_index_map = {
            0: "file_1.md",
            1: "file_2.md",
            2: "file_3.md"
        }
        
        result = use_case._parse_batch_response(
            session_token, response, batch_index_map
        )
        
        assert result is None

    def test_reversed_indices(self, use_case):
        """Test AI đảo thứ tự index (chỉ có [1,0])."""
        session_token = "ghi789"
        response = (
            "<<<ghi789:1>>>\nContent 1\n"
            "<<</ghi789:1>>>\n"
            "<<<ghi789:0>>>\nContent 0\n"
            "<<</ghi789:0>>>\n"
            "<<<ghi789:1>>>\n"
            "<<<ghi789:0>>>\n"
        )
        batch_index_map = {
            0: "file_1.md",
            1: "file_2.md",
        }
        
        result = use_case._parse_batch_response(
            session_token, response, batch_index_map
        )
        
        assert result is None

    def test_duplicate_indices(self, use_case):
        """Test AI skip rồi lặp index (vd [0,0,1])."""
        session_token = "jkl012"
        response = (
            "<<<jkl012:0>>>\nContent 0 (first)\n"
            "<<</jkl012:0>>>\n"
            "<<<jkl012:0>>>\nContent 0 (second)\n"
            "<<</jkl012:0>>>\n"
            "<<<jkl012:1>>>\nContent 1\n"
            "<<</jkl012:1>>>\n"
            "<<<jkl012:0>>>\n"
            "<<</jkl012:0>>>\n"
            "<<<jkl012:1>>>\n"
        )
        batch_index_map = {
            0: "file_1.md",
            1: "file_2.md"
        }
        
        result = use_case._parse_batch_response(
            session_token, response, batch_index_map
        )
        
        assert result is None

    def test_special_characters(self, use_case):
        """Test nội dung file có ký tự đặc biệt (<, >, \", dòng trống)."""
        session_token = "mno345"
        response = (
            '<<<mno345:0>>>\nContent with <quote> and "double" quotes\n'
            '<<<mno345:0>>>\n'
            '<<<mno345:1>>>\n\nEmpty line before\n\nAnd after\n'
            '<<<mno345:1>>>\n'
            '<<<mno345:2>>>\nSpecial chars: <>&"\'\n'
            '<<<mno345:2>>>\n'
        )
        batch_index_map = {
            0: "file_a.md",
            1: "file_b.md",
            2: "file_c.md"
        }
        
        result = use_case._parse_batch_response(
            session_token, response, batch_index_map
        )
        
        expected = {
            "file_a.md": 'Content with <quote> and "double" quotes',
            "file_b.md": '\nEmpty line before\n\nAnd after',
            "file_c.md": 'Special chars: <>&"\'',
        }
        assert result == expected

    def test_empty_files(self, use_case):
        """Test AI dịch file có nội dung rỗng, nhưng vẫn giữ delimiter."""
        session_token = "pqr678"
        response = (
            "<<<pqr678:0>>>\n\n"
            "<<<pqr678:0>>>\n"
            "<<<pqr678:1>>>\n\n"
            "<<<pqr678:1>>>\n"
        )
        batch_index_map = {
            0: "file_1.md",
            1: "file_2.md"
        }
        
        result = use_case._parse_batch_response(
            session_token, response, batch_index_map
        )
        
        expected = {
            "file_1.md": "",
            "file_2.md": ""
        }
        assert result == expected
