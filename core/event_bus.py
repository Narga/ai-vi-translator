# core/event_bus.py - v3.0.0
# Event system for plugin communication

from typing import Callable, Dict, List, Any, Optional
import logging
from datetime import datetime


class Event:
    """
    Event object passed to listeners.
    
    Attributes:
        name: Event name
        data: Event data
        timestamp: When event was emitted
        source: Plugin that emitted the event (optional)
    """
    
    def __init__(self, name: str, data: Any = None, source: Optional[str] = None):
        self.name = name
        self.data = data
        self.source = source
        self.timestamp = datetime.now()
    
    def __repr__(self) -> str:
        return f"<Event: {self.name} from {self.source} at {self.timestamp}>"


class EventBus:
    """
    Event system for plugin communication.
    
    Plugins can emit and listen to events without direct coupling.
    This enables loose coupling and extensibility.
    
    Features:
    - Error isolation: If one listener fails, others still run
    - Event history: Optional event logging
    - Wildcard listeners: Subscribe to all events with '*'
    
    Common events:
    - 'chunk_translated': When a chunk is translated
    - 'file_processed': When a file is processed
    - 'translation_complete': When translation finishes
    - 'error_occurred': When an error happens
    """
    
    def __init__(self, enable_history: bool = False):
        """
        Initialize event bus.
        
        Args:
            enable_history: If True, keep history of all events
        """
        self._listeners: Dict[str, List[Callable]] = {}
        self._logger = logging.getLogger(__name__)
        self._enable_history = enable_history
        self._history: List[Event] = []
    
    def subscribe(self, event_name: str, callback: Callable[[Event], None]) -> None:
        """
        Subscribe to an event.
        
        Args:
            event_name: Event name to listen for (or '*' for all events)
            callback: Function to call when event is emitted
                     Signature: callback(event: Event) -> None
        
        Example:
            >>> def on_chunk_done(event):
            ...     print(f"Chunk {event.data['index']} done!")
            >>> bus.subscribe('chunk_translated', on_chunk_done)
        """
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        
        self._listeners[event_name].append(callback)
        self._logger.debug(f"Subscribed to event: {event_name}")
    
    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """
        Unsubscribe from an event.
        
        Args:
            event_name: Event name
            callback: Callback function to remove
        """
        if event_name in self._listeners:
            try:
                self._listeners[event_name].remove(callback)
                self._logger.debug(f"Unsubscribed from event: {event_name}")
            except ValueError:
                self._logger.warning(f"Callback not found for event: {event_name}")
    
    def emit(
        self, 
        event_name: str, 
        data: Any = None, 
        source: Optional[str] = None
    ) -> None:
        """
        Emit an event to all listeners.
        
        Error isolation: If one listener fails, log error but continue to others.
        
        Args:
            event_name: Event name
            data: Event data (any type)
            source: Source plugin name (optional)
        
        Example:
            >>> bus.emit('chunk_translated', {'index': 0, 'text': '...'}, 'translation')
        """
        event = Event(event_name, data, source)
        
        # Store in history if enabled
        if self._enable_history:
            self._history.append(event)
        
        # Notify specific listeners
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    callback(event)
                except Exception as e:
                    self._logger.error(
                        f"Event listener error ({event_name}): {e}",
                        exc_info=True
                    )
        
        # Notify wildcard listeners
        if '*' in self._listeners:
            for callback in self._listeners['*']:
                try:
                    callback(event)
                except Exception as e:
                    self._logger.error(
                        f"Wildcard listener error: {e}",
                        exc_info=True
                    )
    
    def get_listeners(self, event_name: str) -> List[Callable]:
        """
        Get all listeners for an event.
        
        Args:
            event_name: Event name
        
        Returns:
            List of callback functions
        """
        return self._listeners.get(event_name, [])
    
    def clear_listeners(self, event_name: Optional[str] = None) -> None:
        """
        Clear listeners.
        
        Args:
            event_name: Event name, or None to clear all listeners
        """
        if event_name is None:
            self._listeners.clear()
            self._logger.info("Cleared all event listeners")
        elif event_name in self._listeners:
            del self._listeners[event_name]
            self._logger.info(f"Cleared listeners for event: {event_name}")
    
    def get_history(self, event_name: Optional[str] = None,  limit: int = 100) -> List[Event]:
        """
        Get event history.
        
        Args:
            event_name: Filter by event name, or None for all events
            limit: Maximum number of events to return
        
        Returns:
            List of Event objects (most recent first)
        """
        if not self._enable_history:
            return []
        
        history = self._history[::-1]  # Reverse for most recent first
        
        if event_name:
            history = [e for e in history if e.name == event_name]
        
        return history[:limit]
    
    def clear_history(self) -> None:
        """Clear event history"""
        self._history.clear()
        self._logger.info("Cleared event history")
    
    def __repr__(self) -> str:
        """String representation"""
        listener_count = sum(len(listeners) for listeners in self._listeners.values())
        return f"<EventBus: {listener_count} listeners, {len(self._history)} events in history>"
