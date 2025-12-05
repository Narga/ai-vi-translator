# core/interfaces/converter_plugin.py - v3.0.0
# Converter plugin interface for format conversion plugins

from .plugin_base import PluginBase
from abc import abstractmethod
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional


class ConverterPlugin(PluginBase):
    """
    Interface for file format conversion plugins.
    
    Examples:
    - EPUB to Text converter
    - Text to EPUB converter
    - PDF to Text converter
    - Markdown to HTML converter
    """
    
    @abstractmethod
    def convert(
        self, 
        input_path: Path, 
        output_path: Path, 
        **options
    ) -> bool:
        """
        Convert file from one format to another.
        
        Args:
            input_path: Path to input file
            output_path: Path to output file (will be created)
            **options: Additional conversion options:
                - preserve_formatting: bool = True
                - encoding: str = 'utf-8'
                - metadata: Dict[str, Any] = None
                - ... (plugin-specific options)
        
        Returns:
            bool: True if conversion successful, False otherwise
        
        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If format not supported
            Exception: For other conversion errors
        
        Example:
            >>> converter.convert(
            ...     Path('book.epub'),
            ...     Path('book.txt'),
            ...     encoding='utf-8',
            ...     preserve_formatting=True
            ... )
            True
        """
        pass
    
    @abstractmethod
    def get_supported_conversions(self) -> List[Tuple[str, str]]:
        """
        Get list of supported format conversions.
        
        Returns:
            List of (from_format, to_format) tuples
        
        Example:
            >>> converter.get_supported_conversions()
            [('epub', 'txt'), ('epub', 'md'), ('txt', 'epub')]
        """
        pass
    
    def can_convert(self, from_format: str, to_format: str) -> bool:
        """
        Check if conversion between two formats is supported.
        
        Args:
            from_format: Source format (e.g., 'epub')
            to_format: Target format (e.g., 'txt')
        
        Returns:
            bool: True if conversion is supported
        """
        conversions = self.get_supported_conversions()
        return (from_format, to_format) in conversions
    
    def detect_format(self, file_path: Path) -> Optional[str]:
        """
        Detect file format from file path or content.
        
        Override for custom format detection.
        Default implementation uses file extension.
        
        Args:
            file_path: Path to file
        
        Returns:
            Format string (e.g., 'epub', 'txt') or None if unknown
        """
        if file_path.suffix:
            return file_path.suffix.lstrip('.').lower()
        return None
    
    def validate_conversion_options(self, **options) -> bool:
        """
        Validate conversion options.
        
        Override to add custom validation.
        Default implementation always returns True.
        
        Args:
            **options: Conversion options to validate
        
        Returns:
            bool: True if options are valid
        """
        return True
    
    def get_conversion_metadata(
        self, 
        input_path: Path
    ) -> Dict[str, Any]:
        """
        Extract metadata from input file.
        
        Override to provide format-specific metadata extraction.
        Default returns basic file info.
        
        Args:
            input_path: Path to input file
        
        Returns:
            Dictionary with metadata, e.g.:
            {
                'title': 'Book Title',
                'author': 'Author Name',
                'size_bytes': 1024000,
                'format': 'epub'
            }
        """
        return {
            'file_name': input_path.name,
            'size_bytes': input_path.stat().st_size if input_path.exists() else 0,
            'format': self.detect_format(input_path)
        }
