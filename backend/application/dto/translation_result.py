# backend/application/dto/translation_result.py
# TranslationResult - Output DTO cho translation use case

"""
TranslationResult là output DTO chuẩn cho translation use case.

Phase 08: Tạo translation use case shell.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TranslationResult:
    """
    Output DTO cho translation use case.

    Attributes:
        translated_text: Nội dung đã dịch
        output_path: Đường dẫn file output
        chunks: Số chunks đã dịch
        cached: Số chunks lấy từ cache
        tm_hits: Số chunks lấy từ Translation Memory
        tokens_used: Tổng tokens đã dùng
        source_length: Độ dài text nguồn
        translated_length: Độ dài text đã dịch
        success: Thành công hay không
        error_message: Thông báo lỗi (nếu có)
    """

    translated_text: Optional[str] = None
    output_path: Optional[str] = None
    chunks: int = 0
    cached: int = 0
    tm_hits: int = 0
    tokens_used: int = 0
    source_length: int = 0
    translated_length: int = 0
    success: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert sang dict."""
        return {
            "translated_text": self.translated_text,
            "output_path": self.output_path,
            "chunks": self.chunks,
            "cached": self.cached,
            "tm_hits": self.tm_hits,
            "tokens_used": self.tokens_used,
            "source_length": self.source_length,
            "translated_length": self.translated_length,
            "success": self.success,
            "error_message": self.error_message,
        }
