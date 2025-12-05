# plugins/chinese_detector/plugin.py - v3.0.0
# Chinese character detector plugin

from core.interfaces import ProcessorPlugin
from typing import Dict, Any, Tuple
from pathlib import Path
from .detector import find_chinese_files, find_chinese_chunks
import re


class Plugin(ProcessorPlugin):
    """
    Chinese Character Detector plugin.
    
    Detects Chinese/CJK characters in text or files.
    Used for QA to ensure translation is complete.
    """
    
    # Chinese character regex
    CHINESE_REGEX = re.compile(r'[\u4e00-\u9fff]')
    
    @property
    def name(self) -> str:
        return "chinese_detector"
    
    @property
    def version(self) -> str:
        return "3.0.0"
    
    @property
    def display_name(self) -> str:
        return "Chinese Character Detector"
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize detector plugin"""
        try:
            self.config = config
            self.logger.info(f"✓ {self.display_name} initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            return False
    
    def cleanup(self) -> None:
        """Cleanup resources"""
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return plugin capabilities"""
        return {
            'features': ['detect_chinese', 'count_chinese', 'find_chinese_files'],
            'supported_formats': ['txt', 'md']
        }
    
    def process(self, input_data: Any, context: Dict[str, Any] = None) -> Tuple[Any, str]:
        """
        Detect Chinese characters in text.
        
        Args:
            input_data: Text to check (str) or directory path (str/Path)
            context: Optional context with 'mode' ('text' or 'files')
        
        Returns:
            Tuple[result, status]:
                - For text mode: (chinese_count, status)
                - For files mode: (list of files with chinese, status)
        """
        if context is None:
            context = {}
        
        try:
            mode = context.get('mode', 'text')
            
            if mode == 'text':
                # Check text for Chinese characters
                chinese_chars = self.CHINESE_REGEX.findall(input_data)
                count = len(chinese_chars)
                
                status = 'success' if count == 0 else 'partial'
                
                return {
                    'count': count,
                    'has_chinese': count > 0,
                    'characters': chinese_chars[:10]  # First 10 for reference
                }, status
            
            elif mode == 'files':
                # Find files with Chinese characters
                path = Path(input_data)
                if not path.exists():
                    return None, 'error'
                
                failed_files = find_chinese_files(path)
                
                return {
                    'failed_files': [
                        {'path': str(fp), 'count': count}
                        for fp, count in failed_files
                    ],
                    'total_failed': len(failed_files)
                }, 'success'
            
            elif mode == 'chunks':
                # Find chunks with Chinese characters in a directory
                path = Path(input_data)
                if not path.exists():
                    return None, 'error'
                
                failed_chunks = find_chinese_chunks(path)
                
                return {
                    'failed_chunks': [
                        {'index': idx, 'path': str(fp), 'count': count}
                        for idx, fp, count in failed_chunks
                    ],
                    'total_failed': len(failed_chunks)
                }, 'success'
            
            else:
                self.logger.error(f"Unknown mode: {mode}")
                return None, 'error'
        
        except Exception as e:
            self.logger.error(f"Detection error: {e}", exc_info=True)
            return None, 'error'
    
    def supports_format(self, format: str) -> bool:
        """Check if format is supported"""
        return format.lower() in ['txt', 'md', 'text', 'markdown']
    
    def count_chinese(self, text: str) -> int:
        """
        Count Chinese characters in text.
        
        Args:
            text: Text to check
        
        Returns:
            Number of Chinese characters found
        """
        return len(self.CHINESE_REGEX.findall(text))
    
    def has_chinese(self, text: str) -> bool:
        """
        Quick check if text contains Chinese characters.
        
        Args:
            text: Text to check
        
        Returns:
            True if Chinese characters found
        """
        return bool(self.CHINESE_REGEX.search(text))
