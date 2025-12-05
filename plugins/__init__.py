# Plugins package initialization
"""
Plugin directory for Novel Translator.

Each subdirectory represents a plugin with the following structure:
- __init__.py: Plugin package initialization
- plugin.py: Plugin class implementing PluginBase interface
- config.ini: Plugin-specific configuration (optional)
- Additional modules as needed

Built-in plugins:
- translation: Core translation functionality
- epub_converter: EPUB ↔ Text conversion
- consistency_check: Translation consistency verification
- content_analysis: Content analysis tools
"""

__version__ = "3.0.0"
