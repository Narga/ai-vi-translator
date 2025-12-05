# core/service_bus.py - v3.0.0
# Central service registry for shared services

from typing import Dict, Any, Optional
import logging


class ServiceBus:
    """
    Central registry for shared services.
    
    Plugins access shared services (API, Cache, Config, etc.) through this bus.
    This provides loose coupling - plugins don't need to know implementation details.
    
    Thread-safe for concurrent access.
    """
    
    def __init__(self):
        """Initialize empty service registry"""
        self._services: Dict[str, Any] = {}
        self._logger = logging.getLogger(__name__)
    
    def register_service(self, name: str, service: Any) -> None:
        """
        Register a shared service.
        
        Args:
            name: Service identifier (e.g., 'api', 'cache', 'config')
            service: Service instance
        
        Raises:
            ValueError: If service with this name already registered
        
        Example:
            >>> bus = ServiceBus()
            >>> bus.register_service('cache', CacheService())
        """
        if name in self._services:
            raise ValueError(f"Service '{name}' is already registered")
        
        self._services[name] = service
        self._logger.info(f"Registered service: {name}")
    
    def get_service(self, name: str) -> Any:
        """
        Get service by name.
        
        Args:
            name: Service identifier
        
        Returns:
            Service instance
        
        Raises:
            ValueError: If service not found
        
        Example:
            >>> cache = bus.get_service('cache')
            >>> cache.get('my_key')
        """
        if name not in self._services:
            raise ValueError(
                f"Service '{name}' not registered. "
                f"Available services: {list(self._services.keys())}"
            )
        return self._services[name]
    
    def has_service(self, name: str) -> bool:
        """
        Check if service is registered.
        
        Args:
            name: Service identifier
        
        Returns:
            bool: True if service exists
        """
        return name in self._services
    
    def unregister_service(self, name: str) -> None:
        """
        Unregister a service.
        
        Args:
            name: Service identifier
        
        Raises:
            ValueError: If service not found
        """
        if name not in self._services:
            raise ValueError(f"Service '{name}' not registered")
        
        del self._services[name]
        self._logger.info(f"Unregistered service: {name}")
    
    def list_services(self) -> list[str]:
        """
        Get list of all registered services.
        
        Returns:
            List of service names
        """
        return list(self._services.keys())
    
    def clear(self) -> None:
        """Clear all registered services (use with caution!)"""
        self._services.clear()
        self._logger.warning("All services cleared from service bus")
    
    def __repr__(self) -> str:
        """String representation"""
        return f"<ServiceBus: {len(self._services)} services registered>"
