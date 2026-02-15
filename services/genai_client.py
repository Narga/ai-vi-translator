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

    GOOGLE_GENAI = "google-genai"  # SDK mới (khuyến nghị)
    GOOGLE_GENERATIVEAI = "google-generativeai"  # SDK cũ (legacy)


class GenAIClient:
    """
    Wrapper cho google-genai SDK (Pure Python SDK).
    Tối ưu cho Gemini 3 Flash Preview.
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemini-3-flash-preview",
        thinking_level: str = "MEDIUM",
    ):
        """
        Khởi tạo GenAI Client (chỉ hỗ trợ google-genai mới).

        Args:
            api_key (str): Gemini API key
            default_model (str): Model mặc định
            thinking_level (str): Mức độ thinking (MINIMAL/LOW/MEDIUM/HIGH)
        """
        self.api_key = api_key
        self.default_model = default_model
        self.thinking_level = thinking_level
        self.logger = logging.getLogger(__name__)

        # Khởi tạo client trực tiếp
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Khởi tạo google-genai client."""
        try:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
            self.logger.debug("✅ GenAI Client initialized")
        except ImportError:
            raise ImportError(
                "Thư viện 'google-genai' chưa được cài đặt. "
                "Vui lòng chạy: pip install google-genai"
            )

    def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 1.0,  # Default for Gemini 3
        thinking_level: Optional[str] = None,
        **kwargs,
    ) -> Tuple[Optional[str], str]:
        """
        Sinh nội dung sử dụng google-genai SDK.

        Args:
            prompt (str): Prompt đầu vào
            model (str, optional): Model override
            temperature (float): Nhiệt độ (default 1.0)
            thinking_level (str, optional): Override thinking level

        Returns:
            Tuple[Optional[str], str]: (content, status)
        """
        model_name = model or self.default_model
        curr_thinking = thinking_level or self.thinking_level

        try:
            # Config tối ưu cho Gemini 3
            generation_config: Dict[str, Any] = {
                "temperature": temperature,
            }

            # Chỉ thêm thinking config cho model hỗ trợ (Gemini 3)
            if "gemini-3" in model_name.lower():
                generation_config["thinking_config"] = {"thinking_level": curr_thinking}

            response = self._client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=generation_config,  # type: ignore[arg-type]
            )

            if response and response.text:
                return response.text.strip(), "success"
            return None, "empty_response"

        except Exception as e:
            self.logger.error(f"GenAI Error: {e}")
            return None, f"error: {str(e)}"

    def get_sdk_info(self) -> Dict[str, Any]:
        """Trả về thông tin SDK."""
        return {
            "sdk": "google-genai",
            "model": self.default_model,
            "thinking": self.thinking_level,
        }

    def reconfigure(self, api_key: str) -> None:
        """Cấu hình lại API key."""
        self.api_key = api_key
        self._initialize_client()
