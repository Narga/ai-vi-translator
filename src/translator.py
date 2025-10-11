# src/translator.py - v2.7.0 (Facade)
# Tác giả: Narga
# Chức năng: Facade tái xuất các thành phần con trong gói translators/* để giữ nguyên API công khai.
# Mục tiêu: giảm kích thước file, tăng tính bảo trì mà không phá vỡ import cũ: from . import translator

from .translators.api_manager import ApiManager
from .translators.cache_manager import TranslationCache
from .translators.core import robust_translate
from .translators.consistency import consistency_check_chunk
from .translators.file_manager import GeminiProjectFileManager

__all__ = [
    "ApiManager",
    "TranslationCache",
    "robust_translate",
    "consistency_check_chunk",
    "GeminiProjectFileManager",
]
