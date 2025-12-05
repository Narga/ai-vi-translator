# core/interfaces/processor_plugin.py - v3.0.0
# Processor plugin interface for text/data processing plugins

from .plugin_base import PluginBase
from abc import abstractmethod
from typing import Any, Dict, Tuple


class ProcessorPlugin(PluginBase):
    """
    Interface for plugins that process text/data.
    
    Examples:
    - Translation plugin: translates text
    - Normalization plugin: normalizes text format
    - QA plugin: quality assurance checks
    - Chinese detector: detects Chinese characters
    """
    
    @abstractmethod
    def process(self, input_data: Any, context: Dict[str, Any] = None) -> Tuple[Any, str]:
        """
        Process input data and return result with status.
        
        This is the main processing method that plugins must implement.
        
        Args:
            input_data: Data to process (text, file path, bytes, etc.)
                       Type depends on plugin implementation
            context: Optional processing context with metadata:
                     - 'previous_result': Result from previous processing step
                     - 'chunk_index': Current chunk number (for chunked processing)
                     - 'file_name': Source file name
                     - Additional plugin-specific context
        
        Returns:
            Tuple[result, status]:
                result: Processed data (type depends on plugin)
                status: Status code string, one of:
                    - 'success': Processing completed successfully
                    - 'error': Processing failed
                    - 'partial': Partial processing (some data processed)
                    - 'skipped': Processing skipped (e.g., already cached)
        
        Raises:
            Exception: If processing encounters critical error
        """
        pass
    
    @abstractmethod
    def supports_format(self, format: str) -> bool:
        """
        Check if plugin supports given data format.
        
        Args:
            format: Format identifier (e.g., 'txt', 'md', 'html', 'json')
        
        Returns:
            bool: True if format is supported
        
        Example:
            >>> plugin.supports_format('txt')
            True
            >>> plugin.supports_format('pdf')
            False
        """
        pass
    
    def validate_input(self, input_data: Any) -> bool:
        """
        Validate input data before processing.
        
        Override to add custom validation logic.
        Default implementation always returns True.
        
        Args:
            input_data: Data to validate
        
        Returns:
            bool: True if input is valid
        """
        return True
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Override to provide plugin-specific stats.
        Default returns empty dict.
        
        Returns:
            Dictionary with stats, e.g.:
            {
                'items_processed': 100,
                'success_rate': 0.95,
                'average_time': 2.5
            }
        """
        return {}
