# services/statistics_service.py - v3.0.0
# Adapted from src/statistics.py
# Statistics tracking service for plugin architecture

import time
import logging
from typing import Dict, List, Any, Optional
from threading import Lock


class StatisticsService:
    """
    Service for tracking translation statistics.
    
    Tracks chars/words/tokens, success/failure, API usage, and timing.
    Thread-safe for concurrent access.
    """
    
    def __init__(self):
        """Initialize statistics service."""
        self.total_chars: int = 0
        self.total_words: int = 0
        self.total_tokens: int = 0
        self.successful_chunks: List[int] = []
        self.failed_chunks: List[int] = []
        self.api_call_count: Dict[str, int] = {}
        self.start_time: float = time.time()
        self.end_time: float = 0
        self._lock = Lock()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("📊 StatisticsService initialized")
    
    def add_chunk_result(
        self,
        chunk_index: int,
        chunk_text: str,
        status: str,
        api_key: str
    ) -> None:
        """
        Record result of chunk translation.
        
        Args:
            chunk_index: Chunk number
            chunk_text: Original text
            status: 'success' or 'failed'
            api_key: API key used
        """
        with self._lock:
            char_count = len(chunk_text)
            word_count = len(chunk_text.split())
            token_count = char_count // 4  # Estimate: 1 token ≈ 4 chars
            
            self.total_chars += char_count
            self.total_words += word_count
            self.total_tokens += token_count
            
            if status == 'success':
                self.successful_chunks.append(chunk_index)
            else:
                self.failed_chunks.append(chunk_index)
            
            # Track API usage
            key_suffix = api_key[-4:] if api_key != 'cache' else 'cache'
            self.api_call_count[key_suffix] = self.api_call_count.get(key_suffix, 0) + 1
    
    def mark_complete(self) -> None:
        """Mark translation process as complete."""
        with self._lock:
            self.end_time = time.time()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get statistics summary.
        
        Returns:
            Dictionary with all statistics
        """
        with self._lock:
            elapsed = (self.end_time or time.time()) - self.start_time
            
            return {
                'total_chars': self.total_chars,
                'total_words': self.total_words,
                'total_tokens': self.total_tokens,
                'successful_chunks': len(self.successful_chunks),
                'failed_chunks': len(self.failed_chunks),
                'total_chunks': len(self.successful_chunks) + len(self.failed_chunks),
                'success_rate': (
                    len(self.successful_chunks) / 
                    max(1, len(self.successful_chunks) + len(self.failed_chunks))
                ) * 100,
                'api_calls': dict(self.api_call_count),
                'elapsed_seconds': elapsed,
                'elapsed_formatted': self._format_time(elapsed)
            }
    
    def print_summary(self) -> None:
        """Print formatted statistics summary."""
        summary = self.get_summary()
        
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info("📊 TRANSLATION STATISTICS")
        self.logger.info("=" * 80)
        self.logger.info(f"Total Characters: {summary['total_chars']:,}")
        self.logger.info(f"Total Words: {summary['total_words']:,}")
        self.logger.info(f"Estimated Tokens: {summary['total_tokens']:,}")
        self.logger.info("")
        self.logger.info(f"Successful Chunks: {summary['successful_chunks']}")
        self.logger.info(f"Failed Chunks: {summary['failed_chunks']}")
        self.logger.info(f"Total Chunks: {summary['total_chunks']}")
        self.logger.info(f"Success Rate: {summary['success_rate']:.1f}%")
        self.logger.info("")
        
        if summary['api_calls']:
            self.logger.info("API Key Usage:")
            for key_suffix, count in sorted(summary['api_calls'].items()):
                if key_suffix == 'cache':
                    self.logger.info(f"  Cache hits: {count}")
                else:
                    self.logger.info(f"  Key ...{key_suffix}: {count} calls")
        
        self.logger.info("")
        self.logger.info(f"Total Time: {summary['elapsed_formatted']}")
        self.logger.info("=" * 80)
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """
        Format seconds into human-readable time.
        
        Args:
            seconds: Time in seconds
        
        Returns:
            Formatted string (e.g., "1h 23m 45s")
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")  
        parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    def reset(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self.total_chars = 0
            self.total_words = 0
            self.total_tokens = 0
            self.successful_chunks.clear()
            self.failed_chunks.clear()
            self.api_call_count.clear()
            self.start_time = time.time()
            self.end_time = 0
            
            self.logger.info("📊 Statistics reset")


def print_api_status(api_manager) -> None:
    """
    Print current API key status.
    
    Args:
        api_manager: ApiManager instance
    """
    logger = logging.getLogger(__name__)
    
    logger.info("")
    logger.info("🔑 API KEY STATUS")
    logger.info("-" * 40)
    
    for key in api_manager._key_list:
        key_suffix = key[-4:]
        limiter = api_manager._limiters.get(key)
        
        if limiter:
            status = "✅ Available" if limiter.can_call() else "⏳ Cooldown"
            logger.info(f"  Key ...{key_suffix}: {status}")
        else:
            logger.info(f"  Key ...{key_suffix}: ⚠️ Unknown")
    
    logger.info("-" * 40)
