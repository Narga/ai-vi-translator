from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple
from pathlib import Path
import logging

class PluginBase(ABC):
    """Base class for all plugins."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config: Dict[str, Any] = {}
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Internal plugin name/id"""
        pass
        
    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version"""
        pass
        
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable plugin name"""
        pass
        
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize plugin with config"""
        pass
        
    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup plugin resources"""
        pass
        
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return dict describing what the plugin can do"""
        pass

class ConverterPlugin(PluginBase):
    """Base class for plugins that convert between formats."""
    
    @abstractmethod
    def convert(self, input_path: Path, output_path: Path, **options) -> bool:
        """Convert input to output"""
        pass
        
    @abstractmethod
    def get_supported_conversions(self) -> List[Tuple[str, str]]:
        """Return list of (from_format, to_format) tuples supported"""
        pass
    
    def detect_format(self, path: Path) -> str:
        """Helper to detect format from extension"""
        ext = path.suffix.lower().lstrip('.')
        # basic detection, can be overridden
        return ext
