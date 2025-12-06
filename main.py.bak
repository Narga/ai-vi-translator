# main.py - v3.0.0 Plugin Architecture
# Tác giả: Narga
# Entry point với plugin system

import sys
import logging
from pathlib import Path
from datetime import datetime

# Core imports
from core import PluginManager, ServiceBus, EventBus
from services import ApiManager, TranslationCache, ConfigService


def setup_logging(log_dir: Path) -> None:
    """Setup logging to file and console"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_filename = datetime.now().strftime('%Y-%m-%d_%H-%M') + '_translator.log'
    log_filepath = log_dir / log_filename
    
    # Clear existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.info(f"📝 Log file: {log_filepath}")


def load_api_keys(api_file: str = 'API.txt') -> list[str]:
    """
    Load API keys from file.
    
    Returns:
        List of API keys
    
    Raises:
        FileNotFoundError: If API.txt not found
        ValueError: If no valid keys found
    """
    if not Path(api_file).exists():
        raise FileNotFoundError(
            f"File '{api_file}' not found. "
            "Please create API.txt with your Gemini API keys (one per line)."
        )
    
    keys = []
    with open(api_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                keys.append(line)
    
    if not keys:
        raise ValueError(
            f"No valid API keys found in '{api_file}'. "
            "Please add at least one API key."
        )
    
    return keys


def main():
    """
    Main entry point with plugin architecture.
    
    Workflow:
    1. Initialize services (Config, API, Cache, Logger)
    2. Register services with ServiceBus
    3. Initialize PluginManager and EventBus
    4. Discover and load all plugins
    5. Execute translation workflow via plugins
    """
    try:
        print("=" * 80)
        print("📚 Novel Translator v3.0.0 - Plugin Architecture")
        print("=" * 80)
        print()
        
        # ===== STEP 1: Initialize Services =====
        print("🔧 Initializing services...")
        
        # Config Service
        config_dir = Path('config')
        config_service = ConfigService(config_dir)
        
        # Setup logging
        logs_dir = Path(config_service.get('DIRECTORIES', 'PROGRESS_DIR', fallback='workspace/logs'))
        setup_logging(logs_dir)
        
        logging.info("="*80)
        logging.info("🚀 Novel Translator v3.0.0 Starting...")
        logging.info("="*80)
        
        # Load API keys
        api_keys = load_api_keys('API.txt')
        logging.info(f"✓ Loaded {len(api_keys)} API key(s)")
        
        # API Service
        api_service = ApiManager(api_keys)
        
        # Cache Service
        cache_dir = Path(config_service.get('DIRECTORIES', 'CACHE_DIR', fallback='workspace/cache'))
        enable_cache = config_service.get('CACHE', 'ENABLE_CACHE', fallback=True, value_type=bool)
        cache_service = TranslationCache(str(cache_dir), enabled=enable_cache)
        
        logging.info("✓ Services initialized")
        
        # ===== STEP 2: Register Services with ServiceBus =====
        logging.info("📡 Registering services...")
        
        service_bus = ServiceBus()
        service_bus.register_service('config', config_service)
        service_bus.register_service('api', api_service)
        service_bus.register_service('cache', cache_service)
        
        # Register a simple logger service
        service_bus.register_service('logger', logging.getLogger())
        
        logging.info(f"✓ Registered {len(service_bus.list_services())} service(s)")
        
        # ===== STEP 3: Initialize EventBus and PluginManager =====
        logging.info("🔌 Initializing plugin system...")
        
        event_bus = EventBus(enable_history=True)
        
        # Setup event listeners for monitoring
        def on_plugin_loaded(event):
            logging.info(f"  ✓ Plugin loaded: {event.data.get('plugin_name')}")
        
        def on_chunk_translated(event):
            idx = event.data.get('chunk_index', -1)
            status = event.data.get('status', 'unknown')
            if idx >= 0:
                logging.debug(f"  Chunk {idx}: {status}")
        
        event_bus.subscribe('plugin_loaded', on_plugin_loaded)
        event_bus.subscribe('chunk_translated', on_chunk_translated)
        
        # Initialize PluginManager
        plugins_dir = Path('plugins')
        plugin_manager = PluginManager(service_bus, event_bus, plugins_dir, config_dir)
        
        logging.info("✓ Plugin system initialized")
        
        # ===== STEP 4: Discover and Load Plugins =====
        logging.info("🔍 Discovering plugins...")
        
        load_results = plugin_manager.load_all_plugins()
        
        # Show results
        success_count = sum(load_results.values())
        total_count = len(load_results)
        
        logging.info(f"✓ Loaded {success_count}/{total_count} plugin(s)")
        
        # List loaded plugins
        for plugin_info in plugin_manager.list_plugins():
            logging.info(
                f"  • {plugin_info['display_name']} v{plugin_info['version']} "
                f"[{plugin_info['status']}]"
            )
        
        # Check if critical plugins loaded
        if 'translation' not in load_results or not load_results['translation']:
            logging.critical("❌ Translation plugin failed to load - cannot proceed")
            return 1
        
        # ===== STEP 5: Execute Translation Workflow =====
        logging.info("")
        logging.info("="*80)
        logging.info("🌍 Starting Translation Workflow")
        logging.info("="*80)
        logging.info("")
        
        # For now, just show plugin status (workflow will be implemented next)
        logging.info("✓ Plugin architecture is ready")
        logging.info("  Translation workflow integration coming next...")
        
        # ===== STEP 6: Cleanup =====
        logging.info("")
        logging.info("="*80)
        logging.info("🎉 Plugin System Initialization Complete!")
        logging.info("="*80)
        
        # Show statistics
        event_history = event_bus.get_history(limit=100)
        loaded_events = [e for e in event_history if e.name == 'plugin_loaded']
        
        if loaded_events:
            logging.info(f"📊 {len(loaded_events)} plugin(s) loaded successfully")
        
        # Cleanup plugins
        plugin_manager.cleanup_all_plugins()
        
        return 0
    
    except FileNotFoundError as e:
        logging.critical(f"❌ File not found: {e}")
        return 1
    
    except ValueError as e:
        logging.critical(f"❌ Configuration error: {e}")
        return 1
    
    except Exception as e:
        logging.critical(f"❌ Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
