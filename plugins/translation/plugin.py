# plugins/translation/plugin.py - v3.0.0
# Translation plugin implementation

from core.interfaces import ProcessorPlugin, PluginPriority
from typing import Dict, Any, Tuple
from .translator import robust_translate
from .normalizer import TextNormalizer
from .chunker import process_text_for_chunking, intelligent_chunking
import logging


class Plugin(ProcessorPlugin):
    """
    Translation plugin for Novel Translator.
    
    Provides core translation functionality using Gemini AI with:
    - Smart chunking
    - Text normalization  
    - Chinese character detection and fixing
    - Context chaining for chunk continuity
    """
    
    @property
    def name(self) -> str:
        return "translation"
    
    @property
    def version(self) -> str:
        return "3.0.0"
    
    @property
    def display_name(self) -> str:
        return "Translation Engine"
    
    @property
    def priority(self) -> PluginPriority:
        return PluginPriority.CRITICAL  # Translation is critical functionality
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize translation plugin with configuration"""
        try:
            self.config = config
            self.logger.info(f"Initializing {self.display_name}...")
            
            # Get services from service bus
            self.api_service = self.service_bus.get_service('api')
            self.cache_service = self.service_bus.get_service('cache')
            self.config_service = self.service_bus.get_service('config')
            
            # Initialize normalizer
            # Default to text source unless specified
            is_text_source = config.get('processing', {}).get('is_text_source', True)
            self.normalizer = TextNormalizer(is_text_source=is_text_source)
            
            # Get translation config
            self.translation_config = {
                'model_name': self.config_service.get('MODEL', 'MODEL', fallback='gemini-2.5-flash'),
                'qa_model': self.config_service.get('MODEL', 'QA_MODEL', fallback='gemini-2.5-flash'),
                'temperature': self.config_service.get('PROCESSING', 'TEMPERATURE', fallback=0.75, value_type=float),
                'max_refinement_attempts': self.config_service.get('PROCESSING', 'MAX_REFINEMENT_ATTEMPTS', fallback=2, value_type=int),
                'min_length_ratio': self.config_service.get('PROCESSING', 'MIN_LENGTH_RATIO', fallback=0.5, value_type=float),
                'max_length_ratio': self.config_service.get('PROCESSING', 'MAX_LENGTH_RATIO', fallback=5.0, value_type=float),
                'input_lang': self.config_service.get('PROCESSING', 'INPUT_LANG', fallback='CN'),
                'correction_mode': self.config_service.get('PROCESSING', 'CORRECTION_MODE', fallback='parallel'),
                'context_char_count': self.config_service.get('PROCESSING', 'CONTEXT_CHAR_COUNT', fallback=500, value_type=int),
            }
            
            # Chunking config
            self.min_chunk_size = self.config_service.get('PROCESSING', 'MIN_CHARS_PER_CHUNK', fallback=18000, value_type=int)
            self.max_chunk_size = self.config_service.get('PROCESSING', 'MAX_CHARS_PER_CHUNK', fallback=22000, value_type=int)
            
            self.logger.info(f"✓ {self.display_name} initialized")
            self.logger.info(f"  Model: {self.translation_config['model_name']}")
            self.logger.info(f"  Chunk size: {self.min_chunk_size}-{self.max_chunk_size} chars")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to initialize translation plugin: {e}", exc_info=True)
            return False
    
    def cleanup(self) -> None:
        """Cleanup translation plugin resources"""
        self.logger.info(f"Cleaning up {self.display_name}")
        # No special cleanup needed
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return plugin capabilities"""
        return {
            'features': [
                'translation',
                'retranslation',
                'chinese_correction',
                'context_chaining'
            ],
            'supported_formats': ['txt', 'md'],
            'supported_languages': ['CN', 'EN'],
            'target_language': 'VI',
            'min_chunk_size': self.min_chunk_size,
            'max_chunk_size': self.max_chunk_size,
        }
    
    def process(self, input_data: Any, context: Dict[str, Any] = None) -> Tuple[Any, str]:
        """
        Translate text chunk.
        
        Args:
            input_data: Text to translate (str)
            context: Processing context with:
                - prompts: Dict of prompts (main, retranslate, correction)
                - previous_context: Text from previous chunk (optional)
                - chunk_index: Current chunk number (optional)
        
        Returns:
            Tuple[translated_text, status]:
                - translated_text: Translation result
                - status: 'success', 'error', 'partial'
        """
        if context is None:
            context = {}
        
        try:
            # Get prompts from context (required)
            prompts = context.get('prompts', {})
            if not prompts:
                self.logger.error("No prompts provided in context")
                return None, 'error'
            
            # Get previous context for continuity
            previous_context = context.get('previous_context', '')
            
            # Translate using robust_translate
            result, status, api_key_used = robust_translate(
                original_chunk=input_data,
                api_manager=self.api_service,
                cache=self.cache_service,
                prompts=prompts,
                config_params=self.translation_config,
                previous_chunk_context=previous_context,
                normalizer=self.normalizer
            )
            
            # Emit event
            chunk_index = context.get('chunk_index', -1)
            self.event_bus.emit('chunk_translated', {
                'chunk_index': chunk_index,
                'status': status,
                'api_key': f"...{api_key_used[-4:]}" if api_key_used else None,
                'char_count': len(input_data) if input_data else 0
            }, self.name)
            
            return result, status
        
        except Exception as e:
            self.logger.error(f"Translation error: {e}", exc_info=True)
            return None, 'error'
    
    def chunk_text(self, text: str) -> list[str]:
        """
        Split text into chunks for translation.
        
        Args:
            text: Full text to chunk
        
        Returns:
            List of text chunks
        """
        return process_text_for_chunking(
            text,
            self.min_chunk_size,
            self.max_chunk_size
        )
    
    def supports_format(self, format: str) -> bool:
        """Check if format is supported for translation"""
        return format.lower() in ['txt', 'md', 'text', 'markdown']
    
    def validate_input(self, input_data: Any) -> bool:
        """Validate input text"""
        if not isinstance(input_data, str):
            return False
        
        if not input_data or not input_data.strip():
            return False
        
        return True
