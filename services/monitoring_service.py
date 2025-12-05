# services/monitoring_service.py - v3.0.0
# Health monitoring service
# Optional progress tracking and stall detection

import time
import logging
from typing import Optional
from threading import Lock


class MonitoringService:
    """
    Service for monitoring translation health and progress.
    
    Tracks progress and detects stalls (no updates for long time).
    """
    
    def __init__(self, stall_threshold_minutes: int = 5):
        """
        Initialize monitoring service.
        
        Args:
            stall_threshold_minutes: Minutes before considering stalled
        """
        self.stall_threshold = stall_threshold_minutes * 60  # Convert to seconds
        self.last_update_time: float = time.time()
        self.current_file: Optional[str] = None
        self.current_chunk: Optional[int] = None
        self.total_chunks: Optional[int] = None
        self._lock = Lock()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"🏥 MonitoringService initialized (stall threshold: {stall_threshold_minutes}m)")
    
    def update_progress(
        self,
        file_name: Optional[str] = None,
        chunk_index: Optional[int] = None,
        total_chunks: Optional[int] = None
    ) -> None:
        """
        Update current progress.
        
        Args:
            file_name: Current file being processed
            chunk_index: Current chunk number
            total_chunks: Total number of chunks
        """
        with self._lock:
            self.last_update_time = time.time()
            
            if file_name is not None:
                self.current_file = file_name
            if chunk_index is not None:
                self.current_chunk = chunk_index
            if total_chunks is not None:
                self.total_chunks = total_chunks
    
    def check_stall(self) -> bool:
        """
        Check if process appears stalled.
        
        Returns:
            True if stalled (no update for threshold time)
        """
        with self._lock:
            elapsed = time.time() - self.last_update_time
            is_stalled = elapsed > self.stall_threshold
            
            if is_stalled:
                self.logger.warning(
                    f"⚠️ Process may be stalled! "
                    f"No update for {elapsed/60:.1f} minutes"
                )
            
            return is_stalled
    
    def get_status(self) -> dict:
        """
        Get current monitoring status.
        
        Returns:
            Dictionary with current status
        """
        with self._lock:
            elapsed = time.time() - self.last_update_time
            
            return {
                'current_file': self.current_file,
                'current_chunk': self.current_chunk,
                'total_chunks': self.total_chunks,
                'seconds_since_update': elapsed,
                'is_stalled': elapsed > self.stall_threshold
            }
    
    def reset(self) -> None:
        """Reset monitoring state."""
        with self._lock:
            self.last_update_time = time.time()
            self.current_file = None
            self.current_chunk = None
            self.total_chunks = None
            
            self.logger.info("🏥 Monitoring reset")
