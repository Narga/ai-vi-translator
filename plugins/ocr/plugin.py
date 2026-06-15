# plugins/ocr/plugin.py - v3.0.3
# OCR Plugin - Image and PDF to Text Conversion

from core.interfaces import ConverterPlugin
from pathlib import Path
from typing import List, Tuple, Dict, Any
import sys

# Add OCR plugin modules to path
sys.path.insert(0, str(Path(__file__).parent))

from ocr_engine import ocr_file, ocr_pdf, ocr_image


class Plugin(ConverterPlugin):
    """
    OCR (Optical Character Recognition) Plugin.
    
    Converts images and PDFs to text using Tesseract OCR.
    Supports:
    - PDF (scan and text-based) → Text/DOCX
    - Images (JPG, PNG, BMP, TIFF) → Text
    - AI cleanup and spell check (Gemini integration)
    - Table extraction (3-tier fallback)
    - Multi-language support (Vietnamese, English, Chinese)
    """
    
    @property
    def name(self) -> str:
        return "ocr"
    
    @property
    def version(self) -> str:
        return "3.0.3"
    
    @property
    def display_name(self) -> str:
        return "OCR Reader"
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize OCR plugin"""
        try:
            self.config = config
            
            # Check if Tesseract is available
            try:
                import pytesseract
                # Try to get version to verify Tesseract is installed
                _ = pytesseract.get_tesseract_version()
                self.logger.info(f"✓ {self.display_name} initialized")
            except Exception as e:
                self.logger.warning(f"⚠️ Tesseract OCR not found. OCR functionality may not work: {e}")
                self.logger.warning("Install Tesseract: brew install tesseract (macOS) or apt install tesseract-ocr (Linux)")
            
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
            'features': [
                'ocr_pdf',
                'ocr_image', 
                'ai_cleanup',
                'spell_check',
                'table_extraction'
            ],
            'supported_conversions': self.get_supported_conversions(),
            'supported_languages': ['vie', 'eng', 'chi_sim', 'chi_tra'],
            'supported_image_formats': ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'tif']
        }
    
    def convert(
        self,
        input_path: Path,
        output_path: Path = None,
        **options
    ) -> bool:
        """
        Convert PDF/Image to text format.
        
        Args:
            input_path: Input file path (PDF or image)
            output_path: Output file path (TXT or DOCX)
            **options: Conversion options:
                - pages: List[int] or str - Pages to process (PDF only)
                - process_mode: str - 'process', 'cleanup-only', 'spellcheck-only'
                - skip_steps: dict - Steps to skip {'cleanup': bool, 'spell_check': bool}
                - lang: str - Language code ('vie', 'eng', 'chi', etc.)
        
        Returns:
            bool: True if successful
        """
        try:
            if output_path is None:
                default_out = self.config.get('out_dir', 'workspace/output')
                output_path = Path(default_out) / f"{input_path.stem}.txt"

            from_format = self.detect_format(input_path)
            to_format = self.detect_format(output_path)
            
            # Validate formats
            if from_format not in ['pdf', 'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'tif']:
                self.logger.error(f"Unsupported input format: {from_format}")
                return False
            
            if to_format not in ['txt', 'docx']:
                self.logger.error(f"Unsupported output format: {to_format}")
                return False
            
            # Get OCR configuration from service bus
            config_service = self.service_bus.get_service('config')
            
            # Extract options
            pages = options.get('pages', None)
            process_mode = options.get('process_mode', 'process')
            skip_steps = options.get('skip_steps', None)
            
            # Call OCR engine
            result = ocr_file(
                str(input_path),
                pages=pages,
                output_path=str(output_path),
                skip_steps=skip_steps,
                process_mode=process_mode
            )
            
            if result and result.get('text'):
                self.logger.info(f"✓ OCR completed: {input_path} → {output_path}")
                return True
            else:
                self.logger.error(f"OCR failed: {input_path}")
                return False
        
        except Exception as e:
            self.logger.error(f"Conversion failed: {e}", exc_info=True)
            return False
    
    def get_supported_conversions(self) -> List[Tuple[str, str]]:
        """Get supported format conversions"""
        conversions = []
        
        # PDF conversions
        conversions.extend([
            ('pdf', 'txt'),
            ('pdf', 'docx'),
        ])
        
        # Image conversions
        for img_format in ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'tif']:
            conversions.extend([
                (img_format, 'txt'),
                (img_format, 'docx'),
            ])
        
        return conversions
    
    def detect_format(self, file_path: Path) -> str:
        """Detect file format from extension"""
        if file_path.suffix:
            return file_path.suffix.lstrip('.').lower()
        return None
