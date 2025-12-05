# core/interfaces/plugin_base.py - v3.0.0
# Base plugin interface for Novel Translator plugin architecture

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
import logging


class PluginStatus(Enum):
    """Plugin lifecycle states"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


class PluginPriority(Enum):
    """
    Plugin execution priority.
    
    CRITICAL: Must run, failure will stop execution
    HIGH: Important but can continue if fails
    NORMAL: Standard priority
    LOW: Can be skipped
    OPTIONAL: Nice-to-have, failure is ignored
    """
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    OPTIONAL = 4


class PluginBase(ABC):
    """
    Base interface for all plugins.
    
    Design principles:
    - Each plugin is isolated (error in plugin A doesn't affect plugin B)
    - Plugins communicate via event bus
    - Shared services accessed via service bus
    - Plugins can declare dependencies on other plugins
    
    Lifecycle:
    1. UNLOADED → initialize() → READY
    2. READY → execute action → RUNNING
    3. RUNNING → complete → READY
    4. ERROR → can retry or disable
    5. cleanup() → UNLOADED
    """
    
    def __init__(self, service_bus, event_bus):
        """
        Initialize plugin with service and event buses.
        
        Args:
            service_bus: ServiceBus instance for accessing shared services
            event_bus: EventBus instance for event communication
        """
        self.service_bus = service_bus
        self.event_bus = event_bus
        self.status = PluginStatus.UNLOADED
        self.config: Dict[str, Any] = {}
        self._logger: Optional[logging.Logger] = None
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger from service bus or create default"""
        if self._logger is None:
            if self.service_bus.has_service('logger'):
                self._logger = self.service_bus.get_service('logger')
            else:
                self._logger = logging.getLogger(self.name)
        return self._logger
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Plugin unique identifier.
        
        Should be lowercase with underscores (e.g., 'translation', 'epub_converter')
        """
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """
        Plugin version string.
        
        Should follow semantic versioning (e.g., '1.0.0', '2.1.3')
        """
        pass
    
    @property
    def display_name(self) -> str:
        """
        Human-readable plugin name.
        
        Override for custom display name, defaults to name.
        """
        return self.name.replace('_', ' ').title()
    
    @property
    def priority(self) -> PluginPriority:
        """
        Plugin execution priority.
        
        Override to set custom priority, defaults to NORMAL.
        """
        return PluginPriority.NORMAL
    
    @property
    def dependencies(self) -> List[str]:
        """
        List of plugin names this plugin depends on.
        
        Plugin manager will ensure dependencies are loaded first.
        Override to declare dependencies.
        
        Returns:
            List of plugin names (e.g., ['translation', 'cache'])
        """
        return []
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize plugin with configuration.
        
        This method is called once after plugin is loaded.
        Use this to:
        - Load configuration
        - Initialize internal state
        - Setup event listeners
        - Validate requirements
        
        Args:
            config: Plugin-specific configuration dictionary
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """
        Cleanup resources before plugin unload.
        
        Use this to:
        - Close file handles
        - Release resources
        - Unsubscribe from events
        - Save state if needed
        
        Called when plugin is being unloaded.
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return plugin capabilities and features.
        
        This helps other plugins discover what this plugin can do.
        
        Returns:
            Dictionary describing capabilities, e.g.:
            {
                'features': ['translation', 'retranslation'],
                'supported_formats': ['txt', 'md'],
                'max_chunk_size': 20000
            }
        """
        pass
    
    def on_error(self, error: Exception) -> None:
        """
        Error handler called when plugin encounters an exception.
        
        Default behavior: log error and set status to ERROR.
        Override for custom error handling.
        
        Args:
            error: Exception that occurred
        """
        self.logger.error(f"Plugin {self.name} error: {error}", exc_info=True)
        self.status = PluginStatus.ERROR
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate plugin configuration.
        
        Override to add custom validation logic.
        Default implementation always returns True.
        
        Args:
            config: Configuration dictionary to validate
        
        Returns:
            bool: True if config is valid
        """
        return True
    
    def __repr__(self) -> str:
        """String representation of plugin"""
        return f"<{self.__class__.__name__}: {self.name} v{self.version} ({self.status.value})>"
