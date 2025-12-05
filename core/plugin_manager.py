# core/plugin_manager.py - v3.0.0
# Plugin lifecycle manager: discovery, loading, dependency resolution, execution

import importlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from .interfaces.plugin_base import PluginBase, PluginStatus, PluginPriority
from .service_bus import ServiceBus
from .event_bus import EventBus
import configparser


class PluginManager:
    """
    Manages plugin lifecycle: discovery, loading, initialization, execution.
    
    Features:
    - Auto-discovery from plugins/ directory
    - Dependency resolution
    - Error isolation (try-except per plugin)
    - Priority-based execution
    - Plugin reload support
    
    Lifecycle:
    1. discover_plugins() - Scan plugins/ directory
    2. load_plugin(name) - Load and initialize plugin
    3. resolve_dependencies() - Check dependencies, build execution order
    4. execute_plugin(name, method, *args) - Execute plugin method with isolation
    5. cleanup_plugin(name) - Cleanup and unload plugin
    """
    
    def __init__(
        self,
        service_bus: ServiceBus,
        event_bus: EventBus,
        plugins_dir: Path,
        config_dir: Optional[Path] = None
    ):
        """
        Initialize Plugin Manager.
        
        Args:
            service_bus: ServiceBus instance for shared services
            event_bus: EventBus instance for event communication
            plugins_dir: Path to plugins directory
            config_dir: Path to plugin configs directory (optional)
        """
        self.service_bus = service_bus
        self.event_bus = event_bus
        self.plugins_dir = Path(plugins_dir)
        self.config_dir = Path(config_dir) if config_dir else self.plugins_dir
        
        self.plugins: Dict[str, PluginBase] = {}
        self.execution_order: List[str] = []
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"Plugin Manager initialized (plugins_dir: {self.plugins_dir})")
    
    def discover_plugins(self) -> List[str]:
        """
        Scan plugins/ directory for valid plugins.
        
        Valid plugin structure:
        - Has __init__.py
        - Has plugin.py with a Plugin class
        - Plugin class inherits from PluginBase
        
        Returns:
            List of discovered plugin names
        
        Example:
            >>> manager.discover_plugins()
            ['translation', 'epub_converter', 'consistency_check']
        """
        discovered = []
        
        if not self.plugins_dir.exists():
            self.logger.warning(f"Plugins directory not found: {self.plugins_dir}")
            return discovered
        
        for item in self.plugins_dir.iterdir():
            # Skip non-directories and private directories
            if not item.is_dir() or item.name.startswith('_') or item.name.startswith('.'):
                continue
            
            # Check for plugin.py
            plugin_file = item / 'plugin.py'
            if plugin_file.exists():
                discovered.append(item.name)
                self.logger.info(f"✓ Discovered plugin: {item.name}")
            else:
                self.logger.debug(f"  Skipped {item.name} (no plugin.py)")
        
        self.logger.info(f"Discovered {len(discovered)} plugin(s)")
        return discovered
    
    def load_plugin(self, plugin_name: str) -> bool:
        """
        Load and initialize a single plugin.
        
        Error isolation: If plugin fails to load, log error but continue.
        
        Args:
            plugin_name: Name of plugin to load
        
        Returns:
            bool: True if loaded successfully, False otherwise
        
        Example:
            >>> manager.load_plugin('translation')
            True
        """
        if plugin_name in self.plugins:
            self.logger.warning(f"Plugin '{plugin_name}' already loaded")
            return True
        
        try:
            self.logger.info(f"Loading plugin: {plugin_name}...")
            
            # Import plugin module
            module = importlib.import_module(f'plugins.{plugin_name}.plugin')
            
            # Get Plugin class
            if not hasattr(module, 'Plugin'):
                self.logger.error(f"Plugin '{plugin_name}' missing Plugin class")
                return False
            
            # Instantiate plugin
            plugin_class = getattr(module, 'Plugin')
            plugin = plugin_class(self.service_bus, self.event_bus)
            plugin.status = PluginStatus.LOADING
            
            # Validate plugin implements PluginBase
            if not isinstance(plugin, PluginBase):
                self.logger.error(f"Plugin '{plugin_name}' doesn't inherit from PluginBase")
                return False
            
            # Load plugin-specific config
            config = self._load_plugin_config(plugin_name)
            
            # Validate config
            if not plugin.validate_config(config):
                self.logger.error(f"Plugin '{plugin_name}' config validation failed")
                return False
            
            # Initialize plugin
            if not plugin.initialize(config):
                self.logger.error(f"Plugin '{plugin_name}' initialization failed")
                return False
            
            # Success
            plugin.status = PluginStatus.READY
            self.plugins[plugin_name] = plugin
            
            self.logger.info(
                f"✓ Loaded plugin: {plugin.display_name} v{plugin.version} "
                f"(priority: {plugin.priority.name})"
            )
            
            # Emit event
            self.event_bus.emit('plugin_loaded', {
                'plugin_name': plugin_name,
                'version': plugin.version
            }, 'plugin_manager')
            
            return True
        
        except ImportError as e:
            self.logger.error(f"Failed to import plugin '{plugin_name}': {e}")
            return False
        
        except Exception as e:
            self.logger.error(
                f"Failed to load plugin '{plugin_name}': {e}",
                exc_info=True
            )
            return False
    
    def load_all_plugins(self) -> Dict[str, bool]:
        """
        Discover and load all plugins.
        
        Returns:
            Dictionary mapping plugin names to load success status
        
        Example:
            >>> manager.load_all_plugins()
            {'translation': True, 'epub_converter': True, 'broken_plugin': False}
        """
        discovered = self.discover_plugins()
        results = {}
        
        for plugin_name in discovered:
            results[plugin_name] = self.load_plugin(plugin_name)
        
        # Resolve dependencies after loading
        if any(results.values()):
            self.resolve_dependencies()
        
        success_count = sum(results.values())
        self.logger.info(f"Loaded {success_count}/{len(discovered)} plugin(s)")
        
        return results
    
    def resolve_dependencies(self) -> bool:
        """
        Check if all plugin dependencies are satisfied.
        Build execution order based on dependencies and priorities.
        
        Returns:
            bool: True if all dependencies satisfied
        
        Raises:
            ValueError: If circular dependency detected
        """
        # Build dependency graph
        graph: Dict[str, List[str]] = {}
        for name, plugin in self.plugins.items():
            graph[name] = plugin.dependencies
        
        # Topological sort with DFS
        visited = set()
        temp_mark = set()
        order = []
        
        def visit(node: str):
            if node in temp_mark:
                raise ValueError(f"Circular dependency detected involving '{node}'")
            
            if node not in visited:
                temp_mark.add(node)
                
                # Check dependencies exist
                for dep in graph.get(node, []):
                    if dep not in self.plugins:
                        raise ValueError(
                            f"Plugin '{node}' depends on '{dep}' which is not loaded"
                        )
                    visit(dep)
                
                temp_mark.remove(node)
                visited.add(node)
                order.append(node)
        
        try:
            for plugin_name in self.plugins:
                if plugin_name not in visited:
                    visit(plugin_name)
            
            # Sort by priority within dependency order
            # Dependencies first, then by priority (CRITICAL → OPTIONAL)
            self.execution_order = sorted(
                order,
                key=lambda name: (
                    -order.index(name),  # Dependency order (negative for reverse)
                    self.plugins[name].priority.value  # Priority order
                )
            )
            
            self.logger.info(f"Plugin execution order: {self.execution_order}")
            return True
        
        except ValueError as e:
            self.logger.error(f"Dependency resolution failed: {e}")
            return False
    
    def execute_plugin(
        self,
        plugin_name: str,
        method_name: str,
        *args,
        **kwargs
    ) -> Tuple[Any, str]:
        """
        Execute a plugin method with error isolation.
        
        Args:
            plugin_name: Name of plugin to execute
            method_name: Method name to call
            *args: Positional arguments for method
            **kwargs: Keyword arguments for method
        
        Returns:
            Tuple[result, status]:
                result: Method return value
                status: 'success', 'plugin_not_found', 'plugin_not_ready', or 'error'
        
        Example:
            >>> result, status = manager.execute_plugin('translation', 'process', text)
            >>> if status == 'success':
            ...     print(result)
        """
        # Check plugin exists
        if plugin_name not in self.plugins:
            self.logger.error(f"Plugin '{plugin_name}' not found")
            return None, 'plugin_not_found'
        
        plugin = self.plugins[plugin_name]
        
        # Check plugin is ready
        if plugin.status not in [PluginStatus.READY, PluginStatus.RUNNING]:
            self.logger.error(
                f"Plugin '{plugin_name}' not ready (status: {plugin.status.value})"
            )
            return None, 'plugin_not_ready'
        
        # Execute with error isolation
        try:
            plugin.status = PluginStatus.RUNNING
            
            # Get method
            if not hasattr(plugin, method_name):
                raise AttributeError(
                    f"Plugin '{plugin_name}' has no method '{method_name}'"
                )
            
            method = getattr(plugin, method_name)
            
            # Execute
            result = method(*args, **kwargs)
            
            # Success
            plugin.status = PluginStatus.READY
            return result, 'success'
        
        except Exception as e:
            self.logger.error(
                f"Plugin '{plugin_name}.{method_name}' failed: {e}",
                exc_info=True
            )
            
            # Call plugin error handler
            plugin.on_error(e)
            
            # Critical plugins: re-raise
            if plugin.priority == PluginPriority.CRITICAL:
                raise
            
            # Optional/low priority plugins: continue
            return None, 'error'
    
    def cleanup_plugin(self, plugin_name: str) -> bool:
        """
        Cleanup and unload a plugin.
        
        Args:
            plugin_name: Name of plugin to cleanup
        
        Returns:
            bool: True if successful
        """
        if plugin_name not in self.plugins:
            return False
        
        try:
            plugin = self.plugins[plugin_name]
            plugin.cleanup()
            plugin.status = PluginStatus.UNLOADED
            del self.plugins[plugin_name]
            
            # Remove from execution order
            if plugin_name in self.execution_order:
                self.execution_order.remove(plugin_name)
            
            self.logger.info(f"Cleaned up plugin: {plugin_name}")
            
            # Emit event
            self.event_bus.emit('plugin_unloaded', {'plugin_name': plugin_name}, 'plugin_manager')
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to cleanup plugin '{plugin_name}': {e}")
            return False
    
    def cleanup_all_plugins(self) -> None:
        """Cleanup and unload all plugins"""
        for plugin_name in list(self.plugins.keys()):
            self.cleanup_plugin(plugin_name)
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """
        Get plugin instance by name.
        
        Args:
            plugin_name: Plugin name
        
        Returns:
            Plugin instance or None if not found
        """
        return self.plugins.get(plugin_name)
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        Get list of all loaded plugins with their info.
        
        Returns:
            List of plugin info dictionaries
        """
        return [
            {
                'name': plugin.name,
                'display_name': plugin.display_name,
                'version': plugin.version,
                'status': plugin.status.value,
                'priority': plugin.priority.name,
                'dependencies': plugin.dependencies,
                'capabilities': plugin.get_capabilities()
            }
            for plugin in self.plugins.values()
        ]
    
    def _load_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """
        Load plugin-specific configuration.
        
        Args:
            plugin_name: Plugin name
        
        Returns:
            Configuration dictionary
        """
        config_dict = {}
        
        # Try plugin's own config.ini first
        plugin_config_file = self.plugins_dir / plugin_name / 'config.ini'
        
        if plugin_config_file.exists():
            parser = configparser.ConfigParser()
            parser.read(plugin_config_file)
            
            # Convert to dict
            for section in parser.sections():
                config_dict[section] = dict(parser.items(section))
            
            self.logger.debug(f"Loaded config for '{plugin_name}' from {plugin_config_file}")
        
        # Try global plugin config
        global_config_file = self.config_dir / 'plugins' / f'{plugin_name}.ini'
        
        if global_config_file.exists() and global_config_file != plugin_config_file:
            parser = configparser.ConfigParser()
            parser.read(global_config_file)
            
            # Merge with existing config (global overrides plugin's own)
            for section in parser.sections():
                if section not in config_dict:
                    config_dict[section] = {}
                config_dict[section].update(dict(parser.items(section)))
            
            self.logger.debug(f"Merged config for '{plugin_name}' from {global_config_file}")
        
        return config_dict
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """
        Reload a plugin (cleanup and reload).
        
        Args:
            plugin_name: Plugin name
        
        Returns:
            bool: True if successful
        """
        self.logger.info(f"Reloading plugin: {plugin_name}")
        
        # Cleanup
        if not self.cleanup_plugin(plugin_name):
            self.logger.error(f"Failed to cleanup plugin '{plugin_name}' for reload")
            return False
        
        # Reimport module (force reload)
        try:
            import sys
            module_name = f'plugins.{plugin_name}.plugin'
            if module_name in sys.modules:
                del sys.modules[module_name]
        except Exception as e:
            self.logger.warning(f"Failed to clear module cache: {e}")
        
        # Reload
        return self.load_plugin(plugin_name)
    
    def __repr__(self) -> str:
        """String representation"""
        return (
            f"<PluginManager: {len(self.plugins)} plugins loaded, "
            f"{sum(1 for p in self.plugins.values() if p.status == PluginStatus.READY)} ready>"
        )
