# core/interfaces/__init__.py - v3.0.0
# Plugin interfaces package initialization

from .plugin_base import PluginBase, PluginStatus, PluginPriority
from .processor_plugin import ProcessorPlugin
from .converter_plugin import ConverterPlugin

__all__ = [
    'PluginBase',
    'PluginStatus',
    'PluginPriority',
    'ProcessorPlugin',
    'ConverterPlugin',
]
