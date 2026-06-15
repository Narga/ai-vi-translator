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
- spellcheck: Core spell checking functionality
- epub_converter: EPUB ↔ Text conversion
- ocr: OCR text extraction and cleanup
"""

__version__ = "3.0.0"
