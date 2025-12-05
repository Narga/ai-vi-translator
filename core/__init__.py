# core/__init__.py - v3.0.0
# Core package initialization

from .plugin_manager import PluginManager
from .service_bus import ServiceBus
from .event_bus import EventBus, Event
from .interfaces import (
    PluginBase,
    PluginStatus,
    PluginPriority,
    ProcessorPlugin,
    ConverterPlugin,
)

__version__ = "3.0.0"
__all__ = [
    'PluginManager',
    'ServiceBus',
    'EventBus',
    'Event',
    'PluginBase',
    'PluginStatus',
    'PluginPriority',
    'ProcessorPlugin',
    'ConverterPlugin',
]
