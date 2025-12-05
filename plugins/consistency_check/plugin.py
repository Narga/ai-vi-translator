# plugins/consistency_check/plugin.py - v3.0.0
# Consistency check plugin

from core.interfaces import ProcessorPlugin
from typing import Dict, Any, Tuple
from .checker import consistency_check_chunk


class Plugin(ProcessorPlugin):
    """
    Consistency Check plugin.
    
    Verifies translation consistency for character names and terminology.
    """
    
    @property
    def name(self) -> str:
        return "consistency_check"
    
    @property
    def version(self) -> str:
        return "3.0.0"
    
    @property
    def display_name(self) -> str:
        return "Consistency Checker"
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize consistency check plugin"""
        try:
            self.config = config
            self.api_service = self.service_bus.get_service('api')
            self.cache_service = self.service_bus.get_service('cache')
            self.config_service = self.service_bus.get_service('config')
            
            self.consistency_model = self.config_service.get(
                'MODEL', 'CONSISTENCY_MODEL',
                fallback='gemini-2.5-pro'
            )
            
            self.logger.info(f"✓ {self.display_name} initialized (model: {self.consistency_model})")
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
            'features': ['consistency_check', 'terminology_verification'],
            'supported_formats': ['txt', 'md']
        }
    
    def process(self, input_data: Any, context: Dict[str, Any] = None) -> Tuple[Any, str]:
        """
        Check translation consistency.
        
        Args:
            input_data: Translated text to check
            context: Processing context with 'prompts' dict
        
        Returns:
            Tuple[result, status]: Consistency check result and status
        """
        if context is None:
            context = {}
        
        try:
            prompts = context.get('prompts', {})
            consistency_prompt = prompts.get('consistency', '')
            
            if not consistency_prompt or "Không có ghi chú đặc biệt" in consistency_prompt:
                self.logger.info("Skipping consistency check (no notes)")
                return input_data, 'skipped'
            
            # Run consistency check
            result, status, _ = consistency_check_chunk(
                translated_chunk=input_data,
                api_manager=self.api_service,
                cache=self.cache_service,
                consistency_prompt=consistency_prompt,
                model_name=self.consistency_model
            )
            
            # Emit event
            self.event_bus.emit('consistency_checked', {
                'status': status,
                'has_issues': status != 'success'
            }, self.name)
            
            return result, status
        
        except Exception as e:
            self.logger.error(f"Consistency check error: {e}", exc_info=True)
            return input_data, 'error'
    
    def supports_format(self, format: str) -> bool:
        """Check if format is supported"""
        return format.lower() in ['txt', 'md', 'text', 'markdown']
