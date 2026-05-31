# backend/application/dto/progress_event.py
# ProgressEvent - Standardized progress event contract

"""
ProgressEvent là contract chuẩn cho progress events trong toàn hệ thống.
CLI và WebUI đều tiêu thụ events theo format này.

Phase 07: Chuẩn hóa progress event.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ProgressEventType(str, Enum):
    """Các loại progress event chuẩn."""

    PROGRESS = "progress"
    INFO = "info"
    COMPLETE = "complete"
    ERROR = "error"
    FILE_COMPLETE = "file_complete"
    PING = "ping"


@dataclass
class ProgressEvent:
    """
    Standardized progress event.

    Attributes:
        type: Loại event
        message: Thông báo mô tả
        current: Tiến trình hiện tại (chunk index)
        total: Tổng số (total chunks)
        percent: Phần trăm hoàn thành (0-100)
        result: Kết quả dịch (chỉ có khi complete)
        output_file: Tên file output
        tokens_used: Số tokens đã dùng
        source_length: Độ dài text nguồn
        translated_length: Độ dài text đã dịch
        metadata: Dict chứa dữ liệu bổ sung tùy ý
    """

    type: ProgressEventType
    message: str = ""
    current: Optional[int] = None
    total: Optional[int] = None
    percent: Optional[int] = None
    result: Optional[str] = None
    output_file: Optional[str] = None
    tokens_used: Optional[int] = None
    source_length: Optional[int] = None
    translated_length: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert sang dict để truyền qua queue hoặc callback.

        Returns:
            Dict representation, chỉ chứa fields không None
        """
        d = {"type": self.type.value if isinstance(self.type, ProgressEventType) else self.type}
        if self.message:
            d["message"] = self.message
        if self.current is not None:
            d["current"] = self.current
        if self.total is not None:
            d["total"] = self.total
        if self.percent is not None:
            d["percent"] = self.percent
        if self.result is not None:
            d["result"] = self.result
        if self.output_file is not None:
            d["output_file"] = self.output_file
        if self.tokens_used is not None:
            d["tokens_used"] = self.tokens_used
        if self.source_length is not None:
            d["source_length"] = self.source_length
        if self.translated_length is not None:
            d["translated_length"] = self.translated_length
        if self.metadata:
            d.update(self.metadata)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProgressEvent":
        """
        Tạo ProgressEvent từ dict (backward compatible với format cũ).

        Args:
            data: Dict chứa event data

        Returns:
            ProgressEvent instance
        """
        event_type = data.get("type", "info")
        try:
            event_type = ProgressEventType(event_type)
        except ValueError:
            event_type = ProgressEventType.INFO

        return cls(
            type=event_type,
            message=data.get("message", ""),
            current=data.get("current"),
            total=data.get("total"),
            percent=data.get("percent"),
            result=data.get("result"),
            output_file=data.get("output_file"),
            tokens_used=data.get("tokens_used"),
            source_length=data.get("source_length"),
            translated_length=data.get("translated_length"),
            metadata={k: v for k, v in data.items() if k not in {
                "type", "message", "current", "total", "percent",
                "result", "output_file", "tokens_used",
                "source_length", "translated_length",
            }},
        )


# ------------------------------------------------------------------
# Convenience constructors
# ------------------------------------------------------------------

def progress_event(message: str, current: int, total: int, percent: Optional[int] = None) -> Dict[str, Any]:
    """Tạo progress event dict."""
    if percent is None and total > 0:
        percent = int((current / total) * 100)
    return {
        "type": "progress",
        "message": message,
        "current": current,
        "total": total,
        "percent": percent,
    }


def info_event(message: str) -> Dict[str, Any]:
    """Tạo info event dict."""
    return {"type": "info", "message": message}


def error_event(message: str) -> Dict[str, Any]:
    """Tạo error event dict."""
    return {"type": "error", "message": message}


def complete_event(
    message: str,
    result: Optional[str] = None,
    output_file: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Tạo complete event dict."""
    d = {"type": "complete", "message": message}
    if result is not None:
        d["result"] = result
    if output_file is not None:
        d["output_file"] = output_file
    d.update(kwargs)
    return d


def file_complete_event(message: str) -> Dict[str, Any]:
    """Tạo file_complete event dict."""
    return {"type": "file_complete", "message": message}


def ping_event() -> Dict[str, Any]:
    """Tạo ping event dict."""
    return {"type": "ping"}
