# src/__init__.py - v2.4.1
# Tác giả: Narga
# Chức năng: Package initialization, exports các module chính.

__version__ = "2.4.1"

# Import các class và hàm chính để dễ dàng truy cập
from .translator import ApiManager, TranslationCache, robust_translate, consistency_check_chunk
from .configuration import load_all_configs, setup_directories, load_prompts
from .workflow import run_translation_workflow
from .statistics import TranslationStatistics, print_api_status
from .text_normalizer import TextNormalizer, detect_source_type

__all__ = [
    'ApiManager',
    'TranslationCache',
    'robust_translate',
    'consistency_check_chunk',
    'load_all_configs',
    'setup_directories',
    'load_prompts',
    'run_translation_workflow',
    'TranslationStatistics',
    'print_api_status',
    'TextNormalizer',
    'detect_source_type'
]
