# services/genai_client.py - v4.0.0
# Tác giả: Narga
# Chức năng: Wrapper thống nhất cho Gemini API, hỗ trợ cả google-genai SDK mới và google-generativeai SDK cũ.

"""
GenAI Client - Lớp trừu tượng hóa cho Gemini API.

Hỗ trợ:
- google-genai SDK (mặc định, khuyến nghị)
- google-generativeai SDK (fallback, legacy)

Sử dụng:
    client = GenAIClient(api_key, sdk="google-genai")
    response = client.generate_content(prompt, model="gemini-3-flash-preview")
"""

import logging
from typing import Optional, Dict, Any, Tuple
from enum import Enum


class SDKType(Enum):
    """Enum cho các loại SDK được hỗ trợ."""
    GOOGLE_GENAI = "google-genai"           # SDK mới (khuyến nghị)
    GOOGLE_GENERATIVEAI = "google-generativeai"  # SDK cũ (legacy)


class GenAIClient:
    """
    Wrapper thống nhất cho Gemini API.
    
    Tự động chọn SDK phù hợp và cung cấp interface nhất quán
    cho việc gọi API bất kể SDK nào được sử dụng.
    
    Attributes:
        api_key (str): API key để xác thực với Gemini API
        sdk_type (SDKType): Loại SDK đang sử dụng
        default_model (str): Model mặc định cho các request
        thinking_level (str): Mức độ reasoning cho Gemini 3 (MINIMAL/LOW/MEDIUM/HIGH)
    """
    
    # Model mặc định cho từng SDK
    DEFAULT_MODELS = {
        SDKType.GOOGLE_GENAI: "gemini-3-flash-preview",
        SDKType.GOOGLE_GENERATIVEAI: "gemini-2.0-flash"
    }
    
    def __init__(
        self,
        api_key: str,
        sdk: str = "google-genai",
        default_model: Optional[str] = None,
        thinking_level: str = "MEDIUM"
    ):
        """
        Khởi tạo GenAI Client.
        
        Args:
            api_key (str): Gemini API key
            sdk (str): SDK sử dụng ("google-genai" hoặc "google-generativeai")
            default_model (str, optional): Model mặc định, nếu None sẽ dùng model khuyến nghị
            thinking_level (str): Mức độ thinking cho Gemini 3 models
        """
        self.api_key = api_key
        self.thinking_level = thinking_level
        self.logger = logging.getLogger(__name__)
        
        # Xác định SDK type
        try:
            self.sdk_type = SDKType(sdk)
        except ValueError:
            self.logger.warning(f"SDK '{sdk}' không hợp lệ, sử dụng google-genai")
            self.sdk_type = SDKType.GOOGLE_GENAI
        
        # Set default model
        self.default_model = default_model or self.DEFAULT_MODELS[self.sdk_type]
        
        # Khởi tạo client dựa trên SDK type
        self._client = None
        self._initialize_client()
        
        self.logger.info(f"🔧 GenAI Client initialized: SDK={self.sdk_type.value}, Model={self.default_model}")
    
    def _initialize_client(self) -> None:
        """Khởi tạo client cho SDK đã chọn."""
        try:
            if self.sdk_type == SDKType.GOOGLE_GENAI:
                self._init_google_genai()
            else:
                self._init_google_generativeai()
        except ImportError as e:
            self.logger.error(f"Không thể import SDK {self.sdk_type.value}: {e}")
            # Thử fallback sang SDK còn lại
            self._try_fallback_sdk()
    
    def _init_google_genai(self) -> None:
        """Khởi tạo google-genai SDK mới."""
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            self._genai_module = genai
            self.logger.info("✅ Đã khởi tạo google-genai SDK")
        except ImportError:
            raise ImportError("Không tìm thấy google-genai. Cài đặt: pip install google-genai")
    
    def _init_google_generativeai(self) -> None:
        """Khởi tạo google-generativeai SDK cũ (legacy)."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai
            self._genai_module = genai
            self.logger.info("✅ Đã khởi tạo google-generativeai SDK (legacy)")
        except ImportError:
            raise ImportError("Không tìm thấy google-generativeai. Cài đặt: pip install google-generativeai")
    
    def _try_fallback_sdk(self) -> None:
        """Thử chuyển sang SDK còn lại nếu SDK chính không khả dụng."""
        fallback_type = (
            SDKType.GOOGLE_GENERATIVEAI 
            if self.sdk_type == SDKType.GOOGLE_GENAI 
            else SDKType.GOOGLE_GENAI
        )
        
        self.logger.warning(f"⚠️ Thử fallback sang {fallback_type.value}")
        self.sdk_type = fallback_type
        self.default_model = self.DEFAULT_MODELS[fallback_type]
        
        try:
            self._initialize_client()
        except ImportError:
            raise ImportError("Không có SDK nào khả dụng. Cài đặt: pip install google-genai")
    
    def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 1.0,
        thinking_level: Optional[str] = None,
        **kwargs
    ) -> Tuple[Optional[str], str]:
        """
        Gọi API để sinh nội dung.
        
        Args:
            prompt (str): Prompt đầu vào
            model (str, optional): Model sử dụng, mặc định dùng default_model
            temperature (float): Nhiệt độ sinh (0.0-2.0), mặc định 1.0 cho Gemini 3
            thinking_level (str, optional): Mức độ reasoning (chỉ cho Gemini 3)
            **kwargs: Các tham số bổ sung
        
        Returns:
            Tuple[Optional[str], str]: (kết_quả_text, status)
                status: 'success', 'error', 'empty_response'
        """
        model_name = model or self.default_model
        thinking = thinking_level or self.thinking_level
        
        try:
            if self.sdk_type == SDKType.GOOGLE_GENAI:
                return self._generate_with_new_sdk(prompt, model_name, temperature, thinking, **kwargs)
            else:
                return self._generate_with_legacy_sdk(prompt, model_name, temperature, **kwargs)
        except Exception as e:
            self.logger.error(f"Lỗi generate_content: {e}")
            return None, f"error: {str(e)}"
    
    def _generate_with_new_sdk(
        self,
        prompt: str,
        model: str,
        temperature: float,
        thinking_level: str,
        **kwargs
    ) -> Tuple[Optional[str], str]:
        """Sinh nội dung với google-genai SDK mới."""
        try:
            # Build config cho Gemini 3
            config = {
                "temperature": temperature,
            }
            
            # Thêm thinking_level cho models hỗ trợ
            if "gemini-3" in model.lower():
                config["thinking_config"] = {"thinking_level": thinking_level}
            
            # Gọi API với Client object
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            
            if response and response.text:
                return response.text.strip(), "success"
            else:
                return None, "empty_response"
                
        except Exception as e:
            self.logger.error(f"Lỗi google-genai SDK: {e}")
            return None, f"error: {str(e)}"
    
    def _generate_with_legacy_sdk(
        self,
        prompt: str,
        model: str,
        temperature: float,
        **kwargs
    ) -> Tuple[Optional[str], str]:
        """Sinh nội dung với google-generativeai SDK cũ."""
        try:
            # Tạo model instance
            gen_model = self._client.GenerativeModel(model)
            
            # Tạo generation config
            generation_config = self._client.types.GenerationConfig(
                temperature=temperature
            )
            
            # Gọi API
            response = gen_model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            if response and response.text:
                return response.text.strip(), "success"
            else:
                return None, "empty_response"
                
        except Exception as e:
            self.logger.error(f"Lỗi google-generativeai SDK: {e}")
            return None, f"error: {str(e)}"
    
    def get_sdk_info(self) -> Dict[str, Any]:
        """Trả về thông tin SDK đang sử dụng."""
        return {
            "sdk_type": self.sdk_type.value,
            "default_model": self.default_model,
            "thinking_level": self.thinking_level,
            "api_key_suffix": f"...{self.api_key[-4:]}" if self.api_key else None
        }
    
    def reconfigure(self, api_key: str) -> None:
        """
        Cấu hình lại client với API key mới.
        
        Args:
            api_key (str): API key mới
        """
        self.api_key = api_key
        self._initialize_client()
        self.logger.info(f"🔄 Đã cấu hình lại với key ...{api_key[-4:]}")
