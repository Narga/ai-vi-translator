# services/__init__.py - v4.0.0
# Service exports for plugin architecture

from .api_service import ApiManager, AdaptiveRateLimiter, SmartRateLimiter
from .config_service import ConfigService
from .file_service import FileService
from .statistics_service import StatisticsService, print_api_status
from .monitoring_service import MonitoringService
from .io_service import IOService

# v4.0.0: Các services mới
from .genai_client import GenAIClient, SDKType
from .circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState
from .health_monitor import HealthMonitor
from .emergency_stop import (
    emergency_stop, 
    check_emergency_stop, 
    reset_emergency_stop,
    get_emergency_info,
    EmergencyStopError,
    setup_signal_handlers
)

__all__ = [
    # API/Model services
    'ApiManager',
    'AdaptiveRateLimiter',
    'SmartRateLimiter',  # Backward compatibility alias
    'GenAIClient',
    'SDKType',
    
    # Core services
    'ConfigService',
    'FileService',
    'StatisticsService',
    'MonitoringService',
    'IOService',
    'print_api_status',
    
    # Protection services (v4.0.0)
    'CircuitBreaker',
    'CircuitBreakerError',
    'CircuitState',
    'HealthMonitor',
    
    # Emergency stop (v4.0.0)
    'emergency_stop',
    'check_emergency_stop',
    'reset_emergency_stop',
    'get_emergency_info',
    'EmergencyStopError',
    'setup_signal_handlers',
]
