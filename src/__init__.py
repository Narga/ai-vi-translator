# src/__init__.py - v2.5.1
# Tác giả: Narga
# Chức năng: Package initialization, exports các module chính.

__version__ = "2.5.1"

# Import các class và hàm chính để dễ dàng truy cập
from .translator import ApiManager, TranslationCache, robust_translate, consistency_check_chunk
from .configuration import load_all_configs, setup_directories, load_prompts, load_api_keys
from .workflow import run_translation_workflow
from .statistics import TranslationStatistics, print_api_status
from .text_normalizer import TextNormalizer, detect_source_type
from .translation_guide import (
    StyleProfile, 
    GlossaryManager, 
    CharacterRelationsManager,
    load_guidelines_from_instructions_dir
)

__all__ = [
    'ApiManager',
    'TranslationCache',
    'robust_translate',
    'consistency_check_chunk',
    'load_all_configs',
    'setup_directories',
    'load_prompts',
    'load_api_keys',
    'run_translation_workflow',
    'TranslationStatistics',
    'print_api_status',
    'TextNormalizer',
    'detect_source_type',
    'StyleProfile',
    'GlossaryManager',
    'CharacterRelationsManager',
    'load_guidelines_from_instructions_dir'
]
