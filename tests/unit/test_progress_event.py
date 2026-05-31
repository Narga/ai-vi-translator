# tests/unit/test_progress_event.py
# Unit tests cho Phase 07: Progress Event Contract

import sys
import pytest
from pathlib import Path
from queue import Queue

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestProgressEventType:
    """Test ProgressEventType enum."""

    def test_import(self):
        """Test import ProgressEventType."""
        from backend.application.dto.progress_event import ProgressEventType
        assert ProgressEventType is not None

    def test_values(self):
        """Test enum values."""
        from backend.application.dto.progress_event import ProgressEventType
        assert ProgressEventType.PROGRESS.value == "progress"
        assert ProgressEventType.INFO.value == "info"
        assert ProgressEventType.COMPLETE.value == "complete"
        assert ProgressEventType.ERROR.value == "error"
        assert ProgressEventType.FILE_COMPLETE.value == "file_complete"
        assert ProgressEventType.PING.value == "ping"


class TestProgressEvent:
    """Test ProgressEvent dataclass."""

    def test_import(self):
        """Test import ProgressEvent."""
        from backend.application.dto.progress_event import ProgressEvent
        assert ProgressEvent is not None

    def test_create_minimal(self):
        """Test tạo ProgressEvent với minimal fields."""
        from backend.application.dto.progress_event import ProgressEvent, ProgressEventType
        event = ProgressEvent(type=ProgressEventType.INFO, message="test")
        assert event.type == ProgressEventType.INFO
        assert event.message == "test"

    def test_to_dict(self):
        """Test to_dict bỏ qua None fields."""
        from backend.application.dto.progress_event import ProgressEvent, ProgressEventType
        event = ProgressEvent(
            type=ProgressEventType.PROGRESS,
            message="test",
            current=1,
            total=5,
            percent=20,
        )
        d = event.to_dict()
        assert d["type"] == "progress"
        assert d["message"] == "test"
        assert d["current"] == 1
        assert d["total"] == 5
        assert d["percent"] == 20
        assert "result" not in d

    def test_to_dict_with_metadata(self):
        """Test to_dict với metadata."""
        from backend.application.dto.progress_event import ProgressEvent, ProgressEventType
        event = ProgressEvent(
            type=ProgressEventType.INFO,
            message="test",
            metadata={"custom_field": "value"},
        )
        d = event.to_dict()
        assert d["custom_field"] == "value"

    def test_from_dict(self):
        """Test from_dict tạo ProgressEvent đúng."""
        from backend.application.dto.progress_event import ProgressEvent, ProgressEventType
        d = {
            "type": "progress",
            "message": "test",
            "current": 1,
            "total": 5,
        }
        event = ProgressEvent.from_dict(d)
        assert event.type == ProgressEventType.PROGRESS
        assert event.message == "test"
        assert event.current == 1
        assert event.total == 5

    def test_from_dict_unknown_type(self):
        """Test from_dict với unknown type."""
        from backend.application.dto.progress_event import ProgressEvent, ProgressEventType
        d = {"type": "unknown", "message": "test"}
        event = ProgressEvent.from_dict(d)
        assert event.type == ProgressEventType.INFO

    def test_roundtrip(self):
        """Test to_dict -> from_dict roundtrip."""
        from backend.application.dto.progress_event import ProgressEvent, ProgressEventType
        original = ProgressEvent(
            type=ProgressEventType.COMPLETE,
            message="Done!",
            result="translated text",
            output_file="output.txt",
            tokens_used=100,
        )
        d = original.to_dict()
        restored = ProgressEvent.from_dict(d)
        assert restored.type == original.type
        assert restored.message == original.message
        assert restored.result == original.result
        assert restored.output_file == original.output_file


class TestConvenienceConstructors:
    """Test convenience constructor functions."""

    def test_progress_event(self):
        """Test progress_event()."""
        from backend.application.dto.progress_event import progress_event
        e = progress_event("test", 1, 5)
        assert e["type"] == "progress"
        assert e["current"] == 1
        assert e["total"] == 5
        assert e["percent"] == 20

    def test_info_event(self):
        """Test info_event()."""
        from backend.application.dto.progress_event import info_event
        e = info_event("test")
        assert e["type"] == "info"
        assert e["message"] == "test"

    def test_error_event(self):
        """Test error_event()."""
        from backend.application.dto.progress_event import error_event
        e = error_event("error msg")
        assert e["type"] == "error"
        assert e["message"] == "error msg"

    def test_complete_event(self):
        """Test complete_event()."""
        from backend.application.dto.progress_event import complete_event
        e = complete_event("done", result="text", output_file="out.txt")
        assert e["type"] == "complete"
        assert e["result"] == "text"
        assert e["output_file"] == "out.txt"

    def test_file_complete_event(self):
        """Test file_complete_event()."""
        from backend.application.dto.progress_event import file_complete_event
        e = file_complete_event("file done")
        assert e["type"] == "file_complete"

    def test_ping_event(self):
        """Test ping_event()."""
        from backend.application.dto.progress_event import ping_event
        e = ping_event()
        assert e["type"] == "ping"


class TestProgressMapper:
    """Test ProgressMapper."""

    def test_import(self):
        """Test import ProgressMapper."""
        from backend.infrastructure.progress.progress_mapper import ProgressMapper
        assert ProgressMapper is not None

    def test_for_webui(self):
        """Test for_webui tạo mapper đẩy vào queue."""
        from backend.infrastructure.progress.progress_mapper import ProgressMapper
        queue = Queue()
        mapper = ProgressMapper.for_webui(queue)

        event = {"type": "info", "message": "test"}
        mapper.emit(event)

        assert not queue.empty()
        received = queue.get_nowait()
        assert received["type"] == "info"
        assert received["message"] == "test"

    def test_for_cli(self):
        """Test for_cli tạo mapper với callbacks."""
        from backend.infrastructure.progress.progress_mapper import ProgressMapper

        received = []
        def on_info(event):
            received.append(event)

        mapper = ProgressMapper.for_cli(on_info=on_info)
        mapper.emit({"type": "info", "message": "test"})

        assert len(received) == 1
        assert received[0]["message"] == "test"

    def test_create_callback(self):
        """Test create_callback trả về callable."""
        from backend.infrastructure.progress.progress_mapper import ProgressMapper
        queue = Queue()
        mapper = ProgressMapper.for_webui(queue)
        cb = mapper.create_callback()

        assert callable(cb)
        cb({"type": "progress", "message": "test"})

        assert not queue.empty()

    def test_emit_with_no_callback(self):
        """Test emit không crash khi không có callback."""
        from backend.infrastructure.progress.progress_mapper import ProgressMapper
        mapper = ProgressMapper(callback=None)
        mapper.emit({"type": "info", "message": "test"})  # Should not raise
