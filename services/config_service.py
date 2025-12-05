# services/config_service.py - v3.0.0
# Configuration management service for plugin architecture

import configparser
import logging
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigService:
    """
    Centralized configuration management service.
    
    Manages app-level and plugin-level configurations.
    All plugins access config through this service via ServiceBus.
    """
    
    def __init__(self, config_dir: Path):
        """
        Initialize ConfigService.
        
        Args:
            config_dir: Path to config directory
        """
        self.config_dir = Path(config_dir)
        self.app_config = self._load_app_config()
        self.plugin_configs: Dict[str, configparser.ConfigParser] = {}
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"ConfigService initialized (config_dir: {self.config_dir})")
    
    def _load_app_config(self) -> configparser.ConfigParser:
        """Load main application config from config/app.ini"""
        config = configparser.ConfigParser()
        config_file = self.config_dir / 'app.ini'
        
        if config_file.exists():
            config.read(config_file)
            logging.info(f"Loaded app config from {config_file}")
        else:
            logging.warning(f"App config not found: {config_file}")
        
        return config
    
    def get(
        self,
        section: str,
        key: str,
        fallback: Any = None,
        value_type: type = str
    ) -> Any:
        """
        Get app-level config value.
        
        Args:
            section: Config section name (e.g., 'MODEL', 'PROCESSING')
            key: Config key name
            fallback: Default value if not found
            value_type: Type to convert to (str, int, float, bool)
        
        Returns:
            Config value converted to specified type
        
        Example:
            >>> config.get('PROCESSING', 'MAX_CHARS_PER_CHUNK', fallback=20000, value_type=int)
            20000
        """
        if not self.app_config.has_section(section):
            return fallback
        
        if not self.app_config.has_option(section, key):
            return fallback
        
        # Get value based on type
        if value_type == bool:
            return self.app_config.getboolean(section, key, fallback=fallback)
        elif value_type == int:
            return self.app_config.getint(section, key, fallback=fallback)
        elif value_type == float:
            return self.app_config.getfloat(section, key, fallback=fallback)
        else:
            return self.app_config.get(section, key, fallback=fallback)
    
    def get_section(self, section: str) -> Dict[str, str]:
        """
        Get all key-value pairs from a section.
        
        Args:
            section: Section name
        
        Returns:
            Dictionary of key-value pairs, empty if section doesn't exist
        """
        if self.app_config.has_section(section):
            return dict(self.app_config.items(section))
        return {}
    
    def get_plugin_config(self, plugin_name: str) -> configparser.ConfigParser:
        """
        Get plugin-specific configuration.
        
        Loads from config/plugins/{plugin_name}.ini
        
        Args:
            plugin_name: Plugin name
        
        Returns:
            ConfigParser instance for the plugin
        """
        if plugin_name not in self.plugin_configs:
            config = configparser.ConfigParser()
            config_path = self.config_dir / 'plugins' / f'{plugin_name}.ini'
            
            if config_path.exists():
                config.read(config_path)
                self.logger.debug(f"Loaded plugin config: {plugin_name}")
            else:
                self.logger.debug(f"No config file for plugin: {plugin_name}")
            
            self.plugin_configs[plugin_name] = config
        
        return self.plugin_configs[plugin_name]
    
    def get_plugin_value(
        self,
        plugin_name: str,
        section: str,
        key: str,
        fallback: Any = None
    ) -> Any:
        """
        Get a value from plugin config.
        
        Args:
            plugin_name: Plugin name
            section: Config section
            key: Config key
            fallback: Default value
        
        Returns:
            Config value or fallback
        """
        config = self.get_plugin_config(plugin_name)
        
        if config.has_section(section) and config.has_option(section, key):
            return config.get(section, key)
        
        return fallback
    
    def reload_app_config(self) -> None:
        """Reload application configuration from disk"""
        self.app_config = self._load_app_config()
        self.logger.info("Reloaded app config")
    
    def reload_plugin_config(self, plugin_name: str) -> None:
        """
        Reload a plugin's configuration.
        
        Args:
            plugin_name: Plugin name to reload
        """
        if plugin_name in self.plugin_configs:
            del self.plugin_configs[plugin_name]
        
        # Will be reloaded on next access
        self.logger.info(f"Cleared plugin config cache: {plugin_name}")
    
    def list_plugins_with_config(self) -> list[str]:
        """
        List all plugins that have config files.
        
        Returns:
            List of plugin names with config files
        """
        plugins_config_dir = self.config_dir / 'plugins'
        
        if not plugins_config_dir.exists():
            return []
        
        return [
            f.stem for f in plugins_config_dir.glob('*.ini')
        ]
