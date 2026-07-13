# plugins/epub_converter/plugin.py - v4.0.0
# Converter Tool plugin

from core.interfaces import ConverterPlugin
from pathlib import Path
from typing import List, Tuple, Dict, Any, Union
import sys

# Add epub converter modules to path
sys.path.insert(0, str(Path(__file__).parent))

from epub_to_text.epub2text import convert_epub as epub_to_text_converter
from text_to_epub.main import process_book_directory
from .services.text_converter import convert_html_file, convert_markdown_file


class Plugin(ConverterPlugin):
    """
    Converter Tool plugin.
    
    Supports:
    - HTML → Markdown
    - Markdown → HTML
    - EPUB → Text/Markdown
    - Text/Markdown → EPUB
    """
    
    @property
    def name(self) -> str:
        return "epub_converter"

    @property
    def version(self) -> str:
        return "4.0.0"

    @property
    def display_name(self) -> str:
        return "Công cụ chuyển đổi"

    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize EPUB converter plugin"""
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
            'features': ['html_to_markdown', 'markdown_to_html', 'epub_to_text', 'text_to_epub'],
            'supported_conversions': self.get_supported_conversions()
        }

    def convert(
        self,
        input_path: Path,
        output_path: Path = None,
        **options
    ) -> Union[bool, Path]:
        """
        Convert between EPUB and text formats.

        Args:
            input_path: Input file path
            output_path: Output file/directory path
            **options: Conversion options including 'task'

        Returns:
            bool: True if successful (legacy EPUB conversions)
            Path: Output file path (for html_to_markdown, markdown_to_html tasks)
        """
        try:
            task = options.get('task')
            if task == 'html_to_markdown':
                return self._html_to_markdown(input_path, output_path)

            if task == 'markdown_to_html':
                return self._markdown_to_html(input_path, output_path)

            if output_path is None:
                default_out = self.config.get('out_dir', 'workspace/output')
                if input_path.is_file():
                    output_path = Path(default_out)
                else:
                    output_path = Path(default_out)

            from_format = self.detect_format(input_path)

            # For text_to_epub, if output_path doesn't have an extension, assume we need one
            if from_format in ['txt', 'md'] and not output_path.suffix:
                output_path = output_path / f"{input_path.name}.epub"

            to_format = self.detect_format(output_path)

            if from_format == 'epub' and to_format in ['txt', 'md']:
                return self._epub_to_text(input_path, output_path, **options)

            elif from_format in ['txt', 'md'] and to_format == 'epub':
                return self._text_to_epub(input_path, output_path, **options)

            else:
                self.logger.error(f"Unsupported conversion: {from_format} → {to_format}")
                return False

        except Exception as e:
            self.logger.error(f"Conversion failed: {e}", exc_info=True)
            return False

    def _html_to_markdown(self, input_path: Path, output_path: Path = None) -> Path:
        try:
            result = convert_html_file(input_path, output_path)
            self.logger.info(f"Converted {input_path} → {result}")
            return result
        except Exception as e:
            self.logger.error(f"HTML to Markdown failed: {e}")
            raise

    def _markdown_to_html(self, input_path: Path, output_path: Path = None) -> Path:
        try:
            result = convert_markdown_file(input_path, output_path)
            self.logger.info(f"Converted {input_path} → {result}")
            return result
        except Exception as e:
            self.logger.error(f"Markdown to HTML failed: {e}")
            raise
    
    def _epub_to_text(self, input_path: Path, output_path: Path, **options) -> bool:
        """Convert EPUB to text/markdown"""
        try:
            # Prepare arguments for epub2text converter
            class Args:
                pass
            
            args = Args()
            args.epub_file = str(input_path)
            args.output_dir = str(output_path.parent if output_path.is_file() else output_path)
            args.single_file = options.get('single_file', False)
            args.preserve_underline = options.get('preserve_underline', False)
            args.include_nonspine = options.get('include_nonspine', False)
            args.extract_metadata = options.get('extract_metadata', True)
            
            # Convert
            epub_to_text_converter(args)
            
            self.logger.info(f"Converted {input_path} → {output_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"EPUB to text failed: {e}")
            return False
    
    def _text_to_epub(self, input_path: Path, output_path: Path, **options) -> bool:
        """Convert text/markdown to EPUB"""
        try:
            # text2epub expects a directory
            if input_path.is_file():
                input_dir = input_path.parent
            else:
                input_dir = input_path
            
            use_markdown = options.get('use_markdown', False)
            split_chapters = options.get('split_chapters', True)
            
            # Convert
            process_book_directory(input_dir, use_markdown, split_chapters)
            
            self.logger.info(f"Converted {input_path} → EPUB")
            return True
        
        except Exception as e:
            self.logger.error(f"Text to EPUB failed: {e}")
            return False
    
    def get_supported_conversions(self) -> List[Tuple[str, str]]:
        """Get supported format conversions"""
        return [
            ('html', 'md'),
            ('htm', 'md'),
            ('xhtml', 'md'),
            ('md', 'html'),
            ('epub', 'txt'),
            ('epub', 'md'),
            ('txt', 'epub'),
            ('md', 'epub'),
        ]
