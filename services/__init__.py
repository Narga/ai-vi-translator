# services/__init__.py - v3.0.0
# Services package initialization

from .api_service import ApiManager, SmartRateLimiter
from .cache_service import TranslationCache
from .config_service import ConfigService

__version__ = "3.0.0"
__all__ = [
    'ApiManager',
    'SmartRateLimiter',
    'TranslationCache',
    'ConfigService',
]
